from django.contrib import admin

from shifts.models import Shift, ShiftCheck


class ShiftCheckInline(admin.TabularInline):
    model = ShiftCheck
    extra = 0
    autocomplete_fields = ("item",)


@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ("date", "kind", "status", "accepted", "opened_by", "closed_by", "workshop")
    list_filter = ("status", "kind", "accepted", "date", "workshop")
    search_fields = (
        "opened_by__username",
        "opened_by__last_name",
        "closed_by__username",
        "closed_by__last_name",
        "external_id",
    )
    date_hierarchy = "date"
    list_select_related = ("opened_by", "closed_by", "workshop")
    autocomplete_fields = ("opened_by", "closed_by", "workshop", "handover_to")
    inlines = (ShiftCheckInline,)
    save_on_top = True


@admin.register(ShiftCheck)
class ShiftCheckAdmin(admin.ModelAdmin):
    list_display = ("shift", "item", "condition")
    list_filter = ("condition",)
    list_select_related = ("shift", "item")
    autocomplete_fields = ("shift", "item")
