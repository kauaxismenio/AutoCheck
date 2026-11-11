"""Trabalhador da fila como processo real, em banco temporário e contra um SMTP local nesta máquina.

Nada sai para a internet: cada processo filho confere o servidor antes de começar.
Roda junto com os testes em navegador:
    $env:RUN_E2E="1"; python manage.py test e2e.test_email_worker --settings=config.settings.test
"""
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter
from pathlib import Path
from unittest import skipUnless

from aiosmtpd.controller import Controller
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parent.parent
OFICINA = "dono@oficinaboa.com.br"
TIMEOUT = 60

SETUP = """
import json, os, sys
from datetime import timedelta
sys.path.insert(0, os.getcwd())
import django
django.setup()
from django.conf import settings
from django.db import connection
assert settings.EMAIL_HOST == "127.0.0.1", "SMTP de teste obrigatorio"
assert str(connection.settings_dict["NAME"]) == os.environ["SQLITE_NAME"], "banco temporario obrigatorio"
from django.utils import timezone
from apps.attendances import workflow as wf
from apps.attendances.models import Attendance
from apps.core.testing import default_workshop, make_attendance, make_customer, make_vehicle
from apps.mailing.models import EmailDispatch
from apps.mailing.services import enqueue_report
from apps.reports.services import generate_report

def seed(index, customer_email, pending_report=False):
    workshop = default_workshop()
    workshop.report_email = "dono@oficinaboa.com.br"
    workshop.save()
    customer = make_customer(cpf=None, phone="81990001712")
    attendance = make_attendance(vehicle=make_vehicle(customer, plate=f"ABC1D{index:02d}"), customer_email=customer_email)
    moment = timezone.now() - timedelta(minutes=10)
    Attendance.objects.filter(pk=attendance.pk).update(
        status=wf.STATUS_CONCLUIDO, current_step=wf.FINALIZADO, completed_at=moment, report_pending=pending_report)
    attendance.refresh_from_db()
    if not pending_report:
        enqueue_report(generate_report(attendance))
"""


