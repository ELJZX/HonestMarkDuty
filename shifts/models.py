from __future__ import annotations

from django.db import models
from django.utils import timezone

from core.models import AuditedModel
from inventory.models import Condition


class ShiftQuerySet(models.QuerySet):
    def open(self):
        return self.filter(status=Shift.Status.OPEN)

    def closed(self):
        return self.filter(status=Shift.Status.CLOSED)


class Shift(AuditedModel):
    """Рабочая смена: приём в начале дня и сдача в конце."""

    class Status(models.TextChoices):
        OPEN = "open", "Открыта"
        CLOSED = "closed", "Закрыта"

    class Kind(models.TextChoices):
        DAY = "day", "Дневная"
        NIGHT = "night", "Ночная"

    date = models.DateField("Дата смены", default=timezone.localdate)
    kind = models.CharField("Тип смены", max_length=10, choices=Kind.choices, default=Kind.DAY)
    external_id = models.CharField(
        "Внешний ID", max_length=120, null=True, blank=True, unique=True
    )
    workshop = models.ForeignKey(
        "core.Workshop",
        verbose_name="Цех",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shifts",
    )
    status = models.CharField("Статус", max_length=10, choices=Status.choices, default=Status.OPEN)

    opened_by = models.ForeignKey(
        "accounts.User",
        verbose_name="Принял смену",
        on_delete=models.SET_NULL,
        null=True,
        related_name="shifts_opened",
    )
    opened_at = models.DateTimeField("Время приёма", default=timezone.now)
    opening_notes = models.TextField("Примечания при приёме", blank=True)

    closed_by = models.ForeignKey(
        "accounts.User",
        verbose_name="Сдал смену",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shifts_closed",
    )
    closed_at = models.DateTimeField("Время сдачи", null=True, blank=True)
    closing_notes = models.TextField("Примечания при сдаче", blank=True)
    equipment_condition = models.TextField("Состояние оборудования", blank=True)
    inventory_notes = models.TextField("Состояние склада", blank=True)
    handover_to = models.ForeignKey(
        "accounts.User",
        verbose_name="Передал смену",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shifts_received",
    )

    objects = ShiftQuerySet.as_manager()

    class Meta:
        verbose_name = "Смена"
        verbose_name_plural = "Смены"
        ordering = ("-date", "-opened_at")

    def __str__(self) -> str:
        return f"Смена {self.date:%d.%m.%Y}"

    @property
    def is_open(self) -> bool:
        return self.status == self.Status.OPEN

    @property
    def duration(self):
        end = self.closed_at or timezone.now()
        return end - self.opened_at

    @property
    def duration_display(self) -> str:
        """Длительность в формате чч:мм:сс (без микросекунд)."""
        total = int(self.duration.total_seconds())
        hours, remainder = divmod(total, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


class ShiftCheck(AuditedModel):
    """Проверка конкретной позиции склада при приёме/сдаче смены."""

    shift = models.ForeignKey(Shift, verbose_name="Смена", on_delete=models.CASCADE, related_name="checks")
    item = models.ForeignKey(
        "inventory.InventoryItem",
        verbose_name="Позиция склада",
        on_delete=models.CASCADE,
        related_name="shift_checks",
    )
    condition = models.CharField(
        "Состояние при проверке", max_length=20, choices=Condition.choices, blank=True
    )
    wear_percent = models.PositiveSmallIntegerField("Износ, %", default=0)
    comment = models.CharField("Комментарий", max_length=300, blank=True)

    class Meta:
        verbose_name = "Проверка позиции"
        verbose_name_plural = "Проверки позиций"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.item} — {self.wear_percent}%"
