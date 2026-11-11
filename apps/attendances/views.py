"""Abertura, listagem e consulta de atendimentos."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import urlencode
from django.views.decorators.http import require_POST

from apps.core.validators.documents import normalize_cnpj
from apps.core.validators.plate import normalize_plate

from . import services
from . import workflow as wf
from .forms import IntakeForm
from .intake import save_intake
from .models import Attendance
from .navigation import step_url, steps_nav


def _with_relations():
    return Attendance.objects.select_related("workshop", "customer", "vehicle", "attendant", "mechanic")


def get_attendance(public_id):
    return get_object_or_404(_with_relations(), public_id=public_id)


def search_attendances(queryset, term):
    term = (term or "").strip()
    if not term:
        return queryset
    condition = (Q(code__icontains=term) | Q(customer__full_name__icontains=term.upper())
                 | Q(legal_name__icontains=term.upper()) | Q(trade_name__icontains=term.upper())
                 | Q(vehicle__model__icontains=term.upper()) | Q(vehicle__brand__icontains=term.upper()))
    digits = "".join(c for c in term if c.isdigit())
    if digits:
        condition |= Q(customer__cpf__contains=digits) | Q(customer__phone__contains=digits)
    compact = normalize_cnpj(term)
    if compact:
        condition |= Q(cnpj__icontains=compact)  # o CNPJ informado no atendimento, não o do cadastro
    plate = normalize_plate(term)
    if plate:
        condition |= Q(vehicle__plate__icontains=plate)
    return queryset.filter(condition)


@login_required
def attendance_list(request):
    term = request.GET.get("q", "")
    status = request.GET.get("situacao", "")
    queryset = search_attendances(_with_relations(), term)
    if status in dict(wf.STATUS_CHOICES):
        queryset = queryset.filter(status=status)
    page = Paginator(queryset, 25).get_page(request.GET.get("pagina"))
    return render(request, "attendances/list.html", {
        "page": page, "q": term, "status": status, "status_choices": wf.STATUS_CHOICES,
        "query_string": urlencode({"q": term, "situacao": status}),
    })


@login_required
def history(request):
    term = request.GET.get("q", "")
    queryset = search_attendances(_with_relations().filter(status=wf.STATUS_CONCLUIDO), term).order_by("-completed_at")
    page = Paginator(queryset, 25).get_page(request.GET.get("pagina"))
    return render(request, "attendances/history.html", {
        "page": page, "q": term, "query_string": urlencode({"q": term}),
    })


@login_required
def detail(request, public_id):
    attendance = get_attendance(public_id)
    return redirect(step_url(attendance))


@login_required
def summary(request, public_id):
    from apps.signatures.models import REFUSAL_TEXT

    from .summary import build_summary

    attendance = get_attendance(public_id)
    context = {"attendance": attendance, "summary": build_summary(attendance), "refusal_text": REFUSAL_TEXT}
    if not attendance.is_editable:
        from apps.mailing.services import dispatch_overview

        context.update(dispatch_overview(attendance, request.user))
    return render(request, "attendances/summary.html", context)


def _save_intake_form(request, form, attendance):
    if request.method != "POST" or not form.is_valid():
        return None
    try:
        saved = save_intake(form.cleaned_data, user=request.user, request=request, attendance=attendance)
    except services.StepIncomplete as exc:
        for error in exc.errors:
            form.add_error(None, error)
        return None
    except IntegrityError:
        form.add_error(None, "Outro usuário acabou de cadastrar este documento ou placa. Envie de novo para usar o registro existente.")
        return None
    return redirect(step_url(saved))


@login_required
def new(request):
    form = IntakeForm(request.POST or None)
    response = _save_intake_form(request, form, None)
    return response or render(request, "attendances/intake.html", {"form": form, "steps": None})


@login_required
def edit(request, public_id):
    attendance = get_attendance(public_id)
    services.get_step_or_403(attendance, wf.CADASTRO)
    form = IntakeForm(request.POST or None, attendance=attendance)
    response = _save_intake_form(request, form, attendance)
    return response or render(request, "attendances/intake.html", {
        "form": form, "attendance": attendance, "steps": steps_nav(attendance, wf.CADASTRO),
    })


@login_required
@require_POST
def cancel(request, public_id):
    attendance = get_attendance(public_id)
    try:
        services.cancel(attendance, user=request.user, request=request)
    except wf.WorkflowError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Atendimento cancelado.")
    return redirect("attendances:summary", attendance.public_id)
