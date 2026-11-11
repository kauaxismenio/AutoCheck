from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "first_name", "last_name", "workshop", "is_active", "last_login")
    list_filter = ("workshop", "is_active", "is_staff")
    fieldsets = DjangoUserAdmin.fieldsets + (("AutoCheck", {"fields": ("workshop", "phone")}),)
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ("AutoCheck", {"fields": ("first_name", "last_name", "workshop")}),
    )
