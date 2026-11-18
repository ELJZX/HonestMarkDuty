"""История изменений сервисов и сводка при приёме смены.

Источник истории — архив релизов ``http://172.16.16.27:8091`` (JSON API
``/api/entries``). Сервис отдаёт релизы и коммиты; сменным инженерам
показываем только релизы. Период для каждого аккаунта свой: минимум
``SHIFT_BRIEFING_MIN_DAYS`` дней, а если инженер пропустил смены (больничный) —
все дни с момента его прошлого приёма смены.
"""
from __future__ import annotations

import json
import re
import urllib.request
from datetime import datetime, timedelta
from html import unescape

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from shifts.events import previous_shift_events, previous_shift_warehouse_events

CACHE_KEY = "changes_feed:releases:v1"
CACHE_ERROR_KEY = "changes_feed:error:v1"
CACHE_ERROR_TTL = 60

MONTHS_GENITIVE = (
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)


def _clean_text(value: str) -> str:
    """Приводит текст релиза к читаемому виду (без markdown-разметки)."""
    text = (value or "").replace("\r\n", "\n").replace("\r", "\n")
    if "<" in text and ">" in text:
        text = unescape(re.sub(r"<[^>]+>", "\n", text))
    text = re.sub(r"(?m)^\s*#{1,6}\s*", "", text)
    text = re.sub(r"\s*#{2,6}\s*", " ", text)
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _download_entries() -> list[dict]:
    """Загружает полный список записей архива изменений."""
    request = urllib.request.Request(
        f"{settings.CHANGES_FEED_URL.rstrip('/')}/api/entries",
        headers={"Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=settings.CHANGES_FEED_TIMEOUT) as response:
        payload = json.loads(response.read().decode("utf-8", "replace"))
    return payload.get("entries") or []


def _normalize_release(entry: dict) -> dict | None:
    date_iso = (entry.get("date_iso") or "").strip()
    if not date_iso:
        return None
    app = (entry.get("app") or "").strip()
    version = (entry.get("display_version") or entry.get("version") or "").strip()
    text = _clean_text(entry.get("search_text") or entry.get("changes_html") or "")
    # В конце search_text сервис дописывает имя файла и дату — они не нужны.
    file_name = (entry.get("file_name") or "").strip()
    if file_name and file_name in text:
        text = text.rsplit(file_name, 1)[0].rstrip()
    # Версия и приложение уже показаны в заголовке карточки.
    prefix = f"{version} {app}".lower()
    if prefix.strip() and text.lower().startswith(prefix):
        text = text[len(prefix) :].lstrip(" -—\n")
    return {
        "anchor": entry.get("anchor") or "",
        "app": app,
        "version": version,
        "date": date_iso,
        "date_label": (entry.get("date") or "").strip(),
        "time": (entry.get("time") or "").strip(),
        "weekday": (entry.get("weekday") or "").strip(),
        "text": text,
        "is_beta": bool(entry.get("is_beta")),
        "has_file": bool(entry.get("has_file")),
        "download_url": entry.get("download_url") or "",
        "sort_value": str(entry.get("sort_value") or ""),
    }


def _load_releases() -> tuple[list[dict], dict]:
    """Возвращает кэшированный список релизов и статус источника."""
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached, {"ok": True, "error": None, "cached": True}

    failure = cache.get(CACHE_ERROR_KEY)
    if failure:
        return [], {"ok": False, "error": failure, "cached": False}

    try:
        entries = _download_entries()
    except Exception as exc:  # сеть/формат — не мешаем приёму смены
        error = str(exc)
        cache.set(CACHE_ERROR_KEY, error, CACHE_ERROR_TTL)
        return [], {"ok": False, "error": error, "cached": False}

    releases = [
        normalized
        for normalized in (
            _normalize_release(entry)
            for entry in entries
            if (entry.get("kind") or "").lower() == "release"
        )
        if normalized is not None
    ]
    releases.sort(key=lambda item: item["sort_value"], reverse=True)
    cache.set(CACHE_KEY, releases, settings.CHANGES_FEED_CACHE_TTL)
    cache.delete(CACHE_ERROR_KEY)
    return releases, {"ok": True, "error": None, "cached": False}


def fetch_release_entries(start: datetime, end: datetime) -> tuple[list[dict], dict]:
    """Релизы за период ``start``–``end`` (включительно по датам)."""
    if not settings.CHANGES_FEED_ENABLED:
        return [], {
            "ok": False,
            "disabled": True,
            "error": "История изменений отключена.",
            "cached": False,
        }

    releases, status = _load_releases()
    start_date = timezone.localtime(start).date().isoformat()
    end_date = timezone.localtime(end).date().isoformat()
    selected = [
        item for item in releases if start_date <= item["date"] <= end_date
    ]
    status = dict(status)
    status["count"] = len(selected)
    status["source"] = settings.CHANGES_FEED_URL
    status["fetched_at"] = timezone.localtime().strftime("%d.%m.%Y %H:%M")
    return selected, status


def changes_window(user, now: datetime | None = None) -> tuple[datetime, datetime]:
    """Период истории изменений для аккаунта.

    Не меньше ``SHIFT_BRIEFING_MIN_DAYS`` дней. Если прошлый приём смены был
    раньше (больничный/отпуск), показываем всё с этой даты.
    """
    now = now or timezone.now()
    floor = now - timedelta(days=max(1, settings.SHIFT_BRIEFING_MIN_DAYS))
    seen = getattr(user, "changes_seen_at", None)
    start = floor if not seen else min(seen, floor)
    return start, now


def format_period(start: datetime, end: datetime) -> str:
    """«16–18 ноября 2026» или «28 октября — 3 ноября 2026»."""
    start = timezone.localtime(start)
    end = timezone.localtime(end)
    start_month = MONTHS_GENITIVE[start.month - 1]
    end_month = MONTHS_GENITIVE[end.month - 1]
    if start.date() == end.date():
        return f"{start.day} {start_month} {start.year}"
    if (start.year, start.month) == (end.year, end.month):
        return f"{start.day}–{end.day} {end_month} {end.year}"
    if start.year == end.year:
        return f"{start.day} {start_month} — {end.day} {end_month} {end.year}"
    return f"{start.day} {start_month} {start.year} — {end.day} {end_month} {end.year}"


def mark_changes_seen(user, moment: datetime | None = None) -> None:
    """Запоминает, что изменения просмотрены (при приёме смены)."""
    moment = moment or timezone.now()
    user.changes_seen_at = moment
    user.save(update_fields=["changes_seen_at"])


def build_shift_briefing(user) -> dict:
    """Сводка для окна приёма смены: история релизов, склад, события смены."""
    start, end = changes_window(user)
    releases, status = fetch_release_entries(start, end)
    return {
        "changes": releases,
        "changes_period": format_period(start, end),
        "changes_from": timezone.localtime(start).isoformat(),
        "changes_to": timezone.localtime(end).isoformat(),
        "changes_meta": status,
        "warehouse": previous_shift_warehouse_events(),
        "previous_events": previous_shift_events(),
    }
