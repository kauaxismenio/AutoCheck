from django.contrib import admin

from .models import PartReplacement


@admin.register(PartReplacement)
class PartReplacementAdmin(admin.ModelAdmin):
    list_display = ("attendance", "component_name", "decision", "replaced", "decided_at")
    list_filter = ("decision", "replaced")
    search_fields = ("attendance__code", "component_name")
