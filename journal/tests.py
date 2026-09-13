from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from journal.exports import build_workbook, export_full_journal, group_entries
from journal.forms import JournalEntryForm
from journal.models import JournalEntry, JournalExport
from shifts.models import Shift


class JournalEntryModelTests(TestCase):
    def test_specialist_taken_from_shift(self):
        user = User.objects.create_user(username="u", password="x", last_name="Иванов")
        shift = Shift.objects.create(opened_by=user)
        entry = JournalEntry.objects.create(shift=shift, action_task="тест")
        self.assertEqual(entry.specialist, user)
        self.assertEqual(entry.specialist_name, "Иванов")

    def test_specialist_name_fallback(self):
        entry = JournalEntry.objects.create(action_task="тест", specialist=None)
        self.assertEqual(entry.specialist_name, "—")

    def test_marker_flag(self):
        marker = JournalEntry.objects.create(
            action_task="Смену принял +", entry_type=JournalEntry.EntryType.SHIFT_START
        )
        work = JournalEntry.objects.create(action_task="работа")
        self.assertTrue(marker.is_marker)
        self.assertFalse(work.is_marker)

    def test_entry_date_and_time(self):
        moment = timezone.now()
        entry = JournalEntry.objects.create(action_task="a", occurred_at=moment)
        local = timezone.localtime(moment)
        self.assertEqual(entry.entry_date, local.date())
        self.assertEqual(entry.entry_time.hour, local.hour)

    def test_str(self):
        entry = JournalEntry.objects.create(action_task="Проверка печати")
        self.assertIn("Проверка печати", str(entry))


class JournalExportTests(TestCase):
    def test_empty_journal_returns_none(self):
        self.assertIsNone(export_full_journal())

    def test_full_export_is_singleton(self):
        JournalEntry.objects.create(action_task="A")
        first = export_full_journal()
        self.assertTrue(first.is_full)
        JournalEntry.objects.create(action_task="B")
        second = export_full_journal()
        self.assertEqual(JournalExport.objects.filter(is_full=True).count(), 1)
        self.assertEqual(second.pk, first.pk)
        self.assertEqual(second.entries_count, 2)

    def test_group_entries_splits_by_shift(self):
        user = User.objects.create_user(username="u", password="x")
        shift = Shift.objects.create(opened_by=user)
        JournalEntry.objects.create(shift=shift, action_task="a")
        JournalEntry.objects.create(shift=shift, action_task="b")
        JournalEntry.objects.create(action_task="c")
        groups = group_entries(list(JournalEntry.objects.order_by("occurred_at")))
        self.assertEqual(len(groups), 2)

    def test_build_workbook_title(self):
        entries = [JournalEntry.objects.create(action_task="a")]
        workbook = build_workbook(entries)
        self.assertEqual(
            workbook.active["A1"].value,
            "Сменный журнал специалистов по цифровой маркировке",
        )


class JournalFormTests(TestCase):
    def test_form_valid(self):
        form = JournalEntryForm(
            data={
                "occurred_at": timezone.now().strftime("%Y-%m-%dT%H:%M"),
                "equipment_line": "AVE",
                "action_task": "Проверка",
                "solution": "",
                "downtime": "",
                "print_head": "",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)


class JournalViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin", password="x", role=User.Role.ADMIN, is_superuser=True, is_staff=True
        )
        self.specialist = User.objects.create_user(
            username="spec", password="x", role=User.Role.SPECIALIST
        )
        self.shift = Shift.objects.create(opened_by=self.specialist)
        self.entry = JournalEntry.objects.create(shift=self.shift, action_task="Проверка печати")

    def test_list_renders_and_filters(self):
        self.client.force_login(self.specialist)
        self.assertEqual(self.client.get(reverse("journal:entry_list")).status_code, 200)
        response = self.client.get(reverse("journal:entry_list"), {"q": "печати"})
        self.assertContains(response, "Проверка печати")

    def test_create_entry(self):
        self.client.force_login(self.specialist)
        response = self.client.post(
            reverse("journal:entry_create"),
            {
                "occurred_at": timezone.now().strftime("%Y-%m-%dT%H:%M"),
                "equipment_line": "Serac",
                "action_task": "Новая запись",
                "solution": "решение",
                "downtime": "",
                "print_head": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        created = JournalEntry.objects.get(action_task="Новая запись")
        self.assertEqual(created.created_by, self.specialist)
        self.assertEqual(created.shift, self.shift)

    def test_update_entry(self):
        self.client.force_login(self.specialist)
        response = self.client.post(
            reverse("journal:entry_update", args=[self.entry.pk]),
            {
                "occurred_at": timezone.now().strftime("%Y-%m-%dT%H:%M"),
                "equipment_line": "AVE",
                "action_task": "Обновлено",
                "solution": "",
                "downtime": "",
                "print_head": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.action_task, "Обновлено")

    def test_delete_entry(self):
        self.client.force_login(self.specialist)
        response = self.client.post(reverse("journal:entry_delete", args=[self.entry.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(JournalEntry.objects.filter(pk=self.entry.pk).exists())

    def test_export_create_and_list(self):
        self.client.force_login(self.specialist)
        response = self.client.get(reverse("journal:export_create"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(JournalExport.objects.filter(is_full=True).exists())
        self.assertEqual(self.client.get(reverse("journal:export_list")).status_code, 200)
