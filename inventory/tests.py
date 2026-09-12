from django.test import TestCase

from core.models import AuditLog
from inventory.models import (
    Condition,
    InventoryItem,
    InventoryMovement,
    ItemKind,
    MovementType,
)


class InventoryMovementTests(TestCase):
    def setUp(self):
        self.item = InventoryItem.objects.create(
            name="Сканер", kind=ItemKind.DEVICE, quantity=5, min_quantity=2, unit="шт"
        )

    def _move(self, movement_type, quantity):
        movement = InventoryMovement.objects.create(
            item=self.item, movement_type=movement_type, quantity=quantity
        )
        movement.apply()
        self.item.refresh_from_db()
        return movement

    def test_incoming_increases_quantity(self):
        self._move(MovementType.IN, 3)
        self.assertEqual(self.item.quantity, 8)

    def test_outgoing_decreases_quantity(self):
        self._move(MovementType.OUT, 2)
        self.assertEqual(self.item.quantity, 3)

    def test_write_off_never_negative(self):
        self._move(MovementType.WRITE_OFF, 100)
        self.assertEqual(self.item.quantity, 0)

    def test_correction_sets_absolute_quantity(self):
        self._move(MovementType.CORRECTION, 7)
        self.assertEqual(self.item.quantity, 7)

    def test_low_stock_flag(self):
        self.item.quantity = 1
        self.item.save()
        self.assertTrue(self.item.is_low_stock)

    def test_audit_records_creation(self):
        self.assertTrue(
            AuditLog.objects.filter(model_name="inventoryitem", action=AuditLog.Action.CREATE).exists()
        )
