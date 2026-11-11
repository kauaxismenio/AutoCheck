"""Trabalhador da fila de relatórios e e-mails. É um processo próprio, nunca iniciado por uma requisição.

Contínuo (terminal próprio ou serviço):   python manage.py process_email_queue --loop
Uma passada (agendador a cada minuto):    python manage.py process_email_queue
Situação da fila, sem enviar nada:        python manage.py process_email_queue --status

Rodar mais de um ao mesmo tempo é seguro: cada registro só é assumido por um processo.
Ao receber Ctrl+C ou o pedido de parada do serviço, termina o envio em curso antes de sair,
para não deixar um e-mail com resultado incerto. A saída traz apenas contagens.
"""
import logging
import signal
import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.utils import timezone

from apps.mailing.services import process_queue, queue_status

logger = logging.getLogger("autocheck.mailing")

_STOP_SIGNALS = ("SIGINT", "SIGTERM", "SIGBREAK")  # SIGBREAK só existe no Windows


class Command(BaseCommand):
    help = "Gera relatórios parados e envia os e-mails que estão na fila."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true", help="Continua rodando até ser interrompido.")
        parser.add_argument("--interval", type=int, default=60, help="Segundos entre as passadas com --loop.")
        parser.add_argument("--limit", type=int, default=50, help="Máximo de itens de cada tipo por passada.")
        parser.add_argument("--status", action="store_true", help="Mostra a situação da fila, sem enviar nada.")

    def _line(self, values):
        moment = timezone.localtime().strftime("%d/%m/%Y %H:%M:%S")
        self.stdout.write(f"{moment} | " + " | ".join(f"{key}: {value}" for key, value in values.items()))
        self.stdout.flush()

    def _request_stop(self, *_):
        self.stopping = True

    def _install_signals(self):
        previous = {}
        for name in _STOP_SIGNALS:
            number = getattr(signal, name, None)
            if number is not None:
                previous[number] = signal.signal(number, self._request_stop)
        return previous

    def _wait(self, seconds):
        # Em fatias: no Windows, uma espera longa adiaria a resposta ao Ctrl+C.
        for _ in range(seconds):
            if self.stopping:
                return
            time.sleep(1)

    def _run(self, options):
        """Único mecanismo de execução: sem --loop, faz uma passada; com --loop, repete até o pedido de parada."""
        continuous = options["loop"]
        while not self.stopping:
            try:
                self._line(process_queue(limit=options["limit"], should_stop=lambda: self.stopping))
            except Exception:  # noqa: BLE001 — a fila precisa sobreviver a erros passageiros, como banco ocupado
                if not continuous:
                    raise  # passada única: o agendador precisa saber que falhou
                logger.exception("Falha ao processar a fila de e-mails")
            if not continuous:
                return
            self._wait(options["interval"])
            close_old_connections()

    def handle(self, *args, **options):
        self.stopping = False
        if options["status"]:
            self._line(queue_status())  # só consulta: não processa, não envia e não altera nada
            return
        options["interval"] = max(1, options["interval"])
        if options["loop"]:
            self.stdout.write(f"Fila iniciada: uma passada a cada {options['interval']} s. Ctrl+C para encerrar.")
            self.stdout.flush()
        previous = self._install_signals()  # em qualquer modo: Ctrl+C nunca corta um envio em curso
        try:
            self._run(options)
        except KeyboardInterrupt:
            pass
        finally:
            for number, handler in previous.items():
                signal.signal(number, handler)
        if options["loop"]:
            self.stdout.write("Fila encerrada.")
            self.stdout.flush()
