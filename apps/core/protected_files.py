"""Entrega de arquivos privados somente após autenticação e autorização.

Cada módulo (fotos, assinaturas, relatórios, logotipo) cria a sua view, decide
QUEM pode ver o arquivo e só então chama `serve_protected_file`.
"""
import mimetypes

from django.http import FileResponse, Http404


def serve_protected_file(file_field, *, download_name=None, as_attachment=False):
    if not file_field or not file_field.name:
        raise Http404("Arquivo não encontrado.")
    storage = file_field.storage
    if not storage.exists(file_field.name):
        raise Http404("Arquivo não encontrado.")
    content_type, _ = mimetypes.guess_type(file_field.name)
    response = FileResponse(
        storage.open(file_field.name, "rb"),
        as_attachment=as_attachment,
        filename=download_name or file_field.name.rsplit("/", 1)[-1],
        content_type=content_type or "application/octet-stream",
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    # Arquivo enviado nunca executa nada; o visualizador de imagem do navegador só precisa de estilo próprio.
    response["Content-Security-Policy"] = "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; sandbox"
    return response
