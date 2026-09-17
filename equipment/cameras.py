"""Доступ к камерам через сервис Camera Control.

Сервис отдаёт кадр камеры по адресу ``/camera/<id>/frame`` (JPEG) и живой
поток по WebSocket ``/camera/<id>/ws``; доступ — по сессии (cookie).
Здесь выполняем вход и проксируем кадр на сторону HonestMarkDuty.

Устойчивость: вход выполняется один раз под блокировкой, при неудаче —
пауза (backoff), кадры кэшируются на пару секунд, чтобы не «штормить»
сервис десятками одновременных запросов из браузера.
"""
from __future__ import annotations

import http.cookiejar
import threading
import time
import urllib.parse
import urllib.request

from django.conf import settings

_login_lock = threading.Lock()
_fetch_semaphore = threading.Semaphore(4)

_opener: urllib.request.OpenerDirector | None = None
_last_login = 0.0
_cooldown_until = 0.0

_LOGIN_TTL = 900.0
_BACKOFF = 30.0
_FRAME_TTL = 2.0
_frame_cache: dict[int, tuple[float, bytes]] = {}


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


def _get_opener() -> urllib.request.OpenerDirector | None:
    global _opener, _last_login, _cooldown_until
    now = time.time()
    with _login_lock:
        if _opener is not None and (now - _last_login) < _LOGIN_TTL:
            return _opener
        if now < _cooldown_until:
            return None
        opener = _login()
        if opener is None:
            _cooldown_until = time.time() + _BACKOFF
            _opener = None
            return None
        _opener = opener
        _last_login = time.time()
        _cooldown_until = 0.0
        return _opener


def _invalidate() -> None:
    global _opener, _last_login, _cooldown_until
    with _login_lock:
        _opener = None
        _last_login = 0.0
        _cooldown_until = time.time() + _BACKOFF


def fetch_frame(camera_id: int, timeout: int = 5) -> bytes | None:
    """Возвращает JPEG-кадр камеры или None, если кадр недоступен."""
    camera_id = int(camera_id)
    now = time.time()
    cached = _frame_cache.get(camera_id)
    if cached and (now - cached[0]) < _FRAME_TTL:
        return cached[1]

    opener = _get_opener()
    if opener is None:
        return cached[1] if cached else None

    base = settings.CAMERA_CONTROL_URL.rstrip("/")
    url = f"{base}/camera/{camera_id}/frame"
    with _fetch_semaphore:
        try:
            with opener.open(url, timeout=timeout) as response:
                if "image" not in response.headers.get("Content-Type", ""):
                    _invalidate()
                    return cached[1] if cached else None
                data = response.read()
        except Exception:
            _invalidate()
            return cached[1] if cached else None

    _frame_cache[camera_id] = (time.time(), data)
    return data
