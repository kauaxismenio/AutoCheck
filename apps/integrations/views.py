"""Consultas usadas pelo formulário de cadastro (retorno em JSON).

A consulta nunca impede o preenchimento manual: qualquer falha volta como
mensagem amigável, e o JS apenas a exibe.
"""
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from apps.core.validators.documents import is_valid_cnpj, is_valid_cpf, normalize_cnpj, normalize_cpf
from apps.core.validators.plate import is_valid_plate, normalize_plate
from apps.customers.models import Customer
from apps.vehicles.models import Vehicle

from . import services
from .providers.base import IntegrationError, NotConfigured

_STATUS_BY_CODE = {"nao_encontrado": 404, "nao_configurado": 200, "resposta_invalida": 502, "indisponivel": 503}


def _error(exc):
    return JsonResponse({"found": False, "code": exc.code, "message": exc.user_message},
                        status=_STATUS_BY_CODE.get(exc.code, 503))


def _customer_payload(customer):
    """Somente dados pessoais. CNPJ, Razão Social e Nome Fantasia nunca saem de uma consulta por CPF."""
    return {
        "found": True, "source": "autocheck", "full_name": customer.full_name,
        "phone": customer.phone_formatted, "email": customer.email,
        "message": "Cliente já cadastrado no AutoCheck. Dados preenchidos; confira antes de salvar.",
    }


@login_required
@require_GET
def cnpj_lookup(request):
    """Sempre a BrasilAPI: o CNPJ digitado não consulta nem preenche nada do histórico de clientes."""
    cnpj = normalize_cnpj(request.GET.get("cnpj"))
    if not is_valid_cnpj(cnpj):
        return JsonResponse({"found": False, "code": "invalido", "message": "CNPJ inválido."}, status=400)
    try:
        company = services.lookup_company(cnpj, user=request.user)
    except IntegrationError as exc:
        return _error(exc)
    return JsonResponse({
        "found": True, "source": company.source, "legal_name": company.legal_name,
        "trade_name": company.trade_name, "message": "Dados preenchidos pela consulta. Você pode editar.",
    })


@login_required
@require_GET
def cpf_lookup(request):
    cpf = normalize_cpf(request.GET.get("cpf"))
    if not is_valid_cpf(cpf):
        return JsonResponse({"found": False, "code": "invalido", "message": "CPF inválido."}, status=400)
    customer = Customer.objects.filter(cpf=cpf).first()
    if customer:
        return JsonResponse(_customer_payload(customer))
    try:
        person = services.lookup_person(cpf, user=request.user)
    except NotConfigured:
        # Sem documentação do sistema de gestão: nenhuma consulta externa é simulada.
        return JsonResponse({"found": False, "code": "nao_configurado",
                             "message": "CPF válido. Cliente novo no AutoCheck: preencha os dados."})
    except IntegrationError as exc:
        return _error(exc)
    return JsonResponse({"found": True, "source": person.source, "full_name": person.full_name,
                         "phone": person.phone, "email": person.email,
                         "message": "Dados preenchidos pelo sistema de gestão."})


@login_required
@require_GET
def plate_lookup(request):
    plate = normalize_plate(request.GET.get("placa"))
    if not is_valid_plate(plate):
        return JsonResponse({"found": False, "code": "invalido", "message": "Placa inválida."}, status=400)
    vehicle = Vehicle.objects.filter(plate=plate).select_related("customer").first()
    if vehicle is None:
        return JsonResponse({"found": False, "code": "nao_encontrado", "message": ""})
    return JsonResponse({
        "found": True, "brand": vehicle.brand, "model": vehicle.model, "year": vehicle.year or "",
        "color": vehicle.color, "last_mileage": vehicle.last_mileage,
        "message": f"Veículo já cadastrado para {vehicle.customer}.",
    })
