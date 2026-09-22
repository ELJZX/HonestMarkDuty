from __future__ import annotations

import re

from django.db import models
from django.utils import timezone

from core.models import AuditedModel

PLACEHOLDER_RE = re.compile(r"{{\s*([\w.]+)\s*}}")


class DocumentType(models.TextChoices):
    TECHNICAL_REPORT = "technical_report", "Техническое заключение"
    SERVICE_NOTE = "service_note", "Служебная записка"
    EXPLANATION = "explanation", "Объяснительная записка"
    ACT = "act", "Акт"
    OTHER = "other", "Прочее"


class DocumentTemplate(AuditedModel):
    """Шаблон документа с плейсхолдерами вида {{ workshop_name }}."""

    name = models.CharField("Название шаблона", max_length=200, unique=True)
    doc_type = models.CharField(
        "Тип документа", max_length=30, choices=DocumentType.choices, default=DocumentType.TECHNICAL_REPORT
    )
    title_template = models.CharField("Заголовок (шаблон)", max_length=300)
    body = models.TextField("Тело документа (шаблон)")
    workshops = models.ManyToManyField(
        "core.Workshop",
        verbose_name="Доступен для цехов",
        blank=True,
        related_name="document_templates",
        help_text="Если не выбрано ни одного цеха — шаблон доступен для всех.",
    )
    is_active = models.BooleanField("Активен", default=True)

    class Meta:
        verbose_name = "Шаблон документа"
        verbose_name_plural = "Шаблоны документов"
        ordering = ("doc_type", "name")

    def __str__(self) -> str:
        return self.name

    @property
    def placeholders(self) -> list[str]:
        found = PLACEHOLDER_RE.findall(f"{self.title_template}\n{self.body}")
        return sorted(set(found))

    def available_for(self, workshop) -> bool:
        if not self.workshops.exists():
            return True
        return bool(workshop and self.workshops.filter(pk=workshop.pk).exists())


class DocumentStatus(models.TextChoices):
    DRAFT = "draft", "Черновик"
    SAVED = "saved", "Сохранён"
    ARCHIVED = "archived", "В архиве"


class DocumentKind(models.TextChoices):
    """Вид документа в архиве (определяется по имени загружаемого файла)."""

    TECHNICAL_REPORT = "tz", "Техническое заключение"
    SERVICE_NOTE = "sl", "Служебная записка"


class Document(AuditedModel):
    """Сформированный или загруженный в архив документ."""

    template = models.ForeignKey(
        DocumentTemplate,
        verbose_name="Шаблон",
        on_delete=models.PROTECT,
        related_name="documents",
        null=True,
        blank=True,
    )
    kind = models.CharField(
        "Вид документа", max_length=2, choices=DocumentKind.choices, blank=True, default=""
    )
    workshop = models.ForeignKey(
        "core.Workshop",
        verbose_name="Цех",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents",
    )
    title = models.CharField("Заголовок", max_length=300, blank=True)
    number = models.CharField("Номер документа", max_length=60, blank=True)
    doc_date = models.DateField("Дата документа", default=timezone.localdate)
    context_data = models.JSONField("Поля документа", default=dict, blank=True)
    body = models.TextField("Сформированный текст", blank=True)
    status = models.CharField("Статус", max_length=20, choices=DocumentStatus.choices, default=DocumentStatus.SAVED)
    file = models.FileField("Файл DOCX", upload_to="documents/%Y/%m/", blank=True)
    created_by = models.ForeignKey(
        "accounts.User",
        verbose_name="Создал",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents",
    )

    class Meta:
        verbose_name = "Документ"
        verbose_name_plural = "Документы"
        ordering = ("-doc_date", "-created_at")

    def __str__(self) -> str:
        label = self.title or (self.template.name if self.template else self.get_kind_display())
        return f"{label or 'Документ'} № {self.number or '—'}"

    @property
    def kind_display(self) -> str:
        if self.kind:
            return self.get_kind_display()
        if self.template:
            return self.template.get_doc_type_display()
        return "—"

    def render(self, save: bool = True) -> None:
        """Заполняет заголовок и тело документа по шаблону и данным цеха."""
        from documents.services import build_context, render_text

        if not self.template:
            return
        context = build_context(self)
        self.title = render_text(self.template.title_template, context)
        self.body = render_text(self.template.body, context)
        if save:
            type(self).objects.filter(pk=self.pk).update(title=self.title, body=self.body)
