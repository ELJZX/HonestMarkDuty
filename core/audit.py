"""Аудит изменений: кто и когда менял данные (требование №4)."""
from __future__ import annotations

import threading
from decimal import Decimal
from typing import Any

_thread_locals = threading.local()


def get_current_user():
    return getattr(_thread_locals, "user", None)


def set_current_user(user) -> None:
    _thread_locals.user = user


def serialize(value: Any) -> Any:
    """Приводит значение поля к JSON-совместимому виду."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (list, tuple, dict, set)):
        return str(value)
    return str(value)


def snapshot(instance) -> dict:
    """Снимок значимых полей экземпляра модели."""
    exclude = set(getattr(instance, "AUDIT_EXCLUDE", ()))
    data: dict[str, Any] = {}
    for field in instance._meta.concrete_fields:
        if field.name in {"created_at", "updated_at"} or field.name in exclude:
            continue
        data[field.name] = serialize(getattr(instance, field.attname, None))
    return data


def record_audit(instance, action: str, changes: dict, user=None) -> None:
    """Создаёт запись аудита. Никогда не ломает основной сценарий."""
    from core.models import AuditLog

    if user is None:
        user = get_current_user()
    if user is not None and not getattr(user, "is_authenticated", False):
        user = None
    try:
        AuditLog.objects.create(
            user=user,
            action=action,
            model_name=instance._meta.model_name,
            app_label=instance._meta.app_label,
            object_id=str(getattr(instance, "pk", "")),
            object_repr=str(instance)[:255],
            changes=changes,
        )
    except Exception:  # noqa: BLE001 — аудит не должен ронять бизнес-логику
        pass
