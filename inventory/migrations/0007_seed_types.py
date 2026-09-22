import os
import shutil
import sys

from django.conf import settings
from django.db import migrations

# (название типа, порядок, файл иконки в inventory/type_icons)
TYPES = [
    ("TSC PEX", 0, "type_1.png"),
    ("VideoJet", 0, "type_7.png"),
    ("Zebra", 0, "type_8.png"),
    ("Флешки", 0, "type_5.png"),
    ("Зап.части", 1, "type_2.jfif"),
    ("Datalogic", 2, "type_6.png"),
    ("Расходный материал", 2, ""),
    ("Разное", 3, ""),
]


def seed_types(apps, schema_editor):
    if "test" in sys.argv:
        return
    ItemType = apps.get_model("inventory", "ItemType")
    icons_dir = os.path.join(settings.BASE_DIR, "inventory", "type_icons")
    media_sub = os.path.join(settings.MEDIA_ROOT, "item_types")
    os.makedirs(media_sub, exist_ok=True)

    for name, order, icon in TYPES:
        item_type, _ = ItemType.objects.get_or_create(
            name=name, defaults={"sort_order": order}
        )
        if item_type.sort_order != order:
            item_type.sort_order = order
        if icon:
            source = os.path.join(icons_dir, icon)
            if os.path.exists(source):
                target = os.path.join(media_sub, icon)
                if not os.path.exists(target):
                    shutil.copyfile(source, target)
                item_type.image = f"item_types/{icon}"
        item_type.save()


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0006_itemtype_image"),
    ]

    operations = [
        migrations.RunPython(seed_types, migrations.RunPython.noop),
    ]