class _Smtp:
    """Registra quem recebeu; recusa temporariamente os endereços em `refuse`."""

    def __init__(self):
        self.refuse = set()
        self.received = []
        self.lock = threading.Lock()

    async def handle_RCPT(self, server, session, envelope, address, rcpt_options):  # noqa: ARG002,N802
        if address in self.refuse:
            return "451 Tente mais tarde"
        envelope.rcpt_tos.append(address)
        return "250 OK"

    async def handle_DATA(self, server, session, envelope):  # noqa: ARG002,N802
        with self.lock:
            self.received.extend(envelope.rcpt_tos)
        return "250 OK"

    def counts(self):
        with self.lock:
            return Counter(self.received)


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@skipUnless(os.environ.get("RUN_E2E") == "1", "Processos reais: defina RUN_E2E=1")
class RealWorkerTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.base_dir = Path(tempfile.mkdtemp(prefix="autocheck-worker-"))
        cls.template_db = cls.base_dir / "template.sqlite3"
        env = cls._env(cls.template_db, cls.base_dir, 1)
        subprocess.run([sys.executable, "manage.py", "migrate", "--verbosity=0"], cwd=ROOT, env=env, check=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.base_dir, ignore_errors=True)
        super().tearDownClass()

    @staticmethod
    def _env(database, media, port):
        env = dict(os.environ)
        env.update({
            "DJANGO_SETTINGS_MODULE": "config.settings.development", "SQLITE_NAME": str(database),
            "PRIVATE_MEDIA_DIR": str(media), "EMAIL_HOST": "127.0.0.1", "EMAIL_PORT": str(port), "EMAIL_USE_TLS": "false",
            "EMAIL_USE_SSL": "false", "EMAIL_HOST_USER": "", "EMAIL_HOST_PASSWORD": "", "EMAIL_TIMEOUT": "10",
            "DEFAULT_FROM_EMAIL": "AutoCheck <teste@autocheck.local>", "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1",
            "DJANGO_LOG_LEVEL": "CRITICAL",
        })
        return env

    def setUp(self):
        self.workdir = Path(tempfile.mkdtemp(dir=self.base_dir))
        self.database = self.workdir / "db.sqlite3"
        shutil.copy(self.template_db, self.database)
        self.port = free_port()
        self.env = self._env(self.database, self.workdir, self.port)
        self.smtp = _Smtp()
        self.controller = None
        self.workers = []
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        for worker in self.workers:
            if worker.poll() is None:
                worker.kill()
                worker.communicate()
        if self.controller:
            self.controller.stop()

    def start_smtp(self):
        self.controller = Controller(self.smtp, hostname="127.0.0.1", port=self.port, server_hostname="localhost")
        self.controller.start()

    def start_worker(self):
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        worker = subprocess.Popen(
            [sys.executable, "manage.py", "process_email_queue", "--loop", "--interval=1"], cwd=ROOT, env=self.env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", creationflags=flags,
        )
        self.workers.append(worker)
        return worker

    def stop_worker(self, worker):
        """Pedido de parada real do sistema operacional; precisa terminar sozinho e sem erro."""
        for line in worker.stdout:  # o tratamento do sinal só existe depois de o trabalhador iniciar
            if "Fila iniciada" in line:
                break
        worker.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGTERM)
        output, _ = worker.communicate(timeout=30)
        self.assertEqual(worker.returncode, 0, output)
        self.assertIn("Fila encerrada", output)
        self.assertNotIn("Traceback", output)
        return output

    def django(self, code):
        done = subprocess.run([sys.executable, "-c", SETUP + code], cwd=ROOT, env=self.env, capture_output=True,
                              text=True, encoding="utf-8", errors="replace")
        self.assertEqual(done.returncode, 0, done.stderr[-2000:])
        return done.stdout

    def rows(self):
        output = self.django('print(json.dumps(list(EmailDispatch.objects.order_by("pk").values("recipient_email", "status", "attempts", "next_attempt_at")), default=str))')
        return json.loads(output.strip().splitlines()[-1])

    def wait_for(self, condition, message):
        deadline = time.monotonic() + TIMEOUT
        while time.monotonic() < deadline:
            rows = self.rows()
            if condition(rows):
                return rows
            time.sleep(0.5)
        for worker in self.workers:
            if worker.poll() is not None:
                self.fail(f"{message}: trabalhador encerrou. {worker.communicate()[0][-1500:]}")
        self.fail(f"{message}: {self.rows()}")

    @staticmethod
    def all_accepted(rows):
        return bool(rows) and all(r["status"] == "enviado" for r in rows)

    def make_due(self):
        self.django('EmailDispatch.objects.filter(next_attempt_at__isnull=False).update(next_attempt_at=timezone.now() - timedelta(seconds=1))')

    def test_success_sends_each_recipient_once_and_does_not_repeat(self):
        self.start_smtp()
        self.django('seed(1, "cliente@empresa.com.br")')
        worker = self.start_worker()
        rows = self.wait_for(self.all_accepted, "envio")
        self.assertEqual(len(rows), 2)
        time.sleep(3)  # mais passadas do trabalhador: aceito não pode sair de novo
        self.assertEqual(self.smtp.counts(), Counter({OFICINA: 1, "cliente@empresa.com.br": 1}))
        self.assertEqual({r["attempts"] for r in self.rows()}, {1})
        self.stop_worker(worker)

    def test_temporary_failure_of_one_recipient_retries_only_that_one(self):
        customer = "cliente@empresa.com.br"
        self.smtp.refuse = {customer}
        self.start_smtp()
        self.django(f'seed(1, "{customer}")')
        worker = self.start_worker()
        rows = self.wait_for(lambda r: {x["status"] for x in r} == {"enviado", "falhou"}, "falha do cliente")
        failed = next(r for r in rows if r["status"] == "falhou")
        self.assertEqual(failed["recipient_email"], customer)
        self.assertIsNotNone(failed["next_attempt_at"], "Falha temporária fica agendada")
        self.assertEqual(self.smtp.counts(), Counter({OFICINA: 1}))

        self.smtp.refuse = set()
        self.make_due()
        rows = self.wait_for(self.all_accepted, "recuperação")
        self.assertEqual(self.smtp.counts(), Counter({OFICINA: 1, customer: 1}), "A oficina não recebe de novo")
        attempts = {r["recipient_email"]: r["attempts"] for r in rows}
        self.assertEqual(attempts, {OFICINA: 1, customer: 2})
        self.stop_worker(worker)

    def test_smtp_down_then_recovers_without_any_click(self):
        self.django('seed(1, "")')
        worker = self.start_worker()
        rows = self.wait_for(lambda r: r and r[0]["status"] == "falhou", "falha de conexão")
        self.assertIsNotNone(rows[0]["next_attempt_at"])
        self.start_smtp()
        self.make_due()
        self.wait_for(self.all_accepted, "recuperação do SMTP")
        self.assertEqual(self.smtp.counts(), Counter({OFICINA: 1}))
        self.stop_worker(worker)

    def test_pending_report_is_detected_generated_and_sent(self):
        self.start_smtp()
        self.django('seed(1, "cliente@empresa.com.br", pending_report=True)')
        worker = self.start_worker()
        self.wait_for(lambda r: len(r) == 2 and self.all_accepted(r), "relatório pendente")
        output = self.django('print(Attendance.objects.get().reports.count(), Attendance.objects.get().report_pending)')
        self.assertEqual(output.split()[-2:], ["1", "False"])
        self.stop_worker(worker)

    def test_two_workers_at_the_same_time_never_duplicate(self):
        self.start_smtp()
        customers = [f"cliente{i}@empresa.com.br" for i in range(6)]
        self.django("\n".join(f'seed({i}, "{email}")' for i, email in enumerate(customers)))
        first, second = self.start_worker(), self.start_worker()
        rows = self.wait_for(lambda r: len(r) == 12 and self.all_accepted(r), "dois trabalhadores")
        time.sleep(2)
        counts = self.smtp.counts()
        self.assertEqual(counts[OFICINA], 6, "Uma cópia por atendimento")
        for email in customers:
            self.assertEqual(counts[email], 1)
        self.assertEqual({r["attempts"] for r in rows}, {1})
        self.stop_worker(first)
        self.stop_worker(second)

    def test_two_workers_generate_a_single_report_version(self):
        self.start_smtp()
        self.django('seed(1, "cliente@empresa.com.br", pending_report=True)')
        first, second = self.start_worker(), self.start_worker()
        self.wait_for(lambda r: len(r) == 2 and self.all_accepted(r), "relatório com dois trabalhadores")
        time.sleep(2)
        output = self.django('print(Attendance.objects.get().reports.count())')
        self.assertEqual(output.split()[-1], "1")
        self.assertEqual(self.smtp.counts(), Counter({OFICINA: 1, "cliente@empresa.com.br": 1}))
        self.stop_worker(first)
        self.stop_worker(second)

    def test_old_pending_records_are_left_alone(self):
        self.start_smtp()
        self.django('seed(1, "")\nEmailDispatch.objects.update(next_attempt_at=None)')
        worker = self.start_worker()
        time.sleep(4)
        self.assertEqual(self.smtp.counts(), Counter())
        self.assertEqual(self.rows()[0]["status"], "pendente")
        self.stop_worker(worker)

    def test_restart_continues_the_queue(self):
        self.start_smtp()
        self.django('seed(1, "cliente@empresa.com.br")\nEmailDispatch.objects.update(next_attempt_at=timezone.now() + timedelta(seconds=8))')
        worker = self.start_worker()
        time.sleep(3)
        self.stop_worker(worker)
        self.assertEqual(self.smtp.counts(), Counter(), "Ainda não tinha chegado a hora")
        self.make_due()
        replacement = self.start_worker()
        self.wait_for(self.all_accepted, "continuação depois de reiniciar")
        self.assertEqual(self.smtp.counts(), Counter({OFICINA: 1, "cliente@empresa.com.br": 1}))
        self.stop_worker(replacement)
