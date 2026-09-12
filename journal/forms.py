from __future__ import annotations

from django import forms

from core.forms import StyledModelForm
from journal.models import JournalEntry


class JournalEntryForm(StyledModelForm):
    class Meta:
        model = JournalEntry
        fields = (
            "received_at",
            "source_location",
            "workshop",
            "reported_by",
            "problem",
            "solution",
            "status",
            "priority",
            "assigned_to",
            "equipment",
        )
        widgets = {
            "received_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "problem": forms.Textarea(attrs={"rows": 4}),
            "solution": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["received_at"].input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"]


class JournalFilterForm(forms.Form):
    q = forms.CharField(
        label="Поиск",
        required=False,
        widget=forms.TextInput(attrs={"class": "field-input", "placeholder": "Проблема, место, автор..."}),
    )
