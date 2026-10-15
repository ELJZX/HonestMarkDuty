from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from accounts.models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Пользователи с ролями; пароль хешируется стандартными средствами Django."""

    list_display = ("username", "full_name", "role", "workshop", "position", "is_active")
    list_filter = ("role", "workshop", "is_active", "is_staff")
    search_fields = ("username", "last_name", "first_name", "patronymic", "email")
    ordering = ("last_name", "first_name", "username")
    list_select_related = ("workshop",)
    save_on_top = True
    filter_horizontal = ("groups", "user_permissions")
    readonly_fields = ("last_login", "date_joined")
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (
            "Персональные данные",
            {"fields": ("last_name", "first_name", "patronymic", "email", "phone")},
        ),
        ("Организация", {"fields": ("role", "workshop", "position")}),
        (
            "Права",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Даты", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "last_name",
                    "first_name",
                    "role",
                    "password1",
                    "password2",
                ),
            },
        ),
    )
