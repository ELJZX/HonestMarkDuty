"""Перенос событий смены из /main/shift_live/ в сменный журнал.

    python manage.py sync_shift_live

Запускать по расписанию (например, в 20:00).
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from journal.models import JournalEntry
from shifts.integration import (
    _shift_for_date,
    fetch_shift_live_html,
    login,
    parse_shift_live_html,
    user_for_fio,
)


def _entry_type(action: str) -> str:
    value = (action or "").strip().lower()
    if value.startswith("смену принял"):
        return JournalEntry.EntryType.SHIFT_START
    if value.startswith("смену сдал"):
        return JournalEntry.EntryType.SHIFT_END
    return JournalEntry.EntryType.WORK


def _mileage(value: str):
    value = (value or "").strip().replace(",", ".")
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


class Command(BaseCommand):
    help = "Переносит события смены (/main/shift_live/) в сменный журнал"

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Игнорировать SHIFT_SYNC_ENABLED")

    def handle(self, *args, **options):
        if not settings.SHIFT_SYNC_ENABLED and not options["force"]:
            self.stdout.write(self.style.WARNING("Пропущено: SHIFT_SYNC_ENABLED выключен"))
            return
        try:
            opener = login()
            events = parse_shift_live_html(fetch_shift_live_html(opener))
        except Exception as exc:  # сеть/авторизация/формат
            raise CommandError(f"Не удалось получить события смены: {exc}") from exc

        created = updated = 0
        for event in events:
            day = timezone.localtime(event.occurred_at).date()
            shift = _shift_for_date(day, event.fio)
            _, is_new = JournalEntry.objects.update_or_create(
                external_id=f"shiftlive:{event.event_id}",
                defaults={
                    "shift": shift,
                    "entry_type": _entry_type(event.action_task),
                    "occurred_at": event.occurred_at,
                    "specialist": user_for_fio(event.fio),
                    "equipment_line": event.equipment_line,
                    "downtime": event.downtime,
                    "action_task": event.action_task,
                    "solution": event.solution,
                    "print_head": event.print_head,
                    "mileage": _mileage(event.mileage),
                },
            )
            if is_new:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"События смены: создано {created}, обновлено {updated}, всего {len(events)}."
            )
        )
