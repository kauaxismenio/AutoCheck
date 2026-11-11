from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("entrar/", views.AutoCheckLoginView.as_view(), name="login"),
    path("sair/", views.AutoCheckLogoutView.as_view(), name="logout"),
    path("minha-senha/", views.change_own_password, name="change_password"),
]
