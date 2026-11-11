from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.attendances.views import get_attendance
from apps.core.audit import log_action
from apps.reports.services import latest_report

from . import services
from .models import DispatchStatus


def report_outcome_messages(request, dispatches):
    """Mostra o resultado real informado pelo servidor, um destinatário por vez."""
    for dispatch in dispatches:
        if dispatch.status == DispatchStatus.ENVIADO:
            messages.success(request, f"Relatório aceito pelo servidor de e-mail para {dispatch.recipient_email}.")
        elif dispatch.status == DispatchStatus.ENVIANDO:
            messages.info(request, f"Envio para {dispatch.recipient_email} em processamento.")
        elif dispatch.status == DispatchStatus.INCERTO:
            messages.warning(request, f"Resultado incerto para {dispatch.recipient_email}: {dispatch.last_error}")
        else:
            retry = ""
            if dispatch.next_attempt_at:
                retry = f" Nova tentativa automática às {timezone.localtime(dispatch.next_attempt_at):%H:%M}."
            messages.warning(request, f"Relatório não enviado para {dispatch.recipient_email}: {dispatch.last_error}{retry}")


@login_required
@require_POST
def send_pending(request, public_id):
    attendance = get_attendance(public_id)
    report = latest_report(attendance)
    if report is None:
        messages.error(request, "Gere o relatório antes de enviar.")
        return redirect("attendances:summary", attendance.public_id)
    results = services.send_report(report)
    if results:
        report_outcome_messages(request, results)
    elif attendance.email_dispatches.filter(report=report, status=DispatchStatus.INCERTO).exists():
        messages.warning(request, "Há envio com resultado incerto. Confira se a mensagem chegou e, se precisar, use o reenvio.")
    else:
        messages.info(request, "Nenhum envio pendente.")
    return redirect("attendances:summary", attendance.public_id)


@login_required
@require_POST
def resend(request, public_id):
    attendance = get_attendance(public_id)
    report = latest_report(attendance)
    if report is None:
        messages.error(request, "Gere o relatório antes de enviar.")
        return redirect("attendances:summary", attendance.public_id)
    try:
        dispatch = services.resend(report, request.POST.get("recipient", ""), user=request.user, request=request)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        report_outcome_messages(request, [dispatch])
    return redirect("attendances:summary", attendance.public_id)


@login_required
@require_POST
def test_email(request):
    recipient = request.user.workshop.report_email
    if not recipient:
        messages.error(request, "Informe e salve o e-mail do responsável antes de testar.")
        return redirect("workshop:settings")
    try:
        accepted = services.send_test_email(recipient)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    except Exception as exc:  # noqa: BLE001 — mostra ao administrador o motivo informado pelo servidor
        log_action("mailing.test_failed", request=request, error=type(exc).__name__)
        messages.error(request, f"Falha no envio de teste: {type(exc).__name__}: {str(exc)[:200]}")
    else:
        log_action("mailing.test_sent", request=request, accepted=accepted)
        if accepted:
            messages.success(request, f"E-mail de teste aceito pelo servidor para {recipient}.")
        else:
            messages.error(request, "O servidor de e-mail não confirmou a aceitação.")
    return redirect("workshop:settings")
