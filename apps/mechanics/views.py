"""Cadastro da equipe sem login. Mecânicos e vendedores/atendentes compartilham estas telas.

A inclusão de mecânico durante o atendimento fica no formulário de abertura.
"""
from dataclasses import dataclass

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.core.audit import log_action

from .forms import MechanicForm
from .models import Mechanic


@dataclass(frozen=True)
class TeamPage:
    model: type
    form_class: type
    namespace: str
    audit_prefix: str
    singular: str
    plural: str
    note: str
    show_phone: bool = False


def _base_context(page):
    return {"page": page, "list_url": reverse(f"{page.namespace}:list")}


def team_list(request, page):
    rows = [{"member": member, "edit_url": reverse(f"{page.namespace}:edit", args=[member.pk])}
            for member in page.model.objects.all()]
    return render(request, "team/list.html", {
        **_base_context(page), "rows": rows, "create_url": reverse(f"{page.namespace}:create"),
    })


def team_create(request, page):
    form = page.form_class(request.POST or None, initial={"is_active": True},
                           instance=page.model(workshop=request.user.workshop))
    if request.method == "POST" and form.is_valid():
        member = form.save()
        log_action(f"{page.audit_prefix}.created", request=request, obj=member)
        messages.success(request, f"{page.singular.capitalize()} {member.name} cadastrado.")
        return redirect(f"{page.namespace}:list")
    return render(request, "team/form.html", {**_base_context(page), "form": form, "title": f"Novo {page.singular}"})


def team_edit(request, page, pk):
    member = get_object_or_404(page.model, pk=pk)
    title = f"Editar {member.name}"
    form = page.form_class(request.POST or None, instance=member)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_action(f"{page.audit_prefix}.updated", request=request, obj=member)
        messages.success(request, f"{page.singular.capitalize()} atualizado.")
        return redirect(f"{page.namespace}:list")
    return render(request, "team/form.html", {**_base_context(page), "form": form, "title": title})


PAGE = TeamPage(
    model=Mechanic, form_class=MechanicForm, namespace="mechanics", audit_prefix="mechanic", singular="mecânico",
    plural="Mecânicos", note="Mecânicos não têm login nem senha. Quem está desativado sai da lista do atendimento, "
                             "mas continua nos atendimentos antigos.",
    show_phone=True,
)


@login_required
def mechanic_list(request):
    return team_list(request, PAGE)


@login_required
def mechanic_create(request):
    return team_create(request, PAGE)


@login_required
def mechanic_edit(request, pk):
    return team_edit(request, PAGE, pk)
