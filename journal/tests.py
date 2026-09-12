from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from journal.exports import build_workbook, export_entries_to_excel, export_shift_to_excel
from journal.forms import JournalEntryForm
from journal.models import JournalEntry, JournalExport
from shifts.models import Shift


class JournalEntryModelTests(TestCase):
    def test_done_sets_resolved_at(self):
        entry = JournalEntry.objects.create(
            source_location="Линия", problem="P", status=JournalEntry.Status.DONE
        )
        self.assertIsNotNone(entry.resolved_at)

    def test_reopen_clears_resolved_at(self):
        entry = JournalEntry.objects.create(
            source_location="Линия", problem="P", status=JournalEntry.Status.DONE
        )
        entry.status = JournalEntry.Status.IN_PROGRESS
        entry.save()
        self.assertIsNone(entry.resolved_at)

    def test_badges(self):
        entry = JournalEntry.objects.create(
            source_location="Л", problem="P",
            status=JournalEntry.Status.NEW, priority=JournalEntry.Priority.CRITICAL,
        )
        self.assertEqual(entry.status_badge, "badge-info")
        self.assertEqual(entry.priority_badge, "badge-danger")

    def test_response_time_positive(self):
        entry = JournalEntry.objects.create(source_location="Л", problem="P")
        self.assertGreaterEqual(entry.response_time.total_seconds(), 0)

    def test_str(self):
        entry = JournalEntry.objects.create(source_location="Линия розлива", problem="P")
        self.assertIn("Линия розлива", str(entry))


class JournalExportTests(TestCase):
    def setUp(self):
        self.shift = Shift.objects.create()

    def test_export_empty_shift_returns_none(self):
        self.assertIsNone(export_shift_to_excel(self.shift, None))

    def test_export_shift_creates_file(self):
        JournalEntry.objects.create(
            shift=self.shift, source_location="Цех", problem="П", solution="Р",
            status=JournalEntry.Status.DONE,
        )
        export = export_shift_to_excel(self.shift, None)
        self.assertIsInstance(export, JournalExport)
        self.assertEqual(export.entries_count, 1)
        self.assertTrue(export.file.name.endswith(".xlsx"))

    def test_export_entries_to_excel(self):
        JournalEntry.objects.create(source_location="Цех", problem="П")
        export = export_entries_to_excel(JournalEntry.objects.all(), None)
        self.assertTrue(export.file.name.endswith(".xlsx"))

    def test_build_workbook_has_sheet(self):
        entries = [JournalEntry.objects.create(source_location="Цех", problem="П")]
        workbook = build_workbook(entries, "Заголовок")
        self.assertEqual(workbook.active.title, "Сменный журнал")


class JournalFormTests(TestCase):
    def test_entry_form_valid(self):
        form = JournalEntryForm(
            data={
                "received_at": timezone.now().strftime("%Y-%m-%dT%H:%M"),
                "source_location": "Линия",
                "problem": "Проблема",
                "status": JournalEntry.Status.NEW,
                "priority": JournalEntry.Priority.NORMAL,
            }
        )
        self.assertTrue(form.is_valid())


class JournalViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin", password="x", role=User.Role.ADMIN, is_superuser=True, is_staff=True
        )
        self.specialist = User.objects.create_user(
            username="spec", password="x", role=User.Role.SPECIALIST
        )
        self.shift = Shift.objects.create(opened_by=self.specialist)
        self.entry = JournalEntry.objects.create(
            source_location="Линия розлива",
            problem="Не читается код",
            priority=JournalEntry.Priority.HIGH,
        )

    def test_list_renders_and_filters(self):
        self.client.force_login(self.specialist)
        self.assertEqual(self.client.get(reverse("journal:entry_list")).status_code, 200)
        response = self.client.get(reverse("journal:entry_list"), {"q": "код", "priority": "high"})
        self.assertContains(response, "Не читается код")

    def test_detail_renders(self):
        self.client.force_login(self.specialist)
        response = self.client.get(reverse("journal:entry_detail", args=[self.entry.pk]))
        self.assertContains(response, "Не читается код")

    def test_create_entry_binds_shift_and_author(self):
        self.client.force_login(self.specialist)
        response = self.client.post(
            reverse("journal:entry_create"),
            {
                "received_at": timezone.now().strftime("%Y-%m-%dT%H:%M"),
                "source_location": "Склад",
                "problem": "Новая проблема",
                "status": JournalEntry.Status.NEW,
                "priority": JournalEntry.Priority.NORMAL,
            },
        )
        self.assertEqual(response.status_code, 302)
        created = JournalEntry.objects.get(problem="Новая проблема")
        self.assertEqual(created.created_by, self.specialist)
        self.assertEqual(created.shift, self.shift)

    def test_update_entry(self):
        self.client.force_login(self.specialist)
        response = self.client.post(
            reverse("journal:entry_update", args=[self.entry.pk]),
            {
                "received_at": timezone.now().strftime("%Y-%m-%dT%H:%M"),
                "source_location": "Линия",
                "problem": "Обновлена",
                "status": JournalEntry.Status.DONE,
                "priority": JournalEntry.Priority.HIGH,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.status, JournalEntry.Status.DONE)

    def test_manual_export_view(self):
        self.client.force_login(self.specialist)
        response = self.client.get(reverse("journal:export_create"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(JournalExport.objects.exists())

    def test_export_list_renders(self):
        self.client.force_login(self.specialist)
        self.assertEqual(self.client.get(reverse("journal:export_list")).status_code, 200)
