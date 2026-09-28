from __future__ import annotations

from django.db import models

from core.models import AuditedModel


class ServiceKind(models.TextChoices):
    SERVICE = "service", "Сервис"
    SITE = "site", "Сайт"


class Service(AuditedModel):
    """Внешний сервис или сайт Молвест.Маркировка — кликабельная ссылка."""

    name = models.CharField("Название", max_length=200)
    url = models.URLField("Ссылка", max_length=500)
    kind = models.CharField(
        "Вид", max_length=20, choices=ServiceKind.choices, default=ServiceKind.SERVICE
    )
    sort_order = models.PositiveIntegerField("Порядок", default=0)
    is_active = models.BooleanField("Активен", default=True)

    class Meta:
        verbose_name = "Сервис"
        verbose_name_plural = "Сервисы"
        ordering = ("sort_order", "name")

    def __str__(self) -> str:
        return self.name
