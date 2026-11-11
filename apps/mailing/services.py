"""Envio do relatório com fila persistente, tentativas, erros e aceite do servidor.

Fluxo normal: a finalização grava o pedido de relatório na mesma transação da conclusão;
depois gera o PDF, cria um registro por destinatário e faz a primeira tentativa. O que não
terminar ali (falha, queda do processo, usuário fechou a página) é retomado pelo comando
`process_email_queue`, sem nenhum clique.

Um e-mail só é "enviado" quando o servidor SMTP aceita a mensagem. Sem SMTP configurado
nada é marcado como enviado: o registro fica pendente, com o motivo.
"""
import logging
import smtplib
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage, get_connection
from django.core.mail.message import make_msgid
from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.utils import timezone

from apps.attendances import workflow as wf
from apps.attendances.models import Attendance
from apps.core.audit import log_action
from apps.reports.models import Report
from apps.reports.services import generate_report, latest_report

from .models import ACCEPTED_STATUSES, DispatchStatus, EmailDispatch, RecipientType

logger = logging.getLogger("autocheck.mailing")

NOT_CONFIGURED = "SMTP não configurado no servidor. O e-mail não foi enviado."
UNKNOWN_RESULT = "O envio foi interrompido e não é possível saber se o servidor aceitou a mensagem. Confira antes de reenviar."
STALE_AFTER = timedelta(minutes=15)
RESEND_GUARD = timedelta(seconds=60)
# Intervalo depois de cada falha temporária; ao esgotar, só o reenvio manual tenta de novo.
RETRY_DELAYS = (timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=15), timedelta(hours=1), timedelta(hours=4))
MAX_ATTEMPTS = len(RETRY_DELAYS) + 1
# O comando só assume relatórios parados há algum tempo, para não disputar com a requisição em curso.
REPORT_GRACE = timedelta(minutes=2)
REPORT_RETRY_WINDOW = timedelta(hours=24)
# Item vencido há mais tempo que isto indica que o trabalhador da fila não está rodando.
STALLED_AFTER = timedelta(minutes=5)
# Estes backends não entregam nada: usá-los nunca pode contar como envio.
_NON_DELIVERING = {
    "django.core.mail.backends.console.EmailBackend",
    "django.core.mail.backends.dummy.EmailBackend",
    "django.core.mail.backends.filebased.EmailBackend",
}
_SMTP_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
_SENDABLE = (DispatchStatus.PENDENTE, DispatchStatus.FALHOU)

_ACCEPTED = "aceito"
_RETRY = "falha_temporaria"
_PERMANENT = "falha_definitiva"
_UNCERTAIN = "incerto"


def smtp_configured():
    if settings.EMAIL_BACKEND in _NON_DELIVERING:
        return False
    if settings.EMAIL_BACKEND == _SMTP_BACKEND:
        return bool(settings.EMAIL_HOST)
    return True


def _build_message(report, recipient, message_id):
    attendance = report.attendance
    workshop = attendance.workshop
    subject = f"Relatório do atendimento {attendance.code} — {attendance.vehicle.plate_formatted}"
    body = (
        f"Olá,\n\nSegue em anexo o relatório do atendimento {attendance.code}, "
        f"referente ao veículo {attendance.vehicle.plate_formatted} ({attendance.vehicle.brand} {attendance.vehicle.model}).\n\n"
        f"Atenciosamente,\n{workshop.name}\n"
    )
    message = EmailMessage(subject=subject, body=body, from_email=settings.DEFAULT_FROM_EMAIL, to=[recipient],
                           headers={"Message-ID": message_id})
    with report.file.storage.open(report.file.name, "rb") as stored:
        message.attach(report.download_name, stored.read(), "application/pdf")
    return message


def _safe_error(exc):
    """Texto do erro para registro e tela. A senha do SMTP nunca pode aparecer nele."""
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return f"SMTPAuthenticationError: o servidor recusou o usuário ou a senha (código {exc.smtp_code})."
    text = f"{type(exc).__name__}: {exc}"
    if settings.EMAIL_HOST_PASSWORD:
        text = text.replace(settings.EMAIL_HOST_PASSWORD, "***")
    return text[:500]


def _classify_by_code(code):
    if 400 <= code < 500:
        return _RETRY
    if 500 <= code < 600:
        return _PERMANENT
    return _UNCERTAIN


