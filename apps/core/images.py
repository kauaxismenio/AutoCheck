"""Tratamento seguro de imagens enviadas (fotos, logotipo).

Toda imagem é reaberta e regravada pelo Pillow antes de ir para o disco:
- confirma que o arquivo é mesmo uma imagem de formato permitido;
- aplica a orientação do EXIF e descarta os metadados (GPS, aparelho etc.);
- limita o tamanho em pixels.
"""
import hashlib
import io
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_INPUT_PIXELS = 60_000_000  # protege contra "bombas" de descompressão


class ProcessedImage:
    def __init__(self, content, sha256, size_bytes, width, height):
        self.content, self.sha256, self.size_bytes = content, sha256, size_bytes
        self.width, self.height = width, height


def _flatten(image):
    """Remove transparência sobre fundo branco (JPEG não tem canal alfa)."""
    rgba = image.convert("RGBA")
    background = Image.new("RGB", rgba.size, (255, 255, 255))
    background.paste(rgba, mask=rgba.getchannel("A"))
    return background


def process_upload(uploaded, *, max_side=2000, keep_alpha=False, quality=85):
    """Valida e regrava o arquivo. Levanta ValidationError com mensagem amigável."""
    if uploaded.size > settings.MAX_PHOTO_UPLOAD_BYTES:
        limit = settings.MAX_PHOTO_UPLOAD_BYTES // (1024 * 1024)
        raise ValidationError(f"Imagem muito grande. O limite é de {limit} MB.", code="too_large")

    try:
        uploaded.seek(0)
        with Image.open(uploaded) as probe:
            source_format = probe.format
            width, height = probe.size
            probe.verify()
        if source_format not in ALLOWED_FORMATS:
            raise ValidationError("Formato não aceito. Envie JPG, PNG ou WEBP.", code="bad_format")
        if width * height > MAX_INPUT_PIXELS:
            raise ValidationError("Imagem com resolução acima do permitido.", code="too_many_pixels")

        uploaded.seek(0)
        with Image.open(uploaded) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            if keep_alpha:
                image.convert("RGBA").save(output, format="PNG", optimize=True)
                extension = "png"
            else:
                _flatten(image).save(output, format="JPEG", quality=quality, optimize=True)
                extension = "jpg"
            final_width, final_height = image.size
    except ValidationError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError) as exc:
        raise ValidationError("O arquivo enviado não é uma imagem válida.", code="invalid_image") from exc

    data = output.getvalue()
    content = ContentFile(data, name=f"{uuid.uuid4().hex}.{extension}")
    return ProcessedImage(content, hashlib.sha256(data).hexdigest(), len(data), final_width, final_height)
