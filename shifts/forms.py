from __future__ import annotations

from django import forms
from django.utils import timezone

from core.forms import StyledModelForm
from shifts.models import Shift, ShiftCheck


class ShiftOpenForm(StyledModelForm):
    class Meta:
        model = Shift
        fields = ("date", "kind", "workshop", "opening_notes")
        widgets = {"opening_notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["date"].initial = timezone.localdate()


class ShiftCloseForm(StyledModelForm):
    class Meta:
        model = Shift
        fields = ("equipment_condition", "inventory_notes", "closing_notes", "handover_to")
        widgets = {
            "equipment_condition": forms.Textarea(attrs={"rows": 3}),
            "inventory_notes": forms.Textarea(attrs={"rows": 3}),
            "closing_notes": forms.Textarea(attrs={"rows": 3}),
        }


class ShiftCheckForm(StyledModelForm):
    class Meta:
        model = ShiftCheck
        fields = ("item", "condition", "wear_percent", "comment")
