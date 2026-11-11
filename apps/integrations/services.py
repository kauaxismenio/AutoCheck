"""Chamadas externas com registro em ExternalCallLog (sem gravar o documento consultado)."""
import hashlib
import hmac
import logging
import time

from django.conf import settings

from .models import ExternalCallLog
from .providers.base import IntegrationError
from .providers.brasilapi import BrasilAPIClient
from .providers.management_system import ManagementSystemClient

logger = logging.getLogger("autocheck.integrations")


def _query_hash(value):
    return hmac.new(settings.SECRET_KEY.encode(), value.encode(), hashlib.sha256).hexdigest()


def _log(client, operation, value, user, started, *, success, outcome):
    ExternalCallLog.objects.create(
        provider=client.provider, operation=operation, query_hash=_query_hash(value),
        success=success, outcome=outcome, http_status=getattr(client, "last_status", None),
        duration_ms=int((time.monotonic() - started) * 1000),
        user=user if user is not None and user.is_authenticated else None,
    )


def lookup_company(cnpj, user=None, client=None):
    client = client or BrasilAPIClient()
    started = time.monotonic()
    try:
        company = client.find_company(cnpj)
    except IntegrationError as exc:
        _log(client, "find_company", cnpj, user, started, success=False, outcome=exc.code)
        logger.info("Consulta de CNPJ sem resultado: %s", exc.code)
        raise
    _log(client, "find_company", cnpj, user, started, success=True, outcome="ok")
    return company


def lookup_person(cpf, user=None, client=None):
    """Consulta o sistema de gestão. Hoje sempre levanta NotConfigured (sem documentação)."""
    client = client or ManagementSystemClient()
    started = time.monotonic()
    try:
        person = client.find_customer_by_cpf(cpf)
    except IntegrationError as exc:
        _log(client, "find_customer_by_cpf", cpf, user, started, success=False, outcome=exc.code)
        raise
    _log(client, "find_customer_by_cpf", cpf, user, started, success=True, outcome="ok")
    return person
