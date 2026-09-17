import sys

from django.db import migrations

STRUCTURE = [
    ("Цех №1", "ЦЕХ1", ["New Serac", "Ecolean 1", "FP 1", "FP 2", "FP 3", "Old Serac"]),
    ("КМЦ", "КМЦ", ["AVE", "Finnah", "Trepko", "C3 Flex", "Джонга 1,2"]),
    ("ПМЦ", "ПМЦ", ["Humba"]),
    ("ПСМ", "ПСМ", ["Школьник (А1(1),А1(2))", "EL4", "A3 Flex", "Serac"]),
    ("Творожный цех", "ТВЦ", ["SB 3", "Mondini 4", "SP 4", "SP3", "SP 2", "SP1"]),
]


def seed_structure(apps, schema_editor):
    if "test" in sys.argv:
        return
    Workshop = apps.get_model("core", "Workshop")
    ProductionLine = apps.get_model("core", "ProductionLine")

    for w_index, (name, code, lines) in enumerate(STRUCTURE):
        workshop = Workshop.objects.filter(name=name).first()
        if workshop is None:
            workshop = Workshop.objects.create(
                name=name, code=code, sort_order=w_index, is_active=True
            )
        else:
            workshop.sort_order = w_index
            workshop.is_active = True
            workshop.save()
        for l_index, line_name in enumerate(lines):
            line = ProductionLine.objects.filter(workshop=workshop, name=line_name).first()
            if line is None:
                ProductionLine.objects.create(
                    workshop=workshop, name=line_name, sort_order=l_index, is_active=True
                )
            else:
                line.sort_order = l_index
                line.is_active = True
                line.save()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_workshop_sort_order"),
    ]

    operations = [
        migrations.RunPython(seed_structure, migrations.RunPython.noop),
    ]
