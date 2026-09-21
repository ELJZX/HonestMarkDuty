"""Синхронизация смен и журнала с внешней системой производства.

Запуск по расписанию (08:30, 16:45, 20:00):
    python manage.py sync_shifts
"""
from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from shifts.integration import sync_window


class Command(BaseCommand):
    help = "Читает смены и журнал из внешней системы (только чтение)"

    def add_arguments(self, parser):
        parser.add_argument("--days-back", type=int, default=None)
        parser.add_argument("--days-ahead", type=int, default=None)
        parser.add_argument(
            "--force", action="store_true", help="Игнорировать SHIFT_SYNC_ENABLED"
        )

    def handle(self, *args, **options):
        days_back = (
            options["days_back"]
            if options["days_back"] is not None
            else settings.SHIFT_SYNC_DAYS_BACK
        )
        days_ahead = (
            options["days_ahead"]
            if options["days_ahead"] is not None
            else settings.SHIFT_SYNC_DAYS_AHEAD
        )
        try:
            result = sync_window(days_back, days_ahead, force=options["force"])
        except Exception as exc:  # сеть/авторизация/формат — не роняем сервер
            raise CommandError(f"Синхронизация не удалась: {exc}") from exc
        if "skipped" in result:
            self.stdout.write(self.style.WARNING(f"Пропущено: {result['skipped']}"))
            return
        self.stdout.write(
            self.style.SUCCESS(
                "Синхронизация завершена: "
                f"дней {result['workdays']}, событий {result['events']}, записей {result['entries']}"
            )
        )
