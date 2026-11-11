from django.contrib import admin

from .models import Photo


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ("attendance", "phase", "category", "width", "height", "created_at")
    list_filter = ("phase", "category")
    search_fields = ("attendance__code",)
