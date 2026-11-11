from django.urls import path

from . import views

app_name = "customers"

urlpatterns = [
    path("", views.customer_list, name="list"),
    path("novo/", views.customer_create, name="create"),
    path("<int:pk>/", views.customer_detail, name="detail"),
    path("<int:pk>/editar/", views.customer_edit, name="edit"),
    path("<int:pk>/excluir/", views.customer_delete, name="delete"),
]
