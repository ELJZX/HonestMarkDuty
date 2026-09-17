from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        abstract = True


class AuditLog(models.Model):
    """Журнал изменений (кто, что, когда)."""

    class Action(models.TextChoices):
        CREATE = "create", "Создание"
        UPDATE = "update", "Изменение"
        DELETE = "delete", "Удаление"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Пользователь",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField("Действие", max_length=10, choices=Action.choices)
    app_label = models.CharField("Приложение", max_length=50, blank=True)
    model_name = models.CharField("Модель", max_length=100)
    object_id = models.CharField("ID объекта", max_length=50, blank=True)
    object_repr = models.CharField("Объект", max_length=255, blank=True)
    changes = models.JSONField("Изменения", default=dict, blank=True)
    created_at = models.DateTimeField("Время", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Запись аудита"
        verbose_name_plural = "Аудит изменений"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("model_name", "object_id")),
        ]

    def __str__(self) -> str:
        return f"{self.get_action_display()}: {self.model_name} #{self.object_id}"


class AuditedModel(TimeStampedModel):
    """Базовая модель с автоматической записью изменений в AuditLog."""

    AUDIT_EXCLUDE: tuple[str, ...] = ()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        from core.audit import record_audit, snapshot

        is_new = self._state.adding
        old = None
        if not is_new and self.pk is not None:
            try:
                old = type(self)._base_manager.get(pk=self.pk)
            except ObjectDoesNotExist:
                old = None

        super().save(*args, **kwargs)

        if is_new:
            record_audit(self, AuditLog.Action.CREATE, snapshot(self))
        else:
            new = snapshot(self)
            base = snapshot(old) if old else {}
            changes = {
                key: {"from": base.get(key), "to": value}
                for key, value in new.items()
                if base.get(key) != value
            }
            if changes:
                record_audit(self, AuditLog.Action.UPDATE, changes)

    def delete(self, *args, **kwargs):
        from core.audit import record_audit, snapshot

        record_audit(self, AuditLog.Action.DELETE, snapshot(self))
        return super().delete(*args, **kwargs)


class Workshop(AuditedModel):
    """Производственный цех — используется для автозаполнения документов."""

    name = models.CharField("Название цеха", max_length=200, unique=True)
    code = models.CharField("Код", max_length=30, unique=True)
    site = models.ForeignKey(
        "core.ProductionSite",
        verbose_name="Производственная площадка",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="workshops",
    )
    chief = models.CharField("Начальник цеха", max_length=200, blank=True)
    chief_position = models.CharField(
        "Должность руководителя", max_length=200, blank=True, default="Начальник цеха"
    )
    phone = models.CharField("Телефон", max_length=50, blank=True)
    description = models.TextField("Описание", blank=True)
    sort_order = models.PositiveIntegerField("Порядок", default=0)
    is_active = models.BooleanField("Активен", default=True)

    class Meta:
        verbose_name = "Цех"
        verbose_name_plural = "Цеха"
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class ProductionLine(AuditedModel):
    """Производственная линия внутри цеха — объединяет оборудование."""

    workshop = models.ForeignKey(
        Workshop,
        verbose_name="Цех",
        on_delete=models.CASCADE,
        related_name="lines",
    )
    name = models.CharField("Название линии", max_length=200)
    code = models.CharField("Код", max_length=30, blank=True)
    description = models.TextField("Описание", blank=True)
    sort_order = models.PositiveIntegerField("Порядок", default=0)
    is_active = models.BooleanField("Активна", default=True)

    class Meta:
        verbose_name = "Производственная линия"
        verbose_name_plural = "Производственные линии"
        ordering = ("workshop__name", "sort_order", "name")
        constraints = [
            models.UniqueConstraint(fields=("workshop", "name"), name="unique_line_in_workshop"),
        ]

    def __str__(self) -> str:
        return f"{self.workshop.name} · {self.name}"

    @property
    def equipment_count(self) -> int:
        return self.equipment.filter(is_camera=False).count()


class ProductionSite(AuditedModel):
    """Производственная площадка (здание/адрес)."""

    name = models.CharField("Название площадки", max_length=200, unique=True)
    address = models.CharField("Адрес", max_length=300, blank=True)
    responsible = models.CharField("Ответственный", max_length=200, blank=True)
    description = models.TextField("Описание", blank=True)
    is_active = models.BooleanField("Активна", default=True)

    class Meta:
        verbose_name = "Производственная площадка"
        verbose_name_plural = "Производственные площадки"
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name
