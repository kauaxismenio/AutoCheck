from django.urls import path

from . import views

app_name = "workshop"

urlpatterns = [
    path("", views.settings_view, name="settings"),
    path("logotipo/", views.logo, name="logo"),
    path("avaliacao/link/", views.review_link, name="review_link"),
    path("avaliacao/qrcode.png", views.review_qr, name="review_qr"),
    path("avaliacao/qrcode/baixar/", views.review_qr_download, name="review_qr_download"),
]
