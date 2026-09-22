"""Загрузка/обновление склада отдела «Честный знак».

    python manage.py seed_sklad

Обновляет только наименование/количество/единицу/склад. Типы и категории,
которые пользователь задал вручную, команда НЕ перезаписывает.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from inventory.models import InventoryItem, Storage, StorageLocation
from inventory.sklad_data import LOCATION_DESC, LOCATION_NAME, LOCATION_SHELF, SKLAD, STORAGE_NAME

NOTES = "Загружено из sklad.xlsx (конечный остаток)"


class Command(BaseCommand):
    help = "Загружает и обновляет позиции склада отдела «Честный знак»"

    def handle(self, *args, **options):
        location, _ = StorageLocation.objects.update_or_create(
            name=LOCATION_NAME,
            defaults={"shelf_code": LOCATION_SHELF, "description": LOCATION_DESC},
        )
        storage, _ = Storage.objects.get_or_create(name=STORAGE_NAME, defaults={"sort_order": 0})

        created = updated = 0
        for name, quantity, unit, _kind in SKLAD:
            item, is_new = InventoryItem.objects.get_or_create(
                name=name,
                location=location,
                defaults={
                    "storage": storage,
                    "quantity": quantity,
                    "min_quantity": 0,
                    "unit": unit,
                    "notes": NOTES,
                },
            )
            if is_new:
                created += 1
            else:
                # тип/категорию пользователя не трогаем
                item.quantity = quantity
                item.unit = unit
                item.storage = item.storage or storage
                item.notes = NOTES
                item.save(update_fields=["quantity", "unit", "storage", "notes", "updated_at"])
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Склад «Честный знак»: создано {created}, обновлено {updated}, всего {len(SKLAD)}."
            )
        )
