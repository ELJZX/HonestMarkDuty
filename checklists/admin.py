from django.contrib import admin

from checklists.models import (
    ChecklistCheck,
    ChecklistGroup,
    ChecklistMachine,
    ChecklistMileage,
    ChecklistResult,
    EquipmentChecklist,
)


class ChecklistMachineInline(admin.TabularInline):
    model = ChecklistMachine
    extra = 0


@admin.register(ChecklistGroup)
class ChecklistGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "sort_order")
    inlines = (ChecklistMachineInline,)


@admin.register(ChecklistMachine)
class ChecklistMachineAdmin(admin.ModelAdmin):
    list_display = ("name", "group", "sort_order")
    list_filter = ("group",)


@admin.register(ChecklistCheck)
class ChecklistCheckAdmin(admin.ModelAdmin):
    list_display = ("name", "sort_order")


class ChecklistResultInline(admin.TabularInline):
    model = ChecklistResult
    extra = 0


class ChecklistMileageInline(admin.TabularInline):
    model = ChecklistMileage
    extra = 0


@admin.register(EquipmentChecklist)
class EquipmentChecklistAdmin(admin.ModelAdmin):
    list_display = ("date", "workshop", "performed_by", "status", "shift")
    list_filter = ("status", "date", "workshop")
    inlines = (ChecklistMileageInline, ChecklistResultInline)
