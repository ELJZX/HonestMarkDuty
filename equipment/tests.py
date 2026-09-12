from django.test import TestCase

from equipment.models import Equipment, EquipmentStatus, EquipmentStatusLog


class EquipmentStatusTests(TestCase):
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
        equipment = Equipment.objects.create(
            name="Принтер", inventory_number="EQ-2", status=EquipmentStatus.OPERATIONAL
        )
        equipment.name = "Принтер Zebra"
        equipment.save()
        self.assertEqual(equipment.status_logs.count(), 0)
