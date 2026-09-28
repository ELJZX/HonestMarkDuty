from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("services", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="service",
            name="kind",
            field=models.CharField(
                choices=[("service", "Сервис"), ("site", "Сайт")],
                default="service",
                max_length=20,
                verbose_name="Вид",
            ),
        ),
    ]
