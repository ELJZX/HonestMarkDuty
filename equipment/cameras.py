"""Прототип камер: генерация «живого» кадра без внешнего сервиса.

Принцип повторяет реальную систему (Camera Control): у камеры есть IP,
кадр обновляется и показывает подпись/время, доступен в увеличенном виде.
Здесь кадр рисуется на сервере как SVG (меняется время и «сцена»),
поэтому прототип работает полностью автономно.
"""
from __future__ import annotations

from datetime import datetime
from html import escape


def render_frame(equipment, online: bool = True) -> bytes:
    """Возвращает SVG-кадр камеры (имитация видеопотока)."""
    name = escape(equipment.name)
    ip = escape(equipment.ip_address or "—")
    workshop = escape(equipment.workshop.name) if equipment.workshop else ""
    line = escape(equipment.line.name) if equipment.line else ""
    now = datetime.now()
    clock = now.strftime("%H:%M:%S")
    phase = now.second % 6

    if online:
        status, color = "LIVE", "#65d98a"
    else:
        status, color = "НЕТ СИГНАЛА", "#f07a7a"

    # «Конвейер» с бегущими блоками — визуально меняется каждую секунду
    blocks = []
    for i in range(9):
        x = ((i * 76) + phase * 12) % 720 - 60
        shade = "#1f2a3a" if i % 2 == 0 else "#243244"
        blocks.append(f'<rect x="{x}" y="250" width="60" height="26" rx="3" fill="{shade}"/>')
    conveyor = "".join(blocks)

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 360" width="640" height="360">
  <rect width="640" height="360" fill="#0b1220"/>
  <g stroke="#16202f" stroke-width="1">
    <line x1="0" y1="60" x2="640" y2="60"/>
    <line x1="0" y1="120" x2="640" y2="120"/>
    <line x1="0" y1="180" x2="640" y2="180"/>
    <line x1="0" y1="240" x2="640" y2="240"/>
  </g>
  <rect x="40" y="70" width="240" height="120" rx="6" fill="#111c2c" stroke="#1e2a3b"/>
  <rect x="330" y="90" width="260" height="100" rx="6" fill="#111c2c" stroke="#1e2a3b"/>
  <rect x="0" y="286" width="640" height="74" fill="#0d1626"/>
  <rect x="0" y="284" width="640" height="3" fill="#1e2a3b"/>
  {conveyor}
  <rect x="0" y="0" width="640" height="34" fill="rgba(0,0,0,.45)"/>
  <circle cx="22" cy="17" r="6" fill="{color}"/>
  <text x="38" y="22" fill="#e5edf7" font-family="monospace" font-size="14">{status}</text>
  <text x="618" y="22" fill="#9fb3c8" font-family="monospace" font-size="13" text-anchor="end">{clock}</text>
  <text x="20" y="336" fill="#e5edf7" font-family="monospace" font-size="16">{name}</text>
  <text x="20" y="356" fill="#7d92a8" font-family="monospace" font-size="12">{workshop} {line} · {ip}</text>
</svg>'''
    return svg.encode("utf-8")
