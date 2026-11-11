"""Armazenamento privado de arquivos (fotos, assinaturas, logotipo, PDFs).

Os arquivos ficam em PRIVATE_MEDIA_ROOT, fora das pastas públicas. Não existe
URL pública: `url()` é bloqueado de propósito, e todo download passa por uma
view autenticada (apps.core.protected_files.serve_protected_file).
"""
import os
import uuid

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateMediaStorage(FileSystemStorage):
    def __init__(self, **kwargs):
        kwargs.setdefault("location", settings.PRIVATE_MEDIA_ROOT)
        kwargs["base_url"] = None
        super().__init__(**kwargs)

    def url(self, name):  # noqa: ARG002
        # Arquivos privados não têm URL pública. Retornar string vazia (em vez de
        # levantar erro) evita quebrar widgets do admin que consultam `.url`.
        # Para exibir/baixar, use a view protegida do módulo correspondente.
        return ""


@deconstructible
class UUIDUploadTo:
    """Gera caminhos não adivinháveis: <prefixo>/<AAAA>/<MM>/<uuid>.<ext>."""

    def __init__(self, prefix):
        self.prefix = prefix.strip("/")

    def __call__(self, instance, filename):
        from django.utils import timezone

        ext = os.path.splitext(filename)[1].lower()[:10] or ".bin"
        now = timezone.now()
        return f"{self.prefix}/{now:%Y}/{now:%m}/{uuid.uuid4().hex}{ext}"
