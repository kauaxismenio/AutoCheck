"""Inicialização e preenchimento do checklist."""
from django.db import transaction
from django.utils import timezone

from apps.replacements.services import ensure_for_item, remove_recommendation

from .models import ChecklistComponent, ChecklistItem, Result


def ensure_initialized(attendance):
    """Cria os itens do catálogo e as 5 posições de pneu (idempotente)."""
    from apps.tires.models import TireInspection, TirePosition

    existing = set(attendance.checklist_items.values_list("component_id", flat=True))
    components = ChecklistComponent.objects.filter(active=True, category__active=True).select_related("category")
    new_items = [
        ChecklistItem(attendance=attendance, component=component, category_name=component.category.name,
                      component_name=component.name, order=(component.category.order * 1000) + component.order)
        for component in components if component.pk not in existing
    ]
    ChecklistItem.objects.bulk_create(new_items)
    for position, _ in TirePosition.choices:
        TireInspection.objects.get_or_create(attendance=attendance, position=position)


@transaction.atomic
def save_item(item, *, result=None, notes=None, user=None):
    """Grava avaliação e/ou observação. Levanta ValidationError se a mudança não é possível."""
    from django.core.exceptions import ValidationError

    if result is not None and result not in Result.values:
        raise ValidationError("Avaliação inválida: use OK ou SUBSTITUIR.")
    if result is not None and result != item.result:
        if result == Result.SUBSTITUIR:
            ensure_for_item(item)
        else:
            remove_recommendation(getattr(item, "replacement", None))
        item.result = result
        item.evaluated_by = user
        item.evaluated_at = timezone.now()
    if notes is not None:
        item.notes = notes.strip()
    item.save()
    return item
