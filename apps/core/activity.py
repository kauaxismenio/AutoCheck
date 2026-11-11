"""Tradução da trilha de auditoria para as "Atividades recentes" do dashboard."""
from apps.core.models import AuditLog

ACTION_LABELS = {
    "attendance.created": "abriu o atendimento",
    "attendance.step_advanced": "avançou o atendimento",
    "attendance.cancelled": "cancelou o atendimento",
    "attendance.completed": "concluiu o atendimento",
    "signature.registered": "registrou a assinatura do cliente",
    "signature.refused": "registrou a recusa em assinar",
    "report.generated": "gerou o relatório PDF",
    "mailing.resend": "reenviou o relatório por e-mail",
    "replacement.decision": "registrou uma decisão do cliente",
    "customer.created": "cadastrou um cliente",
    "customer.updated": "atualizou um cliente",
    "vehicle.created": "cadastrou um veículo",
    "vehicle.updated": "atualizou um veículo",
    "workshop.updated": "alterou as configurações da oficina",
}


def recent_activity(workshop_id, limit=8):
    from apps.attendances.models import Attendance

    entries = list(
        AuditLog.objects.filter(action__in=ACTION_LABELS, user__workshop_id=workshop_id)
        .select_related("user", "user__workshop").order_by("-created_at")[:limit]
    )
    ids = {entry.attendance_id for entry in entries if entry.attendance_id}
    attendances = Attendance.objects.filter(pk__in=ids).select_related("vehicle").in_bulk()
    return [
        {
            "when": entry.created_at,
            "who": entry.user.display_name if entry.user else "Sistema",
            "what": ACTION_LABELS[entry.action],
            "attendance": attendances.get(entry.attendance_id),
        }
        for entry in entries
    ]
