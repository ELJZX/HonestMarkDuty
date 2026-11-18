"""Сводка изменений за предыдущую смену (для уведомления при приёме смены)."""
from __future__ import annotations

from django.utils import timezone

from django.db.models import Q

from documents.models import Document
from equipment.models import Equipment
from inventory.models import InventoryItem, InventoryMovement, MovementType
from journal.models import JournalEntry
from services.models import Service
from shifts.models import Shift


def _previous_shift(shift: Shift | None) -> Shift | None:
    if shift is not None:
        return shift
    return Shift.objects.closed().order_by("-closed_at", "-date").first()


def previous_shift_events(shift: Shift | None = None) -> list[dict]:
    """Краткий список событий за последнюю закрытую смену.

    Каждый элемент — ``{"text": str, "tone": "ok" | "danger" | ""}``.
    """
    shift = _previous_shift(shift)
    if shift is None or shift.opened_at is None:
        return []

    start = shift.opened_at
    end = shift.closed_at or timezone.now()
    events: list[dict] = []

    def add(text: str, tone: str = "", qty: str = "") -> None:
        events.append({"text": text, "tone": tone, "qty": qty})

    # Записи сменного журнала за предыдущую смену
    for entry in (
        JournalEntry.objects.filter(shift=shift)
        .select_related("specialist")
        .order_by("occurred_at", "id")
    ):
        time_label = timezone.localtime(entry.occurred_at).strftime("%H:%M")
        if entry.equipment_line:
            add(f"Журнал ({time_label}): {entry.equipment_line} — {entry.action_task}")
        else:
            add(f"Журнал ({time_label}): {entry.action_task}")

    for camera in Equipment.objects.filter(
        is_camera=True, created_at__gte=start, created_at__lte=end
    ).order_by("name"):
        add(f"Добавлена камера: {camera.name}")

    for printer in Equipment.objects.filter(
        is_printer=True, created_at__gte=start, created_at__lte=end
    ).order_by("name"):
        add(f"Добавлен принтер: {printer.name}")

    for service in Service.objects.filter(
        created_at__gte=start, created_at__lte=end
    ).order_by("name"):
        add(f"Добавлен сервис: {service.name}")

    # Документы, добавленные в архив: номер и цех
    for document in (
        Document.objects.filter(created_at__gte=start, created_at__lte=end)
        .select_related("workshop")
        .order_by("created_at")
    ):
        number = document.number or "—"
        workshop = document.workshop.name if document.workshop else "—"
        add(f"{document.kind_display} № {number}, цех: {workshop}")

    return events


def previous_shift_warehouse_events(shift: Shift | None = None) -> list[dict]:
    """Изменения склада за предыдущую смену.

    Для выдачи/списания показываем, на какую линию ушла запчасть
    (``equipment_line``) и какой остаток остался на складе.
    """
    shift = _previous_shift(shift)
    if shift is None or shift.opened_at is None:
        return []

    start = shift.opened_at
    end = shift.closed_at or timezone.now()
    events: list[dict] = []

    movements = (
        InventoryMovement.objects.filter(
            Q(shift=shift) | Q(shift__isnull=True, created_at__gte=start, created_at__lte=end)
        )
        .select_related("item", "created_by")
        .order_by("created_at", "id")
    )
    for movement in movements:
        item = movement.item
        if movement.movement_type == MovementType.IN:
            tone, qty = "ok", f"+{movement.quantity} {item.unit}"
        elif movement.movement_type in (MovementType.OUT, MovementType.WRITE_OFF):
            tone, qty = "danger", f"-{movement.quantity} {item.unit}"
        else:
            tone, qty = "", f"{movement.quantity} {item.unit}"

        events.append(
            {
                "text": f"Склад: {item.name}",
                "tone": tone,
                "qty": qty,
                "operation": movement.get_movement_type_display(),
                "line": movement.equipment_line,
                "remaining": f"{item.quantity} {item.unit}",
                "comment": movement.comment,
                "at": timezone.localtime(movement.created_at).strftime("%H:%M"),
            }
        )

    # Новые позиции склада, заведённые за смену
    for item in InventoryItem.objects.filter(
        created_at__gte=start, created_at__lte=end
    ).order_by("name"):
        events.append(
            {
                "text": f"Новая позиция склада: {item.name}",
                "tone": "ok",
                "qty": f"{item.quantity} {item.unit}",
                "operation": "Новая позиция",
                "line": "",
                "remaining": f"{item.quantity} {item.unit}",
                "comment": "",
                "at": timezone.localtime(item.created_at).strftime("%H:%M"),
            }
        )

    return events
