from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from inventory.models import Condition, InventoryItem
from journal.models import JournalEntry, JournalExport
from shifts.forms import ShiftCheckForm
from shifts.models import Shift, ShiftCheck


class ShiftModelTests(TestCase):
    def test_str_and_is_open(self):
        shift = Shift.objects.create(status=Shift.Status.OPEN)
        self.assertIn("Смена", str(shift))
        self.assertTrue(shift.is_open)

    def test_duration_uses_closed_at(self):
        start = timezone.now() - timedelta(hours=8)
        shift = Shift.objects.create(
            status=Shift.Status.CLOSED, opened_at=start, closed_at=timezone.now()
        )
        self.assertGreaterEqual(shift.duration.total_seconds(), 8 * 3600 - 60)

    def test_shiftcheck_str(self):
        shift = Shift.objects.create()
        item = InventoryItem.objects.create(name="Сканер")
        check = ShiftCheck.objects.create(shift=shift, item=item, wear_percent=10)
        self.assertIn("10", str(check))


class ShiftViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin", password="x", role=User.Role.ADMIN, is_superuser=True, is_staff=True
        )
        self.specialist = User.objects.create_user(
            username="spec", password="x", role=User.Role.SPECIALIST
        )
        self.item = InventoryItem.objects.create(name="Сканер", quantity=5)

    def test_list_and_open_page_render(self):
        self.client.force_login(self.specialist)
        self.assertEqual(self.client.get(reverse("shifts:shift_list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("shifts:shift_open")).status_code, 200)

    def test_open_shift(self):
        self.client.force_login(self.specialist)
        response = self.client.post(
            reverse("shifts:shift_open"),
            {"date": timezone.localdate().isoformat(), "kind": Shift.Kind.DAY, "opening_notes": "старт"},
        )
        self.assertEqual(response.status_code, 302)
        shift = Shift.objects.open().first()
        self.assertIsNotNone(shift)
        self.assertEqual(shift.opened_by, self.specialist)

    def test_open_shift_twice_redirects(self):
        self.client.force_login(self.specialist)
        Shift.objects.create(opened_by=self.specialist, status=Shift.Status.OPEN)
        response = self.client.post(
            reverse("shifts:shift_open"),
            {"date": timezone.localdate().isoformat(), "kind": Shift.Kind.DAY},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Shift.objects.filter(opened_by=self.specialist).count(), 1)

    def test_close_shift_exports_journal(self):
        shift = Shift.objects.create(workshop=None, opened_by=self.specialist)
        JournalEntry.objects.create(
            shift=shift, source_location="Линия", problem="Тест",
            solution="Готово", status=JournalEntry.Status.DONE,
        )
        self.client.force_login(self.specialist)
        response = self.client.post(
            reverse("shifts:shift_close", args=[shift.pk]),
            {"equipment_condition": "норма", "inventory_notes": "ок", "closing_notes": "сдал", "handover_to": ""},
        )
        self.assertEqual(response.status_code, 302)
        shift.refresh_from_db()
        self.assertEqual(shift.status, Shift.Status.CLOSED)
        self.assertTrue(JournalExport.objects.filter(shift=shift).exists())

    def test_close_empty_shift(self):
        shift = Shift.objects.create(opened_by=self.specialist)
        self.client.force_login(self.specialist)
        response = self.client.post(
            reverse("shifts:shift_close", args=[shift.pk]),
            {"equipment_condition": "", "inventory_notes": "", "closing_notes": "", "handover_to": ""},
        )
        self.assertEqual(response.status_code, 302)
        shift.refresh_from_db()
        self.assertEqual(shift.status, Shift.Status.CLOSED)
        self.assertFalse(JournalExport.objects.filter(shift=shift).exists())

    def test_add_check(self):
        shift = Shift.objects.create(opened_by=self.specialist)
        self.client.force_login(self.specialist)
        response = self.client.post(
            reverse("shifts:check_create", args=[shift.pk]),
            {"item": self.item.pk, "condition": Condition.GOOD, "wear_percent": 10, "comment": "ок"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(shift.checks.count(), 1)

    def test_add_check_to_closed_shift_rejected(self):
        shift = Shift.objects.create(status=Shift.Status.CLOSED, opened_by=self.specialist)
        self.client.force_login(self.specialist)
        self.client.post(
            reverse("shifts:check_create", args=[shift.pk]),
            {"item": self.item.pk, "condition": Condition.GOOD, "wear_percent": 10},
        )
        self.assertEqual(shift.checks.count(), 0)

    def test_check_form_valid(self):
        form = ShiftCheckForm(data={"item": self.item.pk, "condition": Condition.NEW, "wear_percent": 0})
        self.assertTrue(form.is_valid())
