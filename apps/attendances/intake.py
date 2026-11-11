"""Grava a primeira etapa: localiza ou cria cliente e veículo e abre o atendimento.

Regras:
- CPF e CNPJ são independentes: nunca se busca ou preenche um a partir do outro.
- O CNPJ e os dados empresariais informados ficam no próprio atendimento. Um
  cliente com CPF não recebe CNPJ pelo atendimento, nem o contrário.
- Com CPF, o cliente é localizado pelo CPF. Só com CNPJ, é o cadastro da própria
  empresa, nunca o de uma pessoa com CPF. Sem documento, usa o dono da placa somente
  se o telefone for o mesmo; caso contrário cria um cliente novo.
- Campo em branco nunca apaga dado histórico do cliente (e-mail, documentos).
- O dono atual do veículo passa a ser o cliente deste atendimento; atendimentos
  antigos continuam apontando para o cliente da época.
- Ao corrigir um atendimento, um cliente ou veículo que tem outros atendimentos
  não é sobrescrito com outro documento/placa: um novo registro é criado.
"""
from django.db import transaction

from apps.core.audit import log_action
from apps.core.validators.text import to_upper
from apps.customers.models import Customer, PersonType
from apps.mechanics.services import get_or_add
from apps.vehicles.models import Vehicle

from . import services
from . import workflow as wf
from .models import Attendance


def _others_exist(obj, attendance):
    return obj.attendances.exclude(pk=attendance.pk).exists()


def _can_keep_customer(current, cpf, cnpj, attendance):
    """Na correção, o cliente atual só serve se não juntar CPF e CNPJ nem sobrescrever outro histórico."""
    if cpf:
        return not current.cnpj and not (current.cpf and cpf != current.cpf and _others_exist(current, attendance))
    if cnpj:
        return not current.cpf and not (current.cnpj and cnpj != current.cnpj and _others_exist(current, attendance))
    return True


def _resolve_customer(data, attendance, workshop):
    cpf, cnpj = data.get("cpf"), data.get("cnpj")
    customers = Customer.objects.filter(workshop=workshop)
    found = customers.filter(cpf=cpf).first() if cpf else cnpj and customers.filter(cnpj=cnpj, cpf__isnull=True).first()
    if found:
        return found
    if attendance is not None:
        if _can_keep_customer(attendance.customer, cpf, cnpj, attendance):
            return attendance.customer
        return Customer(workshop=workshop)
    if not cpf and not cnpj:
        vehicle = Vehicle.objects.filter(workshop=workshop, plate=data["plate"]).select_related("customer").first()
        if vehicle and vehicle.customer.phone == data["phone"]:
            return vehicle.customer
    return Customer(workshop=workshop)


def _customer_kind(customer):
    """O tipo reflete o que o cadastro guarda. Nada é apagado."""
    has_person, has_company = bool(customer.cpf or customer.full_name), bool(customer.cnpj or customer.legal_name)
    if has_person and has_company:
        return PersonType.AMBOS
    return PersonType.PJ if has_company else PersonType.PF


def _apply_customer(customer, data, request):
    creating = customer.pk is None
    for field in ("full_name", "cpf"):
        if data.get(field):
            setattr(customer, field, data[field])
    if not customer.cpf:  # cliente com CPF nunca recebe dados empresariais pelo atendimento
        for field in ("legal_name", "trade_name", "contact_person"):
            if data.get(field):
                setattr(customer, field, data[field])
        cnpj = data.get("cnpj")
        # O CNPJ pode já estar no histórico de uma pessoa com CPF: esse cadastro não é tocado.
        if cnpj and not Customer.objects.filter(workshop=customer.workshop, cnpj=cnpj).exclude(pk=customer.pk).exists():
            customer.cnpj = cnpj
    if data.get("email"):
        customer.email = data["email"]
    customer.phone = data["phone"]
    customer.person_type = _customer_kind(customer)
    customer.save()
    log_action("customer.created" if creating else "customer.updated", request=request, obj=customer)
    return customer


def _resolve_vehicle(data, attendance, workshop):
    found = Vehicle.objects.filter(workshop=workshop, plate=data["plate"]).first()
    if found:
        return found
    if attendance is not None and not _others_exist(attendance.vehicle, attendance):
        return attendance.vehicle
    return Vehicle(workshop=workshop)


def _apply_vehicle(vehicle, customer, data, request):
    creating = vehicle.pk is None
    vehicle.customer = customer
    vehicle.plate = data["plate"]
    vehicle.brand, vehicle.model = data["brand"].strip(), data["model"].strip()
    vehicle.year = data.get("year") or vehicle.year
    vehicle.color = data.get("color", "").strip() or vehicle.color
    vehicle.last_mileage = data["mileage"]
    vehicle.save()
    log_action("vehicle.created" if creating else "vehicle.updated", request=request, obj=vehicle)
    return vehicle


@transaction.atomic
def save_intake(data, *, user, request=None, attendance=None):
    """Cria (ou corrige) o atendimento. Levanta services.StepIncomplete se faltar algo."""
    workshop = user.workshop
    customer = _apply_customer(_resolve_customer(data, attendance, workshop), data, request)
    vehicle = _apply_vehicle(_resolve_vehicle(data, attendance, workshop), customer, data, request)

    creating = attendance is None
    if creating:
        attendance = Attendance(workshop=workshop, created_by=user)
    attendance.customer, attendance.vehicle = customer, vehicle
    attendance.attendant = data["attendant"]
    # Nome digitado tem prioridade sobre a lista, e o cadastro só nasce junto com o atendimento válido.
    new_name = data.get("new_mechanic_name")
    attendance.mechanic = get_or_add(new_name, workshop=workshop, user=user, request=request) if new_name else data["mechanic"]
    attendance.mileage = data["mileage"]
    attendance.origin = data["origin"]
    attendance.cpf_not_informed = data.get("cpf_not_informed", False)
    attendance.cnpj_not_informed = data.get("cnpj_not_informed", False)
    attendance.person_type = data["person_type"]
    attendance.cnpj = data.get("cnpj") or ""
    attendance.legal_name = to_upper(data.get("legal_name"))
    attendance.trade_name = to_upper(data.get("trade_name"))
    attendance.contact_person = data.get("contact_person") or ""
    attendance.email_opt_out = data.get("email_opt_out", False)
    attendance.customer_email = data.get("email", "") or ""
    attendance.save()

    if creating:
        log_action("attendance.created", request=request, user=user, obj=attendance, attendance=attendance)
    else:
        log_action("attendance.intake_updated", request=request, user=user, obj=attendance, attendance=attendance)
    if attendance.current_step == wf.CADASTRO:
        services.advance(attendance, wf.CADASTRO, user=user, request=request)
    return attendance
