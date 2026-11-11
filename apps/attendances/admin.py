from django.contrib import admin

from .models import Attendance


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("code", "customer", "vehicle", "attendant", "mechanic", "status", "current_step", "created_at", "completed_at")
    list_filter = ("status", "current_step", "origin")
    search_fields = ("code", "vehicle__plate", "customer__full_name", "legal_name", "cnpj")
    # Etapa e situação só mudam pelo serviço de fluxo (apps.attendances.services.advance).
    readonly_fields = ("public_id", "code", "status", "current_step", "completed_at",
                       "retention_until", "created_at", "updated_at", "review_requested", "review_requested_at",
                       "review_qr_presented_at", "review_qr_presented_by")
    autocomplete_fields = ("customer", "vehicle", "attendant", "mechanic")
