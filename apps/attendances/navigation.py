"""Endereço de cada etapa e dados do indicador de progresso."""
from django.urls import reverse

from . import workflow as wf

STEP_URL_NAMES = {
    wf.CADASTRO: "attendances:edit",
    wf.CHECKIN: "photos:checkin",
    wf.CHECKLIST: "checklist:step",
    wf.SERVICOS: "replacements:step",
    wf.CHECKOUT: "photos:checkout",
    wf.REVISAO: "signatures:step",
}


def step_url(attendance, step=None):
    """URL da etapa; sem etapa aberta, volta o resumo do atendimento."""
    step = step or attendance.current_step
    name = STEP_URL_NAMES.get(step)
    if name and attendance.is_editable:
        return reverse(name, args=[attendance.public_id])
    return reverse("attendances:summary", args=[attendance.public_id])


def steps_nav(attendance, current_view_step=None):
    items = []
    for number, (step, label, state) in enumerate(attendance.progress(), start=1):
        reachable = attendance.is_editable and state in ("done", "current")
        items.append({
            "number": number, "label": label, "state": state,
            "url": step_url(attendance, step) if reachable else "",
            "active": step == current_view_step,
        })
    return items
