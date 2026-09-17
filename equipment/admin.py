from django.contrib import admin

from equipment.models import (
    Equipment,
    EquipmentCategory,
    EquipmentStatusLog,
    MaintenanceRecord,
)


@admin.register(EquipmentCategory)
class EquipmentCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name",)


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
    list_display = ("name", "site", "workshop", "line", "status", "criticality")
    list_filter = ("status", "criticality", "site", "workshop", "line", "category")
    search_fields = ("name", "serial_number", "model_name")
    inlines = (EquipmentStatusLogInline, MaintenanceRecordInline)


@admin.register(MaintenanceRecord)
class MaintenanceRecordAdmin(admin.ModelAdmin):
    list_display = ("performed_at", "equipment", "kind", "performer", "cost")
    list_filter = ("kind", "performed_at")
