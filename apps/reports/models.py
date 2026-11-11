"""Relatórios PDF gerados. Cada regeração cria uma nova versão (histórico)."""
from django.conf import settings
from django.db import models

from apps.core.tenancy import AttendanceScopedManager
from apps.core.storage import UUIDUploadTo


class Report(models.Model):
    attendance = models.ForeignKey("attendances.Attendance", on_delete=models.CASCADE, related_name="reports")
    version = models.PositiveIntegerField("versão")
    file = models.FileField("arquivo PDF", upload_to=UUIDUploadTo("attendances/reports"))
    sha256 = models.CharField(max_length=64)
    size_bytes = models.PositiveIntegerField(default=0)
    signature_sha256 = models.CharField("hash da versão assinada", max_length=64, blank=True)
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    generated_at = models.DateTimeField("gerado em", auto_now_add=True)

    objects = AttendanceScopedManager()

    class Meta:
        verbose_name = "relatório"
        verbose_name_plural = "relatórios"
        ordering = ["-generated_at"]
        get_latest_by = "version"
        constraints = [
            models.UniqueConstraint(fields=["attendance", "version"], name="uniq_report_version"),
        ]

    @property
    def download_name(self):
        return f"AutoCheck_{self.attendance.code}_v{self.version}.pdf"

    def __str__(self):
        return self.download_name
