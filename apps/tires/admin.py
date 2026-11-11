from django.contrib import admin

from .models import TireInspection


@admin.register(TireInspection)
class TireInspectionAdmin(admin.ModelAdmin):
    list_display = ("attendance", "position", "condition", "pressure_psi", "twi_mm")
    list_filter = ("position", "condition")
