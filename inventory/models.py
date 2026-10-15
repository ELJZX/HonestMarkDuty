from __future__ import annotations

from django.db import models

from core.models import AuditedModel


class Storage(AuditedModel):
    """Склад (помещение/зона хранения)."""

    name = models.CharField("Склад", max_length=150, unique=True)
    sort_order = models.PositiveIntegerField("Порядок", default=0)
    image = models.ImageField("Иконка", upload_to="storages/", blank=True)

    class Meta:
        verbose_name = "Склад"
        verbose_name_plural = "Склады"
        ordering = ("sort_order", "name")

    def __str__(self) -> str:
        return self.name


class ItemType(AuditedModel):
    """Тип позиции склада (редактируемый список)."""

    name = models.CharField("Тип", max_length=100, unique=True)
    sort_order = models.PositiveIntegerField("Порядок", default=0)
    image = models.ImageField("Иконка", upload_to="item_types/", blank=True)

    class Meta:
        verbose_name = "Тип позиции"
        verbose_name_plural = "Типы позиций"
        ordering = ("sort_order", "name")

    def __str__(self) -> str:
        return self.name


class Condition(models.TextChoices):
    NEW = "new", "Новое"
    USED = "used", "Б/у"


class StorageLocation(AuditedModel):
    """Место хранения — полка/шкаф/стеллаж в кабинете."""

    name = models.CharField("Название места", max_length=150)
    shelf_code = models.CharField("Код полки/ячейки", max_length=50, blank=True)
    workshop = models.ForeignKey(
        "core.Workshop",
        verbose_name="Цех",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="storage_locations",
    )
    description = models.CharField("Описание", max_length=300, blank=True)

    class Meta:
        verbose_name = "Место хранения"
        verbose_name_plural = "Места хранения"
        ordering = ("workshop__name", "shelf_code", "name")

    def __str__(self) -> str:
        label = self.shelf_code or self.name
        return f"{label}" if not self.workshop else f"{self.workshop.code} · {label}"


class ItemCategory(AuditedModel):
    name = models.CharField("Категория", max_length=150, unique=True)
    kind = models.ForeignKey(
        ItemType,
        verbose_name="Тип",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="categories",
    )

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class InventoryItem(AuditedModel):
    """Инструмент или запасная часть на полке."""

    name = models.CharField("Наименование", max_length=250)
    inventory_number = models.CharField("Инвентарный номер", max_length=60, blank=True)
    kind = models.ForeignKey(
        ItemType,
        verbose_name="Тип",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="items",
    )
    category = models.ForeignKey(
        ItemCategory,
        verbose_name="Категория",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="items",
    )
    location = models.ForeignKey(
        StorageLocation,
        verbose_name="Место хранения",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="items",
    )
    storage = models.ForeignKey(
        Storage,
        verbose_name="Склад",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="items",
    )
    quantity = models.PositiveIntegerField("Количество", default=0)
    min_quantity = models.PositiveIntegerField("Минимальный остаток", default=0)
    unit = models.CharField("Ед. изм.", max_length=20, default="шт")
    condition = models.CharField("Состояние", max_length=20, choices=Condition.choices, default=Condition.NEW)
    serial_number = models.CharField("Серийный номер", max_length=100, blank=True)
    manufactured_at = models.DateField("Дата производства", null=True, blank=True)
    last_verified_at = models.DateField("Дата поверки/проверки", null=True, blank=True)
    notes = models.TextField("Примечания", blank=True)
    is_active = models.BooleanField("Активен", default=True)

    class Meta:
        verbose_name = "Позиция склада"
        verbose_name_plural = "Склад инструментов и запчастей"
        ordering = ("name",)
        indexes = [
            models.Index(fields=("location",)),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def is_low_stock(self) -> bool:
        return self.quantity <= self.min_quantity

    @property
    def condition_badge(self) -> str:
        return {
            Condition.NEW: "badge-ok",
            Condition.USED: "badge-warn",
        }.get(self.condition, "badge-muted")


class MovementType(models.TextChoices):
    IN = "in", "Приход"
    OUT = "out", "Расход"
    WRITE_OFF = "write_off", "Списание"
    CORRECTION = "correction", "Инвентаризация"


class InventoryMovement(AuditedModel):
    """Движение по складу — история для прозрачности изменений."""

    item = models.ForeignKey(
        InventoryItem, verbose_name="Позиция", on_delete=models.CASCADE, related_name="movements"
    )
    movement_type = models.CharField("Операция", max_length=20, choices=MovementType.choices)
    quantity = models.PositiveIntegerField("Количество")
    comment = models.CharField("Комментарий", max_length=300, blank=True)
    created_by = models.ForeignKey(
        "accounts.User",
        verbose_name="Сотрудник",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_movements",
    )
    shift = models.ForeignKey(
        "shifts.Shift",
        verbose_name="Смена",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_movements",
    )

    class Meta:
        verbose_name = "Движение по складу"
        verbose_name_plural = "Движения по складу"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.get_movement_type_display()} {self.quantity} · {self.item}"

    def apply(self) -> None:
        """Применяет движение к остатку позиции."""
        item = self.item
        if self.movement_type == MovementType.IN:
            item.quantity += self.quantity
        elif self.movement_type in (MovementType.OUT, MovementType.WRITE_OFF):
            item.quantity = max(0, item.quantity - self.quantity)
        elif self.movement_type == MovementType.CORRECTION:
            item.quantity = self.quantity
            self.quantity = item.quantity
        item.save()
