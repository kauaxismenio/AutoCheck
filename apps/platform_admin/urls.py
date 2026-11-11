from django.urls import path

from . import views

app_name = "platform_admin"

urlpatterns = [
    path("", views.workshop_list, name="list"),
    path("nova/", views.workshop_create, name="create"),
    path("<int:pk>/", views.workshop_edit, name="edit"),
    path("<int:pk>/nova-senha/", views.workshop_reset_password, name="reset_password"),
]
