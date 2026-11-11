"""Registro de chamadas a serviços externos (para diagnóstico e auditoria).

LGPD: o documento consultado não é gravado em texto; guarda-se só um hash.
"""
from django.conf import settings
from django.db import models


class ExternalCallLog(models.Model):
    provider = models.CharField("serviço", max_length=40, db_index=True)
    operation = models.CharField("operação", max_length=40)
    query_hash = models.CharField("hash da consulta", max_length=64, blank=True)
    success = models.BooleanField("sucesso", default=False)
    outcome = models.CharField("resultado", max_length=40, blank=True)
    http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(default=0)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "chamada externa"
        verbose_name_plural = "chamadas externas"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.provider}.{self.operation} — {self.outcome}"