def _classify_send_error(exc):
    """Erro com a conexão já aberta. Só há certeza de recusa quando o servidor responde com um código."""
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        codes = {_classify_by_code(code) for code, _ in exc.recipients.values()}
        return codes.pop() if len(codes) == 1 else _UNCERTAIN
    if isinstance(exc, smtplib.SMTPResponseException):
        return _classify_by_code(exc.smtp_code)
    return _UNCERTAIN  # queda ou timeout: o servidor pode ter aceitado sem a resposta chegar aqui


def _transmit(dispatch, message_id):
    """Uma tentativa real. Retorna (desfecho, texto do erro)."""
    try:
        message = _build_message(dispatch.report, dispatch.recipient_email, message_id)
        connection = get_connection(fail_silently=False)
        connection.open()
    except Exception as exc:  # noqa: BLE001 — nada foi transmitido: repetir é seguro
        return _RETRY, _safe_error(exc)
    message.connection = connection
    try:
        accepted = message.send(fail_silently=False)
    except Exception as exc:  # noqa: BLE001 — qualquer falha precisa ficar registrada
        return _classify_send_error(exc), _safe_error(exc)
    finally:
        try:
            connection.close()
        except Exception:  # noqa: BLE001, S110 — encerrar a conexão não muda o resultado do envio
            pass
    if accepted == 1:
        return _ACCEPTED, ""
    return _RETRY, "O servidor de e-mail não confirmou a aceitação da mensagem."


def _next_retry(attempts):
    if attempts >= MAX_ATTEMPTS:
        return None
    return timezone.now() + RETRY_DELAYS[attempts - 1]


def _resolved_elsewhere(dispatch):
    """Outro registro da mesma versão e endereço já foi aceito (ex.: reenvio manual)."""
    return not dispatch.is_manual_resend and EmailDispatch.objects.filter(
        report_id=dispatch.report_id, recipient_email__iexact=dispatch.recipient_email, status__in=ACCEPTED_STATUSES,
    ).exclude(pk=dispatch.pk).exists()


def _recover_stale(attendance=None):
    """Tentativa que parou sem resposta: resultado desconhecido. Não repete sozinha para não duplicar."""
    limit = timezone.now() - STALE_AFTER
    queryset = EmailDispatch.objects.filter(status=DispatchStatus.ENVIANDO, last_attempt_at__lt=limit)
    if attendance is not None:
        queryset = queryset.filter(attendance=attendance)
    queryset.update(status=DispatchStatus.INCERTO, last_error=UNKNOWN_RESULT, next_attempt_at=None)


def deliver(dispatch):
    """Faz uma tentativa. O `update` condicional impede dois envios simultâneos do mesmo registro."""
    if not smtp_configured():
        EmailDispatch.objects.filter(pk=dispatch.pk, status__in=_SENDABLE).update(
            status=DispatchStatus.PENDENTE, last_error=NOT_CONFIGURED, backend=settings.EMAIL_BACKEND,
        )
        dispatch.refresh_from_db()
        return dispatch

    if _resolved_elsewhere(dispatch):
        EmailDispatch.objects.filter(pk=dispatch.pk).update(next_attempt_at=None)
        dispatch.refresh_from_db()
        return dispatch

    claimed = EmailDispatch.objects.filter(pk=dispatch.pk, status__in=_SENDABLE).update(
        status=DispatchStatus.ENVIANDO, attempts=F("attempts") + 1, last_attempt_at=timezone.now(),
        backend=settings.EMAIL_BACKEND, last_error="", next_attempt_at=None,
    )
    dispatch.refresh_from_db()
    if not claimed:
        return dispatch

    message_id = make_msgid(domain="autocheck.local")
    outcome, error = _transmit(dispatch, message_id)
    now = timezone.now()
    if outcome == _ACCEPTED:
        dispatch.status = DispatchStatus.ENVIADO
        dispatch.accepted_at = now
        dispatch.message_id = message_id[:255]
        dispatch.last_error = ""
    elif outcome == _UNCERTAIN:
        dispatch.status = DispatchStatus.INCERTO
        dispatch.message_id = message_id[:255]  # permite localizar a mensagem na conta antes de reenviar
        dispatch.last_error = f"{UNKNOWN_RESULT} Detalhe: {error}"[:500]
    else:
        dispatch.status = DispatchStatus.FALHOU
        dispatch.last_error = error
        dispatch.next_attempt_at = _next_retry(dispatch.attempts) if outcome == _RETRY else None
        if dispatch.next_attempt_at is None:
            logger.error("Envio %s sem nova tentativa automática (%s, %s tentativas).", dispatch.pk, outcome, dispatch.attempts)
    if outcome != _ACCEPTED:
        logger.warning("Falha no envio do e-mail %s: %s", dispatch.pk, outcome)
    dispatch.attempt_log = [*dispatch.attempt_log, {"em": now.isoformat(), "resultado": outcome, "erro": error}]
    dispatch.save(update_fields=["status", "accepted_at", "message_id", "last_error", "next_attempt_at", "attempt_log"])
    if outcome == _ACCEPTED:
        # Aceito: nenhum outro registro desta versão e endereço pode repetir a mensagem sozinho.
        EmailDispatch.objects.filter(
            report_id=dispatch.report_id, recipient_email__iexact=dispatch.recipient_email, next_attempt_at__isnull=False,
        ).exclude(pk=dispatch.pk).update(next_attempt_at=None)
    return dispatch


