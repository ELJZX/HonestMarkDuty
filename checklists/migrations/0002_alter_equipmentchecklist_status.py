from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("checklists", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="equipmentchecklist",
            name="status",
            field=models.CharField(
                choices=[("draft", "В работе"), ("final", "Сформирован")],
                default="draft",
                max_length=10,
                verbose_name="Статус",
            ),
        ),
    ]
