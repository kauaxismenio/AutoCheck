from django.contrib import admin

from .models import Mechanic


@admin.register(Mechanic)
class MechanicAdmin(admin.ModelAdmin):
    list_display = ("name", "workshop", "phone", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)
