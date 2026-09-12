from __future__ import annotations

from django import forms

from core.forms import StyledModelForm
from equipment.models import (
    Equipment,
    EquipmentCategory,
    EquipmentStatusLog,
    MaintenanceRecord,
)


class EquipmentForm(StyledModelForm):
    class Meta:
        model = Equipment
        fields = (
            "name",
            "inventory_number",
            "category",
            "site",
            "workshop",
            "manufacturer",
            "model_name",
            "serial_number",
            "commissioned_at",
            "status",
            "criticality",
            "last_maintenance_at",
            "next_maintenance_at",
            "responsible",
            "notes",
            "is_active",
        )
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}


class EquipmentStatusLogForm(StyledModelForm):
    class Meta:
        model = EquipmentStatusLog
        fields = ("status", "comment")
        widgets = {"comment": forms.Textarea(attrs={"rows": 3})}


class MaintenanceRecordForm(StyledModelForm):
    class Meta:
        model = MaintenanceRecord
        fields = ("kind", "performed_at", "description", "performer", "cost")
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class EquipmentCategoryForm(StyledModelForm):
    class Meta:
        model = EquipmentCategory
        fields = ("name", "description")
