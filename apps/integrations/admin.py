from django.contrib import admin

from .models import ExternalCallLog


@admin.register(ExternalCallLog)
class ExternalCallLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "provider", "operation", "success", "outcome", "http_status", "duration_ms")
    list_filter = ("provider", "success", "outcome")
    readonly_fields = [f.name for f in ExternalCallLog._meta.fields]

    def has_add_permission(self, request):
        return False
