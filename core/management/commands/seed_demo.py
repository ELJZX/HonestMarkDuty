"""Наполнение базы демонстрационными данными: python manage.py seed_demo"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import User
from core.models import ProductionSite, Workshop
from documents.models import Document, DocumentTemplate, DocumentType
from equipment.models import (
    Criticality,
    Equipment,
    EquipmentCategory,
    EquipmentStatus,
    MaintenanceKind,
    MaintenanceRecord,
)
from inventory.models import (
    Condition,
    InventoryItem,
    InventoryMovement,
    ItemCategory,
    ItemKind,
    MovementType,
    StorageLocation,
)
from journal.models import JournalEntry
from shifts.models import Shift


class Command(BaseCommand):
    help = "Создаёт демонстрационные данные для HonestMarkDuty"

    def handle(self, *args, **options):
        self.stdout.write("Создание демо-данных...")

        # --- Пользователи ---
        admin, created = User.objects.get_or_create(
            username="admin",
            defaults={
                "last_name": "Администратор",
                "first_name": "Системный",
                "role": User.Role.ADMIN,
                "position": "Администратор сменного контура",
                "is_staff": True,
                "is_superuser": True,
                "email": "admin@honestmark.ru",
            },
        )
        if created:
            admin.set_password("admin12345")
            admin.save()

        specialists = []
        for username, last, first, patronymic in [
            ("ivanov", "Иванов", "Иван", "Иванович"),
            ("petrova", "Петрова", "Анна", "Сергеевна"),
            ("sidorov", "Сидоров", "Пётр", "Алексеевич"),
        ]:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "last_name": last,
                    "first_name": first,
                    "patronymic": patronymic,
                    "role": User.Role.SPECIALIST,
                    "position": "Сменный специалист по Честному знаку",
                },
            )
            if created:
                user.set_password("demo12345")
                user.save()
            specialists.append(user)

        # --- Площадки и цеха ---
        site, _ = ProductionSite.objects.get_or_create(
            name="Основная площадка",
            defaults={"address": "г. Москва, ул. Производственная, 1", "responsible": "Иванов И.И."},
        )
        workshops_data = [
            ("Мясной цех", "МЦ", "Кузнецов Д.В."),
            ("Упаковочный цех", "УЦ", "Смирнова Е.А."),
            ("Склад готовой продукции", "СГП", "Орлов В.П."),
        ]
        workshops = []
        for name, code, chief in workshops_data:
            workshop, _ = Workshop.objects.get_or_create(
                code=code,
                defaults={"name": name, "chief": chief, "site": site, "phone": "+7 (495) 000-00-00"},
            )
            workshops.append(workshop)

        for user, workshop in zip(specialists, workshops):
            user.workshop = workshop
            user.save()

        # --- Категории и полки ---
        tool_cat, _ = ItemCategory.objects.get_or_create(
            name="Сканеры Честного знака", defaults={"kind": ItemKind.DEVICE}
        )
        tool_cat2, _ = ItemCategory.objects.get_or_create(
            name="Пневмоинструмент", defaults={"kind": ItemKind.TOOL}
        )
        spare_cat, _ = ItemCategory.objects.get_or_create(
            name="Запчасти упаковщика", defaults={"kind": ItemKind.SPARE}
        )

        locations = []
        for workshop, shelf in [(workshops[0], "A-01"), (workshops[1], "B-02"), (workshops[2], "C-03")]:
            loc, _ = StorageLocation.objects.get_or_create(
                workshop=workshop,
                shelf_code=shelf,
                defaults={"name": f"Стеллаж {shelf}", "description": "Кабинет сменного специалиста"},
            )
            locations.append(loc)

        # --- Позиции склада ---
        items_data = [
            ("Сканер 2D Honeywell", "INV-1001", ItemKind.DEVICE, tool_cat, locations[0], 4, 2, Condition.GOOD, 20),
            ("Сканер Zebra DS2208", "INV-1002", ItemKind.DEVICE, tool_cat, locations[1], 1, 2, Condition.WORN, 65),
            ("Гайковёрт пневматический", "INV-2001", ItemKind.TOOL, tool_cat2, locations[0], 3, 1, Condition.GOOD, 35),
            ("Ремень привода упаковщика", "ZAP-3001", ItemKind.SPARE, spare_cat, locations[2], 8, 4, Condition.NEW, 0),
            ("Нож упаковочной машины", "ZAP-3002", ItemKind.SPARE, spare_cat, locations[2], 2, 3, Condition.NEEDS_REPAIR, 80),
        ]
        items = []
        for name, inv, kind, category, location, qty, minqty, condition, wear in items_data:
            item, _ = InventoryItem.objects.get_or_create(
                inventory_number=inv,
                defaults={
                    "name": name,
                    "kind": kind,
                    "category": category,
                    "location": location,
                    "quantity": qty,
                    "min_quantity": minqty,
                    "condition": condition,
                    "wear_percent": wear,
                    "unit": "шт",
                },
            )
            items.append(item)

        InventoryMovement.objects.get_or_create(
            item=items[3],
            movement_type=MovementType.IN,
            quantity=8,
            defaults={"comment": "Первичное поступление", "created_by": admin},
        )

        # --- Оборудование ---
        equip_cat, _ = EquipmentCategory.objects.get_or_create(name="Упаковочное оборудование")
        equip_cat2, _ = EquipmentCategory.objects.get_or_create(name="Маркировочное оборудование")

        equipment_list = []
        for name, inv, cat, workshop, status in [
            ("Упаковочная машина Multivac", "EQ-001", equip_cat, workshops[1], EquipmentStatus.OPERATIONAL),
            ("Принтер этикеток Zebra ZT411", "EQ-002", equip_cat2, workshops[1], EquipmentStatus.MAINTENANCE),
            ("Термоупаковщик", "EQ-003", equip_cat, workshops[0], EquipmentStatus.REPAIR),
            ("Камера маркировки", "EQ-004", equip_cat2, workshops[2], EquipmentStatus.OPERATIONAL),
        ]:
            eq, _ = Equipment.objects.get_or_create(
                inventory_number=inv,
                defaults={
                    "name": name,
                    "category": cat,
                    "site": site,
                    "workshop": workshop,
                    "manufacturer": "Demo",
                    "model_name": "Model-X",
                    "status": status,
                    "criticality": Criticality.HIGH,
                    "next_maintenance_at": timezone.localdate() - timedelta(days=5)
                    if status == EquipmentStatus.MAINTENANCE
                    else timezone.localdate() + timedelta(days=60),
                },
            )
            equipment_list.append(eq)

        MaintenanceRecord.objects.get_or_create(
            equipment=equipment_list[0],
            kind=MaintenanceKind.TO,
            performed_at=timezone.localdate() - timedelta(days=30),
            defaults={"description": "Плановое ТО, замена смазки", "performer": "Сервис-центр", "cost": Decimal("15000.00")},
        )

        # --- Смена и журнал ---
        shift, _ = Shift.objects.get_or_create(
            date=timezone.localdate(),
            kind=Shift.Kind.DAY,
            defaults={
                "workshop": workshops[0],
                "opened_by": specialists[0],
                "status": Shift.Status.OPEN,
                "opening_notes": "Смена принята. Склад проверен, замечаний нет.",
            },
        )

        entries = [
            ("Линия розлива №1", "Не читается код на этикетке", "Заменили сканер, настроили фокус", JournalEntry.Status.DONE, JournalEntry.Priority.HIGH),
            ("Упаковочный цех", "Остановлен принтер этикеток", "Перезапуск и калибровка принтера", JournalEntry.Status.DONE, JournalEntry.Priority.CRITICAL),
            ("Склад ГП", "Требуется дополнительная маркировка партии", "", JournalEntry.Status.IN_PROGRESS, JournalEntry.Priority.NORMAL),
            ("Мясной цех", "Низкий запас ножей упаковщика", "", JournalEntry.Status.NEW, JournalEntry.Priority.LOW),
        ]
        for idx, (source, problem, solution, status, priority) in enumerate(entries):
            JournalEntry.objects.get_or_create(
                source_location=source,
                problem=problem,
                defaults={
                    "shift": shift,
                    "workshop": workshops[idx % len(workshops)],
                    "solution": solution,
                    "status": status,
                    "priority": priority,
                    "assigned_to": specialists[idx % len(specialists)],
                    "created_by": specialists[idx % len(specialists)],
                    "reported_by": "Оператор линии",
                    "equipment": equipment_list[idx % len(equipment_list)] if idx < 2 else None,
                },
            )

        # --- Шаблоны документов ---
        template, _ = DocumentTemplate.objects.get_or_create(
            name="Техническое заключение о состоянии оборудования",
            defaults={
                "doc_type": DocumentType.TECHNICAL_REPORT,
                "title_template": "Техническое заключение по оборудованию {{ workshop_name }}",
                "body": (
                    "Комиссия в составе сменного специалиста {{ author }} произвела осмотр "
                    "оборудования цеха «{{ workshop_name }}» (код {{ workshop_code }}).\n"
                    "Основание: {{ reason }}.\n"
                    "Выявлено: {{ findings }}.\n"
                    "Заключение: {{ conclusion }}.\n"
                    "Оборудование требует {{ action }}."
                ),
            },
        )
        template.workshops.set(workshops)

        DocumentTemplate.objects.get_or_create(
            name="Служебная записка по заявкам",
            defaults={
                "doc_type": DocumentType.SERVICE_NOTE,
                "title_template": "Служебная записка по цеху {{ workshop_name }}",
                "body": (
                    "Начальнику цеха {{ workshop_name }} {{ chief }}.\n"
                    "За отчётный период поступило обращений: {{ count }}.\n"
                    "Суть: {{ essence }}.\n"
                    "Прошу рассмотреть и принять меры.\n\n"
                    "{{ author_position }} {{ author }}"
                ),
            },
        )

        sample_doc = Document.objects.filter(template=template).first()
        if not sample_doc:
            doc = Document(
                template=template,
                workshop=workshops[0],
                number="ТЗ-001",
                doc_date=timezone.localdate(),
                created_by=specialists[0],
                context_data={
                    "reason": "плановый осмотр",
                    "findings": "повышенный износ ремённой передачи",
                    "conclusion": "оборудование пригодно к работе с ограничением",
                    "action": "замену ремня в течение 7 дней",
                },
            )
            doc.save()
            doc.render()
            from documents.services import build_docx

            doc.file.save(f"document_{doc.pk}.docx", build_docx(doc), save=False)
            doc.save()

        self.stdout.write(self.style.SUCCESS("Демо-данные успешно созданы."))
        self.stdout.write("  admin / admin12345 — администратор")
        self.stdout.write("  ivanov / demo12345 — сменный специалист")
