"""Geração e versionamento do relatório. Cada geração cria uma nova versão."""
import hashlib

from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Max

from apps.attendances import workflow as wf
from apps.attendances.models import Attendance
from apps.attendances.summary import build_summary
from apps.core.audit import log_action

from .models import Report
from .pdf import build_pdf


class ReportNotAllowed(Exception):
    """Relatório só existe para atendimento concluído."""


def generate_report(attendance, *, user=None, request=None):
    if attendance.status != wf.STATUS_CONCLUIDO:
        raise ReportNotAllowed("O relatório é gerado após a conclusão do atendimento.")
    fresh = Attendance.objects.select_related("workshop", "customer", "vehicle", "attendant", "mechanic").get(pk=attendance.pk)
    with transaction.atomic():
        Attendance.objects.select_for_update().filter(pk=fresh.pk).first()  # evita versões simultâneas iguais
        version = (Report.objects.filter(attendance=fresh).aggregate(last=Max("version"))["last"] or 0) + 1
        data = build_pdf(fresh, build_summary(fresh), fresh.workshop, version=version)
        signature = getattr(fresh, "signature", None)
        report = Report(
            attendance=fresh, version=version, sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data),
            signature_sha256=signature.snapshot_sha256 if signature else "", generated_by=user,
        )
        report.file.save(f"{fresh.public_id.hex}-v{version}.pdf", ContentFile(data), save=False)
        report.save()
    log_action("report.generated", request=request, user=user, obj=report, attendance=fresh, version=version)
    return report


def latest_report(attendance):
    return Report.objects.filter(attendance=attendance).order_by("-version").first()
