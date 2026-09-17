from __future__ import annotations

from django import forms

from core.forms import StyledModelForm
from core.models import ProductionLine
from equipment.models import (
    Equipment,
    EquipmentCategory,
    EquipmentStatusLog,
    MaintenanceRecord,
)


# Шаблоны быстрого добавления оборудования
EQUIPMENT_PRESETS = [
    {
        "label": "Терминал · ASUS · Tinkerboard 2S",
        "name": "Терминал",
        "manufacturer": "ASUS",
        "model_name": "Tinkerboard 2S",
        "category": "Терминал",
        "fields": "",
    },
    {
        "label": "Камера · Datalogic · Matrix 220",
        "name": "Камера",
        "manufacturer": "Datalogic",
        "model_name": "Matrix 220",
        "category": "Камера",
        "fields": "ip_address",
    },
    {
        "label": "Принтер · VideoJet · 6330 / 6630",
        "name": "Принтер",
        "manufacturer": "VideoJet",
        "model_name": "6330 / 6630",
        "category": "Принтер",
        "fields": "ip_address,print_head",
    },
    {
        "label": "Принтер · TSC · PEX",
        "name": "Принтер",
        "manufacturer": "TSC",
        "model_name": "PEX",
        "category": "Принтер",
        "fields": "ip_address",
    },
    {
        "label": "Принтер · Markem Imaje · 9450",
        "name": "Принтер",
        "manufacturer": "Markem Imaje",
        "model_name": "9450",
        "category": "Принтер",
        "fields": "ip_address,slot",
    },
]


class EquipmentForm(StyledModelForm):
    class Meta:
        model = Equipment
        fields = (
            "name",
            "workshop",
            "line",
            "manufacturer",
            "model_name",
            "ip_address",
            "print_head",
            "notes",
        )
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
            "ip_address": forms.TextInput(attrs={"placeholder": "192.168.0.10"}),
            "print_head": forms.TextInput(attrs={"placeholder": "32 / 53"}),
        }

    def clean(self):
        cleaned = super().clean()
        line = cleaned.get("line")
        if line and not cleaned.get("workshop"):
            cleaned["workshop"] = line.workshop
        return cleaned


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


class ProductionLineForm(StyledModelForm):
    class Meta:
        model = ProductionLine
        fields = ("workshop", "name", "code", "sort_order", "description", "is_active")
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}
