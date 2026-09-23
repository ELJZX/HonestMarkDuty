from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from core.models import Workshop
from documents.models import Document, DocumentTemplate
from equipment.models import Equipment, EquipmentStatus
from inventory.models import Condition, InventoryItem
from journal.models import JournalEntry
from shifts.models import Shift


class AnalyticsViewTests(TestCase):
    def setUp(self):
        self.specialist = User.objects.create_user(
            username="spec", password="x", role=User.Role.SPECIALIST
        )
        self.workshop = Workshop.objects.create(name="Мясной цех", code="МЦ")
        self.item = InventoryItem.objects.create(
            name="Сканер", quantity=0, min_quantity=1, condition=Condition.USED
        )
        Equipment.objects.create(name="Упаковщик", status=EquipmentStatus.OPERATIONAL)
        self.shift = Shift.objects.create(opened_by=self.specialist, workshop=self.workshop)
        JournalEntry.objects.create(shift=self.shift, action_task="Проверка печати", specialist=self.specialist)
        template = DocumentTemplate.objects.create(name="Шаблон", title_template="Т", body="B")
        Document.objects.create(template=template, workshop=self.workshop, title="Док", number="1")

    def test_dashboard_requires_login(self):
        self.assertEqual(self.client.get(reverse("analytics:dashboard")).status_code, 302)

    def test_dashboard_renders_with_kpi(self):
        self.client.force_login(self.specialist)
        response = self.client.get(reverse("analytics:dashboard"))
        self.assertEqual(response.status_code, 200)
        kpi = response.context["kpi"]
        self.assertEqual(kpi["items"], 1)
        self.assertEqual(kpi["low_stock"], 1)
        self.assertEqual(kpi["used"], 1)
        self.assertEqual(kpi["equipment"], 1)
        self.assertEqual(kpi["journal"], 1)
        self.assertEqual(kpi["documents"], 1)
        self.assertIn("journal_series_values", response.context)

    def test_statistics_renders(self):
        self.client.force_login(self.specialist)
        response = self.client.get(reverse("analytics:statistics"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("status_rows", response.context)
        self.assertIn("entry_rows", response.context)
        self.assertIn("workshop_rows", response.context)
