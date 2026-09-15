from __future__ import annotations

from django import forms

from checklists.models import EquipmentChecklist, MarkemChecklist
from core.forms import StyledModelForm


class ChecklistForm(StyledModelForm):
    class Meta:
        model = EquipmentChecklist
        fields = ("date", "performed_by", "note")
        widgets = {"note": forms.Textarea(attrs={"rows": 2})}


class MarkemForm(StyledModelForm):
    class Meta:
        model = MarkemChecklist
        fields = ("date", "performed_by", "checked_by", "note")
        widgets = {"note": forms.Textarea(attrs={"rows": 2})}
