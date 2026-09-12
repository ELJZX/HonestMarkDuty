from django.contrib import admin

from journal.models import JournalEntry, JournalExport


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ("received_at", "source_location", "problem", "status", "priority", "assigned_to")
    list_filter = ("status", "priority", "workshop")
    search_fields = ("source_location", "problem", "solution", "reported_by")
    date_hierarchy = "received_at"


@admin.register(JournalExport)
class JournalExportAdmin(admin.ModelAdmin):
    list_display = ("created_at", "entries_count", "shift", "created_by", "file")
    list_filter = ("created_at",)
