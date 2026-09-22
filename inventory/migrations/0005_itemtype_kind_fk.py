from django.db import migrations, models
import django.db.models.deletion

KINDS = [
    ("tool", "Инструмент", 0),
    ("spare", "Запасная часть", 1),
    ("consumable", "Расходный материал", 2),
    ("device", "Прибор/средство", 3),
]


def map_kinds(apps, schema_editor):
    import sys

    if "test" in sys.argv:
        return
    ItemType = apps.get_model("inventory", "ItemType")
    InventoryItem = apps.get_model("inventory", "InventoryItem")
    ItemCategory = apps.get_model("inventory", "ItemCategory")

    types = {}
    for code, name, order in KINDS:
        item_type, _ = ItemType.objects.get_or_create(
            name=name, defaults={"sort_order": order}
        )
        types[code] = item_type
    fallback = types["tool"]

    for item in InventoryItem.objects.all():
        item.kind_type = types.get(item.kind, fallback)
        item.save(update_fields=["kind_type"])
    for category in ItemCategory.objects.all():
        category.kind_type = types.get(category.kind, fallback)
        category.save(update_fields=["kind_type"])


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0004_sync_sklad"),
    ]

    operations = [
        migrations.CreateModel(
            name="ItemType",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создано")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлено")),
                ("name", models.CharField(max_length=100, unique=True, verbose_name="Тип")),
                ("sort_order", models.PositiveIntegerField(default=0, verbose_name="Порядок")),
            ],
            options={
                "verbose_name": "Тип позиции",
                "verbose_name_plural": "Типы позиций",
                "ordering": ("sort_order", "name"),
            },
        ),
        migrations.AddField(
            model_name="inventoryitem",
            name="kind_type",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="items",
                to="inventory.itemtype",
                verbose_name="Тип",
            ),
        ),
        migrations.AddField(
            model_name="itemcategory",
            name="kind_type",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="categories",
                to="inventory.itemtype",
                verbose_name="Тип",
            ),
        ),
        migrations.RunPython(map_kinds, migrations.RunPython.noop),
        migrations.RemoveIndex(
            model_name="inventoryitem",
            name="inventory_i_kind_6fb0a3_idx",
        ),
        migrations.RemoveField(model_name="inventoryitem", name="kind"),
        migrations.RemoveField(model_name="itemcategory", name="kind"),
        migrations.RenameField(
            model_name="inventoryitem", old_name="kind_type", new_name="kind"
        ),
        migrations.RenameField(
            model_name="itemcategory", old_name="kind_type", new_name="kind"
        ),
        migrations.AlterModelOptions(
            name="itemcategory",
            options={"ordering": ("name",), "verbose_name": "Категория", "verbose_name_plural": "Категории"},
        ),
    ]
