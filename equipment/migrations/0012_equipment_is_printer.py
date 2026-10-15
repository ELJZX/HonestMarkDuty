import sys

from django.db import migrations, models


def mark_printers(apps, schema_editor):
    if "test" in sys.argv:
        return
    Equipment = apps.get_model("equipment", "Equipment")
    Equipment.objects.filter(name__icontains="принтер").update(is_printer=True)


class Migration(migrations.Migration):

    dependencies = [
        ("equipment", "0011_remove_equipment_category_delete_equipmentcategory"),
    ]

    operations = [
        migrations.AddField(
            model_name="equipment",
            name="is_printer",
            field=models.BooleanField(default=False, verbose_name="Принтер"),
        ),
        migrations.RunPython(mark_printers, migrations.RunPython.noop),
    ]
