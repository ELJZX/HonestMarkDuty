from __future__ import annotations

from django import forms

from core.models import ProductionSite, Workshop


class WorkshopForm(forms.ModelForm):
    class Meta:
        model = Workshop
        fields = ("name", "code", "site", "chief", "chief_position", "phone", "description", "is_active")
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class ProductionSiteForm(forms.ModelForm):
    class Meta:
        model = ProductionSite
        fields = ("name", "address", "responsible", "description", "is_active")
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class StyledFormMixin:
    """Единообразное оформление полей ввода для любой формы."""

    def _style_fields(self):
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
                widget.attrs.setdefault("class", "field-checkbox")
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                widget.attrs.setdefault("class", "field-input field-select")
            elif isinstance(widget, forms.Textarea):
                widget.attrs.setdefault("class", "field-input field-textarea")
                widget.attrs.setdefault("rows", 4)
            elif isinstance(widget, forms.DateInput):
                widget.attrs.setdefault("class", "field-input")
                widget.input_type = "date"
            elif isinstance(widget, forms.DateTimeInput):
                widget.attrs.setdefault("class", "field-input")
                widget.input_type = "datetime-local"
            else:
                widget.attrs.setdefault("class", "field-input")
            if field.required:
                widget.attrs.setdefault("required", "required")


class StyledModelForm(StyledFormMixin, forms.ModelForm):
    """ModelForm, который единообразно оформляет все поля ввода."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
