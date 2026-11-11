from django.urls import path

from . import views

app_name = "attendances"

urlpatterns = [
    path("", views.attendance_list, name="list"),
    path("historico/", views.history, name="history"),
    path("novo/", views.new, name="new"),
    path("<uuid:public_id>/", views.detail, name="detail"),
    path("<uuid:public_id>/resumo/", views.summary, name="summary"),
    path("<uuid:public_id>/cadastro/", views.edit, name="edit"),
    path("<uuid:public_id>/cancelar/", views.cancel, name="cancel"),
]
