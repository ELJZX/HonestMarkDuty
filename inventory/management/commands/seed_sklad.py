"""Загрузка/обновление склада отдела «Честный знак».

    python manage.py seed_sklad
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from inventory.models import InventoryItem, ItemCategory, ItemType, StorageLocation
from inventory.sklad_data import CATEGORIES, LOCATION_DESC, LOCATION_NAME, LOCATION_SHELF, SKLAD

NOTES = "Загружено из sklad.xlsx (конечный остаток)"

TYPE_NAMES = {
    "tool": "Инструмент",
    "spare": "Запасная часть",
    "consumable": "Расходный материал",
    "device": "Прибор/средство",
}


class Command(BaseCommand):
    help = "Загружает и обновляет позиции склада отдела «Честный знак»"

    def handle(self, *args, **options):
        types = {
            code: ItemType.objects.get_or_create(name=name, defaults={"sort_order": order})[0]
            for order, (code, name) in enumerate(TYPE_NAMES.items())
        }
        categories = {
            code: ItemCategory.objects.update_or_create(
                name=name, defaults={"kind": types[code]}
            )[0]
            for code, name in CATEGORIES.items()
        }
        location, _ = StorageLocation.objects.update_or_create(
            name=LOCATION_NAME,
            defaults={"shelf_code": LOCATION_SHELF, "description": LOCATION_DESC},
        )

        created = updated = 0
        for name, quantity, unit, kind in SKLAD:
            _, is_new = InventoryItem.objects.update_or_create(
                name=name,
                location=location,
                defaults={
                    "kind": types[kind],
                    "category": categories[kind],
                    "quantity": quantity,
                    "min_quantity": 0,
                    "unit": unit,
                    "notes": NOTES,
                },
            )
            if is_new:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Склад «Честный знак»: создано {created}, обновлено {updated}, всего {len(SKLAD)}."
            )
        )
