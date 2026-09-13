from django.contrib import admin

from journal.models import JournalEntry, JournalExport


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ("occurred_at", "specialist", "equipment_line", "action_task", "entry_type")
    list_filter = ("entry_type", "specialist")
    search_fields = ("action_task", "solution", "equipment_line")
    date_hierarchy = "occurred_at"


@admin.register(JournalExport)
class JournalExportAdmin(admin.ModelAdmin):
    list_display = ("created_at", "entries_count", "is_full", "shift", "created_by", "file")
    list_filter = ("is_full", "created_at")
