from django.urls import path

from . import views

app_name = "replacements"

urlpatterns = [
    path("<uuid:public_id>/servicos/", views.step, name="step"),
    path("<uuid:public_id>/servicos/adicionar/", views.add_service, name="add_service"),
    path("<uuid:public_id>/servicos/<int:pk>/excluir/", views.delete_service, name="delete_service"),
    path("<uuid:public_id>/pecas/<int:pk>/decisao/", views.decision, name="decision"),
    path("<uuid:public_id>/pecas/<int:pk>/confirmar/", views.confirm, name="confirm"),
]
