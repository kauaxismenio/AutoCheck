from django.urls import path

from . import views

app_name = "checklist"

urlpatterns = [
    path("<uuid:public_id>/checklist/", views.step, name="step"),
    path("<uuid:public_id>/checklist/salvar/", views.autosave, name="autosave"),
]
