from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.core.audit import log_action
from apps.core.validators.documents import normalize_cnpj
from apps.core.validators.plate import normalize_plate

from .forms import CustomerForm
from .models import Customer


def search_customers(queryset, term):
    term = (term or "").strip()
    if not term:
        return queryset
    condition = Q(full_name__icontains=term.upper()) | Q(legal_name__icontains=term.upper()) | Q(trade_name__icontains=term.upper())
    digits = "".join(c for c in term if c.isdigit())
    if digits:
        condition |= Q(cpf__contains=digits) | Q(phone__contains=digits)
    compact = normalize_cnpj(term)
    if compact:
        condition |= Q(cnpj__icontains=compact)
    plate = normalize_plate(term)
    if plate:
        condition |= Q(vehicles__plate__icontains=plate)
    return queryset.filter(condition).distinct()


@login_required
def customer_list(request):
    term = request.GET.get("q", "")
    page = Paginator(search_customers(Customer.objects.all(), term), 25).get_page(request.GET.get("pagina"))
    return render(request, "customers/list.html", {"page": page, "q": term})


@login_required
def customer_detail(request, pk):
    from apps.attendances.history import customer_history

    customer = get_object_or_404(Customer, pk=pk)
    return render(request, "customers/detail.html", {"customer": customer, **customer_history(customer)})


def _save_form(request, form, action, title, cancel_url):
    if request.method == "POST" and form.is_valid():
        customer = form.save()
        log_action(action, request=request, obj=customer)
        messages.success(request, "Cliente salvo.")
        return redirect("customers:detail", customer.pk)
    return render(request, "customers/form.html", {"form": form, "title": title, "cancel_url": cancel_url})


@login_required
def customer_create(request):
    form = CustomerForm(request.POST or None)
    return _save_form(request, form, "customer.created", "Novo cliente", reverse("customers:list"))


@login_required
def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    form = CustomerForm(request.POST or None, instance=customer)
    return _save_form(request, form, "customer.updated", f"Editar {customer}",
                      reverse("customers:detail", args=[customer.pk]))


@login_required
@require_POST
def customer_delete(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    try:
        customer.delete()
    except ProtectedError:
        messages.error(request, "Este cliente tem veículos ou atendimentos vinculados e não pode ser excluído.")
        return redirect("customers:detail", pk)
    log_action("customer.deleted", request=request, object_id=pk)
    messages.success(request, "Cliente excluído.")
    return redirect("customers:list")
