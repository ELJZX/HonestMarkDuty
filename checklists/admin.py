from django.contrib import admin

from checklists.models import (
    ChecklistCheck,
    ChecklistGroup,
    ChecklistMachine,
    ChecklistMileage,
    ChecklistResult,
    EquipmentChecklist,
    MarkemChecklist,
    MarkemParameter,
    MarkemPrinter,
    MarkemValue,
)


class ChecklistMachineInline(admin.TabularInline):
    model = ChecklistMachine
    extra = 0
    fields = ("name", "sort_order")
    ordering = ("sort_order", "name")


@admin.register(ChecklistGroup)
class ChecklistGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "sort_order")
    search_fields = ("name",)
    list_editable = ("sort_order",)
    inlines = (ChecklistMachineInline,)
    save_on_top = True


@admin.register(ChecklistMachine)
class ChecklistMachineAdmin(admin.ModelAdmin):
    list_display = ("name", "group", "sort_order")
    list_filter = ("group",)
    search_fields = ("name",)
    list_select_related = ("group",)
    autocomplete_fields = ("group",)
    ordering = ("group", "sort_order", "name")


@admin.register(ChecklistCheck)
class ChecklistCheckAdmin(admin.ModelAdmin):
    list_display = ("name", "sort_order")
    search_fields = ("name",)
    list_editable = ("sort_order",)
    save_on_top = True


class ChecklistResultInline(admin.TabularInline):
    model = ChecklistResult
    extra = 0
    autocomplete_fields = ("machine", "check_item")


class ChecklistMileageInline(admin.TabularInline):
    model = ChecklistMileage
    extra = 0
    autocomplete_fields = ("machine",)


@admin.register(EquipmentChecklist)
class EquipmentChecklistAdmin(admin.ModelAdmin):
    list_display = ("date", "workshop", "performed_by", "status", "shift")
    list_filter = ("status", "date", "workshop")
    search_fields = ("performed_by__last_name", "note")
    date_hierarchy = "date"
    list_select_related = ("workshop", "performed_by", "shift")
    autocomplete_fields = ("workshop", "performed_by", "shift", "created_by")
    inlines = (ChecklistMileageInline, ChecklistResultInline)


@admin.register(MarkemPrinter)
class MarkemPrinterAdmin(admin.ModelAdmin):
    list_display = ("name", "sort_order")
    search_fields = ("name",)
    list_editable = ("sort_order",)
    save_on_top = True


@admin.register(MarkemParameter)
class MarkemParameterAdmin(admin.ModelAdmin):
    list_display = ("name", "sort_order")
    search_fields = ("name",)
    list_editable = ("sort_order",)
    save_on_top = True


class MarkemValueInline(admin.TabularInline):
    model = MarkemValue
    extra = 0
    autocomplete_fields = ("printer", "parameter")


@admin.register(MarkemChecklist)
class MarkemChecklistAdmin(admin.ModelAdmin):
    list_display = ("date", "performed_by", "checked_by", "status")
    list_filter = ("status", "date")
    search_fields = ("performed_by__last_name", "note")
    date_hierarchy = "date"
    list_select_related = ("performed_by", "checked_by", "shift")
    autocomplete_fields = ("performed_by", "checked_by", "shift", "created_by")
    inlines = (MarkemValueInline,)
