from __future__ import annotations

from django import forms

from core.forms import StyledModelForm
from journal.models import JournalEntry


class JournalEntryForm(StyledModelForm):
    class Meta:
        model = JournalEntry
        fields = (
            "occurred_at",
            "specialist",
            "equipment_line",
            "downtime",
            "action_task",
            "solution",
            "print_head",
            "mileage",
        )
        widgets = {
            "occurred_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
            "action_task": forms.Textarea(attrs={"rows": 3}),
            "solution": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["occurred_at"].input_formats = [
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
        ]
