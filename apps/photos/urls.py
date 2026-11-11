from django.urls import path

from . import views

app_name = "photos"

urlpatterns = [
    path("<uuid:public_id>/check-in/", views.checkin, name="checkin"),
    path("<uuid:public_id>/check-out/", views.checkout, name="checkout"),
    path("<uuid:public_id>/fotos/", views.upload, name="upload"),
    path("<uuid:public_id>/fotos/<int:pk>/", views.photo_file, name="file"),
    path("<uuid:public_id>/fotos/<int:pk>/excluir/", views.delete, name="delete"),
]
