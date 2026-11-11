"""Gravação da inspeção de pneus. Valores parciais são aceitos durante o preenchimento;
o validador da etapa exige condição e PSI antes de avançar."""
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.checklist.models import Result
from apps.replacements.services import ensure_for_tire, remove_recommendation

NUMBER_ERRORS = {"pressure_psi": "Calibragem inválida.", "twi_mm": "TWI inválido."}


def _parse(value, field):
    text = (value or "").strip().replace(",", ".")
    if not text:
        return None
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise ValidationError({field: NUMBER_ERRORS[field]}) from exc
    if not number.is_finite():
        raise ValidationError({field: NUMBER_ERRORS[field]})
    return number


@transaction.atomic
def save_tire(tire, *, condition=None, pressure=None, twi=None, notes=None, user=None):
    if condition is not None and condition not in Result.values:
        raise ValidationError({"condition": "Condição inválida: use OK ou SUBSTITUIR."})
    if pressure is not None:
        tire.pressure_psi = _parse(pressure, "pressure_psi")
    if twi is not None:
        tire.twi_mm = _parse(twi, "twi_mm")
    if notes is not None:
        tire.notes = notes.strip()
    if condition is not None and condition != tire.condition:
        if condition == Result.SUBSTITUIR:
            ensure_for_tire(tire)
        else:
            remove_recommendation(getattr(tire, "replacement", None))
        tire.condition = condition
        tire.evaluated_by = user
        tire.evaluated_at = timezone.now()
    tire.clean_fields(exclude=["attendance", "evaluated_by", "condition"])
    tire.save()
    return tire
