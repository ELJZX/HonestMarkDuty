import sys

from django.db import migrations

# позиция -> тип (снимок пользовательского распределения)
ITEM_TYPES = [
    ('128GB Digma Флешки\\Digma', 'Флешки'),
    ('Datalogic CBX100', 'Datalogic'),
    ('GAC-20A Картридж угольный NatureWater SL 20" CG', 'Разное'),
    ('SP-PEX-2000-0064 Модуль отделения этикетки, левый', 'TSC PEX'),
    ('SP-PEX-2000-0065 Модуль отделения этикетки, правый', 'TSC PEX'),
    ('Tinker Board 2S 4GB/16GB', 'Зап.части'),
    ('VideoJet 5З мм_ТТ (III) ленточный рычаг', 'VideoJet'),
    ('VideoJet Запасной передатчик ТТ (III) IASSURE 53 мм - левая трубка', 'VideoJet'),
    ('VideoJet Запасной передатчик ТТ (III) IASSURE 53 мм - правая трубка', 'VideoJet'),
    ('VideoJet Запасной ролик (53 мм)', 'VideoJet'),
    ('VideoJet Запасные части объектива - линза датчика IASSURE', 'VideoJet'),
    ('VideoJet Рычаг отделяющий 5ЗММ Правый', 'VideoJet'),
    ('WDR-120-24 Блок питания Mean Well', 'Зап.части'),
    ('WDR-480-24 Блок питания', 'Зап.части'),
    ('Waveshare 10.1inch HDMI LCD (B) (with case)', 'Зап.части'),
    ('Блок питания LRS-35-12', 'Зап.части'),
    ('Блок питания для Raspberry Pi 5', 'Зап.части'),
    ('Гайка М14 латунная на пастеризатор', 'Разное'),
    ('Диск кассеты серебристого цвета (Механика)', 'Разное'),
    ('Диск кассеты черного цвета (Механика)', 'Разное'),
    ('Источник питания LRS-35-5', 'Зап.части'),
    ('Кабель PWR I/O P-Series to CBX (DB25) 5 метров CAB-DS05-S', 'Datalogic'),
    ('Кабель датчика OMRON XS3F-LM8PVC4S2M', 'Разное'),
    ('Каретка MGN9HZ0HM (HIWIN)', 'Разное'),
    ('Картридж угольный блоковый SL20"', 'Разное'),
    ('Кассета, 53 мм, VJ6330 (Механика)', 'VideoJet'),
    ('Линейная направляющая, 53 мм', 'VideoJet'),
    ('Мембрана для клапанов периодической продувки MPA46/47/48 DN20-50', 'Разное'),
    ('Металлический корпус для Raspberry Pi 5 c охлаждающим вентилятором\\ACD', 'Зап.части'),
    ('Монитор GLA-12-GS-B-I-HB-AG-30PS-WT2-R50 12/1"', 'Зап.части'),
    ('Мультиграф 1АААOОOOO1М1А2', 'Разное'),
    ('Печатающая головка 32мм, VJ6330', 'VideoJet'),
    ('Печатающая головка 53мм, VJ6330 / VJ6530', 'VideoJet'),
    ('Печатающая головка для принтера PEX 1131/ PEX 1231, 300dpi', 'TSC PEX'),
    ('Предохранитель 6,0x30, ток 10 А, керамика KF-0460D ЦБ-00097379', 'Разное'),
    ('Преобразователь температуры APLISENS ATL/Q/Pt100/', 'Разное'),
    ('Ремень зубчатый PU T5 500 400 (14мм)', 'Разное'),
    ('Ремень зубчатый к 6330, 53 мм', 'VideoJet'),
    ('Светосигнальный маячок d=70мм, L=85мм, 24VDC IP54', 'Зап.части'),
    ('Соединительная коробка COMPACT CBX100', 'Datalogic'),
    ('Термоголовка Videojet 6330 53mm', 'VideoJet'),
    ('Термоголовка Zebra ZT610, 300dpi', 'Zebra'),
    ('Фильтр YAG Cut LT 36L M320/P2', 'Зап.части'),
    ('Фрикционный конус узла размотки к DF (Механика)', 'Разное'),
    ('Шпиндель красящей ленты, 53 мм (Механика)', 'VideoJet'),
    ('ЭФГ 63/508 (5 мкм) Картридж, вспененный ПП, SL20"', 'Разное'),
    ('блок питания,MEAN WELL WDR-240-24', 'Зап.части'),
    ('блок питания,MEAN WELL WDR-480-24', 'Зап.части'),
]

SHELF_CODE = "НС07П01Я15"
UNUSED_BASE_TYPES = ["Инструмент", "Запасная часть", "Прибор/средство"]


def assign_types(apps, schema_editor):
    if "test" in sys.argv:
        return
    ItemType = apps.get_model("inventory", "ItemType")
    InventoryItem = apps.get_model("inventory", "InventoryItem")

    types = {t.name: t for t in ItemType.objects.all()}
    for item_name, type_name in ITEM_TYPES:
        item_type = types.get(type_name)
        if item_type is None:
            continue
        InventoryItem.objects.filter(
            name=item_name, location__shelf_code=SHELF_CODE
        ).update(kind=item_type)

    for name in UNUSED_BASE_TYPES:
        item_type = types.get(name)
        if item_type and not InventoryItem.objects.filter(kind=item_type).exists():
            item_type.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0008_storage_inventoryitem_storage"),
    ]

    operations = [
        migrations.RunPython(assign_types, migrations.RunPython.noop),
    ]