def required_recipients(attendance):
    """Sempre a oficina; o cliente só se forneceu e-mail. O mesmo endereço recebe uma única cópia."""
    recipients = []
    report_email = attendance.workshop.report_email
    if report_email:
        recipients.append((RecipientType.OFICINA, report_email))
    if attendance.should_email_customer and attendance.customer_email.strip().lower() != report_email.strip().lower():
        recipients.append((RecipientType.CLIENTE, attendance.customer_email))
    return recipients


def _already_confirmed(attendance, email):
    return EmailDispatch.objects.filter(
        attendance=attendance, recipient_email__iexact=email, status__in=ACCEPTED_STATUSES, accepted_at__isnull=False,
    ).exists()


def _supersede_older_versions(report):
    """Uma versão nova substitui o que ainda não saiu das anteriores. O que já foi aceito fica como está."""
    EmailDispatch.objects.filter(attendance_id=report.attendance_id, status__in=_SENDABLE).exclude(report=report).filter(
        Q(status=DispatchStatus.PENDENTE) | Q(next_attempt_at__isnull=False),
    ).update(status=DispatchStatus.FALHOU, next_attempt_at=None,
             last_error=f"Não enviado: substituído pela versão {report.version} do relatório.")


def _automatic_dispatch(report, recipient_type, email):
    existing = EmailDispatch.objects.filter(
        attendance_id=report.attendance_id, report=report, recipient_email__iexact=email, is_manual_resend=False,
    ).first()
    if existing:
        return existing
    key = EmailDispatch.automatic_key(report, email)
    try:
        with transaction.atomic():
            dispatch, _ = EmailDispatch.objects.get_or_create(
                idempotency_key=key,
                defaults={"attendance_id": report.attendance_id, "report": report, "recipient_type": recipient_type,
                          "recipient_email": email, "next_attempt_at": timezone.now()},
            )
    except IntegrityError:
        dispatch = EmailDispatch.objects.get(idempotency_key=key)
    return dispatch


def enqueue_report(report):
    """Grava um registro por destinatário da versão atual. Versões antigas nunca entram na fila."""
    latest = latest_report(report.attendance)
    if latest is None or latest.pk != report.pk:
        return []
    _supersede_older_versions(report)
    return [_automatic_dispatch(report, kind, email) for kind, email in required_recipients(report.attendance)]


def send_report(report):
    """Tenta agora o que está em aberto nesta versão. Quem já foi aceito não recebe de novo."""
    _recover_stale(report.attendance)
    rows = [row for row in enqueue_report(report) if row.status in _SENDABLE and not _resolved_elsewhere(row)]
    return [deliver(row) for row in rows]


def issue_report(attendance, *, user=None, request=None, force=False):
    """Gera o PDF definitivo e grava a fila na mesma transação.

    Sem `force`, só age se o relatório da finalização ainda estiver pendente: chamar de novo
    (requisição repetida, comando) não cria outra versão. `force` é o "Gerar nova versão".
    """
    with transaction.atomic():
        locked = Attendance.objects.select_for_update().get(pk=attendance.pk)
        if not force and not locked.report_pending:
            return latest_report(locked)
        report = generate_report(locked, user=user, request=request)
        enqueue_report(report)
        Attendance.objects.filter(pk=locked.pk).update(report_pending=False)
    return report


