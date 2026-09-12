from django.contrib import admin

from accounts.models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("username", "full_name", "role", "workshop", "position", "is_active")
    list_filter = ("role", "workshop", "is_active", "is_staff")
    search_fields = ("username", "last_name", "first_name", "email")
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Персональные данные", {"fields": ("last_name", "first_name", "patronymic", "email", "phone")}),
        ("Организация", {"fields": ("role", "workshop", "position")}),
        ("Права", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Даты", {"fields": ("last_login", "date_joined")}),
    )
