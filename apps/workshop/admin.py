from django.contrib import admin

from .models import WorkshopSettings


@admin.register(WorkshopSettings)
class WorkshopSettingsAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "cnpj", "phone", "report_email", "updated_at")

    def has_delete_permission(self, request, obj=None):
        return False
