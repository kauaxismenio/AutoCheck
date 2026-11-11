from django.contrib import admin

from .models import AttendanceSignature


@admin.register(AttendanceSignature)
class AttendanceSignatureAdmin(admin.ModelAdmin):
    list_display = ("attendance", "refused", "created_at", "registered_by")
    readonly_fields = ("snapshot", "snapshot_sha256", "ip_address", "user_agent", "created_at")

    def has_change_permission(self, request, obj=None):
        return False  # assinatura não é editável; se o atendimento mudar, coleta-se outra.
