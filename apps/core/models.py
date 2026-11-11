"""Modelos base e trilha de auditoria."""
from django.conf import settings
from django.db import models

from .tenancy import AttendanceScopedManager, WorkshopScopedManager, current_workshop_id  # noqa: F401


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField("criado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        abstract = True


class WorkshopOwned(models.Model):
    """Registro que pertence a uma oficina. As consultas por `objects` são isoladas (apps.core.tenancy)."""

    workshop = models.ForeignKey(
        "workshop.WorkshopSettings", verbose_name="oficina", on_delete=models.PROTECT, related_name="%(class)ss",
    )

    objects = WorkshopScopedManager()

    class Meta:
        abstract = True

    def infer_workshop_id(self):
        return current_workshop_id()

    def save(self, *args, **kwargs):
        if self.workshop_id is None:
            self.workshop_id = self.infer_workshop_id()
        super().save(*args, **kwargs)


class AuditLog(models.Model):
    """Registro de operações importantes (LGPD: quem fez o quê e quando).

    Não guarda dados pessoais completos em `details`, apenas identificadores
    e metadados necessários para rastrear a operação.
    """

    created_at = models.DateTimeField("data", auto_now_add=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="usuário", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="audit_logs",
    )
    action = models.CharField("ação", max_length=80, db_index=True)
    object_type = models.CharField("tipo de objeto", max_length=80, blank=True)
    object_id = models.CharField("id do objeto", max_length=64, blank=True)
    attendance_id = models.BigIntegerField("atendimento", null=True, blank=True, db_index=True)
    details = models.JSONField("detalhes", default=dict, blank=True)
    ip_address = models.GenericIPAddressField("IP", null=True, blank=True)

    class Meta:
        verbose_name = "registro de auditoria"
        verbose_name_plural = "registros de auditoria"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.created_at:%d/%m/%Y %H:%M} {self.action}"