def _tally(summary, dispatch):
    if dispatch.is_confirmed:
        summary["aceitos"] += 1
    elif dispatch.status == DispatchStatus.INCERTO:
        summary["incertos"] += 1
    elif dispatch.status == DispatchStatus.FALHOU:
        summary["falhas"] += 1


def process_queue(*, limit=50, should_stop=None):
    """Uma passada da fila: retoma relatórios parados e envia o que venceu. Não apaga nada.

    `should_stop` é consultado entre os itens: o envio em curso sempre termina.
    """
    should_stop = should_stop or (lambda: False)
    summary = {"relatorios": 0, "relatorios_com_erro": 0, "aceitos": 0, "falhas": 0, "incertos": 0, "smtp_configurado": smtp_configured()}
    _recover_stale()
    now = timezone.now()
    stuck = Attendance.objects.filter(
        report_pending=True, status=wf.STATUS_CONCLUIDO,
        completed_at__lte=now - REPORT_GRACE, completed_at__gte=now - REPORT_RETRY_WINDOW,
    ).order_by("completed_at")[:limit]
    for attendance in stuck:
        if should_stop():
            return summary
        try:
            issue_report(attendance)
        except Exception:  # noqa: BLE001 — um atendimento com problema não para os demais
            logger.exception("Falha ao gerar o relatório do atendimento %s", attendance.pk)
            summary["relatorios_com_erro"] += 1
        else:
            summary["relatorios"] += 1
    if not summary["smtp_configurado"]:
        return summary  # sem SMTP os registros continuam na fila e saem quando for configurado
    due = EmailDispatch.objects.filter(status__in=_SENDABLE, next_attempt_at__lte=timezone.now()).select_related(
        "report", "attendance",
    ).order_by("next_attempt_at")[:limit]
    for dispatch in due:
        if should_stop():
            break
        try:
            _tally(summary, deliver(dispatch))
        except Exception:  # noqa: BLE001 — o registro continua na fila ou é tratado como incerto
            logger.exception("Falha ao processar o envio %s", dispatch.pk)
            summary["falhas"] += 1
    return summary


def queue_status():
    """Situação da fila para acompanhamento. Só lê: não envia nem altera nada."""
    now = timezone.now()
    scheduled = EmailDispatch.objects.filter(status__in=_SENDABLE, next_attempt_at__isnull=False)
    return {
        "smtp_configurado": smtp_configured(),
        "na_fila": scheduled.count(),
        "atrasados": scheduled.filter(next_attempt_at__lt=now - STALLED_AFTER).count(),
        "em_processamento": EmailDispatch.objects.filter(status=DispatchStatus.ENVIANDO).count(),
        "aceitos": EmailDispatch.objects.filter(status__in=ACCEPTED_STATUSES).count(),
        "falhas_sem_nova_tentativa": EmailDispatch.objects.filter(status=DispatchStatus.FALHOU, next_attempt_at__isnull=True).count(),
        "incertos": EmailDispatch.objects.filter(status=DispatchStatus.INCERTO).count(),
        "pendentes_manuais": EmailDispatch.objects.filter(status=DispatchStatus.PENDENTE, next_attempt_at__isnull=True).count(),
        "relatorios_pendentes": Attendance.objects.filter(report_pending=True).count(),
    }


def queue_stalled(attendance):
    """Algo deste atendimento já deveria ter sido processado: o trabalhador provavelmente está parado."""
    limit = timezone.now() - STALLED_AFTER
    if attendance.report_pending and attendance.completed_at and attendance.completed_at < limit:
        return True
    return EmailDispatch.objects.filter(attendance=attendance, status__in=_SENDABLE, next_attempt_at__lt=limit).exists()


