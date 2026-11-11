from django.contrib import admin

from .models import Employee


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("name", "workshop", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)
