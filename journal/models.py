from __future__ import annotations

from django.db import models
from django.utils import timezone

from core.models import AuditedModel


class JournalEntry(AuditedModel):
    """Обращение пользователя и его решение (сменный журнал)."""

    class Status(models.TextChoices):
        NEW = "new", "Новое"
        IN_PROGRESS = "in_progress", "В работе"
        DONE = "done", "Решено"
        CANCELLED = "cancelled", "Отменено"

    class Priority(models.TextChoices):
        LOW = "low", "Низкий"
        NORMAL = "normal", "Обычный"
        HIGH = "high", "Высокий"
        CRITICAL = "critical", "Критический"

    shift = models.ForeignKey(
        "shifts.Shift",
        verbose_name="Смена",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="journal_entries",
    )
    received_at = models.DateTimeField("Время обращения", default=timezone.now)
    source_location = models.CharField("Место поступления заявки", max_length=250)
    workshop = models.ForeignKey(
        "core.Workshop",
        verbose_name="Цех",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="journal_entries",
    )
    reported_by = models.CharField("Кто обратился", max_length=200, blank=True)
    problem = models.TextField("Описание проблемы")
    solution = models.TextField("Решение", blank=True)
    status = models.CharField("Статус", max_length=20, choices=Status.choices, default=Status.NEW)
    priority = models.CharField(
        "Приоритет", max_length=20, choices=Priority.choices, default=Priority.NORMAL
    )
    assigned_to = models.ForeignKey(
        "accounts.User",
        verbose_name="Исполнитель",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_entries",
    )
    resolved_at = models.DateTimeField("Время решения", null=True, blank=True)
    created_by = models.ForeignKey(
        "accounts.User",
        verbose_name="Зарегистрировал",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_entries",
    )
    equipment = models.ForeignKey(
        "equipment.Equipment",
        verbose_name="Оборудование",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="journal_entries",
    )

    class Meta:
        verbose_name = "Запись журнала"
        verbose_name_plural = "Сменный журнал"
        ordering = ("-received_at",)
        indexes = [
            models.Index(fields=("status", "priority")),
            models.Index(fields=("received_at",)),
        ]

    def __str__(self) -> str:
        return f"{self.received_at:%d.%m.%Y %H:%M} — {self.source_location}"

    @property
    def response_time(self):
        end = self.resolved_at or timezone.now()
        return end - self.received_at

    @property
    def status_badge(self) -> str:
        return {
            self.Status.NEW: "badge-info",
            self.Status.IN_PROGRESS: "badge-warn",
            self.Status.DONE: "badge-ok",
            self.Status.CANCELLED: "badge-muted",
        }.get(self.status, "badge-muted")

    @property
    def priority_badge(self) -> str:
        return {
            self.Priority.LOW: "badge-muted",
            self.Priority.NORMAL: "badge-info",
            self.Priority.HIGH: "badge-warn",
            self.Priority.CRITICAL: "badge-danger",
        }.get(self.priority, "badge-muted")

    def save(self, *args, **kwargs):
        if self.status == self.Status.DONE and self.resolved_at is None:
            self.resolved_at = timezone.now()
        if self.status != self.Status.DONE:
            self.resolved_at = None
        super().save(*args, **kwargs)


class JournalExport(AuditedModel):
    """Архивная Excel-выгрузка сменного журнала."""

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
        return self.file.name.split("/")[-1] if self.file else f"Выгрузка #{self.pk}"
