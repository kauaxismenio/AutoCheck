"""Limpeza de atendimentos com retenção vencida.

Por padrão é SIMULAÇÃO: apenas lista o que aconteceria, sem apagar nada.
A exclusão real exige o comando explícito:  python manage.py purge_expired --execute
"""
from django.core.management.base import BaseCommand

from apps.aftersales.services import expired_items, purge


class Command(BaseCommand):
    help = "Lista (simulação) ou exclui, com --execute, os atendimentos com retenção vencida."

    def add_arguments(self, parser):
        parser.add_argument("--execute", action="store_true", help="Exclui de verdade. Sem esta opção, nada é apagado.")

    def handle(self, *args, **options):
        execute = options["execute"]
        items = expired_items()
        mode = "EXCLUSÃO REAL" if execute else "SIMULAÇÃO (nada será apagado)"
        self.stdout.write(f"Modo: {mode}")
        self.stdout.write(f"Atendimentos com prazo vencido: {len(items)}")

        excluded = blocked = failed = 0
        for item in items:
            att = item.attendance
            line = f"{att.code} | manter até {att.retention_until:%d/%m/%Y} | {len(item.files)} arquivo(s), {item.size_bytes} bytes"
            if not item.eligible:
                blocked += 1
                self.stdout.write(self.style.WARNING(f"BLOQUEADO  {line} | {item.reason}"))
                continue
            if not execute:
                excluded += 1
                self.stdout.write(f"EXCLUIRIA  {line}")
                continue
            try:
                purge(item)
            except Exception as exc:  # noqa: BLE001 — um erro não interrompe os demais; fica relatado
                failed += 1
                self.stdout.write(self.style.ERROR(f"FALHOU     {line} | {type(exc).__name__}: {exc}"))
            else:
                excluded += 1
                self.stdout.write(self.style.SUCCESS(f"EXCLUÍDO   {line}"))

        verb = "Excluídos" if execute else "Seriam excluídos"
        self.stdout.write(f"{verb}: {excluded} | Bloqueados: {blocked} | Falhas: {failed}")
        if not execute and excluded:
            self.stdout.write("Para excluir de verdade: python manage.py purge_expired --execute")
