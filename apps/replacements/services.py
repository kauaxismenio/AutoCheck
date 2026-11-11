"""Recomendações de substituição e decisões do cliente.

A recomendação nasce sozinha quando um item ou pneu é marcado como SUBSTITUIR:
o mecânico não redigita o nome do componente.
"""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.audit import log_action
from apps.photos import categories as cat

from .models import Decision, PartReplacement


def ensure_for_item(item):
    replacement, _ = PartReplacement.objects.get_or_create(
        checklist_item=item, defaults={"attendance": item.attendance, "component_name": item.component_name},
    )
    return replacement


def ensure_for_tire(tire):
    replacement, _ = PartReplacement.objects.get_or_create(
        tire_inspection=tire,
        defaults={"attendance": tire.attendance, "component_name": f"Pneu {tire.get_position_display().lower()}"},
    )
    return replacement


def remove_recommendation(replacement):
    """Item voltou a OK. Decisão já registrada não some sem o usuário refazê-la."""
    if replacement is None:
        return
    if replacement.decision != Decision.AGUARDANDO:
        raise ValidationError(
            f"{replacement.component_name}: já existe decisão do cliente. Na etapa de serviços, "
            "use \"Alterar decisão\" antes de mudar esta avaliação."
        )
    replacement.delete()


def _clear_execution(replacement):
    from apps.services.models import ServiceRecord

    ServiceRecord.objects.filter(replacement=replacement).delete()
    replacement.replaced = False
    replacement.replaced_at = None
    replacement.replaced_by = None


@transaction.atomic
def register_decision(replacement, decision, *, user=None, request=None):
    if decision not in Decision.values:
        raise ValidationError("Decisão inválida.")
    if decision != Decision.AUTORIZADO:
        _clear_execution(replacement)
        # Recusa não exige fotos: as de uma autorização anterior deixam de valer.
        for photo in replacement.photos.all():
            photo.delete()
    replacement.decision = decision
    replacement.decided_at = None if decision == Decision.AGUARDANDO else timezone.now()
    replacement.decision_registered_by = None if decision == Decision.AGUARDANDO else user
    replacement.save()
    log_action("replacement.decision", request=request, user=user, obj=replacement,
               attendance=replacement.attendance_id, decision=decision)
    return replacement


@transaction.atomic
def confirm_replacement(replacement, *, part_description="", user=None, request=None):
    from apps.services.models import ServiceRecord

    if replacement.decision != Decision.AUTORIZADO:
        raise ValidationError("A substituição só pode ser registrada após a autorização do cliente.")
    phases = set(replacement.photos.values_list("phase", flat=True))
    missing = []
    if cat.PHASE_PART_OLD not in phases:
        missing.append("Envie a foto da peça antiga.")
    if cat.PHASE_PART_NEW not in phases:
        missing.append("Envie a foto da peça nova.")
    if missing:
        raise ValidationError(missing)

    now = timezone.now()
    replacement.part_description = (part_description or "").strip()[:200]
    replacement.replaced, replacement.replaced_at, replacement.replaced_by = True, now, user
    replacement.save()
    ServiceRecord.objects.update_or_create(
        replacement=replacement,
        defaults={"attendance": replacement.attendance, "description": f"Substituição: {replacement.component_name}",
                  "performed_by": user, "performed_at": now},
    )
    log_action("replacement.done", request=request, user=user, obj=replacement, attendance=replacement.attendance_id)
    return replacement


def undo_replacement_if_incomplete(replacement):
    """Foto de peça excluída: a substituição deixa de contar como comprovada."""
    if not replacement.replaced:
        return
    phases = set(replacement.photos.values_list("phase", flat=True))
    if {cat.PHASE_PART_OLD, cat.PHASE_PART_NEW} <= phases:
        return
    with transaction.atomic():
        _clear_execution(replacement)
        replacement.save()


def add_manual_service(attendance, description, *, user=None, request=None):
    from apps.services.models import ServiceRecord

    description = (description or "").strip()
    if not description:
        raise ValidationError("Descreva o serviço realizado.")
    service = ServiceRecord.objects.create(attendance=attendance, description=description[:200],
                                           performed_by=user, performed_at=timezone.now())
    log_action("service.added", request=request, user=user, obj=service, attendance=attendance)
    return service
