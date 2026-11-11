from django.contrib import admin

from .models import ServiceRecord


@admin.register(ServiceRecord)
class ServiceRecordAdmin(admin.ModelAdmin):
    list_display = ("attendance", "description", "replacement", "performed_at")
    search_fields = ("attendance__code", "description")
