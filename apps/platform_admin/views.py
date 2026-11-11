"""Área exclusiva do proprietário da plataforma: mostra só totais, nunca dados dos clientes das oficinas."""
from datetime import timedelta

from django.contrib import messages
from django.db.models import Count, Max
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from apps.core.audit import log_action
from apps.core.permissions import platform_owner_required
from apps.workshop.models import WorkshopSettings

from . import services
from .forms import WorkshopCreateForm, WorkshopEditForm

RECENT_DAYS = 30


def _credentials_page(request, workshop, email, password):
    """A senha aparece só nesta resposta: não é guardada em texto nem registrada na auditoria."""
    return render(request, "platform_admin/credentials.html", {"item": workshop, "email": email, "password": password})


@platform_owner_required
def workshop_list(request):
    workshops = list(
        WorkshopSettings.objects.annotate(attendance_count=Count("attendances", distinct=True),
                                          last_login=Max("accounts__last_login"))
        .prefetch_related("accounts").order_by("name")
    )
    limit = timezone.now() - timedelta(days=RECENT_DAYS)
    for workshop in workshops:
        workshop.login = services.login_account(workshop)
    return render(request, "platform_admin/list.html", {
        "workshops": workshops, "recent_days": RECENT_DAYS,
        "stats": {
            "total": len(workshops),
            "active": sum(w.is_active for w in workshops),
            "recent": sum(bool(w.last_login and w.last_login >= limit) for w in workshops),
        },
    })


@platform_owner_required
@never_cache
def workshop_create(request):
    form = WorkshopCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        workshop, generated = services.create_workshop(data["name"], data["login_email"], data["password"])
        log_action("platform.workshop_created", request=request, obj=workshop)
        if generated:
            return _credentials_page(request, workshop, data["login_email"], generated)
        messages.success(request, f"Oficina {workshop.name} cadastrada.")
        return redirect("platform_admin:list")
    return render(request, "platform_admin/form.html", {"form": form, "title": "Nova oficina"})


@platform_owner_required
@never_cache
def workshop_edit(request, pk):
    workshop = get_object_or_404(WorkshopSettings, pk=pk)
    form = WorkshopEditForm(request.POST or None, instance=workshop)
    if request.method == "POST" and form.is_valid():
        form.save()
        generated = services.update_login(workshop, form.cleaned_data["login_email"])
        log_action("platform.workshop_updated", request=request, obj=workshop, active=workshop.is_active)
        if generated:
            return _credentials_page(request, workshop, form.cleaned_data["login_email"], generated)
        messages.success(request, "Oficina atualizada.")
        return redirect("platform_admin:list")
    return render(request, "platform_admin/form.html", {
        "form": form, "title": f"Editar {workshop.name}", "item": workshop, "account": form.account,
    })


@platform_owner_required
@require_POST
@never_cache
def workshop_reset_password(request, pk):
    workshop = get_object_or_404(WorkshopSettings, pk=pk)
    account = services.login_account(workshop)
    if account is None:
        messages.error(request, "Informe o e-mail de acesso para criar a conta desta oficina.")
        return redirect("platform_admin:edit", workshop.pk)
    password = services.reset_password(account)
    log_action("platform.password_reset", request=request, obj=workshop)
    return _credentials_page(request, workshop, account.email, password)
