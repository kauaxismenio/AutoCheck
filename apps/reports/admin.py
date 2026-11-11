from django.contrib import admin

from .models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("attendance", "version", "size_bytes", "generated_at", "generated_by")
    readonly_fields = ("sha256", "size_bytes", "signature_sha256", "generated_at")
