from django.urls import path

from . import views

app_name = "mailing"

urlpatterns = [
    path("atendimentos/<uuid:public_id>/email/pendentes/", views.send_pending, name="send_pending"),
    path("atendimentos/<uuid:public_id>/email/reenviar/", views.resend, name="resend"),
    path("configuracoes/email-teste/", views.test_email, name="test"),
]
