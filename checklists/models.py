from __future__ import annotations

from django.db import models
from django.utils import timezone

from core.models import AuditedModel


class ChecklistGroup(AuditedModel):
    """Группа оборудования (цех/участок) в шапке чеклиста."""

    name = models.CharField("Название группы", max_length=150, unique=True)
    sort_order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Группа чеклиста"
        verbose_name_plural = "Группы чеклиста"
        ordering = ("sort_order", "name")

    def __str__(self) -> str:
        return self.name


class ChecklistMachine(AuditedModel):
    """Единица оборудования (автомат) — колонка чеклиста."""

    group = models.ForeignKey(
        ChecklistGroup, verbose_name="Группа", on_delete=models.CASCADE, related_name="machines"
    )
    name = models.CharField("Название оборудования", max_length=150)
    sort_order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Оборудование чеклиста"
        verbose_name_plural = "Оборудование чеклиста"
        ordering = ("group__sort_order", "sort_order", "name")
        constraints = [
            models.UniqueConstraint(fields=("group", "name"), name="unique_machine_in_group"),
        ]

    def __str__(self) -> str:
        return f"{self.group.name} · {self.name}"


class ChecklistCheck(AuditedModel):
    """Строка проверки чеклиста."""

    name = models.CharField("Проверка", max_length=300)
    sort_order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Проверка чеклиста"
        verbose_name_plural = "Проверки чеклиста"
        ordering = ("sort_order", "id")

    def __str__(self) -> str:
        return self.name


class ChecklistStatus(models.TextChoices):
    DRAFT = "draft", "В работе"
    FINAL = "final", "Сформирован"


class EquipmentChecklist(AuditedModel):
    """Заполненный чеклист технического осмотра оборудования «Честный знак»."""

    shift = models.ForeignKey(
        "shifts.Shift",
        verbose_name="Смена",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="checklists",
    )
    date = models.DateField("Дата", default=timezone.localdate)
    workshop = models.ForeignKey(
        "core.Workshop",
        verbose_name="Цех",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="checklists",
    )
    performed_by = models.ForeignKey(
        "accounts.User",
        verbose_name="Выполнил",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="checklists_performed",
    )
    note = models.TextField("Примечание", blank=True)
    status = models.CharField(
        "Статус", max_length=10, choices=ChecklistStatus.choices, default=ChecklistStatus.DRAFT
    )
    file = models.FileField("Файл XLSX", upload_to="checklists/%Y/%m/", blank=True)
    created_by = models.ForeignKey(
        "accounts.User",
        verbose_name="Создал",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="checklists_created",
    )

    class Meta:
        verbose_name = "Чеклист оборудования"
        verbose_name_plural = "Чеклисты оборудования"
        ordering = ("-date", "-created_at")

    def __str__(self) -> str:
        return f"Чеклист от {self.date:%d.%m.%Y}"

    @property
    def status_badge(self) -> str:
        return "badge-ok" if self.status == ChecklistStatus.FINAL else "badge-muted"

    @property
    def critical_count(self) -> int:
        return self.results.filter(score=ChecklistScore.BAD).count()


class ChecklistScore(models.IntegerChoices):
    BAD = 1, "1 — Неудовлетворительно"
    WARN = 2, "2 — Удовлетворительно"
    OK = 3, "3 — Готово к работе"


class ChecklistMileage(AuditedModel):
    """Пробег печатающей головки по конкретному оборудованию."""

    checklist = models.ForeignKey(
        EquipmentChecklist, verbose_name="Чеклист", on_delete=models.CASCADE, related_name="mileages"
    )
    machine = models.ForeignKey(
        ChecklistMachine, verbose_name="Оборудование", on_delete=models.CASCADE, related_name="mileages"
    )
    value = models.DecimalField("Пробег (км)", max_digits=10, decimal_places=1, null=True, blank=True)

    class Meta:
        verbose_name = "Пробег головки"
        verbose_name_plural = "Пробеги головок"
        constraints = [
            models.UniqueConstraint(fields=("checklist", "machine"), name="unique_mileage_per_machine"),
        ]


