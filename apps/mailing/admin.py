from django.contrib import admin

from .models import EmailDispatch


@admin.register(EmailDispatch)
class EmailDispatchAdmin(admin.ModelAdmin):
    list_display = ("attendance", "recipient_type", "recipient_email", "status", "attempts", "next_attempt_at", "accepted_at", "is_manual_resend")
    list_filter = ("status", "recipient_type", "is_manual_resend")
    search_fields = ("attendance__code", "recipient_email")
    readonly_fields = [f.name for f in EmailDispatch._meta.fields]

    def has_add_permission(self, request):
        return False
