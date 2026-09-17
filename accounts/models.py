from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Пользователь с ролью, определяющей права доступа."""

    class Role(models.TextChoices):
        ADMIN = "admin", "Администратор"
        SPECIALIST = "specialist", "Сменный специалист"
        VIEWER = "viewer", "Наблюдатель"

    role = models.CharField("Роль", max_length=20, choices=Role.choices, default=Role.SPECIALIST)
    patronymic = models.CharField("Отчество", max_length=150, blank=True)
    position = models.CharField("Должность", max_length=150, blank=True)
    phone = models.CharField("Телефон", max_length=50, blank=True)
    workshop = models.ForeignKey(
        "core.Workshop",
        verbose_name="Закреплённый цех",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
    )

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        ordering = ("last_name", "first_name", "username")

    @property
    def full_name(self) -> str:
        parts = [self.last_name, self.first_name, self.patronymic]
        name = " ".join(part for part in parts if part)
        return name or self.username

    @property
    def is_admin(self) -> bool:
        return self.role == self.Role.ADMIN or self.is_superuser or self.is_staff

    @property
    def is_specialist(self) -> bool:
        return self.role == self.Role.SPECIALIST

    @property
    def can_edit(self) -> bool:
        return self.is_admin or self.is_specialist
