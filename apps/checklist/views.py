"""Etapa de checklist e pneus.

A página envia um formulário único (funciona sozinho) e o JS grava cada alteração
assim que acontece, para não perder o preenchimento em conexões instáveis.
"""
from itertools import groupby

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.attendances import services as att_services
from apps.attendances import workflow as wf
from apps.attendances.navigation import step_url, steps_nav
from apps.attendances.views import get_attendance
from apps.photos import categories as cat
from apps.photos.services import build_slot
from apps.tires.services import save_tire

from . import services
from .models import Result


def _groups(attendance):
    items = attendance.checklist_items.select_related("attendance").prefetch_related("photos__attendance").order_by("order")
    groups = []
    for name, rows in groupby(items, key=lambda item: item.category_name):
        rows = list(rows)
        for item in rows:
            item.photo_slot = build_slot(attendance, label="Foto do componente (opcional)", phase=cat.PHASE_COMPONENT,
                                         target=item, photos=item.photos.all())
        pending = sum(1 for item in rows if not item.result)
        groups.append({"name": name, "items": rows, "pending": pending, "total": len(rows)})
    return groups


def _tires(attendance):
    tires = list(attendance.tire_inspections.prefetch_related("photos__attendance").order_by("id"))
    for tire in tires:
        tire.photo_slot = build_slot(attendance, label="Foto do pneu", phase=cat.PHASE_TIRE, target=tire,
                                     required=tire.needs_replacement, photos=tire.photos.all())
    return tires


def _error_messages(exc):
    return exc.messages


def _save_all(request, attendance):
    """Grava o formulário inteiro e devolve a lista de erros."""
    errors = []
    user = request.user
    for item in attendance.checklist_items.select_related("attendance"):
        result = request.POST.get(f"item-{item.pk}")
        notes = request.POST.get(f"notes-{item.pk}")
        try:
            services.save_item(item, result=result or None, notes=notes, user=user)
        except ValidationError as exc:
            errors.extend(_error_messages(exc))
    for tire in attendance.tire_inspections.select_related("attendance"):
        prefix = f"tire-{tire.pk}"
        try:
            save_tire(tire, condition=request.POST.get(f"{prefix}-condition") or None,
                      pressure=request.POST.get(f"{prefix}-psi"), twi=request.POST.get(f"{prefix}-twi"),
                      notes=request.POST.get(f"{prefix}-notes"), user=user)
        except ValidationError as exc:
            errors.extend(f"Pneu {tire.get_position_display()}: {message}" for message in _error_messages(exc))
    return errors


@login_required
def step(request, public_id):
    attendance = get_attendance(public_id)
    att_services.get_step_or_403(attendance, wf.CHECKLIST)
    services.ensure_initialized(attendance)
    errors = []
    if request.method == "POST":
        errors = _save_all(request, attendance)
        if not errors:
            try:
                att_services.complete_step(attendance, wf.CHECKLIST, user=request.user, request=request)
            except att_services.StepIncomplete as exc:
                errors = exc.errors
            else:
                return redirect(step_url(attendance))
    groups = _groups(attendance)
    tires = _tires(attendance)
    return render(request, "checklist/step.html", {
        "attendance": attendance, "steps": steps_nav(attendance, wf.CHECKLIST), "errors": errors,
        "groups": groups, "tires": tires,
        "total": sum(g["total"] for g in groups) + len(tires),
        "done": sum(g["total"] - g["pending"] for g in groups) + sum(1 for t in tires if t.condition),
        "OK": Result.OK, "SUBSTITUIR": Result.SUBSTITUIR,
        "catalog_empty": not groups,
    })


@login_required
@require_POST
def autosave(request, public_id):
    attendance = get_attendance(public_id)
    try:
        att_services.get_step_or_403(attendance, wf.CHECKLIST)
    except PermissionDenied:
        return JsonResponse({"error": "Esta etapa não está aberta."}, status=403)
    kind, raw_id = request.POST.get("kind"), request.POST.get("id", "")
    if not raw_id.isdigit():
        return JsonResponse({"error": "Item inválido."}, status=400)
    try:
        if kind == "item":
            item = attendance.checklist_items.select_related("attendance").filter(pk=int(raw_id)).first()
            if item is None:
                return JsonResponse({"error": "Item não encontrado."}, status=404)
            services.save_item(item, result=request.POST.get("result") or None, notes=request.POST.get("notes"),
                               user=request.user)
        elif kind == "tire":
            tire = attendance.tire_inspections.select_related("attendance").filter(pk=int(raw_id)).first()
            if tire is None:
                return JsonResponse({"error": "Pneu não encontrado."}, status=404)
            save_tire(tire, condition=request.POST.get("condition") or None, pressure=request.POST.get("psi"),
                      twi=request.POST.get("twi"), notes=request.POST.get("notes"), user=request.user)
        else:
            return JsonResponse({"error": "Tipo inválido."}, status=400)
    except ValidationError as exc:
        return JsonResponse({"error": " ".join(exc.messages)}, status=400)
    return JsonResponse({"saved": True})
