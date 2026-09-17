"""Версия приложения HonestMarkDuty.

Основной источник — файл VERSION в корне проекта. Значение ниже используется
как резервное, если файл недоступен (например, при неполном деплое).
"""
from __future__ import annotations

from pathlib import Path

__version__ = "0.1.3"

_VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"


def get_version() -> str:
    try:
        value = _VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return __version__
    return value or __version__
