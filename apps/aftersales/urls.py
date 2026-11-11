from django.urls import path

from . import views

app_name = "aftersales"

urlpatterns = [
    path("", views.aftersales_list, name="list"),
]
