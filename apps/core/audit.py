"""Serviço de auditoria: um único ponto para registrar operações importantes."""
import logging

from django.conf import settings

logger = logging.getLogger("autocheck.audit")


def client_ip(request):
    if request is None:
        return None
    if settings.AUTOCHECK["TRUST_PROXY_HEADERS"]:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


def log_action(action, *, request=None, user=None, obj=None, attendance=None, **details):
    """Grava um AuditLog. Falhas de auditoria são logadas, sem derrubar a operação."""
    from apps.core.models import AuditLog

    if user is None and request is not None and getattr(request, "user", None) is not None:
        user = request.user if request.user.is_authenticated else None
    try:
        return AuditLog.objects.create(
            user=user,
            action=action,
            object_type=obj._meta.label if obj is not None else "",
            object_id=str(obj.pk) if obj is not None and obj.pk is not None else "",
            attendance_id=getattr(attendance, "pk", attendance),
            details=details,
            ip_address=client_ip(request),
        )
    except Exception:  # noqa: BLE001 — auditoria nunca deve quebrar o fluxo principal
        logger.exception("Falha ao registrar auditoria: %s", action)
        return None
