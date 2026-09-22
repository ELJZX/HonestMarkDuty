"""Наполнение базы демонстрационными данными: python manage.py seed_demo"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import User
from checklists.models import (
    ChecklistCheck,
    ChecklistGroup,
    ChecklistMachine,
    ChecklistMileage,
    ChecklistResult,
    EquipmentChecklist,
)
from core.models import ProductionLine, ProductionSite, Workshop
from documents.models import Document, DocumentTemplate, DocumentType
from equipment.models import (
    Criticality,
    Equipment,
    EquipmentStatus,
    MaintenanceKind,
    MaintenanceRecord,
)
from inventory.models import (
    Condition,
    InventoryItem,
    InventoryMovement,
    ItemCategory,
    ItemType,
    MovementType,
    StorageLocation,
)
from journal.models import JournalEntry
from shifts.models import Shift


class Command(BaseCommand):
    help = "Создаёт демонстрационные данные для HonestMarkDuty"

    def handle(self, *args, **options):
        self.stdout.write("Создание демо-данных...")
        admin = self._users()
        sites, workshops, specialists, lines = self._organization(admin)
        self._inventory(workshops, admin)
        equipment_list = self._equipment(sites, workshops, lines)
        shift = self._shift_and_journal(workshops, specialists, equipment_list)
        self._checklists(shift, workshops, specialists)
        self._documents(workshops, specialists)

        self.stdout.write(self.style.SUCCESS("Демо-данные успешно созданы."))
        self.stdout.write("  admin / admin12345 — администратор")
        self.stdout.write("  ivanov / demo12345 — сменный специалист")

    # ------------------------------------------------------------------ users
    def _users(self):
        admin, created = User.objects.get_or_create(
            username="admin",
            defaults={
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
        return admin

    # ----------------------------------------------------------- organization
    def _organization(self, admin):
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
                    "position": "Сменный специалист по цифровой маркировке",
                },
            )
            if created:
                user.set_password("demo12345")
                user.save()
            specialists.append(user)

        for user, workshop in zip(specialists, workshops):
            user.workshop = workshop
            user.save()

        lines_data = [
            ("МЦ", "Линия №1", "L-01"),
            ("МЦ", "Линия №2", "L-02"),
            ("УЦ", "Линия упаковки №1", "L-11"),
            ("УЦ", "Линия упаковки №2", "L-12"),
            ("СГП", "Зона отгрузки", "L-21"),
        ]
        workshop_by_code = {w.code: w for w in workshops}
        lines = {}
        for order, (wcode, lname, lcode) in enumerate(lines_data):
            line, _ = ProductionLine.objects.get_or_create(
                workshop=workshop_by_code[wcode],
                name=lname,
                defaults={"code": lcode, "sort_order": order},
            )
            lines[lcode] = line
        return site, workshops, specialists, lines

    # -------------------------------------------------------------- inventory
    def _inventory(self, workshops, admin):
        type_device, _ = ItemType.objects.get_or_create(name="Прибор/средство")
        type_tool, _ = ItemType.objects.get_or_create(name="Инструмент")
        type_spare, _ = ItemType.objects.get_or_create(name="Запасная часть")
        device_cat, _ = ItemCategory.objects.get_or_create(
            name="Сканеры Честного знака", defaults={"kind": type_device}
        )
        tool_cat, _ = ItemCategory.objects.get_or_create(
            name="Пневмоинструмент", defaults={"kind": type_tool}
        )
        spare_cat, _ = ItemCategory.objects.get_or_create(
            name="Запчасти упаковщика", defaults={"kind": type_spare}
        )
        locations = []
        for workshop, shelf in [(workshops[0], "A-01"), (workshops[1], "B-02"), (workshops[2], "C-03")]:
            location, _ = StorageLocation.objects.get_or_create(
                workshop=workshop,
                shelf_code=shelf,
                defaults={"name": f"Стеллаж {shelf}", "description": "Кабинет сменного специалиста"},
            )
            locations.append(location)

        items_data = [
            ("Сканер 2D Honeywell", "INV-1001", type_device, device_cat, locations[0], 4, 2, Condition.GOOD, 20),
            ("Сканер Zebra DS2208", "INV-1002", type_device, device_cat, locations[1], 1, 2, Condition.WORN, 65),
            ("Гайковёрт пневматический", "INV-2001", type_tool, tool_cat, locations[0], 3, 1, Condition.GOOD, 35),
            ("Ремень привода упаковщика", "ZAP-3001", type_spare, spare_cat, locations[2], 8, 4, Condition.NEW, 0),
            ("Нож упаковочной машины", "ZAP-3002", type_spare, spare_cat, locations[2], 2, 3, Condition.NEEDS_REPAIR, 80),
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
        return items

    # -------------------------------------------------------------- equipment
    def _equipment(self, site, workshops, lines):
        line_by_name = {
            "Упаковочная машина Multivac": "L-11",
            "Принтер этикеток Zebra ZT411": "L-11",
            "Термоупаковщик": "L-01",
            "Камера маркировки": "L-21",
        }
        equipment_list = []
        for name, workshop, status in [
            ("Упаковочная машина Multivac", workshops[1], EquipmentStatus.OPERATIONAL),
            ("Принтер этикеток Zebra ZT411", workshops[1], EquipmentStatus.MAINTENANCE),
            ("Термоупаковщик", workshops[0], EquipmentStatus.REPAIR),
            ("Камера маркировки", workshops[2], EquipmentStatus.OPERATIONAL),
        ]:
            equipment, _ = Equipment.objects.get_or_create(
                name=name,
                defaults={
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
            line = lines.get(line_by_name.get(name))
            if line and equipment.line_id != line.pk:
                equipment.line = line
                equipment.workshop = line.workshop
                equipment.save()
            equipment_list.append(equipment)
        MaintenanceRecord.objects.get_or_create(
            equipment=equipment_list[0],
            kind=MaintenanceKind.TO,
            performed_at=timezone.localdate() - timedelta(days=30),
            defaults={"description": "Плановое ТО, замена смазки", "performer": "Сервис-центр", "cost": Decimal("15000.00")},
        )
        return equipment_list

    # ----------------------------------------------------------- shift/journal
    def _shift_and_journal(self, workshops, specialists, equipment_list):
        shift = (
            Shift.objects.filter(date=timezone.localdate(), kind=Shift.Kind.DAY)
            .order_by("opened_at", "id")
            .first()
        )
        if shift is None:
            shift = Shift.objects.create(
                date=timezone.localdate(),
                kind=Shift.Kind.DAY,
                workshop=workshops[0],
                opened_by=specialists[0],
                status=Shift.Status.OPEN,
                opening_notes="Смена принята. Склад проверен, замечаний нет.",
            )
        specialist = specialists[0]
        base = shift.opened_at

        JournalEntry.objects.get_or_create(
            shift=shift,
            entry_type=JournalEntry.EntryType.SHIFT_START,
            defaults={
                "occurred_at": base,
                "specialist": specialist,
                "action_task": "Смену принял +",
                "created_by": specialist,
            },
        )
        rows = [
            (30, "Serac Old", "", "Часто печатались смазанные коды", "Оператор поправил датчик на крышку", "", None),
            (60, "Джонгай", "", "Часто скидывала камера, которая ближе к терминалам", "Скорректировал положение камеры", "", None),
            (120, "AVE", "", "Часто скидывались бутылки", "Настройка положения датчика на крышку, а также настройка фокуса камеры", "", Decimal("17.5")),
            (180, "", "", "Проверить код ЧЗ, грейд Школьник", "Правая голова — ЧЗ считывает, грейд 2,1. Левая голова — ЧЗ считывает, грейд 3,0", "", None),
        ]
        for minutes, equipment_line, downtime, action, solution, print_head, mileage in rows:
            JournalEntry.objects.get_or_create(
                shift=shift,
                action_task=action,
                defaults={
                    "entry_type": JournalEntry.EntryType.WORK,
                    "occurred_at": base + timedelta(minutes=minutes),
                    "specialist": specialist,
                    "equipment_line": equipment_line,
                    "downtime": downtime,
                    "solution": solution,
                    "print_head": print_head,
                    "mileage": mileage,
                    "created_by": specialist,
                },
            )
        return shift

    # ------------------------------------------------------------- checklists
    def _checklists(self, shift, workshops, specialists):
        groups_data = {
            "Цех №1": ["New Serac", "Евобан 1", "FP 1", "FP 2", "FP 3", "Old Serac"],
            "КМЦ": ["Терко", "Finnah", "AVE"],
            "ЦМП": ["C3 Flex", "TT 1.1", "TT 1.2", "Джонга1", "Джонга2"],
            "ЦСМ": ["Пимба", "A3 Flex", "Serac"],
            "Творожный цех": ["SP1", "SP2", "SP3", "SP4", "SB 3", "Mondini 4"],
        }
        for order, (group_name, machines) in enumerate(groups_data.items()):
            group, _ = ChecklistGroup.objects.get_or_create(
                name=group_name, defaults={"sort_order": order}
            )
            for machine_order, machine_name in enumerate(machines):
                ChecklistMachine.objects.get_or_create(
                    group=group, name=machine_name, defaults={"sort_order": machine_order}
                )

        checks = [
            "Проверка целостности узла ЦМ (Экран, провода, валы, принтер)",
            "Проверка технического зрения (чистоты и поле зрения)",
            "Проверка датчика камеры и отбраковщика",
            "Проверка состояния принт-ап, чистота, состояние роликов",
            "Диагностика печатающей головки (график, параметры печати)",
            "Проверка износа и чистоты подложки",
            "Проверка печати принтера",
        ]
        for order, name in enumerate(checks):
            ChecklistCheck.objects.get_or_create(name=name, defaults={"sort_order": order})

        if EquipmentChecklist.objects.exists():
            return
        checklist = EquipmentChecklist.objects.create(
            shift=shift,
            date=timezone.localdate(),
            workshop=workshops[0],
            performed_by=specialists[0],
            created_by=specialists[0],
        )
        checks_qs = list(ChecklistCheck.objects.order_by("sort_order"))
        for machine in ChecklistMachine.objects.all():
            ChecklistMileage.objects.create(
                checklist=checklist, machine=machine, value=Decimal("23.9")
            )
            for check in checks_qs:
                ChecklistResult.objects.create(
                    checklist=checklist, machine=machine, check_item=check, score=3
                )

    # -------------------------------------------------------------- documents
    def _documents(self, workshops, specialists):
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
        if not Document.objects.filter(template=template).exists():
            document = Document(
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
            document.save()
            document.render()
            from documents.services import build_docx

            document.file.save(f"document_{document.pk}.docx", build_docx(document), save=False)
            document.save()
