import sys

from django.db import migrations

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

WORKSHOP_ALIASES = {
    "Цех №1": ["Цех №1", "Цех#1", "Цех 1"],
    "КМЦ": ["КМЦ"],
    "Творожный цех": ["Творожный цех"],
    "ПМЦ": ["ПМЦ", "ЦМЦ"],
    "ПСМ": ["ПСМ", "ЦСМ"],
}

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


def seed_cameras(apps, schema_editor):
    if "test" in sys.argv:
        return
    Equipment = apps.get_model("equipment", "Equipment")
    EquipmentCategory = apps.get_model("equipment", "EquipmentCategory")
    Workshop = apps.get_model("core", "Workshop")
    ProductionLine = apps.get_model("core", "ProductionLine")

    category, _ = EquipmentCategory.objects.get_or_create(name="Камера")

    for camera_id, workshop_hint, line_hint, ip in CAMERAS:
        canonical = None
        workshop = None
        for name, aliases in WORKSHOP_ALIASES.items():
            if workshop_hint in aliases:
                canonical = name
                workshop = Workshop.objects.filter(name__in=aliases).first()
                break
        line = None
        if canonical and workshop:
            line_name = LINE_ALIASES.get(canonical, {}).get(line_hint, line_hint)
            line = ProductionLine.objects.filter(workshop=workshop, name=line_name).first()

        defaults = {
            "name": line_hint,
            "category": category,
            "workshop": workshop,
            "line": line,
            "ip_address": ip,
            "manufacturer": "Datalogic",
            "model_name": "Matrix 220",
            "is_camera": True,
            "is_active": True,
        }
        existing = Equipment.objects.filter(camera_id=camera_id).first()
        if existing is None:
            Equipment.objects.create(camera_id=camera_id, **defaults)
        else:
            for field, value in defaults.items():
                setattr(existing, field, value)
            existing.save()


class Migration(migrations.Migration):

    dependencies = [
        ("equipment", "0006_equipment_is_camera"),
    ]

    operations = [
        migrations.RunPython(seed_cameras, migrations.RunPython.noop),
    ]
