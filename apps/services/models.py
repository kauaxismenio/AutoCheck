"""Serviços efetivamente realizados no atendimento.

Uma substituição autorizada e concluída gera automaticamente um serviço
vinculado (sem redigitar o nome). Serviços sem troca de peça (ex.: alinhamento)
podem ser registrados manualmente.
"""
from django.conf import settings
from django.db import models

from apps.core.tenancy import AttendanceScopedManager
from apps.core.models import TimeStampedModel


class ServiceRecord(TimeStampedModel):
    attendance = models.ForeignKey("attendances.Attendance", on_delete=models.CASCADE, related_name="services")
    replacement = models.OneToOneField("replacements.PartReplacement", null=True, blank=True, on_delete=models.CASCADE, related_name="service")
    description = models.CharField("serviço", max_length=200)
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    performed_at = models.DateTimeField("realizado em", null=True, blank=True)

    objects = AttendanceScopedManager()

    class Meta:
        verbose_name = "serviço realizado"
        verbose_name_plural = "serviços realizados"
        ordering = ["created_at"]

    def __str__(self):
        return self.description
