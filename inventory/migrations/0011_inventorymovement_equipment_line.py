from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0010_remove_inventoryitem_wear_percent_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="inventorymovement",
            name="equipment_line",
            field=models.CharField(
                blank=True,
                help_text="Куда установлена запчасть (линия или оборудование).",
                max_length=200,
                verbose_name="Линия/оборудование",
            ),
        ),
    ]
