import re

from django.apps import AppConfig
from django.db.backends.signals import connection_created


def _sql_like(pattern, value, escape=None):
    """LIKE с регистронезависимостью для Юникода (SQLite так не умеет)."""
    if pattern is None or value is None:
        return False
    parts = []
    index = 0
    length = len(pattern)
    while index < length:
        char = pattern[index]
        if escape and char == escape and index + 1 < length:
            parts.append(re.escape(pattern[index + 1]))
            index += 2
            continue
        if char == "%":
            parts.append(".*")
        elif char == "_":
            parts.append(".")
        else:
            parts.append(re.escape(char))
        index += 1
    try:
        return re.match("^" + "".join(parts) + "$", value, re.IGNORECASE | re.DOTALL) is not None
    except re.error:
        return False


def _register_sqlite_unicode_like(sender, connection, **kwargs):
    if connection.vendor != "sqlite":
        return
    try:
        connection.connection.create_function("like", 2, _sql_like)
        connection.connection.create_function("like", 3, _sql_like)
    except Exception:  # noqa: BLE001 — не мешаем работе
        pass


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        connection_created.connect(_register_sqlite_unicode_like)
