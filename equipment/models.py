from __future__ import annotations

from django.db import models
from django.utils import timezone

from core.models import AuditedModel


class EquipmentStatus(models.TextChoices):
    OPERATIONAL = "operational", "В работе"
    MAINTENANCE = "maintenance", "Обслуживание"
    REPAIR = "repair", "Ремонт"
    DECOMMISSIONED = "decommissioned", "Списано"


class Criticality(models.TextChoices):
    LOW = "low", "Низкая"
    MEDIUM = "medium", "Средняя"
    HIGH = "high", "Высокая"
    CRITICAL = "critical", "Критическая"


class EquipmentCategory(AuditedModel):
    name = models.CharField("Категория оборудования", max_length=150, unique=True)
    description = models.CharField("Описание", max_length=300, blank=True)

    class Meta:
        verbose_name = "Категория оборудования"
        verbose_name_plural = "Категории оборудования"
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class Equipment(AuditedModel):
    """Единица оборудования на производственной площадке."""

    name = models.CharField("Наименование", max_length=250)
    inventory_number = models.CharField("Инвентарный номер", max_length=60, unique=True)
    category = models.ForeignKey(
        EquipmentCategory,
        verbose_name="Категория",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="equipment",
    )
    site = models.ForeignKey(
        "core.ProductionSite",
        verbose_name="Производственная площадка",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="equipment",
    )
    workshop = models.ForeignKey(
        "core.Workshop",
        verbose_name="Цех",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="equipment",
    )
    line = models.ForeignKey(
        "core.ProductionLine",
        verbose_name="Линия",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="equipment",
    )
    manufacturer = models.CharField("Производитель", max_length=150, blank=True)
    model_name = models.CharField("Модель", max_length=150, blank=True)
    ip_address = models.CharField("IP-адрес", max_length=60, blank=True)
    print_head = models.CharField("Печатающая головка", max_length=50, blank=True)
    slot = models.CharField("Значение (первый/второй)", max_length=50, blank=True)
    serial_number = models.CharField("Серийный номер", max_length=150, blank=True)
    commissioned_at = models.DateField("Дата ввода в эксплуатацию", null=True, blank=True)
    status = models.CharField(
        "Состояние", max_length=20, choices=EquipmentStatus.choices, default=EquipmentStatus.OPERATIONAL
    )
    criticality = models.CharField(
        "Критичность", max_length=20, choices=Criticality.choices, default=Criticality.MEDIUM
    )
    last_maintenance_at = models.DateField("Последнее ТО", null=True, blank=True)
    next_maintenance_at = models.DateField("Следующее ТО", null=True, blank=True)
    responsible = models.ForeignKey(
        "accounts.User",
        verbose_name="Ответственный",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="responsible_equipment",
    )
    notes = models.TextField("Примечания", blank=True)
    is_active = models.BooleanField("Учтено", default=True)

    class Meta:
        verbose_name = "Оборудование"
        verbose_name_plural = "Оборудование"
        ordering = ("site__name", "name")
        indexes = [models.Index(fields=("status",))]

    def __str__(self) -> str:
        return f"{self.name} ({self.inventory_number})"

    @property
    def status_badge(self) -> str:
        return {
            EquipmentStatus.OPERATIONAL: "badge-ok",
            EquipmentStatus.MAINTENANCE: "badge-warn",
            EquipmentStatus.REPAIR: "badge-danger",
            EquipmentStatus.DECOMMISSIONED: "badge-muted",
        }.get(self.status, "badge-muted")

    @property
    def is_maintenance_overdue(self) -> bool:
        return bool(self.next_maintenance_at and self.next_maintenance_at < timezone.localdate())

    def save(self, *args, **kwargs):
        previous_status = None
        if self.pk and not self._state.adding:
            previous_status = (
                type(self).objects.filter(pk=self.pk).values_list("status", flat=True).first()
            )
        super().save(*args, **kwargs)
        if previous_status and previous_status != self.status:
            from core.audit import get_current_user

            EquipmentStatusLog.objects.create(
                equipment=self,
                status=self.status,
                comment="Автоматическая фиксация изменения состояния",
                changed_by=get_current_user(),
            )


class EquipmentStatusLog(AuditedModel):
    """История изменения состояния оборудования."""

    equipment = models.ForeignKey(
        Equipment, verbose_name="Оборудование", on_delete=models.CASCADE, related_name="status_logs"
    )
    status = models.CharField("Состояние", max_length=20, choices=EquipmentStatus.choices)
    comment = models.TextField("Комментарий", blank=True)
    changed_by = models.ForeignKey(
        "accounts.User",
        verbose_name="Изменил",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="equipment_status_logs",
    )

    class Meta:
        verbose_name = "Запись состояния оборудования"
        verbose_name_plural = "История состояний оборудования"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.equipment} → {self.get_status_display()}"


class MaintenanceKind(models.TextChoices):
    TO = "to", "Техническое обслуживание"
    REPAIR = "repair", "Ремонт"
    INSPECTION = "inspection", "Осмотр"
    CALIBRATION = "calibration", "Поверка/калибровка"
    OTHER = "other", "Прочее"


class MaintenanceRecord(AuditedModel):
    """Работы по оборудованию."""

    equipment = models.ForeignKey(
        Equipment, verbose_name="Оборудование", on_delete=models.CASCADE, related_name="maintenance_records"
    )
    kind = models.CharField("Вид работ", max_length=20, choices=MaintenanceKind.choices)
    performed_at = models.DateField("Дата работ", default=timezone.localdate)
    description = models.TextField("Описание работ")
    performer = models.CharField("Исполнитель", max_length=200, blank=True)
    cost = models.DecimalField("Стоимость, руб.", max_digits=12, decimal_places=2, null=True, blank=True)
    created_by = models.ForeignKey(
        "accounts.User",
        verbose_name="Зарегистрировал",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_records",
    )

    class Meta:
        verbose_name = "Запись о работах"
        verbose_name_plural = "Работы по оборудованию"
        ordering = ("-performed_at",)

    def __str__(self) -> str:
        return f"{self.get_kind_display()} · {self.equipment}"
