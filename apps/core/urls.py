from django.urls import path

from . import pwa, views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("saude/", views.health, name="health"),
    path("manifest.webmanifest", pwa.manifest, name="manifest"),
    path("sw.js", pwa.service_worker, name="sw"),
    path("sem-conexao/", pwa.offline, name="offline"),
]
