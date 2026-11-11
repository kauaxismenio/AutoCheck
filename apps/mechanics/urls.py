from django.urls import path

from . import views

app_name = "mechanics"

urlpatterns = [
    path("", views.mechanic_list, name="list"),
    path("novo/", views.mechanic_create, name="create"),
    path("<int:pk>/editar/", views.mechanic_edit, name="edit"),
]
