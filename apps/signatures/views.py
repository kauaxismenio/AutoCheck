"""Etapa de revisão, assinatura e finalização do atendimento."""
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.attendances import services as att_services
from apps.attendances import workflow as wf
from apps.attendances.navigation import steps_nav
from apps.attendances.summary import build_summary
from apps.attendances.views import get_attendance
from apps.core.protected_files import serve_protected_file
from apps.mailing.services import issue_report, send_report
from apps.mailing.views import report_outcome_messages

from . import services
from .models import REFUSAL_TEXT, AttendanceSignature

logger = logging.getLogger("autocheck.signatures")


def _register(attendance, request):
    """Aplica o que veio do formulário. Assinatura válida já existente é mantida."""
    refused = bool(request.POST.get("refused"))
    data = request.POST.get("signature_data", "")
    existing = AttendanceSignature.objects.filter(attendance=attendance).first()
    if refused:
        services.register_refusal(attendance, user=request.user, request=request)
    elif data:
        services.register_signature(attendance, data, user=request.user, request=request)
    elif existing and existing.refused:
        # Desmarcou a recusa e não assinou: a recusa anterior deixa de valer.
        existing.delete()
        attendance._state.fields_cache.pop("signature", None)


def _finalize(attendance, request):
    with transaction.atomic():
        _register(attendance, request)
        att_services.advance(attendance, wf.REVISAO, user=request.user, request=request)


def _issue_report(attendance, request):
    """Depois do commit: falha no PDF ou no e-mail não desfaz a conclusão e o comando da fila retoma o que faltar."""
    attendance.refresh_from_db()
    try:
        report = issue_report(attendance, user=request.user, request=request)
    except Exception:  # noqa: BLE001 — o atendimento já está concluído; o erro completo vai para o log
        logger.exception("Falha ao gerar o relatório do atendimento %s", attendance.pk)
        messages.error(request, "Não foi possível gerar o relatório agora. O sistema tentará de novo automaticamente.")
        return
    try:
        report_outcome_messages(request, send_report(report))
    except Exception:  # noqa: BLE001 — os registros já estão gravados na fila
        logger.exception("Falha ao iniciar os envios do atendimento %s", attendance.pk)
        messages.warning(request, "Os e-mails do relatório ficaram na fila e serão enviados automaticamente.")
    if not attendance.workshop.report_email:
        messages.warning(request, "E-mail do responsável não configurado: o relatório da oficina não foi enviado.")


@login_required
def step(request, public_id):
    attendance = get_attendance(public_id)
    att_services.get_step_or_403(attendance, wf.REVISAO)
    errors = []
    if request.method == "POST":
        try:
            _finalize(attendance, request)
        except att_services.StepIncomplete as exc:
            errors = exc.errors
        except ValidationError as exc:
            errors = exc.messages
        else:
            messages.success(request, "Atendimento concluído.")
            _issue_report(attendance, request)
            return redirect("attendances:summary", attendance.public_id)
        attendance = get_attendance(public_id)

    signature = AttendanceSignature.objects.filter(attendance=attendance).first()
    return render(request, "signatures/step.html", {
        "attendance": attendance, "steps": steps_nav(attendance, wf.REVISAO), "errors": errors,
        "summary": build_summary(attendance), "signature": signature,
        "signature_is_current": bool(signature and signature.matches_current_version()),
        "refusal_text": REFUSAL_TEXT,
    })


@login_required
@require_POST
def review_qr(request, public_id):
    """Registra (ou desfaz) a apresentação do QR Code. Com JS, responde sem recarregar e sem perder a assinatura."""
    attendance = get_attendance(public_id)
    att_services.get_step_or_403(attendance, wf.REVISAO)
    wants_json = "application/json" in request.headers.get("Accept", "")
    try:
        services.set_review_qr_presented(attendance, request.POST.get("action") != "clear",
                                         user=request.user, request=request)
    except ValidationError as exc:
        if wants_json:
            return JsonResponse({"error": exc.messages[0]}, status=400)
        messages.error(request, exc.messages[0])
    if wants_json:
        return JsonResponse({"presented": bool(attendance.review_qr_presented_at), "note": attendance.review_qr_note})
    return redirect("signatures:step", attendance.public_id)


@login_required
def signature_file(request, public_id):
    signature = get_object_or_404(AttendanceSignature, attendance__public_id=public_id, refused=False)
    return serve_protected_file(signature.image)
