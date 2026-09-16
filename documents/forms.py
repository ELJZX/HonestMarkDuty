from __future__ import annotations

from django import forms

from core.forms import StyledModelForm
from documents.models import Document, DocumentTemplate

AUTO_PLACEHOLDERS = {
    "organization",
    "city",
    "workshop_name",
    "workshop_code",
    "chief",
    "chief_position",
    "site",
    "date",
    "date_long",
    "number",
    "author",
    "author_position",
    "title",
}

MULTILINE = {"content", "body", "reason", "description", "text", "justification", "essence"}


class DocumentTemplateForm(StyledModelForm):
    class Meta:
        model = DocumentTemplate
        fields = ("name", "doc_type", "title_template", "body", "workshops", "is_active")
        widgets = {
            "body": forms.Textarea(attrs={"rows": 16, "class": "field-input field-textarea code"}),
            "workshops": forms.SelectMultiple(attrs={"class": "field-input field-select"}),
        }
        help_texts = {
            "body": "Используйте поля вида {{ workshop_name }}, {{ chief }}, {{ date_long }} и т.д.",
        }


class DocumentForm(StyledModelForm):
    class Meta:
        model = Document
        fields = ("template", "workshop", "number", "doc_date")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.template_obj = self._resolve_template()
        existing = (self.instance.context_data or {}) if self.instance.pk else {}
        self.dynamic_field_names: list[str] = []

        if self.template_obj:
            for key in self.template_obj.placeholders:
                if key in AUTO_PLACEHOLDERS or key in self.fields:
                    continue
                widget = (
                    forms.Textarea(attrs={"class": "field-input", "rows": 4})
                    if key in MULTILINE
                    else forms.TextInput(attrs={"class": "field-input"})
                )
                self.fields[key] = forms.CharField(
                    label=key,
                    required=False,
                    widget=widget,
                    initial=existing.get(key, ""),
                )
                self.dynamic_field_names.append(key)

    def _resolve_template(self) -> DocumentTemplate | None:
        if self.is_bound:
            template_id = self.data.get("template")
        else:
            template_id = self.initial.get("template") or (
                self.instance.template_id if self.instance.pk else None
            )
        if not template_id:
            return None
        return DocumentTemplate.objects.filter(pk=template_id).first()

    @property
    def dynamic_fields(self):
        return [self[name] for name in self.dynamic_field_names]

    def collect_context(self) -> dict:
        return {name: self.cleaned_data.get(name, "") for name in self.dynamic_field_names}
