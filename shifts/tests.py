from datetime import timedelta
from unittest import mock

from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from inventory.models import Condition, InventoryItem
from journal.models import JournalEntry, JournalExport
from shifts.forms import ShiftCheckForm
from shifts.models import Shift, ShiftCheck
from shifts.views import _plural_ru, close_shift_with, open_shift_for


class ShiftHelperTests(TestCase):
    def setUp(self):
        self.specialist = User.objects.create_user(
            username="spec", password="x", role=User.Role.SPECIALIST
        )

    def _request(self, user):
        request = RequestFactory().post("/")
        request.user = user
        return request

    def test_plural_ru_forms(self):
        self.assertEqual(_plural_ru(1, "запись", "записи", "записей"), "запись")
        self.assertEqual(_plural_ru(2, "запись", "записи", "записей"), "записи")
        self.assertEqual(_plural_ru(5, "запись", "записи", "записей"), "записей")
        self.assertEqual(_plural_ru(11, "запись", "записи", "записей"), "записей")
        self.assertEqual(_plural_ru(21, "запись", "записи", "записей"), "запись")

    def test_open_shift_for_creates_shift_and_marker(self):
        shift, message = open_shift_for(self._request(self.specialist))
        self.assertIsNotNone(shift)
        self.assertEqual(message, "Смена открыта")
        self.assertTrue(
            JournalEntry.objects.filter(
                shift=shift, entry_type=JournalEntry.EntryType.SHIFT_START
            ).exists()
        )

    def test_open_shift_for_twice_returns_none(self):
        Shift.objects.create(opened_by=self.specialist, status=Shift.Status.OPEN)
        shift, message = open_shift_for(self._request(self.specialist))
        self.assertIsNone(shift)
        self.assertIn("уже есть открытая смена", message)

    def test_close_shift_with_creates_end_marker(self):
        shift = Shift.objects.create(opened_by=self.specialist, status=Shift.Status.OPEN)
        close_shift_with(self._request(self.specialist), shift)
        shift.refresh_from_db()
        self.assertEqual(shift.status, Shift.Status.CLOSED)
        self.assertTrue(
            JournalEntry.objects.filter(
                shift=shift, entry_type=JournalEntry.EntryType.SHIFT_END
            ).exists()
        )

    def test_close_shift_with_tolerates_export_errors(self):
        shift = Shift.objects.create(opened_by=self.specialist, status=Shift.Status.OPEN)
        with mock.patch("shifts.views.export_full_journal", side_effect=RuntimeError("boom")), \
                mock.patch("checklists.services.finalize_shift_checklists",
                           side_effect=RuntimeError("boom")):
            close_shift_with(self._request(self.specialist), shift)
        shift.refresh_from_db()
        self.assertEqual(shift.status, Shift.Status.CLOSED)


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

    def test_duration_display_format(self):
        start = timezone.now()
        shift = Shift.objects.create(
            status=Shift.Status.CLOSED,
            opened_at=start,
            closed_at=start + timedelta(hours=2, minutes=3, seconds=4),
        )
        self.assertEqual(shift.duration_display, "02:03:04")

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

    def test_open_shift_creates_marker(self):
        self.client.force_login(self.specialist)
        response = self.client.post(
            reverse("shifts:shift_open"),
            {"date": timezone.localdate().isoformat(), "kind": Shift.Kind.DAY, "opening_notes": "старт"},
        )
        self.assertEqual(response.status_code, 302)
        shift = Shift.objects.open().first()
        self.assertEqual(shift.opened_by, self.specialist)
        self.assertTrue(
            JournalEntry.objects.filter(
                shift=shift, entry_type=JournalEntry.EntryType.SHIFT_START
            ).exists()
        )

    def test_open_shift_twice_redirects(self):
        self.client.force_login(self.specialist)
        Shift.objects.create(opened_by=self.specialist, status=Shift.Status.OPEN)
        response = self.client.post(
            reverse("shifts:shift_open"),
            {"date": timezone.localdate().isoformat(), "kind": Shift.Kind.DAY},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Shift.objects.filter(opened_by=self.specialist).count(), 1)

    def test_close_shift_creates_end_marker_and_export(self):
        shift = Shift.objects.create(opened_by=self.specialist)
        JournalEntry.objects.create(shift=shift, action_task="Работа за смену")
        self.client.force_login(self.specialist)
        response = self.client.post(
            reverse("shifts:shift_close", args=[shift.pk]),
            {"equipment_condition": "норма", "inventory_notes": "ок", "closing_notes": "сдал", "handover_to": ""},
        )
        self.assertEqual(response.status_code, 302)
        shift.refresh_from_db()
        self.assertEqual(shift.status, Shift.Status.CLOSED)
        self.assertTrue(
            JournalEntry.objects.filter(
                shift=shift, entry_type=JournalEntry.EntryType.SHIFT_END
            ).exists()
        )
        self.assertTrue(JournalExport.objects.filter(is_full=True).exists())

    def test_close_shift_without_entries_still_exports_marker(self):
        shift = Shift.objects.create(opened_by=self.specialist)
        self.client.force_login(self.specialist)
        response = self.client.post(
            reverse("shifts:shift_close", args=[shift.pk]),
            {"equipment_condition": "", "inventory_notes": "", "closing_notes": "", "handover_to": ""},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(JournalExport.objects.filter(is_full=True).exists())

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

    def test_detail_and_close_pages_render(self):
        shift = Shift.objects.create(opened_by=self.specialist)
        JournalEntry.objects.create(shift=shift, action_task="x")
        self.client.force_login(self.specialist)
        detail = self.client.get(reverse("shifts:shift_detail", args=[shift.pk]))
        self.assertEqual(detail.status_code, 200)
        close = self.client.get(reverse("shifts:shift_close", args=[shift.pk]))
        self.assertEqual(close.status_code, 200)
        self.assertEqual(close.context["journal_count"], 1)

    def test_list_filters_by_status_and_date(self):
        closed = Shift.objects.create(
            opened_by=self.specialist, status=Shift.Status.CLOSED, date=timezone.localdate()
        )
        opened = Shift.objects.create(
            opened_by=self.specialist,
            status=Shift.Status.OPEN,
            date=timezone.localdate() - timedelta(days=1),
        )
        self.client.force_login(self.specialist)
        response = self.client.get(reverse("shifts:shift_list"), {"status": Shift.Status.CLOSED})
        self.assertIn(closed, response.context["shifts"])
        self.assertNotIn(opened, response.context["shifts"])
        response = self.client.get(reverse("shifts:shift_list"), {"date": closed.date.isoformat()})
        self.assertIn(closed, response.context["shifts"])
        self.assertNotIn(opened, response.context["shifts"])

    def test_add_check_invalid_form_shows_error(self):
        shift = Shift.objects.create(opened_by=self.specialist)
        self.client.force_login(self.specialist)
        response = self.client.post(reverse("shifts:check_create", args=[shift.pk]), {})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(shift.checks.count(), 0)

    def test_shift_open_ajax_requires_login(self):
        response = self.client.post(reverse("shifts:shift_open_ajax"))
        self.assertEqual(response.status_code, 403)

    def test_shift_open_ajax_forbidden_for_viewer(self):
        viewer = User.objects.create_user(username="viewer", password="x", role=User.Role.VIEWER)
        self.client.force_login(viewer)
        response = self.client.post(reverse("shifts:shift_open_ajax"))
        self.assertEqual(response.status_code, 403)

    def test_shift_open_ajax_opens_shift(self):
        self.client.force_login(self.specialist)
        response = self.client.post(reverse("shifts:shift_open_ajax"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertTrue(Shift.objects.open().filter(opened_by=self.specialist).exists())

    def test_shift_open_ajax_duplicate_returns_400(self):
        Shift.objects.create(opened_by=self.specialist, status=Shift.Status.OPEN)
        self.client.force_login(self.specialist)
        response = self.client.post(reverse("shifts:shift_open_ajax"))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])

    def test_shift_close_ajax_requires_login(self):
        shift = Shift.objects.create(opened_by=self.specialist)
        response = self.client.post(reverse("shifts:shift_close_ajax", args=[shift.pk]))
        self.assertEqual(response.status_code, 403)

    def test_shift_close_ajax_forbidden_for_viewer(self):
        shift = Shift.objects.create(opened_by=self.specialist)
        viewer = User.objects.create_user(username="viewer2", password="x", role=User.Role.VIEWER)
        self.client.force_login(viewer)
        response = self.client.post(reverse("shifts:shift_close_ajax", args=[shift.pk]))
        self.assertEqual(response.status_code, 403)

    def test_shift_close_ajax_closes_shift(self):
        shift = Shift.objects.create(opened_by=self.specialist, status=Shift.Status.OPEN)
        self.client.force_login(self.specialist)
        response = self.client.post(reverse("shifts:shift_close_ajax", args=[shift.pk]))
        self.assertEqual(response.status_code, 200)
        shift.refresh_from_db()
        self.assertEqual(shift.status, Shift.Status.CLOSED)
