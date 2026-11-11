"""Envio e exclusão de fotografias, sempre validados no servidor."""
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.attendances import workflow as wf
from apps.attendances.services import get_step_or_403
from apps.core.audit import log_action
from apps.core.images import process_upload

from . import categories as cat
from .models import Photo

PHASE_STEP = {
    cat.PHASE_CHECKIN: wf.CHECKIN,
    cat.PHASE_CHECKOUT: wf.CHECKOUT,
    cat.PHASE_COMPONENT: wf.CHECKLIST,
    cat.PHASE_TIRE: wf.CHECKLIST,
    cat.PHASE_PART_OLD: wf.SERVICOS,
    cat.PHASE_PART_NEW: wf.SERVICOS,
}


def _resolve_target(attendance, phase, target_id):
    """O vínculo precisa pertencer a este atendimento (impede usar IDs de outro)."""
    relations = {
        cat.PHASE_COMPONENT: ("checklist_item", attendance.checklist_items),
        cat.PHASE_TIRE: ("tire_inspection", attendance.tire_inspections),
        cat.PHASE_PART_OLD: ("replacement", attendance.replacements),
        cat.PHASE_PART_NEW: ("replacement", attendance.replacements),
    }
    if phase not in relations:
        return {}
    field, manager = relations[phase]
    if not str(target_id or "").isdigit():
        raise ValidationError("A foto precisa estar vinculada ao item correspondente.")
    target = manager.filter(pk=int(target_id)).first()
    if target is None:
        raise ValidationError("Item não encontrado neste atendimento.")
    if field == "replacement" and target.decision != "autorizado":
        raise ValidationError("Fotos da peça só são exigidas quando o cliente autoriza a substituição.")
    return {field: target}


def save_photo(attendance, *, phase, category, uploaded, user=None, target_id=None, request=None):
    step = PHASE_STEP.get(phase)
    if step is None:
        raise ValidationError("Fase de fotografia desconhecida.")
    get_step_or_403(attendance, step)
    if not cat.is_category_allowed(phase, category):
        raise ValidationError("Categoria não permitida para esta fase.")
    link = _resolve_target(attendance, phase, target_id)

    processed = process_upload(uploaded)
    photo = Photo(attendance=attendance, phase=phase, category=category, taken_by=user,
                  sha256=processed.sha256, size_bytes=processed.size_bytes, **link)
    photo.image.save(processed.content.name, processed.content, save=False)
    photo.save()
    log_action("photo.uploaded", request=request, user=user, obj=photo, attendance=attendance, phase=phase, category=category)
    return photo


def delete_photo(photo, *, user=None, request=None):
    attendance = photo.attendance
    get_step_or_403(attendance, PHASE_STEP[photo.phase])
    log_action("photo.deleted", request=request, user=user, obj=photo, attendance=attendance, phase=photo.phase)
    replacement = photo.replacement
    photo.delete()
    if replacement is not None:
        from apps.replacements.services import undo_replacement_if_incomplete

        undo_replacement_if_incomplete(replacement)


def photo_payload(photo):
    public_id = photo.attendance.public_id
    return {
        "id": photo.pk,
        "url": reverse("photos:file", args=[public_id, photo.pk]),
        "delete_url": reverse("photos:delete", args=[public_id, photo.pk]),
    }


def build_slot(attendance, *, label, phase, category=cat.GERAL, required=False, target=None, photos=()):
    return {
        "label": label, "phase": phase, "category": category, "required": required,
        "target": target.pk if target is not None else "",
        "upload_url": reverse("photos:upload", args=[attendance.public_id]),
        "photos": [photo_payload(photo) for photo in photos],
    }


def phase_slots(attendance, phase):
    """Espaços de foto de check-in ou check-out: obrigatórios e opcionais."""
    required = {cat.PHASE_CHECKIN: cat.CHECKIN_REQUIRED, cat.PHASE_CHECKOUT: cat.CHECKOUT_REQUIRED}[phase]
    optional = cat.CHECKIN_OPTIONAL if phase == cat.PHASE_CHECKIN else ()
    existing = {}
    for photo in attendance.photos.filter(phase=phase).select_related("attendance"):
        existing.setdefault(photo.category, []).append(photo)

    def slots(categories, is_required):
        return [
            build_slot(attendance, label=cat.CATEGORY_LABELS[c], phase=phase, category=c,
                       required=is_required, photos=existing.get(c, []))
            for c in categories
        ]

    return {"required": slots(required, True), "optional": slots(optional, False)}
