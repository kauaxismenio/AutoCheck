from django.urls import path

from . import views

app_name = "integrations"

urlpatterns = [
    path("cnpj/", views.cnpj_lookup, name="cnpj"),
    path("cpf/", views.cpf_lookup, name="cpf"),
    path("placa/", views.plate_lookup, name="plate"),
]
