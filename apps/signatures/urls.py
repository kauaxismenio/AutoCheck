from django.urls import path

from . import views

app_name = "signatures"

urlpatterns = [
    path("<uuid:public_id>/revisao/", views.step, name="step"),
    path("<uuid:public_id>/revisao/qr-avaliacao/", views.review_qr, name="review_qr"),
    path("<uuid:public_id>/assinatura/", views.signature_file, name="file"),
]
