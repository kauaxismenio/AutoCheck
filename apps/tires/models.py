"""Inspeção individual dos cinco pneus.

Regras (validadas no backend):
- Condição (OK/SUBSTITUIR) e calibragem em PSI são obrigatórias.
- TWI é opcional.
- Foto obrigatória somente quando o pneu precisa ser substituído.
Decisão: "ruim" é tratado como SUBSTITUIR, mantendo o padrão OK/SUBSTITUIR
de todo o checklist.
"""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.tenancy import AttendanceScopedManager
from apps.checklist.models import Result
from apps.core.models import TimeStampedModel


class TirePosition(models.TextChoices):
    DIANTEIRO_DIREITO = "dd", "Dianteiro direito"
    DIANTEIRO_ESQUERDO = "de", "Dianteiro esquerdo"
    TRASEIRO_DIREITO = "td", "Traseiro direito"
    TRASEIRO_ESQUERDO = "te", "Traseiro esquerdo"
    ESTEPE = "estepe", "Estepe"


class TireInspection(TimeStampedModel):
    attendance = models.ForeignKey("attendances.Attendance", on_delete=models.CASCADE, related_name="tire_inspections")
    position = models.CharField("posição", max_length=6, choices=TirePosition.choices)
    condition = models.CharField("condição", max_length=12, choices=Result.choices, blank=True)
    pressure_psi = models.DecimalField(
        "calibragem (PSI)", max_digits=4, decimal_places=1, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("150"))],
    )
    twi_mm = models.DecimalField(
        "TWI (mm)", max_digits=3, decimal_places=1, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("20"))],
    )
    notes = models.TextField("observações", blank=True)
    evaluated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    evaluated_at = models.DateTimeField("avaliado em", null=True, blank=True)

    objects = AttendanceScopedManager()

    class Meta:
        verbose_name = "inspeção de pneu"
        verbose_name_plural = "inspeções de pneus"
        constraints = [
            models.UniqueConstraint(fields=["attendance", "position"], name="uniq_tire_position_per_attendance"),
        ]

    def clean(self):
        super().clean()
        if self.condition and self.pressure_psi is None:
            raise ValidationError({"pressure_psi": "Informe a calibragem em PSI."})

    @property
    def needs_replacement(self):
        return self.condition == Result.SUBSTITUIR

    def __str__(self):
        return f"{self.get_position_display()}: {self.get_condition_display() or 'pendente'}"
