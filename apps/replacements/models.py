"""Recomendação de substituição e decisão (autorização) do cliente.

Criada automaticamente quando um item do checklist ou um pneu é marcado como
SUBSTITUIR — o mecânico não redigita o nome do componente. Origem: exatamente
um entre `checklist_item` e `tire_inspection`.
"""
from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.tenancy import AttendanceScopedManager
from apps.core.models import TimeStampedModel


class Decision(models.TextChoices):
    AGUARDANDO = "aguardando", "Aguardando decisão"
    AUTORIZADO = "autorizado", "Autorizado"
    NAO_AUTORIZADO = "nao_autorizado", "Não autorizado"


class PartReplacement(TimeStampedModel):
    attendance = models.ForeignKey("attendances.Attendance", on_delete=models.CASCADE, related_name="replacements")
    checklist_item = models.OneToOneField("checklist.ChecklistItem", null=True, blank=True, on_delete=models.CASCADE, related_name="replacement")
    tire_inspection = models.OneToOneField("tires.TireInspection", null=True, blank=True, on_delete=models.CASCADE, related_name="replacement")

    component_name = models.CharField("componente recomendado", max_length=150)
    part_description = models.CharField("identificação da peça", max_length=200, blank=True,
                                        help_text="Marca, código ou especificação da peça (opcional).")

    decision = models.CharField("decisão do cliente", max_length=20, choices=Decision.choices, default=Decision.AGUARDANDO, db_index=True)
    decided_at = models.DateTimeField("decisão registrada em", null=True, blank=True)
    decision_registered_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    replaced = models.BooleanField("substituição realizada", default=False)
    replaced_at = models.DateTimeField("substituída em", null=True, blank=True)
    replaced_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    objects = AttendanceScopedManager()

    class Meta:
        verbose_name = "substituição de peça"
        verbose_name_plural = "substituições de peças"
        ordering = ["created_at"]
        constraints = [
            models.CheckConstraint(
                condition=(Q(checklist_item__isnull=False, tire_inspection__isnull=True)
                           | Q(checklist_item__isnull=True, tire_inspection__isnull=False)),
                name="replacement_single_source",
            ),
            models.CheckConstraint(
                condition=Q(replaced=False) | Q(decision="autorizado"),
                name="replacement_only_if_authorized",
            ),
        ]

    @property
    def is_pending(self):
        return self.decision == Decision.AGUARDANDO

    def __str__(self):
        return f"{self.component_name} — {self.get_decision_display()}"
