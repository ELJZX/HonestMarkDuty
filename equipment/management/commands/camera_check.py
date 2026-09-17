"""Проверка доступа к сервису камер.

python manage.py camera_check [camera_id]
"""
from __future__ import annotations

import time

from django.conf import settings
from django.core.management.base import BaseCommand

from equipment.cameras import fetch_frame


class Command(BaseCommand):
    help = "Проверяет вход в Camera Control и получение кадра"

    def add_arguments(self, parser):
        parser.add_argument("camera_id", nargs="?", type=int, default=5)

    def handle(self, *args, **options):
        camera_id = options["camera_id"]
        self.stdout.write(f"Сервис: {settings.CAMERA_CONTROL_URL}")
        start = time.time()
        frame = fetch_frame(camera_id, timeout=10)
        elapsed = round(time.time() - start, 1)
        if frame:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Кадр камеры {camera_id} получен: {len(frame)} байт за {elapsed} с"
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR(
                    f"Кадр камеры {camera_id} не получен за {elapsed} с. "
                    "Проверьте доступность Camera Control (вход) и камеры."
                )
            )
