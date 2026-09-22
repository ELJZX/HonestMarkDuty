from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from inventory.forms import InventoryItemForm, InventoryMovementForm
from inventory.models import (
    Condition,
    InventoryItem,
    InventoryMovement,
    ItemCategory,
    ItemKind,
    MovementType,
    StorageLocation,
)
from core.models import Workshop


def make_users():
    admin = User.objects.create_user(
        username="admin", password="x", role=User.Role.ADMIN, is_superuser=True, is_staff=True
    )
    specialist = User.objects.create_user(username="spec", password="x", role=User.Role.SPECIALIST)
    viewer = User.objects.create_user(username="viewer", password="x", role=User.Role.VIEWER)
    return admin, specialist, viewer


class InventoryModelTests(TestCase):
    def setUp(self):
        self.item = InventoryItem.objects.create(
            name="Сканер", kind=ItemKind.DEVICE, quantity=5, min_quantity=2
        )

    def test_is_low_stock(self):
        self.assertFalse(self.item.is_low_stock)
        self.item.quantity = 2
        self.item.save()
        self.assertTrue(self.item.is_low_stock)

    def test_condition_badge_mapping(self):
        expectations = {
            Condition.NEW: "badge-ok",
            Condition.GOOD: "badge-ok",
            Condition.WORN: "badge-warn",
            Condition.NEEDS_REPAIR: "badge-warn",
            Condition.BROKEN: "badge-danger",
        }
        for condition, badge in expectations.items():
            self.item.condition = condition
            self.assertEqual(self.item.condition_badge, badge)

    def test_str(self):
        self.assertEqual(str(self.item), "Сканер")

    def test_location_str(self):
        workshop = Workshop.objects.create(name="Цех", code="Ц")
        location = StorageLocation.objects.create(name="Стеллаж", shelf_code="A-01", workshop=workshop)
        self.assertIn("A-01", str(location))

    def test_category_str(self):
        category = ItemCategory.objects.create(name="Инструмент")
        self.assertEqual(str(category), "Инструмент")


class InventoryMovementTests(TestCase):
    def setUp(self):
        self.item = InventoryItem.objects.create(name="Сканер", quantity=5, min_quantity=2)

    def _apply(self, movement_type, quantity):
        movement = InventoryMovement.objects.create(
            item=self.item, movement_type=movement_type, quantity=quantity
        )
        movement.apply()
        self.item.refresh_from_db()
        return movement

    def test_increases_on_in(self):
        self._apply(MovementType.IN, 3)
        self.assertEqual(self.item.quantity, 8)

    def test_decreases_on_out(self):
        self._apply(MovementType.OUT, 2)
        self.assertEqual(self.item.quantity, 3)

    def test_never_negative_on_write_off(self):
        self._apply(MovementType.WRITE_OFF, 100)
        self.assertEqual(self.item.quantity, 0)

    def test_correction_sets_absolute(self):
        self._apply(MovementType.CORRECTION, 9)
        self.assertEqual(self.item.quantity, 9)

    def test_str(self):
        movement = InventoryMovement.objects.create(
            item=self.item, movement_type=MovementType.IN, quantity=1
        )
        self.assertIn("Приход", str(movement))


class InventoryFormTests(TestCase):
    def test_wear_percent_over_100_invalid(self):
        form = InventoryItemForm(data={"name": "X", "kind": ItemKind.TOOL, "quantity": 1, "wear_percent": 150})
        self.assertFalse(form.is_valid())
        self.assertIn("wear_percent", form.errors)

    def test_item_form_valid(self):
        form = InventoryItemForm(
            data={
                "name": "X",
                "kind": ItemKind.TOOL,
                "quantity": 1,
                "min_quantity": 0,
                "unit": "шт",
                "condition": Condition.GOOD,
                "wear_percent": 10,
            }
        )
        self.assertTrue(form.is_valid())

    def test_movement_form_valid(self):
        form = InventoryMovementForm(data={"movement_type": MovementType.IN, "quantity": 2})
        self.assertTrue(form.is_valid())


