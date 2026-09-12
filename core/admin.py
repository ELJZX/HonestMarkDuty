from django.contrib import admin

from core.models import AuditLog, ProductionSite, Workshop


@admin.register(Workshop)
class WorkshopAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "site", "chief", "is_active")
    list_filter = ("site", "is_active")
    search_fields = ("name", "code", "chief")


@admin.register(ProductionSite)
class ProductionSiteAdmin(admin.ModelAdmin):
    list_display = ("name", "address", "responsible", "is_active")
    search_fields = ("name", "address")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "action", "model_name", "object_repr")
    list_filter = ("action", "model_name")
    search_fields = ("object_repr", "object_id")
    readonly_fields = (
        "user",
        "action",
        "app_label",
        "model_name",
        "object_id",
        "object_repr",
        "changes",
        "created_at",
    )

    def has_add_permission(self, request):
        return False
