from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("equipment", "0012_equipment_is_printer"),
    ]

    operations = [
        migrations.CreateModel(
            name="Camera",
            fields=[],
            options={
                "verbose_name": "Камера",
                "verbose_name_plural": "Камеры",
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("equipment.equipment",),
        ),
    ]
