from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="changes_seen_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Последний приём смены: с этой даты показываются изменения в сервисах.",
                null=True,
                verbose_name="История изменений просмотрена",
            ),
        ),
    ]
