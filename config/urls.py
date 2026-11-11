"""Rotas principais. Cada módulo registra as próprias URLs com namespace."""
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "AutoCheck — Administração"
admin.site.site_title = "AutoCheck"
admin.site.index_title = "Painel administrativo"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("conta/", include("apps.accounts.urls")),
    path("plataforma/", include("apps.platform_admin.urls")),
    path("configuracoes/", include("apps.workshop.urls")),
    path("atendimentos/", include("apps.attendances.urls")),
    path("atendimentos/", include("apps.photos.urls")),
    path("atendimentos/", include("apps.checklist.urls")),
    path("atendimentos/", include("apps.replacements.urls")),
    path("atendimentos/", include("apps.signatures.urls")),
    path("atendimentos/", include("apps.reports.urls")),
    path("", include("apps.mailing.urls")),
    path("pos-venda/", include("apps.aftersales.urls")),
    path("mecanicos/", include("apps.mechanics.urls")),
    path("funcionarios/", include("apps.employees.urls")),
    path("clientes/", include("apps.customers.urls")),
    path("veiculos/", include("apps.vehicles.urls")),
    path("integracoes/", include("apps.integrations.urls")),
    path("", include("apps.core.urls")),
]
