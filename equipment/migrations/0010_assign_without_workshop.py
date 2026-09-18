import sys

from django.db import migrations


def assign_without_workshop(apps, schema_editor):
    if "test" in sys.argv:
        return
    Equipment = apps.get_model("equipment", "Equipment")
    Workshop = apps.get_model("core", "Workshop")

    cameras = Equipment.objects.filter(is_camera=True, workshop__isnull=True)
    if not cameras.exists():
        return

    workshop = Workshop.objects.filter(name__in=["ПМЦ", "ЦМЦ"]).first()
    if workshop is None:
        workshop = Workshop.objects.filter(code__in=["ПМЦ", "ЦМЦ"]).first()
    if workshop is None:
        workshop = Workshop.objects.create(name="ЦМЦ", code="ЦМЦ", is_active=True)

    cameras.update(workshop=workshop)


class Migration(migrations.Migration):

    dependencies = [
        ("equipment", "0009_move_hamba_camera"),
    ]

    operations = [
        migrations.RunPython(assign_without_workshop, migrations.RunPython.noop),
    ]
