"""Сводка изменений за предыдущую смену (для уведомления при приёме смены)."""
from __future__ import annotations

from django.utils import timezone

from equipment.models import Equipment
from inventory.models import InventoryItem, InventoryMovement, MovementType
from services.models import Service
from shifts.models import Shift


def previous_shift_events(shift: Shift | None = None) -> list[str]:
    """Краткий список событий за последнюю закрытую смену."""
    if shift is None:
        shift = Shift.objects.closed().order_by("-closed_at", "-date").first()
    if shift is None or shift.opened_at is None:
        return []

    start = shift.opened_at
    end = shift.closed_at or timezone.now()
    events: list[str] = []

    for item in InventoryItem.objects.filter(
        created_at__gte=start, created_at__lte=end
    ).order_by("name"):
        events.append(f"Новая позиция склада: {item.name}")

    movements = (
        InventoryMovement.objects.filter(
            created_at__gte=start,
            created_at__lte=end,
            movement_type__in=(MovementType.OUT, MovementType.WRITE_OFF),
        )
        .select_related("item")
        .order_by("created_at")
    )
    for movement in movements:
        events.append(
            f"Склад: {movement.get_movement_type_display()} — "
            f"{movement.item.name} ({movement.quantity})"
        )

    for camera in Equipment.objects.filter(
        is_camera=True, created_at__gte=start, created_at__lte=end
    ).order_by("name"):
        events.append(f"Добавлена камера: {camera.name}")

    for printer in Equipment.objects.filter(
        is_printer=True, created_at__gte=start, created_at__lte=end
    ).order_by("name"):
        events.append(f"Добавлен принтер: {printer.name}")

    for service in Service.objects.filter(
        created_at__gte=start, created_at__lte=end
    ).order_by("name"):
        events.append(f"Добавлен сервис: {service.name}")

    return events
