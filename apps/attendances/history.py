"""Consultas de histórico por cliente e por veículo."""
from apps.replacements.models import Decision

from . import workflow as wf


def _rows(queryset):
    attendances = list(
        queryset.select_related("customer", "vehicle", "mechanic")
        .prefetch_related("replacements", "services", "reports").order_by("-created_at")
    )
    for att in attendances:
        replacements = list(att.replacements.all())
        att.replaced_names = [r.component_name for r in replacements if r.replaced]
        att.refused_names = [r.component_name for r in replacements if r.decision == Decision.NAO_AUTORIZADO]
        att.service_names = [s.description for s in att.services.all()]
        reports = sorted(att.reports.all(), key=lambda report: report.version, reverse=True)
        att.last_report = reports[0] if reports else None
    return attendances


def customer_history(customer):
    return {
        "vehicles": customer.vehicles.all(),
        "attendances": _rows(customer.attendances.all()),
        "completed_status": wf.STATUS_CONCLUIDO,
    }


def vehicle_history(vehicle):
    return {
        "attendances": _rows(vehicle.attendances.all()),
        "completed_status": wf.STATUS_CONCLUIDO,
    }
