"""Etapa de execução: decisão do cliente, troca de peças e serviços realizados."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.attendances import services as att_services
from apps.attendances import workflow as wf
from apps.attendances.navigation import step_url, steps_nav
from apps.attendances.views import get_attendance
from apps.core.audit import log_action
from apps.photos import categories as cat
from apps.photos.services import build_slot
from apps.services.models import ServiceRecord

from . import services
from .models import Decision, PartReplacement


def _open_step(public_id):
    attendance = get_attendance(public_id)
    att_services.get_step_or_403(attendance, wf.SERVICOS)
    return attendance


def _cards(attendance):
    replacements = list(attendance.replacements.prefetch_related("photos__attendance"))
    for replacement in replacements:
        photos = list(replacement.photos.all())
        replacement.old_slot = build_slot(
            attendance, label="Peça antiga", phase=cat.PHASE_PART_OLD, required=True, target=replacement,
            photos=[p for p in photos if p.phase == cat.PHASE_PART_OLD],
        )
        replacement.new_slot = build_slot(
            attendance, label="Peça nova", phase=cat.PHASE_PART_NEW, required=True, target=replacement,
            photos=[p for p in photos if p.phase == cat.PHASE_PART_NEW],
        )
    return replacements


def _back_to(attendance, replacement=None):
    url = reverse("replacements:step", args=[attendance.public_id])
    return redirect(f"{url}#peca-{replacement.pk}" if replacement else url)


@login_required
def step(request, public_id):
    attendance = _open_step(public_id)
    errors = []
    if request.method == "POST":
        try:
            att_services.complete_step(attendance, wf.SERVICOS, user=request.user, request=request)
        except att_services.StepIncomplete as exc:
            errors = exc.errors
        else:
            return redirect(step_url(attendance))
    return render(request, "replacements/step.html", {
        "attendance": attendance, "steps": steps_nav(attendance, wf.SERVICOS), "errors": errors,
        "replacements": _cards(attendance),
        "services": attendance.services.select_related("performed_by", "replacement"),
        "AGUARDANDO": Decision.AGUARDANDO, "AUTORIZADO": Decision.AUTORIZADO, "NAO_AUTORIZADO": Decision.NAO_AUTORIZADO,
    })


@login_required
@require_POST
def decision(request, public_id, pk):
    attendance = _open_step(public_id)
    replacement = get_object_or_404(PartReplacement, pk=pk, attendance=attendance)
    try:
        services.register_decision(replacement, request.POST.get("decision", ""), user=request.user, request=request)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return _back_to(attendance)  # topo da página, onde a mensagem aparece
    return _back_to(attendance, replacement)


@login_required
@require_POST
def confirm(request, public_id, pk):
    attendance = _open_step(public_id)
    replacement = get_object_or_404(PartReplacement, pk=pk, attendance=attendance)
    try:
        services.confirm_replacement(replacement, part_description=request.POST.get("part_description", ""),
                                     user=request.user, request=request)
    except ValidationError as exc:
        messages.error(request, f"{replacement.component_name}: " + " ".join(exc.messages))
        return _back_to(attendance)  # topo da página, onde a mensagem aparece
    return _back_to(attendance, replacement)  # o selo "Substituída" no cartão confirma


@login_required
@require_POST
def add_service(request, public_id):
    attendance = _open_step(public_id)
    try:
        services.add_manual_service(attendance, request.POST.get("description"), user=request.user, request=request)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    return _back_to(attendance)


@login_required
@require_POST
def delete_service(request, public_id, pk):
    attendance = _open_step(public_id)
    # Serviço ligado a uma peça é desfeito pela decisão ou pelas fotos, não por aqui.
    service = get_object_or_404(ServiceRecord, pk=pk, attendance=attendance, replacement__isnull=True)
    log_action("service.deleted", request=request, obj=service, attendance=attendance)
    service.delete()
    return _back_to(attendance)
