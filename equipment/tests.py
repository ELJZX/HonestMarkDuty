from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from core.models import ProductionLine, ProductionSite, Workshop
from equipment.forms import EquipmentForm
from equipment.models import (
    Criticality,
    Equipment,
    EquipmentStatus,
    MaintenanceKind,
    MaintenanceRecord,
)


class EquipmentModelTests(TestCase):
    def test_status_change_creates_log(self):
        equipment = Equipment.objects.create(
            name="Упаковщик", status=EquipmentStatus.OPERATIONAL
        )
        self.assertEqual(equipment.status_logs.count(), 0)
        equipment.status = EquipmentStatus.REPAIR
        equipment.save()
        self.assertEqual(equipment.status_logs.count(), 1)
        self.assertEqual(equipment.status_logs.first().status, EquipmentStatus.REPAIR)

    def test_no_log_when_status_unchanged(self):
        equipment = Equipment.objects.create(name="Принтер")
        equipment.name = "Принтер Zebra"
        equipment.save()
        self.assertEqual(equipment.status_logs.count(), 0)

    def test_status_badge_mapping(self):
        equipment = Equipment.objects.create(name="X")
        expectations = {
            EquipmentStatus.OPERATIONAL: "badge-ok",
            EquipmentStatus.MAINTENANCE: "badge-warn",
            EquipmentStatus.REPAIR: "badge-danger",
            EquipmentStatus.DECOMMISSIONED: "badge-muted",
        }
        for status, badge in expectations.items():
            equipment.status = status
            self.assertEqual(equipment.status_badge, badge)

    def test_maintenance_overdue(self):
        equipment = Equipment.objects.create(
            name="X",
            next_maintenance_at=timezone.localdate() - timedelta(days=1),
        )
        self.assertTrue(equipment.is_maintenance_overdue)
        equipment.next_maintenance_at = timezone.localdate() + timedelta(days=10)
        self.assertFalse(equipment.is_maintenance_overdue)

    def test_str_and_maintenance_str(self):
        equipment = Equipment.objects.create(name="Упаковщик")
        self.assertIn("Упаковщик", str(equipment))
        record = MaintenanceRecord.objects.create(
            equipment=equipment, kind=MaintenanceKind.TO, description="ТО"
        )
        self.assertIn("Техническое обслуживание", str(record))


class EquipmentViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin", password="x", role=User.Role.ADMIN, is_superuser=True, is_staff=True
        )
        self.specialist = User.objects.create_user(
            username="spec", password="x", role=User.Role.SPECIALIST
        )
        self.viewer = User.objects.create_user(username="viewer", password="x", role=User.Role.VIEWER)
        self.equipment = Equipment.objects.create(
            name="Упаковщик",
            status=EquipmentStatus.OPERATIONAL,
        )

    def test_list_and_detail_render(self):
        self.client.force_login(self.specialist)
        self.assertEqual(self.client.get(reverse("equipment:equipment_list")).status_code, 200)
        self.assertEqual(
            self.client.get(reverse("equipment:equipment_detail", args=[self.equipment.pk])).status_code, 200
        )
        response = self.client.get(reverse("equipment:equipment_list"), {"q": "Упаковщик"})
        self.assertContains(response, "Упаковщик")

    def test_create_equipment(self):
        self.client.force_login(self.specialist)
        response = self.client.post(
            reverse("equipment:equipment_create"),
            {
                "name": "Новое оборудование",
                "status": EquipmentStatus.OPERATIONAL,
                "criticality": Criticality.MEDIUM,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Equipment.objects.filter(name="Новое оборудование").exists())

    def test_viewer_cannot_create(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(reverse("equipment:equipment_create")).status_code, 403)

    def test_form_has_minimal_fields(self):
        self.assertEqual(
            list(EquipmentForm().fields.keys()),
            ["name", "workshop", "line", "manufacturer", "model_name", "ip_address", "print_head", "notes"],
        )

    def test_update_equipment(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("equipment:equipment_update", args=[self.equipment.pk]),
            {
                "name": "Упаковщик v2",
                "status": EquipmentStatus.OPERATIONAL,
                "criticality": Criticality.HIGH,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.equipment.refresh_from_db()
        self.assertEqual(self.equipment.name, "Упаковщик v2")

    def test_delete_equipment_admin_only(self):
        self.client.force_login(self.specialist)
        self.assertEqual(
            self.client.post(reverse("equipment:equipment_delete", args=[self.equipment.pk])).status_code, 403
        )
        self.client.force_login(self.admin)
        self.assertEqual(
            self.client.post(reverse("equipment:equipment_delete", args=[self.equipment.pk])).status_code, 302
        )

    def test_status_change_view(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("equipment:status_change", args=[self.equipment.pk]),
            {"status": EquipmentStatus.REPAIR, "comment": "поломка"},
        )
        self.assertEqual(response.status_code, 302)
        self.equipment.refresh_from_db()
        self.assertEqual(self.equipment.status, EquipmentStatus.REPAIR)
        self.assertEqual(self.equipment.status_logs.first().comment, "поломка")

    def test_status_change_same_status_creates_note(self):
        self.client.force_login(self.admin)
        self.client.post(
            reverse("equipment:status_change", args=[self.equipment.pk]),
            {"status": EquipmentStatus.OPERATIONAL, "comment": "осмотр без изменений"},
        )
        self.assertEqual(self.equipment.status_logs.count(), 1)

    def test_maintenance_create_view(self):
        self.client.force_login(self.specialist)
        response = self.client.post(
            reverse("equipment:maintenance_create", args=[self.equipment.pk]),
            {"kind": MaintenanceKind.TO, "performed_at": "2026-09-12", "description": "ТО", "performer": "Сервис"},
        )
        self.assertEqual(response.status_code, 302)
        self.equipment.refresh_from_db()
        self.assertEqual(self.equipment.maintenance_records.count(), 1)
        self.assertIsNotNone(self.equipment.next_maintenance_at)


class SeedStructureCommandTests(TestCase):
    def test_seed_structure_order(self):
        call_command("seed_structure", verbosity=0)
        names = list(
            Workshop.objects.filter(is_active=True)
            .order_by("sort_order", "name")
            .values_list("name", flat=True)
        )
        self.assertEqual(names, ["Цех №1", "КМЦ", "ПМЦ", "ПСМ", "Творожный цех"])

        kmc = Workshop.objects.get(name="КМЦ")
        lines = list(
            kmc.lines.filter(is_active=True)
            .order_by("sort_order", "name")
            .values_list("name", flat=True)
        )
        self.assertEqual(lines, ["AVE", "Finnah", "Trepko", "C3 Flex", "Джонга 1,2"])

        pmc = Workshop.objects.get(name="ПСМ")
        lines = list(
            pmc.lines.filter(is_active=True)
            .order_by("sort_order", "name")
            .values_list("name", flat=True)
        )
        self.assertEqual(lines, ["Школьник (А1(1),А1(2))", "EL4", "A3 Flex", "Serac"])


class EquipmentBoardTests(TestCase):
    def setUp(self):
        self.specialist = User.objects.create_user(
            username="board-spec", password="x", role=User.Role.SPECIALIST
        )
        self.admin = User.objects.create_user(
            username="board-admin-0", password="x", role=User.Role.ADMIN, is_superuser=True
        )
        self.workshop = Workshop.objects.create(name="Мясной цех", code="МЦ")
        self.line = ProductionLine.objects.create(
            workshop=self.workshop, name="Линия №1", code="L-01"
        )
        self.equipment = Equipment.objects.create(
            name="Термоупаковщик",
            workshop=self.workshop,
            line=self.line,
        )

    def test_line_str_and_equipment_count(self):
        self.assertEqual(str(self.line), "Мясной цех · Линия №1")
        self.assertEqual(self.line.equipment_count, 1)

    def test_board_renders_workshops(self):
        self.client.force_login(self.specialist)
        response = self.client.get(reverse("equipment:board"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.workshop.name)

    def test_workshop_lines_page(self):
        self.client.force_login(self.specialist)
        response = self.client.get(reverse("equipment:workshop_lines", args=[self.workshop.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.line.name)

    def test_line_equipment_page(self):
        self.client.force_login(self.specialist)
        response = self.client.get(reverse("equipment:line_equipment", args=[self.line.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.equipment.name)

    def test_registry_shows_line(self):
        self.client.force_login(self.specialist)
        response = self.client.get(reverse("equipment:equipment_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.line.name)

    def test_line_create_view(self):
        self.client.force_login(self.specialist)
        response = self.client.get(
            reverse("equipment:line_create") + f"?workshop={self.workshop.pk}"
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            reverse("equipment:line_create"),
            {
                "workshop": self.workshop.pk,
                "name": "Линия №2",
                "sort_order": 0,
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ProductionLine.objects.filter(workshop=self.workshop, name="Линия №2").exists()
        )

    def test_viewer_cannot_create_line(self):
        viewer = User.objects.create_user(
            username="board-viewer", password="x", role=User.Role.VIEWER
        )
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(reverse("equipment:line_create")).status_code, 403)

    def test_fab_add_buttons(self):
        self.client.force_login(self.specialist)
        self.assertContains(
            self.client.get(reverse("equipment:workshop_lines", args=[self.workshop.pk])),
            "Добавить линию",
        )
        self.assertContains(
            self.client.get(reverse("equipment:line_equipment", args=[self.line.pk])),
            "Добавить оборудование",
        )

    def test_board_fab_admin_only(self):
        self.client.force_login(self.specialist)
        self.assertNotContains(self.client.get(reverse("equipment:board")), "Добавить цех")
        admin = User.objects.create_user(
            username="board-admin", password="x", role=User.Role.ADMIN, is_superuser=True
        )
        self.client.force_login(admin)
        self.assertContains(self.client.get(reverse("equipment:board")), "Добавить цех")

    def test_line_delete_admin_only(self):
        self.client.force_login(self.specialist)
        self.assertEqual(
            self.client.post(reverse("equipment:line_delete", args=[self.line.pk])).status_code,
            403,
        )
        admin = User.objects.create_user(
            username="board-admin2", password="x", role=User.Role.ADMIN, is_superuser=True
        )
        self.client.force_login(admin)
        response = self.client.post(reverse("equipment:line_delete", args=[self.line.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ProductionLine.objects.filter(pk=self.line.pk).exists())

    def test_delete_equipment_returns_to_line(self):
        self.client.force_login(
            User.objects.create_user(
                username="board-admin3", password="x", role=User.Role.ADMIN, is_superuser=True
            )
        )
        response = self.client.post(reverse("equipment:equipment_delete", args=[self.equipment.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("equipment:line_equipment", args=[self.line.pk]))

    def test_line_update_view(self):
        self.client.force_login(self.admin)
        self.assertEqual(
            self.client.get(reverse("equipment:line_update", args=[self.line.pk])).status_code,
            200,
        )
        response = self.client.post(
            reverse("equipment:line_update", args=[self.line.pk]),
            {
                "workshop": self.workshop.pk,
                "name": "Линия №1-бис",
                "sort_order": 0,
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.line.refresh_from_db()
        self.assertEqual(self.line.name, "Линия №1-бис")

    def test_viewer_cannot_edit_line(self):
        viewer = User.objects.create_user(
            username="board-viewer2", password="x", role=User.Role.VIEWER
        )
        self.client.force_login(viewer)
        self.assertEqual(
            self.client.get(reverse("equipment:line_update", args=[self.line.pk])).status_code,
            403,
        )

    def test_line_reorder(self):
        second = ProductionLine.objects.create(
            workshop=self.workshop, name="Линия №2", sort_order=1
        )
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("equipment:line_reorder", args=[self.workshop.pk]),
            {"order": f"{second.pk},{self.line.pk}"},
        )
        self.assertEqual(response.status_code, 302)
        second.refresh_from_db()
        self.line.refresh_from_db()
        self.assertEqual(second.sort_order, 0)
        self.assertEqual(self.line.sort_order, 1)

    def test_reorder_ignores_foreign_lines(self):
        other = Workshop.objects.create(name="Другой цех", code="ДЦ")
        foreign = ProductionLine.objects.create(workshop=other, name="Чужая", sort_order=5)
        self.client.force_login(self.specialist)
        self.client.post(
            reverse("equipment:line_reorder", args=[self.workshop.pk]),
            {"order": f"{foreign.pk},{self.line.pk}"},
        )
        foreign.refresh_from_db()
        self.assertEqual(foreign.sort_order, 5)

    def test_viewer_cannot_reorder_lines(self):
        viewer = User.objects.create_user(
            username="board-viewer3", password="x", role=User.Role.VIEWER
        )
        self.client.force_login(viewer)
        self.assertEqual(
            self.client.post(
                reverse("equipment:line_reorder", args=[self.workshop.pk]), {"order": ""}
            ).status_code,
            403,
        )

    def test_workshop_reorder(self):
        other = Workshop.objects.create(name="Второй цех", code="ВЦ")
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("equipment:workshop_reorder"),
            {"order": f"{other.pk},{self.workshop.pk}"},
        )
        self.assertEqual(response.status_code, 302)
        other.refresh_from_db()
        self.workshop.refresh_from_db()
        self.assertEqual(other.sort_order, 0)
        self.assertEqual(self.workshop.sort_order, 1)

    def test_viewer_cannot_reorder_workshops(self):
        viewer = User.objects.create_user(
            username="board-viewer4", password="x", role=User.Role.VIEWER
        )
        self.client.force_login(viewer)
        self.assertEqual(
            self.client.post(reverse("equipment:workshop_reorder"), {"order": ""}).status_code,
            403,
        )

    def test_create_equipment_with_extra_fields(self):
        self.client.force_login(self.specialist)
        response = self.client.post(
            reverse("equipment:equipment_create"),
            {
                "name": "Принтер",
                "manufacturer": "VideoJet",
                "model_name": "6330",
                "ip_address": "192.168.0.10",
            },
        )
        self.assertEqual(response.status_code, 302)
        equipment = Equipment.objects.get(name="Принтер", manufacturer="VideoJet")
        self.assertEqual(equipment.ip_address, "192.168.0.10")

    def test_create_form_has_presets(self):
        self.client.force_login(self.specialist)
        response = self.client.get(reverse("equipment:equipment_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Быстрое добавление")
        self.assertContains(response, "Matrix 220")
        self.assertContains(response, "Markem Imaje")

    def test_form_sets_workshop_from_line(self):
        form = EquipmentForm(
            data={
                "name": "Новое",
                "line": self.line.pk,
                "status": EquipmentStatus.OPERATIONAL,
                "criticality": Criticality.MEDIUM,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["workshop"], self.workshop)


class EquipmentFilterAndEdgeTests(TestCase):
    def setUp(self):
        self.specialist = User.objects.create_user(
            username="edge-spec", password="x", role=User.Role.SPECIALIST
        )
        self.site = ProductionSite.objects.create(name="Площадка")
        self.workshop = Workshop.objects.create(name="Цех", code="Ц", site=self.site)
        self.line = ProductionLine.objects.create(workshop=self.workshop, name="Линия", code="L")
        self.equipment = Equipment.objects.create(
            name="Обор",
            site=self.site,
            workshop=self.workshop,
            line=self.line,
        )

    def test_list_applies_all_filters(self):
        self.client.force_login(self.specialist)
        response = self.client.get(
            reverse("equipment:equipment_list"),
            {
                "site": self.site.pk,
                "workshop": self.workshop.pk,
                "status": self.equipment.status,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Обор")

    def test_create_get_initial_from_line(self):
        self.client.force_login(self.specialist)
        response = self.client.get(
            reverse("equipment:equipment_create") + f"?line={self.line.pk}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"].initial["line"], self.line.pk)
        self.assertEqual(response.context["form"].initial["workshop"], self.workshop.pk)

    def test_line_create_without_workshop_cancels_to_board(self):
        self.client.force_login(self.specialist)
        response = self.client.get(reverse("equipment:line_create"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["cancel_url"], reverse("equipment:board"))

    def test_status_change_invalid_form_keeps_status(self):
        self.client.force_login(
            User.objects.create_user(
                username="edge-admin", password="x", role=User.Role.ADMIN, is_superuser=True
            )
        )
        response = self.client.post(
            reverse("equipment:status_change", args=[self.equipment.pk]),
            {"status": "not-a-status"},
        )
        self.assertEqual(response.status_code, 302)
        self.equipment.refresh_from_db()
        self.assertNotEqual(self.equipment.status, "not-a-status")

    def test_maintenance_create_invalid_form(self):
        self.client.force_login(self.specialist)
        response = self.client.post(
            reverse("equipment:maintenance_create", args=[self.equipment.pk]), {}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.equipment.maintenance_records.count(), 0)


class SeedStructureEdgeTests(TestCase):
    def test_verbose_output(self):
        out = StringIO()
        call_command("seed_structure", stdout=out)
        self.assertIn("Структура цехов и линий обновлена", out.getvalue())

    def test_recovers_from_integrity_error(self):
        original_save = Workshop.save
        state = {"raised": False}

        def flaky_save(self, *args, **kwargs):
            if not kwargs.get("force_insert") and not state["raised"]:
                state["raised"] = True
                raise IntegrityError("duplicate code")
            return original_save(self, *args, **kwargs)

        with mock.patch.object(Workshop, "save", flaky_save):
            call_command("seed_structure", verbosity=0)
        self.assertTrue(Workshop.objects.filter(name="Цех №1", is_active=True).exists())


class CameraTests(TestCase):
    def setUp(self):
        self.specialist = User.objects.create_user(
            username="cam-spec", password="x", role=User.Role.SPECIALIST
        )
        self.workshop = Workshop.objects.create(name="КМЦ", code="КМЦ")
        self.line = ProductionLine.objects.create(
            workshop=self.workshop, name="AVE", code="L-AVE"
        )
        self.camera = Equipment.objects.create(
            name="AVE",
            workshop=self.workshop,
            line=self.line,
            ip_address="172.16.52.121",
            is_camera=True,
            camera_id=999,
        )
        self.plain = Equipment.objects.create(name="Стол", workshop=self.workshop)

    def test_cameras_page(self):
        self.client.force_login(self.specialist)
        response = self.client.get(reverse("equipment:cameras"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.workshop.name)

    def test_camera_workshop_page(self):
        self.client.force_login(self.specialist)
        response = self.client.get(
            reverse("equipment:camera_workshop", args=[self.workshop.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "AVE")
        self.assertContains(response, 'data-cam-ip="172.16.52.121"')

    def test_camera_detail_has_live_box(self):
        self.client.force_login(self.specialist)
        response = self.client.get(reverse("equipment:equipment_detail", args=[self.camera.pk]))
        self.assertContains(response, "data-cam-ip=\"172.16.52.121\"")

    def test_seed_cameras_maps(self):
        call_command("seed_cameras", verbosity=0)
        camera = Equipment.objects.get(camera_id=5)
        self.assertEqual(camera.name, "AVE")
        self.assertEqual(camera.workshop, self.workshop)
        self.assertEqual(camera.line, self.line)
        self.assertEqual(camera.ip_address, "172.16.52.121")
        self.assertTrue(camera.is_camera)

    def test_camera_not_in_equipment_registry(self):
        self.client.force_login(self.specialist)
        response = self.client.get(reverse("equipment:equipment_list"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "AVE")

    def test_admin_can_create_camera(self):
        admin = User.objects.create_user(
            username="cam-admin", password="x", role=User.Role.ADMIN, is_superuser=True
        )
        self.client.force_login(admin)
        response = self.client.post(
            reverse("equipment:camera_create"),
            {
                "name": "Камера 2",
                "workshop": self.workshop.pk,
                "ip_address": "10.0.0.1",
            },
        )
        self.assertEqual(response.status_code, 302)
        camera = Equipment.objects.get(name="Камера 2")
        self.assertTrue(camera.is_camera)

    def test_specialist_cannot_create_camera(self):
        self.client.force_login(self.specialist)
        self.assertEqual(self.client.get(reverse("equipment:camera_create")).status_code, 403)

    def test_admin_can_delete_camera(self):
        admin = User.objects.create_user(
            username="cam-admin2", password="x", role=User.Role.ADMIN, is_superuser=True
        )
        self.client.force_login(admin)
        response = self.client.post(reverse("equipment:camera_delete", args=[self.camera.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Equipment.objects.filter(pk=self.camera.pk).exists())

    def test_specialist_cannot_delete_camera(self):
        self.client.force_login(self.specialist)
        response = self.client.post(reverse("equipment:camera_delete", args=[self.camera.pk]))
        self.assertEqual(response.status_code, 403)
