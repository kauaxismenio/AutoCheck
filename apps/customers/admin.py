from django.contrib import admin

from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("__str__", "person_type", "cpf_formatted", "cnpj_formatted", "phone_formatted", "created_at")
    list_filter = ("person_type",)
    search_fields = ("full_name", "legal_name", "trade_name", "cpf", "cnpj", "phone", "email")
