from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("<uuid:public_id>/relatorio/gerar/", views.generate, name="generate"),
    path("<uuid:public_id>/relatorio/<int:pk>/", views.download, name="download"),
]
