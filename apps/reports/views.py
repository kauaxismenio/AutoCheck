from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.attendances.views import get_attendance
from apps.core.protected_files import serve_protected_file
from apps.mailing.services import RESEND_GUARD, issue_report, send_report
from apps.mailing.views import report_outcome_messages

from . import services
from .models import Report


@login_required
def download(request, public_id, pk):
    report = get_object_or_404(Report.objects.select_related("attendance"), pk=pk, attendance__public_id=public_id)
    return serve_protected_file(report.file, download_name=report.download_name, as_attachment=True)


@login_required
@require_POST
def generate(request, public_id):
    """Nova versão controlada: entra na fila e substitui o que não saiu das versões anteriores."""
    attendance = get_attendance(public_id)
    latest = services.latest_report(attendance)
    if latest and timezone.now() - latest.generated_at < RESEND_GUARD:
        # Duplo clique não pode criar outra versão nem outro e-mail para o cliente.
        messages.info(request, f"A versão {latest.version} acabou de ser gerada. Aguarde um minuto para gerar outra.")
        return redirect("attendances:summary", attendance.public_id)
    try:
        report = issue_report(attendance, user=request.user, request=request, force=True)
    except services.ReportNotAllowed as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"Relatório versão {report.version} gerado.")
        report_outcome_messages(request, send_report(report))
    return redirect("attendances:summary", attendance.public_id)
