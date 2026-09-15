from django.db import migrations

PRINTERS = [
    "FR21250291",
    "FR21250290",
    "FR21400242",
    "FR21270099",
    "FR21400227",
    "FR21400219",
    "FR21270124",
    "FR21400249",
    "FR21250289",
    "FR21400243",
    "FR21400217",
    "FR21270122",
]

PARAMETERS = [
    "Счетчик принтера (ч)",
    "Эталонная вязкость (с)",
    "Вязкость (с)",
    "Значение Piezo",
    "Счетчик работы чернильной системы (ч)",
    "Месторасположение",
    "Номера ошибок (при наличии)",
    (
        "Значение параметров: Давление чернил (бар), Частота вращения двигателя (об/мин), "
        "Уровень рекуперации, имеют ли отклонения от нормы в режиме «Готов»?"
    ),
    "Комментарий",
]


def seed_defaults(apps, schema_editor):
    MarkemPrinter = apps.get_model("checklists", "MarkemPrinter")
    MarkemParameter = apps.get_model("checklists", "MarkemParameter")
    for index, name in enumerate(PRINTERS):
        MarkemPrinter.objects.get_or_create(name=name, defaults={"sort_order": index})
    for index, name in enumerate(PARAMETERS):
        MarkemParameter.objects.get_or_create(name=name, defaults={"sort_order": index})


def unseed_defaults(apps, schema_editor):
    MarkemPrinter = apps.get_model("checklists", "MarkemPrinter")
    MarkemParameter = apps.get_model("checklists", "MarkemParameter")
    MarkemPrinter.objects.filter(name__in=PRINTERS).delete()
    MarkemParameter.objects.filter(name__in=PARAMETERS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("checklists", "0003_markemparameter_markemprinter_markemchecklist_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_defaults, unseed_defaults),
    ]
