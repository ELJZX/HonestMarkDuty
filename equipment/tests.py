from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from equipment.models import (
    Criticality,
    Equipment,
    EquipmentCategory,
    EquipmentStatus,
    MaintenanceKind,
    MaintenanceRecord,
)


class EquipmentModelTests(TestCase):
    def test_status_change_creates_log(self):
        equipment = Equipment.objects.create(
            name="Упаковщик", inventory_number="EQ-1", status=EquipmentStatus.OPERATIONAL
        )
        self.assertEqual(equipment.status_logs.count(), 0)
        equipment.status = EquipmentStatus.REPAIR
        equipment.save()
        self.assertEqual(equipment.status_logs.count(), 1)
        self.assertEqual(equipment.status_logs.first().status, EquipmentStatus.REPAIR)

    def test_no_log_when_status_unchanged(self):
        equipment = Equipment.objects.create(name="Принтер", inventory_number="EQ-2")
        equipment.name = "Принтер Zebra"
        equipment.save()
        self.assertEqual(equipment.status_logs.count(), 0)

    def test_status_badge_mapping(self):
        equipment = Equipment.objects.create(name="X", inventory_number="EQ-3")
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
            name="X", inventory_number="EQ-4",
            next_maintenance_at=timezone.localdate() - timedelta(days=1),
        )
        self.assertTrue(equipment.is_maintenance_overdue)
        equipment.next_maintenance_at = timezone.localdate() + timedelta(days=10)
        self.assertFalse(equipment.is_maintenance_overdue)

    def test_str_and_maintenance_str(self):
        equipment = Equipment.objects.create(name="Упаковщик", inventory_number="EQ-5")
        self.assertIn("EQ-5", str(equipment))
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
        self.category = EquipmentCategory.objects.create(name="Упаковочное")
        self.equipment = Equipment.objects.create(
            name="Упаковщик", inventory_number="EQ-100", category=self.category,
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
                "inventory_number": "EQ-200",
                "status": EquipmentStatus.OPERATIONAL,
                "criticality": Criticality.MEDIUM,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Equipment.objects.filter(inventory_number="EQ-200").exists())

    def test_viewer_cannot_create(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(reverse("equipment:equipment_create")).status_code, 403)

    def test_update_equipment(self):
        self.client.force_login(self.specialist)
        response = self.client.post(
            reverse("equipment:equipment_update", args=[self.equipment.pk]),
            {
                "name": "Упаковщик v2",
                "inventory_number": "EQ-100",
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
        self.client.force_login(self.specialist)
        response = self.client.post(
            reverse("equipment:status_change", args=[self.equipment.pk]),
            {"status": EquipmentStatus.REPAIR, "comment": "поломка"},
        )
        self.assertEqual(response.status_code, 302)
        self.equipment.refresh_from_db()
        self.assertEqual(self.equipment.status, EquipmentStatus.REPAIR)
        self.assertEqual(self.equipment.status_logs.first().comment, "поломка")

    def test_status_change_same_status_creates_note(self):
        self.client.force_login(self.specialist)
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

    def test_category_views(self):
        self.client.force_login(self.specialist)
        self.assertEqual(self.client.get(reverse("equipment:category_list")).status_code, 200)
        response = self.client.post(reverse("equipment:category_create"), {"name": "Новая"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(EquipmentCategory.objects.filter(name="Новая").exists())
