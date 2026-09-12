from django.contrib import admin

from documents.models import Document, DocumentTemplate


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "doc_type", "is_active")
    list_filter = ("doc_type", "is_active")
    search_fields = ("name", "title_template")
    filter_horizontal = ("workshops",)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "template", "workshop", "number", "doc_date", "status", "created_by")
    list_filter = ("status", "template__doc_type", "workshop")
    search_fields = ("title", "number", "body")
    date_hierarchy = "doc_date"
