import sys

from django.db import migrations


def move_hamba(apps, schema_editor):
    if "test" in sys.argv:
        return
    Equipment = apps.get_model("equipment", "Equipment")
    Workshop = apps.get_model("core", "Workshop")
    ProductionLine = apps.get_model("core", "ProductionLine")

    camera = Equipment.objects.filter(camera_id=2).first()
    if camera is None:
        return
    workshop = Workshop.objects.filter(name__in=["ПМЦ", "ЦМЦ"]).first()
    if workshop is None:
        return
    camera.workshop = workshop
    camera.line = ProductionLine.objects.filter(workshop=workshop, name="Humba").first()
    camera.save()


class Migration(migrations.Migration):

    dependencies = [
        ("equipment", "0008_assign_cameras"),
    ]

    operations = [
        migrations.RunPython(move_hamba, migrations.RunPython.noop),
    ]
