from django.contrib import admin

from equipment.models import (
    Camera,
    Equipment,
    EquipmentStatusLog,
    MaintenanceRecord,
)


class EquipmentStatusLogInline(admin.TabularInline):
    model = EquipmentStatusLog
    extra = 0
    readonly_fields = ("created_at", "changed_by")


class MaintenanceRecordInline(admin.TabularInline):
    model = MaintenanceRecord
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = (
        "name", "site", "workshop", "line", "status", "criticality",
        "is_camera", "is_printer",
    )
    list_filter = (
        "status", "criticality", "site", "workshop", "line",
        "is_camera", "is_printer",
    )
    search_fields = ("name", "serial_number", "model_name")
    inlines = (EquipmentStatusLogInline, MaintenanceRecordInline)


@admin.register(Camera)
class CameraAdmin(admin.ModelAdmin):
    """Управление камерами (Camera Control) в Django-админке."""

    list_display = ("name", "workshop", "line", "ip_address", "camera_id", "is_active")
    list_filter = ("workshop", "is_active")
    search_fields = ("name", "ip_address", "model_name")

    def save_model(self, request, obj, form, change):
        obj.is_camera = True
        super().save_model(request, obj, form, change)


@admin.register(MaintenanceRecord)
class MaintenanceRecordAdmin(admin.ModelAdmin):
    list_display = ("performed_at", "equipment", "kind", "performer", "cost")
    list_filter = ("kind", "performed_at")
