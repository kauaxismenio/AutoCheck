"""Consultas de pós-venda e rotina de retenção.

Retenção: seis meses de calendário após a conclusão. A exclusão só acontece com
comando explícito, e somente depois que os e-mails obrigatórios foram aceitos pelo
servidor. Não há agendamento automático.
"""
from dataclasses import dataclass, field

from django.db import transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone

from apps.attendances import workflow as wf
from apps.attendances.models import Attendance
from apps.core.audit import log_action
from apps.mailing.services import mandatory_emails_confirmed
from apps.replacements.models import Decision, PartReplacement


# ---------------------------------------------------------------------------
# Pós-venda
# ---------------------------------------------------------------------------
def _later_replacements(outer_vehicle, outer_name, outer_completed):
    return PartReplacement.objects.filter(
        attendance__vehicle=outer_vehicle, component_name=outer_name, replaced=True,
        attendance__completed_at__gt=outer_completed,
    )


def with_pending_recommendations(queryset):
    """Atendimentos com recusa ainda não resolvida em atendimento posterior do mesmo veículo."""
    later = _later_replacements(OuterRef("attendance__vehicle"), OuterRef("component_name"),
                                OuterRef("attendance__completed_at"))
    pending = PartReplacement.objects.filter(attendance=OuterRef("pk"), decision=Decision.NAO_AUTORIZADO).annotate(
        solved=Exists(later),
    ).filter(solved=False)
    return queryset.filter(Exists(pending))


def describe(attendance):
    """Dados de uma linha do pós-venda."""
    replacements = list(attendance.replacements.all())
    refused = [r for r in replacements if r.decision == Decision.NAO_AUTORIZADO]
    pending = [
        r.component_name for r in refused
        if not _later_replacements(attendance.vehicle_id, r.component_name, attendance.completed_at).exists()
    ]
    return {
        "attendance": attendance,
        "services": [s.description for s in attendance.services.all()],
        "parts": [r.component_name for r in replacements if r.replaced],
        "refused": [r.component_name for r in refused],
        "pending": pending,
    }


# ---------------------------------------------------------------------------
# Retenção
# ---------------------------------------------------------------------------
@dataclass
class RetentionItem:
    attendance: Attendance
    eligible: bool
    reason: str
    files: list = field(default_factory=list)

    @property
    def size_bytes(self):
        return sum(size for _, size in self.files)


def _file_inventory(attendance):
    """Arquivos físicos do atendimento: (nome, tamanho)."""
    fields = [photo.image for photo in attendance.photos.all()]
    fields += [report.file for report in attendance.reports.all()]
    signature = getattr(attendance, "signature", None)
    if signature is not None and signature.image:
        fields.append(signature.image)
    inventory = []
    for file_field in fields:
        size = file_field.storage.size(file_field.name) if file_field.storage.exists(file_field.name) else 0
        inventory.append((file_field.name, size))
    return inventory


def evaluate(attendance):
    if attendance.status == wf.STATUS_EM_ANDAMENTO:
        return False, "Atendimento em andamento."
    if attendance.status == wf.STATUS_CONCLUIDO and not mandatory_emails_confirmed(attendance):
        return False, "E-mails obrigatórios ainda sem aceite confirmado."
    return True, "Prazo vencido e requisitos atendidos."


def expired_items(now=None):
    """Tudo que passou do prazo, indicando o que pode e o que não pode ser excluído."""
    now = now or timezone.now()
    queryset = Attendance.objects.filter(retention_until__isnull=False, retention_until__lte=now).exclude(
        status=wf.STATUS_EM_ANDAMENTO,
    ).select_related("customer", "vehicle").order_by("retention_until")
    items = []
    for attendance in queryset:
        eligible, reason = evaluate(attendance)
        items.append(RetentionItem(attendance, eligible, reason, _file_inventory(attendance)))
    return items


def _remove_orphans(customer, vehicle):
    """Cliente e veículo sem nenhum outro atendimento também saem (LGPD)."""
    removed = {"vehicle": False, "customer": False}
    if not vehicle.attendances.exists():
        vehicle.delete()
        removed["vehicle"] = True
    if not customer.attendances.exists() and not customer.vehicles.exists():
        customer.delete()
        removed["customer"] = True
    return removed


def purge(item, *, user=None):
    """Exclui registros e, depois do commit, os arquivos físicos. Reavalia antes de apagar."""
    with transaction.atomic():
        attendance = Attendance.objects.select_for_update().select_related("customer", "vehicle").get(
            pk=item.attendance.pk,
        )
        if attendance.retention_until is None or attendance.retention_until > timezone.now():
            raise ValueError("Atendimento fora do prazo de exclusão.")
        eligible, reason = evaluate(attendance)
        if not eligible:
            raise ValueError(reason)
        code, attendance_id = attendance.code, attendance.pk
        customer, vehicle = attendance.customer, attendance.vehicle
        attendance.delete()  # cascata em fotos, checklist, pneus, peças, serviços, assinatura, relatórios, e-mails
        removed = _remove_orphans(customer, vehicle)
        # Trilha sem dados pessoais: somente identificadores e contagens.
        log_action("retention.purged", user=user, attendance=attendance_id, code=code, files=len(item.files),
                   bytes=item.size_bytes, **{f"{key}_removed": value for key, value in removed.items()})
    return removed