class ChecklistResult(AuditedModel):
    """Оценка проверки по конкретному оборудованию (1/2/3)."""

    checklist = models.ForeignKey(
        EquipmentChecklist, verbose_name="Чеклист", on_delete=models.CASCADE, related_name="results"
    )
    machine = models.ForeignKey(
        ChecklistMachine, verbose_name="Оборудование", on_delete=models.CASCADE, related_name="results"
    )
    check_item = models.ForeignKey(
        ChecklistCheck, verbose_name="Проверка", on_delete=models.CASCADE, related_name="results"
    )
    score = models.PositiveSmallIntegerField("Оценка", choices=ChecklistScore.choices)

    class Meta:
        verbose_name = "Результат проверки"
        verbose_name_plural = "Результаты проверок"
        constraints = [
            models.UniqueConstraint(
                fields=("checklist", "machine", "check_item"), name="unique_result_cell"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.machine} / {self.check_item}: {self.score}"


class MarkemPrinter(AuditedModel):
    """Принтер Markem Image (серийный номер) — колонка чеклиста Markem."""

    name = models.CharField("Серийный номер", max_length=100, unique=True)
    sort_order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Принтер Markem"
        verbose_name_plural = "Принтеры Markem"
        ordering = ("sort_order", "id")

    def __str__(self) -> str:
        return self.name


class MarkemParameter(AuditedModel):
    """Проверяемый параметр (строка) чеклиста Markem."""

    name = models.CharField("Параметр", max_length=300, unique=True)
    sort_order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Параметр чеклиста Markem"
        verbose_name_plural = "Параметры чеклиста Markem"
        ordering = ("sort_order", "id")

    def __str__(self) -> str:
        return self.name


class MarkemChecklist(AuditedModel):
    """Заполненный чек лист технического осмотра и обслуживания принтеров Markem Image 9450."""

    date = models.DateField("Дата", default=timezone.localdate)
    shift = models.ForeignKey(
        "shifts.Shift",
        verbose_name="Смена",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="markem_checklists",
    )
    performed_by = models.ForeignKey(
        "accounts.User",
        verbose_name="Выполнил",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="markem_performed",
    )
    checked_by = models.ForeignKey(
        "accounts.User",
        verbose_name="Проверил",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="markem_checked",
    )
    note = models.TextField("Примечание", blank=True)
    status = models.CharField(
        "Статус", max_length=10, choices=ChecklistStatus.choices, default=ChecklistStatus.DRAFT
    )
    file = models.FileField("Файл XLSX", upload_to="markem/%Y/%m/", blank=True)
    created_by = models.ForeignKey(
        "accounts.User",
        verbose_name="Создал",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="markem_created",
    )

    class Meta:
        verbose_name = "Чеклист Markem Image 9450"
        verbose_name_plural = "Чеклисты Markem Image 9450"
        ordering = ("-date", "-created_at")

    def __str__(self) -> str:
        return f"Чеклист Markem от {self.date:%d.%m.%Y}"

    @property
    def status_badge(self) -> str:
        return "badge-ok" if self.status == ChecklistStatus.FINAL else "badge-muted"


class MarkemValue(AuditedModel):
    """Значение параметра по конкретному принтеру в чеклисте Markem."""

    checklist = models.ForeignKey(
        MarkemChecklist,
        verbose_name="Чеклист",
        on_delete=models.CASCADE,
        related_name="values",
    )
    printer = models.ForeignKey(
        MarkemPrinter,
        verbose_name="Принтер",
        on_delete=models.CASCADE,
        related_name="values",
    )
    parameter = models.ForeignKey(
        MarkemParameter,
        verbose_name="Параметр",
        on_delete=models.CASCADE,
        related_name="values",
    )
    value = models.CharField("Значение", max_length=300, blank=True)

    class Meta:
        verbose_name = "Значение параметра Markem"
        verbose_name_plural = "Значения параметров Markem"
        constraints = [
            models.UniqueConstraint(
                fields=("checklist", "printer", "parameter"),
                name="unique_markem_cell",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.printer} / {self.parameter}: {self.value}"
