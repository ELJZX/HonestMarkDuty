from django.contrib import admin

from inventory.models import (
    InventoryItem,
    InventoryMovement,
    ItemCategory,
    ItemType,
    Storage,
    StorageLocation,
)


@admin.register(Storage)
class StorageAdmin(admin.ModelAdmin):
    list_display = ("name", "sort_order")
    search_fields = ("name",)


@admin.register(ItemType)
class ItemTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "sort_order")
    search_fields = ("name",)


@admin.register(StorageLocation)
class StorageLocationAdmin(admin.ModelAdmin):
    list_display = ("name", "shelf_code", "workshop", "description")
    list_filter = ("workshop",)
    search_fields = ("name", "shelf_code")


@admin.register(ItemCategory)
class ItemCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "kind")
    list_filter = ("kind",)


class InventoryMovementInline(admin.TabularInline):
    model = InventoryMovement
    extra = 0
    readonly_fields = ("created_at", "created_by")


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "storage", "location", "quantity", "unit", "condition")
    list_filter = ("kind", "condition", "storage", "location", "is_active")
    search_fields = ("name", "inventory_number", "serial_number")
    inlines = (InventoryMovementInline,)


@admin.register(InventoryMovement)
class InventoryMovementAdmin(admin.ModelAdmin):
    list_display = ("created_at", "item", "movement_type", "quantity", "created_by")
    list_filter = ("movement_type",)
