from __future__ import annotations

from django.db import models
from django.utils import timezone

from core.models import AuditedModel


class JournalEntry(AuditedModel):
    """Запись сменного журнала специалистов по цифровой маркировке.

    Колонки соответствуют утверждённой форме Excel:
    Дата, Дежурный специалист, Время, Оборудование/Линия, Время простоя,
    Действие/Задача, Решение (комментарий), Печ. головка, Пробег (км).
    """

    class EntryType(models.TextChoices):
        SHIFT_START = "shift_start", "Смена принята"
        SHIFT_END = "shift_end", "Смена сдана"
        WORK = "work", "Работа"

    shift = models.ForeignKey(
        "shifts.Shift",
        verbose_name="Смена",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="journal_entries",
    )
    entry_type = models.CharField(
        "Тип записи", max_length=20, choices=EntryType.choices, default=EntryType.WORK
    )
    occurred_at = models.DateTimeField("Дата и время", default=timezone.now)
    specialist = models.ForeignKey(
        "accounts.User",
        verbose_name="Дежурный специалист",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="journal_records",
    )
    equipment_line = models.CharField("Оборудование / Линия", max_length=200, blank=True)
    downtime = models.CharField("Время простоя", max_length=50, blank=True)
    action_task = models.TextField("Действие / Задача", default="")
    solution = models.TextField("Решение (комментарий)", blank=True)
    print_head = models.CharField("Печ. головка", max_length=100, blank=True)
    mileage = models.DecimalField(
        "Пробег (км)", max_digits=10, decimal_places=2, null=True, blank=True
    )
    created_by = models.ForeignKey(
        "accounts.User",
        verbose_name="Зарегистрировал",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_entries",
    )

    class Meta:
        verbose_name = "Запись журнала"
        verbose_name_plural = "Сменный журнал"
        ordering = ("occurred_at", "id")
        indexes = [
            models.Index(fields=("occurred_at",)),
            models.Index(fields=("entry_type",)),
        ]

    def __str__(self) -> str:
        return f"{self.occurred_at:%d.%m.%Y %H:%M} — {self.action_task[:50]}"

    @property
    def entry_date(self):
        return timezone.localtime(self.occurred_at).date()

    @property
    def entry_time(self):
        return timezone.localtime(self.occurred_at).time()

    @property
    def is_marker(self) -> bool:
        return self.entry_type in (self.EntryType.SHIFT_START, self.EntryType.SHIFT_END)

    @property
    def specialist_name(self) -> str:
        if self.specialist:
            return self.specialist.full_name
        if self.shift and self.shift.opened_by:
            return self.shift.opened_by.full_name
        return "—"

    def save(self, *args, **kwargs):
        if self.specialist is None and self.shift and self.shift.opened_by_id:
            self.specialist = self.shift.opened_by
        super().save(*args, **kwargs)


class JournalExport(AuditedModel):
    """Excel-выгрузка сменного журнала. is_full=True — единый кумулятивный архив."""

    shift = models.ForeignKey(
        "shifts.Shift",
        verbose_name="Смена",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exports",
    )
    file = models.FileField("Файл", upload_to="journal_exports/%Y/%m/")
    entries_count = models.PositiveIntegerField("Количество записей", default=0)
    period_start = models.DateTimeField("Начало периода", null=True, blank=True)
    period_end = models.DateTimeField("Конец периода", null=True, blank=True)
    is_full = models.BooleanField("Единый архив", default=False)
    created_by = models.ForeignKey(
        "accounts.User",
        verbose_name="Создал",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="journal_exports",
    )

    class Meta:
        verbose_name = "Выгрузка журнала"
        verbose_name_plural = "Выгрузки журнала"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        name = self.file.name.split("/")[-1] if self.file else f"Выгрузка #{self.pk}"
        return name
