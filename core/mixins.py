from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


class RoleRequiredMixin(LoginRequiredMixin):
    """Ограничивает доступ по ролям. Администратор проходит всегда."""

    allowed_roles: tuple[str, ...] = ()
    admin_only: bool = False

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        user = request.user
        is_admin = user.is_superuser or getattr(user, "role", None) == "admin"
        if is_admin:
            return super().dispatch(request, *args, **kwargs)
        if self.admin_only:
            raise PermissionDenied("Операция доступна только администратору.")
        if self.allowed_roles and getattr(user, "role", None) not in self.allowed_roles:
            raise PermissionDenied("Недостаточно прав для выполнения операции.")
        return super().dispatch(request, *args, **kwargs)


class EditorRequiredMixin(RoleRequiredMixin):
    """Создание/редактирование — администратор и сменный специалист."""

    allowed_roles = ("specialist",)


class AdminRequiredMixin(RoleRequiredMixin):
    admin_only = True
