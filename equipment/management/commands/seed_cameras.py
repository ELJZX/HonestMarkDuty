"""Камеры Camera Control, распределённые по цехам и линиям.

python manage.py seed_cameras
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from core.models import ProductionLine, Workshop
from equipment.models import Equipment, EquipmentCategory

# (id камеры в Camera Control, цех, линия, IP)
CAMERAS = [
    (5, "КМЦ", "AVE", "172.16.52.121"),
    (4, "КМЦ", "C3 Flex", "172.16.52.111"),
    (8, "КМЦ", "Finna", "172.16.52.115"),
    (11, "КМЦ", "Trepko", "172.16.52.107"),
    (24, "КМЦ", "Zhongya. Левая", "172.16.52.126"),
    (23, "КМЦ", "Zhongya. Правая", "172.16.52.125"),
    (19, "Творожный цех", "Mondini4", "172.16.55.108"),
    (16, "Творожный цех", "SignalPack 1", "172.16.55.101"),
    (15, "Творожный цех", "SignalPack 2", "172.16.55.103"),
    (18, "Творожный цех", "SignalPack3", "172.16.55.107"),
    (20, "Творожный цех", "SignalPack4", "172.16.55.120"),
    (17, "Творожный цех", "Стабилобэг", "172.16.55.105"),
    (1, "ЦМЦ", "Хамба. Левая", "172.16.52.147"),
    (2, "ЦСМ", "Хамба. Правая", "172.16.52.148"),
    (22, "ЦСМ", "A3Flex", "172.16.54.10"),
    (3, "ЦСМ", "Ecolean 4", "172.16.54.33"),
    (21, "ЦСМ", "SeracAseptic1", "172.16.54.8"),
    (7, "Цех №1", "Ecoline 1 (Master)", "172.16.52.132"),
    (6, "Цех №1", "Ecoline 1 (Slave)", "172.16.52.137"),
    (12, "Цех №1", "FinPack 1", "172.16.52.105"),
    (13, "Цех №1", "FinPack 2", "172.16.52.103"),
    (14, "Цех №1", "FinPack 3", "172.16.52.101"),
    (9, "Цех №1", "Serac NEW", "172.16.52.117"),
    (10, "Цех №1", "Serac OLD", "172.16.52.109"),
]

# Соответствие названий цехов в Camera Control названиям в системе
WORKSHOP_ALIASES = {
    "Цех №1": ["Цех №1", "Цех#1", "Цех 1"],
    "КМЦ": ["КМЦ"],
    "Творожный цех": ["Творожный цех"],
    "ПМЦ": ["ПМЦ", "ЦМЦ"],
    "ПСМ": ["ПСМ", "ЦСМ"],
}

# Соответствие названий линий камер названиям линий в системе
LINE_ALIASES = {
    "Цех №1": {
        "FinPack 1": "FP 1",
        "FinPack 2": "FP 2",
        "FinPack 3": "FP 3",
        "Serac NEW": "New Serac",
        "Serac OLD": "Old Serac",
        "Ecoline 1 (Master)": "Ecolean 1",
        "Ecoline 1 (Slave)": "Ecolean 1",
    },
    "КМЦ": {
        "Finna": "Finnah",
        "Zhongya. Левая": "Джонга 1,2",
        "Zhongya. Правая": "Джонга 1,2",
    },
    "Творожный цех": {
        "Mondini4": "Mondini 4",
        "SignalPack 1": "SP1",
        "SignalPack 2": "SP 2",
        "SignalPack3": "SP3",
        "SignalPack4": "SP 4",
        "Стабилобэг": "SB 3",
    },
    "ПМЦ": {"Хамба. Левая": "Humba", "Хамба. Правая": "Humba"},
    "ПСМ": {"A3Flex": "A3 Flex", "Ecolean 4": "EL4", "SeracAseptic1": "Serac"},
}


class Command(BaseCommand):
    help = "Создаёт оборудование-камеры и распределяет их по цехам и линиям"

    def _resolve_workshop(self, hint: str):
        for canonical, aliases in WORKSHOP_ALIASES.items():
            if hint in aliases:
                workshop = Workshop.objects.filter(name__in=aliases).first()
                if workshop:
                    return canonical, workshop
        return None, None

    def handle(self, *args, **options):
        verbose = options.get("verbosity", 1) > 0
        category, _ = EquipmentCategory.objects.get_or_create(name="Камера")
        created = updated = 0
        for camera_id, workshop_hint, line_hint, ip in CAMERAS:
            canonical, workshop = self._resolve_workshop(workshop_hint)
            line = None
            if canonical:
                line_name = LINE_ALIASES.get(canonical, {}).get(line_hint, line_hint)
                if line_name:
                    line = ProductionLine.objects.filter(
                        workshop=workshop, name=line_name
                    ).first()
            defaults = {
                "name": line_hint,
                "category": category,
                "workshop": workshop,
                "line": line,
                "ip_address": ip,
                "manufacturer": "Datalogic",
                "model_name": "Matrix 220",
                "is_active": True,
            }
            equipment = Equipment.objects.filter(camera_id=camera_id).first()
            if equipment is None:
                Equipment.objects.create(camera_id=camera_id, **defaults)
                created += 1
            else:
                for field, value in defaults.items():
                    setattr(equipment, field, value)
                equipment.save()
                updated += 1

        if not verbose:
            return
        self.stdout.write(
            self.style.SUCCESS(
                f"Камеры: создано {created}, обновлено {updated}, всего {len(CAMERAS)}."
            )
        )
