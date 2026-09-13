from __future__ import annotations

from django import forms

from checklists.models import EquipmentChecklist
from core.forms import StyledModelForm


class ChecklistForm(StyledModelForm):
    class Meta:
        model = EquipmentChecklist
        fields = ("date", "workshop", "performed_by", "note")
        widgets = {"note": forms.Textarea(attrs={"rows": 2})}
