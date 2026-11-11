"""Cabeçalhos de segurança e isolamento entre oficinas."""
from django.shortcuts import redirect

from .tenancy import NO_WORKSHOP, workshop_scope

CONTENT_SECURITY_POLICY = "; ".join((
    "default-src 'self'",
    "img-src 'self' data: blob:",
    "style-src 'self'",
    "script-src 'self'",
    "connect-src 'self'",
    "font-src 'self'",
    "manifest-src 'self'",
    "worker-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
))
PERMISSIONS_POLICY = "camera=(self), microphone=(), geolocation=(), payment=(), usb=()"


class SecurityHeadersMiddleware:
    """O admin do Django fica fora da CSP porque usa recursos próprios fora deste controle."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not request.path.startswith("/admin/"):
            response.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        response.setdefault("Permissions-Policy", PERMISSIONS_POLICY)
        return response


# Únicos caminhos do proprietário da plataforma: ele não entra nos dados das oficinas.
PLATFORM_OWNER_PATHS = ("/plataforma/", "/admin/", "/conta/", "/saude/", "/manifest.webmanifest", "/sw.js", "/sem-conexao/")


class WorkshopScopeMiddleware:
    """Define a oficina da requisição; toda consulta aos modelos da oficina passa a ser isolada."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if not user.is_authenticated:
            return self.get_response(request)
        if user.is_superuser:
            if not request.path.startswith(PLATFORM_OWNER_PATHS):
                return redirect("platform_admin:list")
            return self.get_response(request)
        with workshop_scope(user.workshop_id or NO_WORKSHOP):
            return self.get_response(request)
