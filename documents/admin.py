from django.contrib import admin

from documents.models import Document, DocumentTemplate


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "doc_type", "is_active")
    list_filter = ("doc_type", "is_active")
    search_fields = ("name", "title_template")
    filter_horizontal = ("workshops",)
    save_on_top = True


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("number", "kind", "workshop", "doc_date", "created_by", "template")
    list_filter = ("kind", "workshop", "doc_date")
    search_fields = ("number", "title", "body")
    date_hierarchy = "doc_date"
    list_select_related = ("workshop", "created_by", "template")
    autocomplete_fields = ("template", "workshop", "created_by")
    save_on_top = True
