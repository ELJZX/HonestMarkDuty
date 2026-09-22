"""Загрузка/обновление склада отдела «Честный знак».

    python manage.py seed_sklad
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from inventory.models import InventoryItem, ItemCategory, StorageLocation
from inventory.sklad_data import CATEGORIES, LOCATION_DESC, LOCATION_NAME, LOCATION_SHELF, SKLAD

NOTES = "Загружено из sklad.xlsx (конечный остаток)"


class Command(BaseCommand):
    help = "Загружает и обновляет позиции склада отдела «Честный знак»"

    def handle(self, *args, **options):
        categories = {
            kind: ItemCategory.objects.get_or_create(name=name, defaults={"kind": kind})[0]
            for kind, name in CATEGORIES.items()
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
                    "kind": kind,
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
