from django.contrib import admin

from .models import ChecklistCategory, ChecklistComponent, ChecklistItem


class ChecklistComponentInline(admin.TabularInline):
    model = ChecklistComponent
    extra = 0


@admin.register(ChecklistCategory)
class ChecklistCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "order", "active")
    inlines = [ChecklistComponentInline]


@admin.register(ChecklistComponent)
class ChecklistComponentAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "order", "active")
    list_filter = ("category", "active")


@admin.register(ChecklistItem)
class ChecklistItemAdmin(admin.ModelAdmin):
    list_display = ("attendance", "category_name", "component_name", "result", "evaluated_at")
    list_filter = ("result",)
    search_fields = ("attendance__code", "component_name")
