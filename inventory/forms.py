from __future__ import annotations

from django import forms

from core.forms import StyledModelForm
from inventory.models import (
    InventoryItem,
    InventoryMovement,
    ItemCategory,
    ItemType,
    Storage,
    StorageLocation,
)


class InventoryItemForm(StyledModelForm):
    class Meta:
        model = InventoryItem
        fields = (
            "name",
            "inventory_number",
            "kind",
            "category",
            "location",
            "storage",
            "quantity",
            "min_quantity",
            "unit",
            "condition",
            "serial_number",
            "manufactured_at",
            "last_verified_at",
            "notes",
            "is_active",
        )
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class InventoryMovementForm(StyledModelForm):
    class Meta:
        model = InventoryMovement
        fields = ("movement_type", "quantity", "comment")

    def clean_quantity(self):
        quantity = self.cleaned_data["quantity"]
        if self.instance.pk is None and quantity < 0:
            raise forms.ValidationError("Количество не может быть отрицательным.")
        return quantity


class StorageLocationForm(StyledModelForm):
    class Meta:
        model = StorageLocation
        fields = ("name", "shelf_code", "workshop", "description")


class ItemCategoryForm(StyledModelForm):
    class Meta:
        model = ItemCategory
        fields = ("name", "kind")


class ItemTypeForm(StyledModelForm):
    class Meta:
        model = ItemType
        fields = ("name", "sort_order", "image")


class StorageForm(StyledModelForm):
    class Meta:
        model = Storage
        fields = ("name", "sort_order", "image")
