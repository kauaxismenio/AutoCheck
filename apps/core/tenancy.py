"""Isolamento entre oficinas.

O middleware define a oficina da requisição; os gerenciadores `objects` dos
modelos filtram por ela sozinhos, inclusive em relações como `customer.vehicles`.
Assim uma consulta nova nasce isolada, sem depender de lembrar do filtro.

Sem oficina definida (comandos, migrações, administração da plataforma) nada é
filtrado. Conta sem oficina recebe NO_WORKSHOP e não enxerga nenhum registro.
"""
from contextlib import contextmanager
from contextvars import ContextVar

from django.db import models

NO_WORKSHOP = 0

_current_workshop_id = ContextVar("autocheck_current_workshop_id", default=None)


def current_workshop_id():
    return _current_workshop_id.get()


@contextmanager
def workshop_scope(workshop_id):
    token = _current_workshop_id.set(workshop_id)
    try:
        yield
    finally:
        _current_workshop_id.reset(token)


class WorkshopScopedManager(models.Manager):
    """Modelo com o campo `workshop`."""

    # Atributo de classe: o Django recria o gerenciador nas relações sem repassar argumentos.
    scope_field = "workshop_id"

    def get_queryset(self):
        queryset = super().get_queryset()
        workshop_id = current_workshop_id()
        if workshop_id is None:
            return queryset
        return queryset.filter(**{self.scope_field: workshop_id})


class AttendanceScopedManager(WorkshopScopedManager):
    """Modelo que pertence a um atendimento (fotos, checklist, relatórios...)."""

    scope_field = "attendance__workshop_id"
