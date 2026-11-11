"""Fotografias do atendimento, armazenadas no ambiente privado da aplicação.

Uma foto pertence sempre a um atendimento e, conforme a fase, pode estar
vinculada a um item do checklist, a um pneu ou a uma substituição de peça.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.tenancy import AttendanceScopedManager
from apps.core.storage import UUIDUploadTo

from . import categories as cat


class Photo(models.Model):
    attendance = models.ForeignKey("attendances.Attendance", on_delete=models.CASCADE, related_name="photos")
    phase = models.CharField("fase", max_length=20, choices=cat.PHASE_CHOICES)
    category = models.CharField("categoria", max_length=30, choices=cat.CATEGORY_CHOICES, default=cat.GERAL)
    image = models.ImageField("imagem", upload_to=UUIDUploadTo("attendances/photos"),
                              width_field="width", height_field="height")
    width = models.PositiveIntegerField(null=True, blank=True, editable=False)
    height = models.PositiveIntegerField(null=True, blank=True, editable=False)
    size_bytes = models.PositiveIntegerField("tamanho (bytes)", default=0, editable=False)
    sha256 = models.CharField(max_length=64, blank=True, editable=False)

    checklist_item = models.ForeignKey("checklist.ChecklistItem", null=True, blank=True, on_delete=models.CASCADE, related_name="photos")
    tire_inspection = models.ForeignKey("tires.TireInspection", null=True, blank=True, on_delete=models.CASCADE, related_name="photos")
    replacement = models.ForeignKey("replacements.PartReplacement", null=True, blank=True, on_delete=models.CASCADE, related_name="photos")

    taken_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField("enviada em", auto_now_add=True)

    objects = AttendanceScopedManager()

    class Meta:
        verbose_name = "fotografia"
        verbose_name_plural = "fotografias"
        ordering = ["created_at"]
        indexes = [models.Index(fields=["attendance", "phase", "category"])]

    def clean(self):
        super().clean()
        if not cat.is_category_allowed(self.phase, self.category):
            raise ValidationError({"category": "Categoria não permitida para esta fase."})
        links = {
            cat.PHASE_COMPONENT: self.checklist_item_id,
            cat.PHASE_TIRE: self.tire_inspection_id,
            cat.PHASE_PART_OLD: self.replacement_id,
            cat.PHASE_PART_NEW: self.replacement_id,
        }
        if self.phase in links and not links[self.phase]:
            raise ValidationError("A foto precisa estar vinculada ao item correspondente.")

    def __str__(self):
        return f"{self.get_phase_display()} — {self.get_category_display()}"
