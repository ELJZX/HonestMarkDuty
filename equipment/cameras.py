"""Доступ к камерам через сервис Camera Control.

Сервис отдаёт кадр камеры по адресу ``/camera/<id>/frame`` (JPEG) и живой
поток по WebSocket ``/camera/<id>/ws``; доступ — по сессии (cookie).
Здесь выполняем вход и проксируем кадр на сторону HonestMarkDuty.
"""
from __future__ import annotations

import http.cookiejar
import threading
import time
import urllib.parse
import urllib.request

from django.conf import settings

_login_lock = threading.Lock()
_opener: urllib.request.OpenerDirector | None = None
_last_login = 0.0
_LOGIN_TTL = 600.0


def _login() -> urllib.request.OpenerDirector | None:
    base = settings.CAMERA_CONTROL_URL.rstrip("/")
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    payload = urllib.parse.urlencode(
        {
            "username": settings.CAMERA_CONTROL_USER,
            "password": settings.CAMERA_CONTROL_PASSWORD,
            "next": "",
        }
    ).encode()
    request = urllib.request.Request(base + "/auth/login", data=payload, method="POST")
    try:
        opener.open(request, timeout=5).read()
    except Exception:
        return None
    return opener


def _get_opener(force: bool = False) -> urllib.request.OpenerDirector | None:
    global _opener, _last_login
    with _login_lock:
        stale = (time.time() - _last_login) > _LOGIN_TTL
        if _opener is None or force or stale:
            opener = _login()
            if opener is None:
                return None
            _opener = opener
            _last_login = time.time()
        return _opener


def fetch_frame(camera_id: int, timeout: int = 5) -> bytes | None:
    """Возвращает JPEG-кадр камеры или None, если кадр недоступен."""
    base = settings.CAMERA_CONTROL_URL.rstrip("/")
    url = f"{base}/camera/{int(camera_id)}/frame"
    for force in (False, True):
        opener = _get_opener(force=force)
        if opener is None:
            return None
        try:
            with opener.open(url, timeout=timeout) as response:
                if "image" not in response.headers.get("Content-Type", ""):
                    continue
                return response.read()
        except Exception:
            continue
    return None
