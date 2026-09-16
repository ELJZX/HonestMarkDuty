from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from checklists.exports import _machines_layout, build_checklist_workbook, save_checklist_file
from checklists.markem_exports import build_markem_workbook, save_markem_file
from checklists.models import (
    ChecklistCheck,
    ChecklistGroup,
    ChecklistMachine,
    ChecklistMileage,
    ChecklistResult,
    ChecklistStatus,
    EquipmentChecklist,
    MarkemChecklist,
    MarkemParameter,
    MarkemPrinter,
    MarkemValue,
)
from checklists.services import (
    apply_matrix,
    apply_markem_values,
    build_matrix,
    finalize_checklist,
    finalize_markem_checklist,
    finalize_shift_checklists,
    markem_matrix,
)
from shifts.models import Shift
from checklists.views import CurrentArchiveMixin


class ChecklistBaseTestCase(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin", password="x", role=User.Role.ADMIN, is_superuser=True, is_staff=True
        )
        self.specialist = User.objects.create_user(
            username="spec", password="x", role=User.Role.SPECIALIST
        )
        self.group = ChecklistGroup.objects.create(name="Цех №1", sort_order=0)
        self.machine = ChecklistMachine.objects.create(group=self.group, name="New Serac", sort_order=0)
        self.check = ChecklistCheck.objects.create(name="Проверка печати", sort_order=0)
        self.checklist = EquipmentChecklist.objects.create(
            date=timezone.localdate(), performed_by=self.specialist, created_by=self.specialist
        )


class ChecklistModelTests(ChecklistBaseTestCase):
    def test_str_and_status_badge(self):
        self.assertIn("Чеклист", str(self.checklist))
        self.assertEqual(self.checklist.status_badge, "badge-muted")

    def test_critical_count(self):
        ChecklistResult.objects.create(
            checklist=self.checklist, machine=self.machine, check_item=self.check, score=1
        )
        ChecklistResult.objects.create(
            checklist=self.checklist,
            machine=self.machine,
            check_item=ChecklistCheck.objects.create(name="Вторая", sort_order=1),
            score=3,
        )
        self.assertEqual(self.checklist.critical_count, 1)


class ChecklistServiceTests(ChecklistBaseTestCase):
    def test_build_matrix_structure(self):
        matrix = build_matrix(self.checklist)
        self.assertIn("machine_columns", matrix)
        self.assertIn("rows", matrix)
        self.assertIn("mileage_cells", matrix)
        self.assertEqual(len(matrix["all_machines"]), 1)

    def test_apply_matrix(self):
        apply_matrix(
            self.checklist,
            {
                f"score__{self.machine.id}__{self.check.id}": "2",
                f"mileage__{self.machine.id}": "12,5",
            },
        )
        self.assertTrue(
            ChecklistResult.objects.filter(checklist=self.checklist, score=2).exists()
        )
        mileage = ChecklistMileage.objects.get(checklist=self.checklist)
        self.assertEqual(float(mileage.value), 12.5)

    def test_apply_matrix_ignores_blank(self):
        apply_matrix(self.checklist, {f"score__{self.machine.id}__{self.check.id}": ""})
        self.assertEqual(self.checklist.results.count(), 0)

    def test_finalize_creates_file(self):
        apply_matrix(self.checklist, {f"score__{self.machine.id}__{self.check.id}": "3"})
        finalize_checklist(self.checklist)
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.status, ChecklistStatus.FINAL)
        self.assertTrue(self.checklist.file)

    def test_build_workbook_title(self):
        workbook = build_checklist_workbook(self.checklist)
        self.assertIn("Чек лист технического осмотра", workbook.active["A1"].value)

    def test_machines_layout_skips_empty_group_and_spans(self):
        ChecklistMachine.objects.create(group=self.group, name="Второй", sort_order=1)
        ChecklistGroup.objects.create(name="Пустая", sort_order=1)
        machines, spans, last_col = _machines_layout()
        names = [m.name for m in machines]
        self.assertIn("New Serac", names)
        self.assertIn("Второй", names)
        self.assertNotIn("Пустая", [s[0] for s in spans])
        span = next(s for s in spans if s[0] == "Цех №1")
        self.assertEqual(span[2] - span[1], 1)
        self.assertGreaterEqual(last_col, 3)

    def test_workbook_with_multiple_machines(self):
        ChecklistMachine.objects.create(group=self.group, name="Второй", sort_order=1)
        ChecklistGroup.objects.create(name="Пустая", sort_order=1)
        workbook = build_checklist_workbook(self.checklist)
        self.assertIn("Чек лист", workbook.active["A1"].value)

    def test_save_checklist_file(self):
        save_checklist_file(self.checklist)
        self.checklist.refresh_from_db()
        self.assertTrue(self.checklist.file.name.endswith(".xlsx"))


