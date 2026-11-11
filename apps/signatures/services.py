"""Registro da assinatura (ou da recusa), vinculada à versão atual do atendimento."""
import base64
import binascii
import io
import uuid

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageChops, UnidentifiedImageError

from apps.core.audit import client_ip, log_action

from .models import AttendanceSignature

_PREFIX = "data:image/png;base64,"
MAX_BASE64_CHARS = 3_000_000
MAX_SIDE = 4000
MIN_INK_PIXELS = 20


def decode_signature(data_url):
    """Converte o traço enviado em PNG sobre fundo branco; recusa conteúdo inválido ou em branco."""
    if not data_url or not data_url.startswith(_PREFIX) or len(data_url) > MAX_BASE64_CHARS:
        raise ValidationError("Assinatura inválida. Peça ao cliente para assinar de novo.")
    try:
        raw = base64.b64decode(data_url[len(_PREFIX):], validate=True)
        with Image.open(io.BytesIO(raw)) as probe:
            if probe.format != "PNG" or max(probe.size) > MAX_SIDE:
                raise ValidationError("Assinatura inválida. Peça ao cliente para assinar de novo.")
            probe.verify()
        with Image.open(io.BytesIO(raw)) as source:
            rgba = source.convert("RGBA")
    except (binascii.Error, ValueError, OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise ValidationError("Assinatura inválida. Peça ao cliente para assinar de novo.") from exc

    canvas = Image.new("RGB", rgba.size, (255, 255, 255))
    canvas.paste(rgba, mask=rgba.getchannel("A"))
    ink = ImageChops.difference(canvas, Image.new("RGB", canvas.size, (255, 255, 255))).convert("L")
    if sum(ink.point(lambda value: 1 if value > 40 else 0).getdata()) < MIN_INK_PIXELS:
        raise ValidationError("A assinatura está em branco. Peça ao cliente para assinar.")

    output = io.BytesIO()
    canvas.save(output, format="PNG", optimize=True)
    return ContentFile(output.getvalue(), name=f"{uuid.uuid4().hex}.png")


def _new_record(attendance, user, request):
    AttendanceSignature.objects.filter(attendance=attendance).delete()
    # Evita reaproveitar uma assinatura antiga guardada em cache no objeto.
    attendance._state.fields_cache.pop("signature", None)
    record = AttendanceSignature(attendance=attendance, registered_by=user, ip_address=client_ip(request))
    if request is not None:
        record.user_agent = request.META.get("HTTP_USER_AGENT", "")[:255]
    record.bind_to_current_version()
    return record


@transaction.atomic
def register_signature(attendance, data_url, *, user=None, request=None):
    content = decode_signature(data_url)
    record = _new_record(attendance, user, request)
    record.refused = False
    record.image.save(content.name, content, save=False)
    record.save()
    log_action("signature.registered", request=request, user=user, obj=record, attendance=attendance,
               sha256=record.snapshot_sha256)
    return record


@transaction.atomic
def register_refusal(attendance, *, user=None, request=None):
    record = _new_record(attendance, user, request)
    record.refused = True
    record.save()
    log_action("signature.refused", request=request, user=user, obj=record, attendance=attendance,
               sha256=record.snapshot_sha256)
    return record


def set_review_qr_presented(attendance, presented, *, user, request=None):
    """Registra só que o código foi mostrado. Mantém o primeiro registro se a ação for repetida."""
    from apps.attendances.models import Attendance

    if presented and not attendance.workshop.google_review_url:
        raise ValidationError("O link de avaliação da oficina não está configurado.")
    if presented == bool(attendance.review_qr_presented_at):
        return
    attendance.review_qr_presented_at = timezone.now() if presented else None
    attendance.review_qr_presented_by = user if presented else None
    Attendance.objects.filter(pk=attendance.pk).update(
        review_qr_presented_at=attendance.review_qr_presented_at, review_qr_presented_by=attendance.review_qr_presented_by,
    )
    log_action("attendance.review_qr_presented" if presented else "attendance.review_qr_cleared",
               request=request, user=user, obj=attendance, attendance=attendance)
