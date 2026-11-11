"""Assinatura digital do cliente ou registro de recusa em assinar."""
from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.tenancy import AttendanceScopedManager
from apps.core.storage import UUIDUploadTo

from .snapshot import build_snapshot, snapshot_hash, with_uppercase_identifiers

REFUSAL_TEXT = (
    "O cliente foi informado sobre as condições identificadas no veículo e os serviços "
    "recomendados, bem como sobre as autorizações e recusas registradas neste relatório. "
    "O cliente optou por não registrar sua assinatura digital."
)


class AttendanceSignature(models.Model):
    attendance = models.OneToOneField("attendances.Attendance", on_delete=models.CASCADE, related_name="signature")
    image = models.ImageField("assinatura", upload_to=UUIDUploadTo("attendances/signatures"), blank=True)
    refused = models.BooleanField("cliente não aceitou assinar", default=False)

    snapshot = models.JSONField("retrato do atendimento assinado", default=dict)
    snapshot_sha256 = models.CharField("hash da versão assinada", max_length=64)

    registered_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField("registrada em", auto_now_add=True)

    objects = AttendanceScopedManager()

    class Meta:
        verbose_name = "assinatura"
        verbose_name_plural = "assinaturas"
        constraints = [
            models.CheckConstraint(
                condition=(Q(refused=True, image="") | (Q(refused=False) & ~Q(image=""))),
                name="signature_image_xor_refusal",
            ),
        ]

    def bind_to_current_version(self):
        self.snapshot = build_snapshot(self.attendance)
        self.snapshot_sha256 = snapshot_hash(self.snapshot)

    def matches_current_version(self):
        current = snapshot_hash(build_snapshot(self.attendance))
        return current in (self.snapshot_sha256, snapshot_hash(with_uppercase_identifiers(self.snapshot)))

    def __str__(self):
        return f"{self.attendance} — {'recusou assinar' if self.refused else 'assinado'}"
