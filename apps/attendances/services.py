"""Proteção das etapas no servidor.

Toda view de etapa deve:
1. chamar `get_step_or_403(attendance, step)` antes de exibir/salvar;
2. ao concluir a etapa, chamar `complete_step(attendance, step, user, request)`.

`advance` valida a etapa atual e TODAS as anteriores e só então move
`current_step`, com bloqueio de linha para evitar avanços concorrentes. Assim,
reabrir uma etapa antiga e deixá-la incompleta (por exemplo, marcar SUBSTITUIR
depois de passar pelos serviços) impede o avanço. Ninguém avança alterando a
URL ou o HTML.
"""
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from apps.core.audit import log_action
from apps.core.dates import add_months

from . import step_validators
from . import workflow as wf
from .models import Attendance


class StepIncomplete(Exception):
    def __init__(self, errors):
        super().__init__("; ".join(errors))
        self.errors = list(errors)


def get_step_or_403(attendance, step):
    if not attendance.can_open(step):
        raise PermissionDenied("Esta etapa ainda não está liberada para este atendimento.")
    return attendance


def validate_step(attendance, step):
    validator = step_validators.VALIDATORS.get(step)
    return validator(attendance) if validator else []


def validate_through(attendance, step):
    """Erros da etapa informada e de todas as anteriores, na ordem do fluxo."""
    errors = []
    for candidate in wf.WORK_STEPS[: wf.step_index(step) + 1]:
        errors.extend(validate_step(attendance, candidate))
    return errors


@transaction.atomic
def advance(attendance, from_step, user=None, request=None):
    locked = Attendance.objects.select_for_update().get(pk=attendance.pk)
    target = wf.ensure_can_advance(locked.current_step, from_step, locked.status)
    errors = validate_through(locked, from_step)
    if errors:
        raise StepIncomplete(errors)

    locked.current_step = target
    update_fields = ["current_step", "updated_at"]
    if target == wf.FINALIZADO:
        locked.status = wf.STATUS_CONCLUIDO
        locked.completed_at = timezone.now()
        locked.retention_until = locked.compute_retention_until()
        locked.report_pending = True
        update_fields += ["status", "completed_at", "retention_until", "report_pending"]
    locked.save(update_fields=update_fields)

    log_action("attendance.step_advanced", request=request, user=user, obj=locked,
               attendance=locked, from_step=from_step, to_step=target)
    if target == wf.FINALIZADO:
        log_action("attendance.completed", request=request, user=user, obj=locked, attendance=locked)
    attendance.refresh_from_db()
    return attendance


def complete_step(attendance, step, user=None, request=None):
    """Conclui a etapa aberta: avança se for a atual; se for antiga, só revalida."""
    if attendance.current_step == step:
        return advance(attendance, step, user=user, request=request)
    errors = validate_step(attendance, step)
    if errors:
        raise StepIncomplete(errors)
    return attendance


@transaction.atomic
def cancel(attendance, user=None, request=None):
    locked = Attendance.objects.select_for_update().get(pk=attendance.pk)
    if locked.status != wf.STATUS_EM_ANDAMENTO:
        raise wf.WorkflowError("Só é possível cancelar atendimentos em andamento.")
    now = timezone.now()
    locked.status = wf.STATUS_CANCELADO
    locked.cancelled_at = now
    # Atendimento cancelado não fica guardado para sempre (LGPD).
    locked.retention_until = add_months(now, settings.AUTOCHECK["RETENTION_MONTHS"])
    locked.save(update_fields=["status", "cancelled_at", "retention_until", "updated_at"])
    log_action("attendance.cancelled", request=request, user=user, obj=locked, attendance=locked)
    attendance.refresh_from_db()
    return attendance
