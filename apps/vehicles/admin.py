from django.contrib import admin

from .models import Vehicle


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("plate_formatted", "brand", "model", "year", "color", "customer", "last_mileage")
    search_fields = ("plate", "brand", "model", "customer__full_name", "customer__legal_name")
    autocomplete_fields = ("customer",)