def register_provider_event(dispatch, status, detail=""):
    """Entrega ou devolução, somente com comprovação do provedor. O SMTP sozinho não informa isso."""
    if status not in (DispatchStatus.ENTREGUE, DispatchStatus.DEVOLVIDO):
        raise ValueError("Situação inválida para evento do provedor.")
    if dispatch.accepted_at is None:
        raise ValueError("Só existe entrega ou devolução de mensagem aceita pelo servidor.")
    dispatch.status = status
    dispatch.provider_event_at = timezone.now()
    dispatch.last_error = detail[:500] if status == DispatchStatus.DEVOLVIDO else ""
    dispatch.save(update_fields=["status", "provider_event_at", "last_error"])
    return dispatch


def resend(report, recipient_type, *, user=None, request=None):
    """Reenvio manual: sempre um novo registro, com proteção contra duplo clique."""
    attendance = report.attendance
    _recover_stale(attendance)
    recipients = dict(required_recipients(attendance))
    if recipient_type not in recipients:
        if recipient_type == RecipientType.CLIENTE:
            if attendance.should_email_customer:
                raise ValidationError("O cliente usa o mesmo e-mail da oficina. Use \"Reenviar à oficina\".")
            raise ValidationError("O cliente não forneceu e-mail ou optou por não receber o relatório.")
        raise ValidationError("Configure o e-mail do responsável pela oficina.")
    email = recipients[recipient_type]
    recent = timezone.now() - RESEND_GUARD
    same_address = EmailDispatch.objects.filter(attendance=attendance, recipient_email__iexact=email)
    if same_address.filter(status=DispatchStatus.ENVIANDO).exists() or same_address.filter(
            created_at__gte=recent, status=DispatchStatus.ENVIADO).exists():
        raise ValidationError("Este destinatário acabou de receber o relatório. Aguarde um minuto para reenviar.")
    dispatch = EmailDispatch.objects.create(
        attendance=attendance, report=report, recipient_type=recipient_type, recipient_email=email,
        is_manual_resend=True, requested_by=user,
        idempotency_key=f"manual:{report.pk}:{recipient_type}:{uuid.uuid4().hex}",
    )
    log_action("mailing.resend", request=request, user=user, obj=dispatch, attendance=attendance, recipient=recipient_type)
    return deliver(dispatch)


def _has_open_dispatches(attendance):
    """Envio em aberto na versão atual, sem outro registro aceito para o mesmo endereço."""
    latest = latest_report(attendance)
    if latest is None:
        return False
    rows = EmailDispatch.objects.filter(attendance=attendance, report=latest).filter(
        Q(status__in=(DispatchStatus.PENDENTE, DispatchStatus.ENVIANDO, DispatchStatus.INCERTO))
        | Q(next_attempt_at__isnull=False),
    )
    return any(
        not EmailDispatch.objects.filter(report=latest, recipient_email__iexact=row.recipient_email,
                                         status__in=ACCEPTED_STATUSES).exists()
        for row in rows
    )


def mandatory_emails_confirmed(attendance):
    """Base da retenção: sem o aceite obrigatório ou com envio em aberto, os dados não podem ser excluídos."""
    if attendance.report_pending or _has_open_dispatches(attendance):
        return False
    required = required_recipients(attendance)
    if not any(kind == RecipientType.OFICINA for kind, _ in required):
        return False
    return all(_already_confirmed(attendance, email) for _, email in required)


def send_test_email(recipient):
    """Teste do SMTP. Levanta exceção se não funcionar; o retorno é o aceite do servidor."""
    if not smtp_configured():
        raise ValidationError(NOT_CONFIGURED)
    message = EmailMessage(
        subject="Teste de e-mail do AutoCheck", body="Se você recebeu esta mensagem, o envio de e-mail está funcionando.",
        from_email=settings.DEFAULT_FROM_EMAIL, to=[recipient], connection=get_connection(fail_silently=False),
    )
    return message.send(fail_silently=False) == 1


def dispatch_overview(attendance, user):  # noqa: ARG001
    reports = list(Report.objects.filter(attendance=attendance).order_by("-version"))
    recipients = dict(required_recipients(attendance))
    return {
        "reports": reports,
        "latest_report": reports[0] if reports else None,
        "dispatches": attendance.email_dispatches.select_related("report").order_by("-created_at"),
        "can_send_workshop": RecipientType.OFICINA in recipients,
        "can_send_customer": RecipientType.CLIENTE in recipients,
        "smtp_ok": smtp_configured(),
        "queue_stalled": queue_stalled(attendance),
        "emails_confirmed": mandatory_emails_confirmed(attendance),
    }
