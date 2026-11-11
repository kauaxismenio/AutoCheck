"""Veículo. Um cliente pode ter vários veículos; um veículo, vários atendimentos.

`customer` é o proprietário atual. Cada atendimento guarda o cliente da época,
então o histórico continua correto se o veículo mudar de dono.
"""
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.django_validators import validate_mileage, validate_plate
from apps.core.models import TimeStampedModel, WorkshopOwned
from apps.core.validators.plate import format_plate, normalize_plate
from apps.core.validators.text import to_upper


class Vehicle(WorkshopOwned, TimeStampedModel):
    customer = models.ForeignKey(
        "customers.Customer", verbose_name="proprietário atual",
        on_delete=models.PROTECT, related_name="vehicles",
    )
    plate = models.CharField("placa", max_length=8, validators=[validate_plate])
    brand = models.CharField("marca", max_length=60)
    model = models.CharField("modelo", max_length=80)
    year = models.PositiveSmallIntegerField(
        "ano", null=True, blank=True,
        validators=[MinValueValidator(1900), MaxValueValidator(2100)],
    )
    color = models.CharField("cor", max_length=40, blank=True)
    last_mileage = models.PositiveIntegerField(
        "última quilometragem", null=True, blank=True, validators=[validate_mileage],
    )
    # Preservado para outras partes do sistema; não aparece na tela de atendimento.
    chassis = models.CharField("chassi", max_length=17, blank=True)
    external_id = models.CharField("ID no sistema de gestão", max_length=64, blank=True, db_index=True)

    class Meta:
        verbose_name = "veículo"
        verbose_name_plural = "veículos"
        ordering = ["plate"]
        constraints = [models.UniqueConstraint(fields=["workshop", "plate"], name="uniq_vehicle_workshop_plate")]

    def infer_workshop_id(self):
        return self.customer.workshop_id

    def clean(self):
        super().clean()
        self.plate = normalize_plate(self.plate)
        from django.utils import timezone

        if self.year and self.year > timezone.localdate().year + 1:
            raise ValidationError({"year": "Ano do veículo inválido."})

    def save(self, *args, **kwargs):
        self.plate = normalize_plate(self.plate)
        self.chassis = to_upper(self.chassis)
        self.brand, self.model, self.color = to_upper(self.brand), to_upper(self.model), to_upper(self.color)
        super().save(*args, **kwargs)

    @property
    def plate_formatted(self):
        return format_plate(self.plate)

    def __str__(self):
        return f"{self.plate_formatted} — {self.brand} {self.model}".strip()
