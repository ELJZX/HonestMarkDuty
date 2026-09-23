from django.contrib import admin

from shifts.models import Shift, ShiftCheck


class ShiftCheckInline(admin.TabularInline):
    model = ShiftCheck
    extra = 0


@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ("date", "kind", "status", "opened_by", "closed_by", "workshop")
    list_filter = ("status", "kind", "date", "workshop")
    search_fields = ("opened_by__username", "closed_by__username")
    inlines = (ShiftCheckInline,)


@admin.register(ShiftCheck)
class ShiftCheckAdmin(admin.ModelAdmin):
    list_display = ("shift", "item", "condition")
    list_filter = ("condition",)
