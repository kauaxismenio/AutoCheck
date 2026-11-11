from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.core.audit import log_action
from apps.core.validators.plate import normalize_plate

from .forms import VehicleForm
from .models import Vehicle


def _search(queryset, term):
    term = (term or "").strip()
    if not term:
        return queryset
    condition = Q(brand__icontains=term.upper()) | Q(model__icontains=term.upper()) | Q(customer__full_name__icontains=term.upper()) \
        | Q(customer__legal_name__icontains=term.upper()) | Q(customer__trade_name__icontains=term.upper())
    plate = normalize_plate(term)
    if plate:
        condition |= Q(plate__icontains=plate)
    return queryset.filter(condition)


@login_required
def vehicle_list(request):
    term = request.GET.get("q", "")
    queryset = _search(Vehicle.objects.select_related("customer"), term)
    page = Paginator(queryset, 25).get_page(request.GET.get("pagina"))
    return render(request, "vehicles/list.html", {"page": page, "q": term})


@login_required
def vehicle_detail(request, pk):
    from apps.attendances.history import vehicle_history

    vehicle = get_object_or_404(Vehicle.objects.select_related("customer"), pk=pk)
    return render(request, "vehicles/detail.html", {"vehicle": vehicle, **vehicle_history(vehicle)})


def _save_form(request, form, action, title, cancel_url):
    if request.method == "POST" and form.is_valid():
        vehicle = form.save()
        log_action(action, request=request, obj=vehicle)
        messages.success(request, "Veículo salvo.")
        return redirect("vehicles:detail", vehicle.pk)
    return render(request, "vehicles/form.html", {"form": form, "title": title, "cancel_url": cancel_url})


@login_required
def vehicle_create(request):
    initial = {"customer": request.GET.get("cliente")} if request.GET.get("cliente", "").isdigit() else {}
    form = VehicleForm(request.POST or None, initial=initial)
    return _save_form(request, form, "vehicle.created", "Novo veículo", reverse("vehicles:list"))


@login_required
def vehicle_edit(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk)
    form = VehicleForm(request.POST or None, instance=vehicle)
    return _save_form(request, form, "vehicle.updated", f"Editar {vehicle.plate_formatted}",
                      reverse("vehicles:detail", args=[vehicle.pk]))


@login_required
@require_POST
def vehicle_delete(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk)
    try:
        vehicle.delete()
    except ProtectedError:
        messages.error(request, "Este veículo tem atendimentos vinculados e não pode ser excluído.")
        return redirect("vehicles:detail", pk)
    log_action("vehicle.deleted", request=request, object_id=pk)
    messages.success(request, "Veículo excluído.")
    return redirect("vehicles:list")
