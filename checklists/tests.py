from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from checklists.exports import build_checklist_workbook, save_checklist_file
from checklists.models import (
    ChecklistCheck,
    ChecklistGroup,
    ChecklistMachine,
    ChecklistMileage,
    ChecklistResult,
    ChecklistStatus,
    EquipmentChecklist,
)
from checklists.services import apply_matrix, build_matrix, finalize_checklist


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

    def test_list_shows_current_and_previous(self):
        final = EquipmentChecklist.objects.create(
            date=timezone.localdate() - timedelta(days=1),
            performed_by=self.specialist,
            created_by=self.specialist,
            status=ChecklistStatus.FINAL,
        )
        self.client.force_login(self.specialist)
        response = self.client.get(reverse("checklists:checklist_list"))
        self.assertEqual(response.context["current_checklist"], self.checklist)
        self.assertEqual(response.context["previous_checklist"], final)
        self.assertContains(response, "Создать новый чеклист")
        self.assertContains(response, "Редактировать чеклист")
        self.assertContains(response, "Текущий чеклист")
        self.assertContains(response, "Предыдущий (закрытый) чеклист")
        self.assertContains(response, 'class="data checklist-matrix"', count=2)

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