class InventoryViewTests(TestCase):
    def setUp(self):
        self.admin, self.specialist, self.viewer = make_users()
        self.workshop = Workshop.objects.create(name="Цех", code="Ц")
        self.location = StorageLocation.objects.create(name="Стеллаж", shelf_code="A-01", workshop=self.workshop)
        self.category = ItemCategory.objects.create(name="Сканеры")
        self.item = InventoryItem.objects.create(
            name="Сканер", kind=ItemKind.DEVICE, location=self.location, category=self.category,
            quantity=1, min_quantity=2, wear_percent=90, condition=Condition.WORN,
        )

    def test_list_renders_and_filters(self):
        self.client.force_login(self.specialist)
        self.assertEqual(self.client.get(reverse("inventory:item_list")).status_code, 200)
        response = self.client.get(reverse("inventory:item_list"), {"q": "Сканер", "low": "1"})
        self.assertContains(response, "Сканер")
        response = self.client.get(reverse("inventory:item_list"), {"condition": Condition.WORN})
        self.assertEqual(response.status_code, 200)

    def test_detail_renders(self):
        self.client.force_login(self.specialist)
        response = self.client.get(reverse("inventory:item_detail", args=[self.item.pk]))
        self.assertContains(response, "Сканер")

    def test_create_item(self):
        self.client.force_login(self.specialist)
        response = self.client.post(
            reverse("inventory:item_create"),
            {"name": "Новый инструмент", "kind": ItemKind.TOOL, "quantity": 3, "min_quantity": 1, "unit": "шт", "condition": Condition.GOOD, "wear_percent": 0},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(InventoryItem.objects.filter(name="Новый инструмент").exists())

    def test_viewer_cannot_create(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("inventory:item_create"))
        self.assertEqual(response.status_code, 403)

    def test_update_item(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("inventory:item_update", args=[self.item.pk]),
            {"name": "Сканер обновлён", "kind": ItemKind.DEVICE, "quantity": 1, "min_quantity": 2, "unit": "шт", "condition": Condition.WORN, "wear_percent": 90},
        )
        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.name, "Сканер обновлён")

    def test_delete_item_admin_only(self):
        self.client.force_login(self.specialist)
        self.assertEqual(self.client.post(reverse("inventory:item_delete", args=[self.item.pk])).status_code, 403)
        self.client.force_login(self.admin)
        response = self.client.post(reverse("inventory:item_delete", args=[self.item.pk]))
        self.assertEqual(response.status_code, 302)

    def test_movement_create(self):
        self.client.force_login(self.specialist)
        response = self.client.post(
            reverse("inventory:movement_create", args=[self.item.pk]),
            {"movement_type": MovementType.IN, "quantity": 5, "comment": "поставка"},
        )
        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 6)
        movement = self.item.movements.first()
        self.assertEqual(movement.created_by, self.specialist)

    def test_location_views(self):
        self.client.force_login(self.specialist)
        self.assertEqual(self.client.get(reverse("inventory:location_list")).status_code, 200)
        response = self.client.post(
            reverse("inventory:location_create"), {"name": "Новая полка", "shelf_code": "B-02"}
        )
        self.assertEqual(response.status_code, 302)

    def test_category_views(self):
        self.client.force_login(self.specialist)
        self.assertEqual(self.client.get(reverse("inventory:category_list")).status_code, 200)
        response = self.client.post(
            reverse("inventory:category_create"), {"name": "Новая категория", "kind": ItemKind.SPARE}
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ItemCategory.objects.filter(name="Новая категория").exists())


class InventoryFilterAndEdgeTests(TestCase):
    def setUp(self):
        self.admin, self.specialist, self.viewer = make_users()
        self.workshop = Workshop.objects.create(name="Цех", code="Ц")
        self.location = StorageLocation.objects.create(
            name="Ст", shelf_code="A-01", workshop=self.workshop
        )
        self.category = ItemCategory.objects.create(name="Кат")
        self.item = InventoryItem.objects.create(
            name="Сканер",
            kind=ItemKind.DEVICE,
            location=self.location,
            category=self.category,
            quantity=1,
            min_quantity=2,
        )

    def test_list_applies_kind_location_category_filters(self):
        self.client.force_login(self.specialist)
        response = self.client.get(
            reverse("inventory:item_list"),
            {
                "kind": ItemKind.DEVICE,
                "location": self.location.pk,
                "category": self.category.pk,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Сканер")

    def test_movement_create_invalid_form(self):
        self.client.force_login(self.specialist)
        response = self.client.post(
            reverse("inventory:movement_create", args=[self.item.pk]),
            {"movement_type": "", "quantity": ""},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.item.movements.count(), 0)

    def test_movement_form_rejects_negative_on_create(self):
        form = InventoryMovementForm()
        form.cleaned_data = {"quantity": -3}
        with self.assertRaises(ValidationError):
            form.clean_quantity()

    def test_breadcrumb_is_clickable(self):
        self.client.force_login(self.specialist)
        response = self.client.get(reverse("inventory:item_list"))
        self.assertContains(response, f'href="{reverse("inventory:item_list")}"')
        self.assertContains(response, ">Учет</a>")


class SeedSkladCommandTests(TestCase):
    def test_seed_sklad_creates_items_and_location(self):
        from django.core.management import call_command

        from inventory.models import InventoryItem, StorageLocation
        from inventory.sklad_data import LOCATION_SHELF, SKLAD

        call_command("seed_sklad", verbosity=0)
        self.assertTrue(StorageLocation.objects.filter(shelf_code=LOCATION_SHELF).exists())
        self.assertEqual(
            InventoryItem.objects.filter(location__shelf_code=LOCATION_SHELF).count(),
            len(SKLAD),
        )

    def test_seed_sklad_is_idempotent(self):
        from django.core.management import call_command

        from inventory.models import InventoryItem
        from inventory.sklad_data import LOCATION_SHELF, SKLAD

        call_command("seed_sklad", verbosity=0)
        call_command("seed_sklad", verbosity=0)
        self.assertEqual(
            InventoryItem.objects.filter(location__shelf_code=LOCATION_SHELF).count(),
            len(SKLAD),
        )
