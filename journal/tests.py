from datetime import timedelta

from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from journal.exports import build_workbook, export_full_journal, group_entries, workbook_response
from journal.forms import JournalEntryForm
from journal.models import JournalEntry, JournalExport
from journal.views import _filter_entries, build_groups
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

    def test_specialist_name_from_shift(self):
        user = User.objects.create_user(username="u3", password="x", last_name="Сидоров")
        shift = Shift.objects.create(opened_by=user)
        entry = JournalEntry(specialist=None, shift=shift)
        self.assertEqual(entry.specialist_name, "Сидоров")

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

    def test_current_shift_on_top_reversed_and_closed_ascending(self):
        JournalEntry.objects.create(
            shift=self.shift,
            action_task="старое",
            occurred_at=timezone.now() - timedelta(hours=2),
        )
        closed = Shift.objects.create(opened_by=self.specialist, status=Shift.Status.CLOSED)
        JournalEntry.objects.create(
            shift=closed,
            action_task="ранняя",
            occurred_at=timezone.now() - timedelta(days=1, hours=1),
        )
        JournalEntry.objects.create(
            shift=closed,
            action_task="поздняя",
            occurred_at=timezone.now() - timedelta(days=1),
        )

        self.client.force_login(self.specialist)
        response = self.client.get(reverse("journal:entry_list"))
        groups = response.context["groups"]

        self.assertTrue(groups[0]["is_current"])
        current_times = [row.occurred_at for row in groups[0]["rows"]]
        self.assertEqual(current_times, sorted(current_times, reverse=True))

        self.assertFalse(groups[-1]["is_current"])
        closed_times = [row.occurred_at for row in groups[-1]["rows"]]
        self.assertEqual(closed_times, sorted(closed_times))

        self.assertContains(response, "j-current")

    def test_create_entry(self):
        self.client.force_login(self.specialist)
        response = self.client.post(
            reverse("journal:entry_create"),
            {
                "occurred_at": timezone.now().strftime("%Y-%m-%dT%H:%M"),
                "equipment_line": "Serac New",
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
        self.client.force_login(self.admin)
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
        self.client.force_login(self.admin)
        response = self.client.post(reverse("journal:entry_delete", args=[self.entry.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(JournalEntry.objects.filter(pk=self.entry.pk).exists())

    def test_export_create_and_list(self):
        self.client.force_login(self.specialist)
        response = self.client.get(reverse("journal:export_create"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(JournalExport.objects.filter(is_full=True).exists())
        self.assertEqual(self.client.get(reverse("journal:export_list")).status_code, 200)

    def test_export_create_empty_journal_warns(self):
        JournalEntry.objects.all().delete()
        self.client.force_login(self.specialist)
        response = self.client.get(reverse("journal:export_create"), follow=True)
        self.assertRedirects(response, reverse("journal:export_list"))
        self.assertContains(response, "Журнал пуст")

    def test_export_list_has_accordion_sections(self):
        self.client.force_login(self.specialist)
        response = self.client.get(reverse("journal:export_list"))
        self.assertContains(response, "Сменный журнал")
        self.assertContains(response, "Чек-лист осмотра оборудования «Честный знак»")
        self.assertContains(
            response,
            "Чек-лист технического осмотра и обслуживания принтеров Markem Image 9450",
        )
        self.assertContains(response, reverse("checklists:checklist_date_export"))
        self.assertContains(response, reverse("checklists:markem_date_export"))

    def test_shift_export_downloads_xlsx(self):
        self.client.force_login(self.specialist)
        response = self.client.get(reverse("journal:shift_export", args=[self.shift.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("spreadsheetml", response["Content-Type"])
        self.assertIn(".xlsx", response["Content-Disposition"])

    def test_period_export_requires_dates(self):
        self.client.force_login(self.specialist)
        response = self.client.get(reverse("journal:export_period"), follow=True)
        self.assertRedirects(response, reverse("journal:export_list"))
        self.assertContains(response, "Укажите начало и конец периода")

    def test_period_export_downloads_and_swaps_dates(self):
        today = timezone.localdate()
        later = (today + timedelta(days=1)).isoformat()
        self.client.force_login(self.specialist)
        response = self.client.get(
            reverse("journal:export_period"),
            {"date_from": later, "date_to": today.isoformat()},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("spreadsheetml", response["Content-Type"])

    def test_period_export_empty_redirects(self):
        self.client.force_login(self.specialist)
        response = self.client.get(
            reverse("journal:export_period"),
            {"date_from": "2000-01-01", "date_to": "2000-01-02"},
            follow=True,
        )
        self.assertRedirects(response, reverse("journal:export_list"))
        self.assertContains(response, "За выбранный период записей нет")


class JournalFilterAndGroupTests(TestCase):
    def setUp(self):
        self.spec = User.objects.create_user(username="spec", password="x", last_name="Иванов")
        self.other = User.objects.create_user(username="other", password="x", last_name="Петров")

    def test_filter_entries_by_query_specialist_and_dates(self):
        entry = JournalEntry.objects.create(
            action_task="проверка печати", specialist=self.spec, occurred_at=timezone.now()
        )
        old = JournalEntry.objects.create(
            action_task="другое",
            specialist=self.other,
            occurred_at=timezone.now() - timedelta(days=5),
        )

        ids = list(_filter_entries(RequestFactory().get("/", {"q": "печати"})).values_list("pk", flat=True))
        self.assertIn(entry.pk, ids)
        self.assertNotIn(old.pk, ids)

        ids = list(_filter_entries(
            RequestFactory().get("/", {"specialist": str(self.other.pk)})
        ).values_list("pk", flat=True))
        self.assertIn(old.pk, ids)
        self.assertNotIn(entry.pk, ids)

        today = timezone.localdate().isoformat()
        ids = list(_filter_entries(
            RequestFactory().get("/", {"date_from": today})
        ).values_list("pk", flat=True))
        self.assertIn(entry.pk, ids)
        self.assertNotIn(old.pk, ids)

    def test_build_groups_marks_current_and_closed(self):
        open_shift = Shift.objects.create(opened_by=self.spec, status=Shift.Status.OPEN)
        JournalEntry.objects.create(shift=open_shift, action_task="a")
        closed = Shift.objects.create(opened_by=self.spec, status=Shift.Status.CLOSED)
        JournalEntry.objects.create(shift=closed, action_task="b")
        groups = build_groups(
            JournalEntry.objects.order_by("occurred_at"), current_shift_id=open_shift.pk
        )
        self.assertEqual(len([g for g in groups if g["is_current"]]), 1)
        self.assertEqual(len([g for g in groups if g["shift_closed"]]), 1)

    def test_workbook_response_headers(self):
        entries = [JournalEntry.objects.create(action_task="a")]
        response = workbook_response(entries, "test_file")
        self.assertEqual(response.status_code, 200)
        self.assertIn("spreadsheetml", response["Content-Type"])
        self.assertIn("test_file.xlsx", response["Content-Disposition"])


class JournalFilterAndFormEdgeTests(TestCase):
    def setUp(self):
        self.specialist = User.objects.create_user(
            username="journal-edge", password="x", role=User.Role.SPECIALIST
        )

    def test_filter_by_date_range(self):
        JournalEntry.objects.create(action_task="В диапазоне", occurred_at=timezone.now())
        self.client.force_login(self.specialist)
        response = self.client.get(
            reverse("journal:entry_list"),
            {"date_from": "2000-01-01", "date_to": "2999-12-31"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "В диапазоне")

    def test_form_keeps_custom_equipment_line_and_print_head(self):
        entry = JournalEntry.objects.create(
            action_task="x", equipment_line="Кастомная линия", print_head="99"
        )
        form = JournalEntryForm(instance=entry)
        line_values = [value for value, _label in form.fields["equipment_line"].choices]
        head_values = [value for value, _label in form.fields["print_head"].choices]
        self.assertIn("Кастомная линия", line_values)
        self.assertIn("99", head_values)
