"""Registro de cada envio de relatório por e-mail. É também a fila persistente de envios.

Aceite do servidor SMTP (status ENVIADO + `accepted_at`) não significa entrega na caixa
do destinatário: entrega e devolução só existem com comprovação do provedor.

Proteção contra duplicidade: o envio automático tem `idempotency_key` única por
ATENDIMENTO + VERSÃO DO RELATÓRIO + ENDEREÇO. Nunca por cliente: outro atendimento do
mesmo cliente gera novos envios. Reenvios manuais são registros próprios (`is_manual_resend`).

A fila automática só processa registros com `next_attempt_at` preenchido.
"""
import hashlib

from django.conf import settings
from django.db import models

from apps.core.tenancy import AttendanceScopedManager


class RecipientType(models.TextChoices):
    OFICINA = "oficina", "Responsável pela oficina"
    CLIENTE = "cliente", "Cliente"


class DispatchStatus(models.TextChoices):
    PENDENTE = "pendente", "Pendente"
    ENVIANDO = "enviando", "Em processamento"
    ENVIADO = "enviado", "Aceito pelo servidor SMTP"
    FALHOU = "falhou", "Falha"
    INCERTO = "incerto", "Resultado incerto"
    ENTREGUE = "entregue", "Entrega confirmada"
    DEVOLVIDO = "devolvido", "Devolvido"


ACCEPTED_STATUSES = (DispatchStatus.ENVIADO, DispatchStatus.ENTREGUE)


class EmailDispatch(models.Model):
    attendance = models.ForeignKey("attendances.Attendance", on_delete=models.CASCADE, related_name="email_dispatches")
    report = models.ForeignKey("reports.Report", on_delete=models.CASCADE, related_name="email_dispatches")
    recipient_type = models.CharField("destinatário", max_length=10, choices=RecipientType.choices)
    recipient_email = models.EmailField("e-mail")

    status = models.CharField("situação", max_length=10, choices=DispatchStatus.choices, default=DispatchStatus.PENDENTE, db_index=True)
    attempts = models.PositiveSmallIntegerField("tentativas", default=0)
    last_attempt_at = models.DateTimeField("última tentativa", null=True, blank=True)
    next_attempt_at = models.DateTimeField("próxima tentativa automática", null=True, blank=True, db_index=True)
    accepted_at = models.DateTimeField("aceito pelo servidor em", null=True, blank=True)
    provider_event_at = models.DateTimeField("comprovação do provedor em", null=True, blank=True)
    last_error = models.TextField("último erro", blank=True)
    attempt_log = models.JSONField("histórico de tentativas", default=list, blank=True)
    backend = models.CharField("backend de e-mail", max_length=120, blank=True)
    message_id = models.CharField("Message-ID", max_length=255, blank=True)

    idempotency_key = models.CharField(max_length=200, unique=True)
    is_manual_resend = models.BooleanField("reenvio manual", default=False)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField("criado em", auto_now_add=True)

    objects = AttendanceScopedManager()

    class Meta:
        verbose_name = "envio de e-mail"
        verbose_name_plural = "envios de e-mail"
        ordering = ["-created_at"]

    @staticmethod
    def automatic_key(report, email):
        """Atendimento + versão + endereço. O hash mantém a chave curta para qualquer e-mail válido."""
        address = hashlib.sha256(email.strip().lower().encode()).hexdigest()
        return f"auto:{report.attendance_id}:v{report.version}:{address}"

    @property
    def is_confirmed(self):
        return self.status in ACCEPTED_STATUSES and self.accepted_at is not None

    def __str__(self):
        return f"{self.recipient_email} — {self.get_status_display()}"