class ChecklistViewTests(ChecklistBaseTestCase):
    def test_list_requires_login(self):
        self.assertEqual(self.client.get(reverse("checklists:checklist_list")).status_code, 302)

    def test_list_renders(self):
        self.client.force_login(self.specialist)
        self.assertEqual(self.client.get(reverse("checklists:checklist_list")).status_code, 200)

    def test_list_shows_current_and_archive(self):
        final = EquipmentChecklist.objects.create(
            date=timezone.localdate() - timedelta(days=1),
            performed_by=self.specialist,
            created_by=self.specialist,
            status=ChecklistStatus.FINAL,
        )
        self.client.force_login(self.specialist)
        response = self.client.get(reverse("checklists:checklist_list"))
        self.assertEqual(response.context["current_checklist"], self.checklist)
        self.assertIn(final, list(response.context["archive_checklists"]))
        self.assertContains(response, "Создать новый чеклист")
        self.assertContains(response, "Редактировать чеклист")
        self.assertContains(response, "Текущий чеклист")
        self.assertContains(response, "Архив чеклистов")
        self.assertContains(response, "Скачать чеклист")

    def test_hub_lists_both_checklists(self):
        self.client.force_login(self.specialist)
        response = self.client.get(reverse("checklists:hub"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Осмотр оборудования «Честный знак»")
        self.assertContains(response, "Технический осмотр и обслуживание принтеров Markem Image")

    def test_markem_page_renders(self):
        self.client.force_login(self.specialist)
        self.assertEqual(self.client.get(reverse("checklists:markem")).status_code, 200)

    def test_close_moves_to_archive(self):
        self.client.force_login(self.specialist)
        response = self.client.post(
            reverse("checklists:checklist_close", args=[self.checklist.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.status, ChecklistStatus.FINAL)
        self.assertTrue(self.checklist.file)

    def test_closed_checklist_not_editable_by_specialist(self):
        self.checklist.status = ChecklistStatus.FINAL
        self.checklist.save()
        self.client.force_login(self.specialist)
        self.assertEqual(
            self.client.get(
                reverse("checklists:checklist_update", args=[self.checklist.pk])
            ).status_code,
            403,
        )
        self.client.force_login(self.admin)
        self.assertEqual(
            self.client.get(
                reverse("checklists:checklist_update", args=[self.checklist.pk])
            ).status_code,
            200,
        )

    def test_download_generates_file(self):
        self.client.force_login(self.specialist)
        response = self.client.get(
            reverse("checklists:checklist_download", args=[self.checklist.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.checklist.refresh_from_db()
        self.assertTrue(self.checklist.file)

    def test_date_export_generates_and_redirects(self):
        self.client.force_login(self.specialist)
        response = self.client.get(
            reverse("checklists:checklist_date_export"),
            {"date": timezone.localdate().isoformat()},
        )
        self.assertEqual(response.status_code, 302)
        self.checklist.refresh_from_db()
        self.assertTrue(self.checklist.file)

    def test_date_export_missing_shows_message(self):
        self.client.force_login(self.specialist)
        response = self.client.get(
            reverse("checklists:checklist_date_export"),
            {"date": "2000-01-01"},
            follow=True,
        )
        self.assertRedirects(response, reverse("journal:export_list"))
        self.assertContains(response, "Чек-лист за выбранную дату не найден")

    def test_detail_renders(self):
        self.client.force_login(self.specialist)
        response = self.client.get(reverse("checklists:checklist_detail", args=[self.checklist.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("machine_columns", response.context)

    def test_create_with_finalize(self):
        self.client.force_login(self.specialist)
        response = self.client.post(
            reverse("checklists:checklist_create"),
            {
                "date": timezone.localdate().isoformat(),
                "performed_by": self.specialist.pk,
                "note": "",
                f"score__{self.machine.id}__{self.check.id}": "3",
                f"mileage__{self.machine.id}": "21.5",
                "finalize": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        checklist = EquipmentChecklist.objects.latest("id")
        self.assertEqual(checklist.status, ChecklistStatus.FINAL)
        self.assertTrue(checklist.file)
        self.assertEqual(checklist.results.count(), 1)

    def test_viewer_cannot_create(self):
        viewer = User.objects.create_user(username="v", password="x", role=User.Role.VIEWER)
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(reverse("checklists:checklist_create")).status_code, 403)

    def test_create_without_finalize_stays_draft(self):
        self.client.force_login(self.specialist)
        response = self.client.post(
            reverse("checklists:checklist_create"),
            {
                "date": timezone.localdate().isoformat(),
                "performed_by": self.specialist.pk,
                "note": "",
                f"score__{self.machine.id}__{self.check.id}": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        created = EquipmentChecklist.objects.latest("id")
        self.assertEqual(created.status, ChecklistStatus.DRAFT)

    def test_update_with_finalize(self):
        self.client.force_login(self.specialist)
        response = self.client.post(
            reverse("checklists:checklist_update", args=[self.checklist.pk]),
            {
                "date": timezone.localdate().isoformat(),
                "performed_by": self.specialist.pk,
                "note": "",
                f"score__{self.machine.id}__{self.check.id}": "3",
                "finalize": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.status, ChecklistStatus.FINAL)

    def test_generate_view(self):
        self.client.force_login(self.specialist)
        response = self.client.post(
            reverse("checklists:checklist_generate", args=[self.checklist.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.checklist.refresh_from_db()
        self.assertTrue(self.checklist.file)

    def test_delete_admin_only(self):
        self.client.force_login(self.specialist)
        self.assertEqual(
            self.client.post(reverse("checklists:checklist_delete", args=[self.checklist.pk])).status_code,
            403,
        )
        self.client.force_login(self.admin)
        self.assertEqual(
            self.client.post(reverse("checklists:checklist_delete", args=[self.checklist.pk])).status_code,
            302,
        )

    def test_create_form_renders(self):
        self.client.force_login(self.specialist)
        response = self.client.get(reverse("checklists:checklist_create"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)

    def test_update_checklist_get_and_post(self):
        self.client.force_login(self.specialist)
        response = self.client.get(reverse("checklists:checklist_update", args=[self.checklist.pk]))
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            reverse("checklists:checklist_update", args=[self.checklist.pk]),
            {
                "date": timezone.localdate().isoformat(),
                "performed_by": self.specialist.pk,
                "note": "обновлено",
                f"score__{self.machine.id}__{self.check.id}": "2",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.checklist.results.count(), 1)

    def test_date_export_invalid_date_shows_message(self):
        self.client.force_login(self.specialist)
        response = self.client.get(
            reverse("checklists:checklist_date_export"), {"date": "bad"}, follow=True
        )
        self.assertRedirects(response, reverse("journal:export_list"))
        self.assertContains(response, "Укажите дату")


class MarkemBaseTestCase(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="madmin", password="x", role=User.Role.ADMIN, is_superuser=True, is_staff=True
        )
        self.specialist = User.objects.create_user(
            username="mspec", password="x", role=User.Role.SPECIALIST
        )
        self.printer = MarkemPrinter.objects.create(name="TEST-FR-0001", sort_order=999)
        self.parameter = MarkemParameter.objects.create(name="Тестовый параметр", sort_order=999)
        self.checklist = MarkemChecklist.objects.create(
            date=timezone.localdate(), performed_by=self.specialist, created_by=self.specialist
        )


class MarkemServiceTests(MarkemBaseTestCase):
    def test_defaults_seeded(self):
        self.assertGreaterEqual(MarkemPrinter.objects.count(), 12)
        self.assertGreaterEqual(MarkemParameter.objects.count(), 9)

    def test_matrix_structure(self):
        matrix = markem_matrix(self.checklist)
        self.assertIn(self.printer, matrix["printers"])
        self.assertIn(self.parameter, [row["parameter"] for row in matrix["rows"]])
        parameters = matrix["rows"]
        self.assertTrue(all(len(row["cells"]) == len(matrix["printers"]) for row in parameters))

    def test_matrix_without_checklist(self):
        matrix = markem_matrix(None)
        self.assertIn(self.printer, matrix["printers"])

    def test_apply_values(self):
        apply_markem_values(
            self.checklist, {f"val__{self.printer.id}__{self.parameter.id}": "  42  "}
        )
        value = MarkemValue.objects.get(checklist=self.checklist)
        self.assertEqual(value.value, "42")

    def test_apply_values_ignores_blank_and_bad_keys(self):
        apply_markem_values(
            self.checklist,
            {
                f"val__{self.printer.id}__{self.parameter.id}": "   ",
                "val__broken": "1",
                "unrelated": "x",
            },
        )
        self.assertEqual(self.checklist.values.count(), 0)

    def test_apply_values_replaces_existing(self):
        MarkemValue.objects.create(
            checklist=self.checklist, printer=self.printer, parameter=self.parameter, value="old"
        )
        apply_markem_values(
            self.checklist, {f"val__{self.printer.id}__{self.parameter.id}": "new"}
        )
        self.assertEqual(self.checklist.values.count(), 1)
        self.assertEqual(self.checklist.values.first().value, "new")

    def test_finalize_creates_file(self):
        apply_markem_values(
            self.checklist, {f"val__{self.printer.id}__{self.parameter.id}": "15066"}
        )
        finalize_markem_checklist(self.checklist)
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.status, ChecklistStatus.FINAL)
        self.assertTrue(self.checklist.file)

    def test_save_markem_file(self):
        save_markem_file(self.checklist)
        self.checklist.refresh_from_db()
        self.assertTrue(self.checklist.file.name.endswith(".xlsx"))

    def test_workbook_title(self):
        workbook = build_markem_workbook(self.checklist)
        self.assertIn("Markem Image 9450", workbook.active["A1"].value)


class MarkemViewTests(MarkemBaseTestCase):
    def test_list_requires_login(self):
        self.assertEqual(self.client.get(reverse("checklists:markem")).status_code, 302)

    def test_list_renders_with_current_and_archive(self):
        final = MarkemChecklist.objects.create(
            date=timezone.localdate() - timedelta(days=1),
            performed_by=self.specialist,
            created_by=self.specialist,
            status=ChecklistStatus.FINAL,
        )
        self.client.force_login(self.specialist)
        response = self.client.get(reverse("checklists:markem"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["current_checklist"], self.checklist)
        self.assertIn(final, list(response.context["archive_checklists"]))
        self.assertContains(response, "Архив чеклистов")
        self.assertContains(response, "Скачать чеклист")

    def test_create_checklist(self):
        self.client.force_login(self.specialist)
        response = self.client.post(
            reverse("checklists:markem_create"),
            {
                "date": timezone.localdate().isoformat(),
                "performed_by": self.specialist.pk,
                "note": "",
                f"val__{self.printer.id}__{self.parameter.id}": "15066",
            },
        )
        self.assertEqual(response.status_code, 302)
        created = MarkemChecklist.objects.latest("id")
        self.assertEqual(created.values.count(), 1)
        self.assertEqual(created.created_by, self.specialist)

    def test_viewer_cannot_create(self):
        viewer = User.objects.create_user(username="mv", password="x", role=User.Role.VIEWER)
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(reverse("checklists:markem_create")).status_code, 403)

    def test_create_with_finalize(self):
        self.client.force_login(self.specialist)
        response = self.client.post(
            reverse("checklists:markem_create"),
            {
                "date": timezone.localdate().isoformat(),
                "performed_by": self.specialist.pk,
                "note": "",
                f"val__{self.printer.id}__{self.parameter.id}": "15066",
                "finalize": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        created = MarkemChecklist.objects.latest("id")
        self.assertEqual(created.status, ChecklistStatus.FINAL)

    def test_update_with_finalize(self):
        self.client.force_login(self.specialist)
        response = self.client.post(
            reverse("checklists:markem_update", args=[self.checklist.pk]),
            {
                "date": timezone.localdate().isoformat(),
                "performed_by": self.specialist.pk,
                "note": "",
                f"val__{self.printer.id}__{self.parameter.id}": "1",
                "finalize": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.status, ChecklistStatus.FINAL)

    def test_close_moves_to_archive(self):
        self.client.force_login(self.specialist)
        response = self.client.post(
            reverse("checklists:markem_close", args=[self.checklist.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.status, ChecklistStatus.FINAL)
        self.assertTrue(self.checklist.file)

    def test_download_generates_file(self):
        self.client.force_login(self.specialist)
        response = self.client.get(
            reverse("checklists:markem_download", args=[self.checklist.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.checklist.refresh_from_db()
        self.assertTrue(self.checklist.file)

    def test_date_export_generates_and_redirects(self):
        self.client.force_login(self.specialist)
        response = self.client.get(
            reverse("checklists:markem_date_export"),
            {"date": timezone.localdate().isoformat()},
        )
        self.assertEqual(response.status_code, 302)
        self.checklist.refresh_from_db()
        self.assertTrue(self.checklist.file)

    def test_date_export_missing_shows_message(self):
        self.client.force_login(self.specialist)
        response = self.client.get(
            reverse("checklists:markem_date_export"),
            {"date": "2000-01-01"},
            follow=True,
        )
        self.assertRedirects(response, reverse("journal:export_list"))
        self.assertContains(response, "Чек-лист за выбранную дату не найден")

    def test_closed_not_editable_by_specialist(self):
        self.checklist.status = ChecklistStatus.FINAL
        self.checklist.save()
        self.client.force_login(self.specialist)
        self.assertEqual(
            self.client.get(
                reverse("checklists:markem_update", args=[self.checklist.pk])
            ).status_code,
            403,
        )
        self.client.force_login(self.admin)
        self.assertEqual(
            self.client.get(
                reverse("checklists:markem_update", args=[self.checklist.pk])
            ).status_code,
            200,
        )

    def test_create_form_renders(self):
        self.client.force_login(self.specialist)
        self.assertEqual(
            self.client.get(reverse("checklists:markem_create")).status_code, 200
        )

    def test_update_markem_checklist_get_and_post(self):
        self.client.force_login(self.specialist)
        self.assertEqual(
            self.client.get(
                reverse("checklists:markem_update", args=[self.checklist.pk])
            ).status_code,
            200,
        )
        response = self.client.post(
            reverse("checklists:markem_update", args=[self.checklist.pk]),
            {
                "date": timezone.localdate().isoformat(),
                "performed_by": self.specialist.pk,
                "note": "обновлено",
                f"val__{self.printer.id}__{self.parameter.id}": "999",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.checklist.values.count(), 1)

    def test_delete_markem_admin(self):
        self.client.force_login(self.specialist)
        self.assertEqual(
            self.client.post(
                reverse("checklists:markem_delete", args=[self.checklist.pk])
            ).status_code,
            403,
        )
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("checklists:markem_delete", args=[self.checklist.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(MarkemChecklist.objects.filter(pk=self.checklist.pk).exists())

    def test_date_export_invalid_date_shows_message(self):
        self.client.force_login(self.specialist)
        response = self.client.get(
            reverse("checklists:markem_date_export"), {"date": "bad"}, follow=True
        )
        self.assertRedirects(response, reverse("journal:export_list"))
        self.assertContains(response, "Укажите дату")


class ChecklistServiceEdgeTests(ChecklistBaseTestCase):
    def test_apply_matrix_ignores_malformed_entries(self):
        apply_matrix(
            self.checklist,
            {
                f"score__{self.machine.id}__{self.check.id}": "не число",
                f"mileage__{self.machine.id}": "abc",
                "score__malformed": "2",
                f"score__{self.machine.id}__{self.check.id}__extra": "2",
            },
        )
        self.assertEqual(self.checklist.results.count(), 0)
        self.assertEqual(self.checklist.mileages.count(), 0)

    def test_apply_matrix_ignores_out_of_range_score(self):
        apply_matrix(
            self.checklist, {f"score__{self.machine.id}__{self.check.id}": "9"}
        )
        self.assertEqual(self.checklist.results.count(), 0)

    def test_finalize_shift_checklists(self):
        shift = Shift.objects.create(opened_by=self.specialist)
        draft = EquipmentChecklist.objects.create(
            shift=shift,
            date=timezone.localdate(),
            performed_by=self.specialist,
            created_by=self.specialist,
            status=ChecklistStatus.DRAFT,
        )
        count = finalize_shift_checklists(shift)
        self.assertEqual(count, 1)
        draft.refresh_from_db()
        self.assertEqual(draft.status, ChecklistStatus.FINAL)
        self.assertTrue(draft.file)

    def test_finalize_shift_checklists_skips_final(self):
        shift = Shift.objects.create(opened_by=self.specialist)
        EquipmentChecklist.objects.create(
            shift=shift,
            date=timezone.localdate(),
            performed_by=self.specialist,
            created_by=self.specialist,
            status=ChecklistStatus.FINAL,
        )
        self.assertEqual(finalize_shift_checklists(shift), 0)


class ChecklistListBranchTests(TestCase):
    def setUp(self):
        self.specialist = User.objects.create_user(
            username="cl-branch", password="x", role=User.Role.SPECIALIST
        )
        self.shift = Shift.objects.create(
            opened_by=self.specialist, status=Shift.Status.OPEN
        )

    def test_list_current_taken_from_open_shift(self):
        checklist = EquipmentChecklist.objects.create(
            shift=self.shift,
            date=timezone.localdate(),
            performed_by=self.specialist,
            created_by=self.specialist,
            status=ChecklistStatus.DRAFT,
        )
        self.client.force_login(self.specialist)
        response = self.client.get(reverse("checklists:checklist_list"))
        self.assertEqual(response.context["current_checklist"], checklist)

    def test_markem_list_current_taken_from_open_shift(self):
        checklist = MarkemChecklist.objects.create(
            shift=self.shift,
            date=timezone.localdate(),
            performed_by=self.specialist,
            created_by=self.specialist,
        )
        self.client.force_login(self.specialist)
        response = self.client.get(reverse("checklists:markem"))
        self.assertEqual(response.context["current_checklist"], checklist)

    def test_matrix_for_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            CurrentArchiveMixin().matrix_for(None)

    def test_checklist_create_invalid_post_rerenders(self):
        self.client.force_login(self.specialist)
        response = self.client.post(reverse("checklists:checklist_create"), {"date": "bad"})
        self.assertEqual(response.status_code, 200)

    def test_checklist_update_invalid_post_rerenders(self):
        checklist = EquipmentChecklist.objects.create(
            date=timezone.localdate(),
            performed_by=self.specialist,
            created_by=self.specialist,
        )
        self.client.force_login(self.specialist)
        response = self.client.post(
            reverse("checklists:checklist_update", args=[checklist.pk]), {"date": "bad"}
        )
        self.assertEqual(response.status_code, 200)

    def test_markem_create_invalid_post_rerenders(self):
        self.client.force_login(self.specialist)
        response = self.client.post(reverse("checklists:markem_create"), {"date": "bad"})
        self.assertEqual(response.status_code, 200)

    def test_markem_update_invalid_post_rerenders(self):
        checklist = MarkemChecklist.objects.create(
            date=timezone.localdate(),
            performed_by=self.specialist,
            created_by=self.specialist,
        )
        self.client.force_login(self.specialist)
        response = self.client.post(
            reverse("checklists:markem_update", args=[checklist.pk]), {"date": "bad"}
        )
        self.assertEqual(response.status_code, 200)
