"""Сводка изменений за предыдущую смену (для уведомления при приёме смены)."""
from __future__ import annotations

from django.utils import timezone

from documents.models import Document
from equipment.models import Equipment
from inventory.models import InventoryItem, InventoryMovement, MovementType
from journal.models import JournalEntry
from services.models import Service
from shifts.models import Shift


def previous_shift_events(shift: Shift | None = None) -> list[dict]:
    """Краткий список событий за последнюю закрытую смену.

    Каждый элемент — ``{"text": str, "tone": "ok" | "danger" | ""}``.
    """
    if shift is None:
        shift = Shift.objects.closed().order_by("-closed_at", "-date").first()
    if shift is None or shift.opened_at is None:
        return []

    start = shift.opened_at
    end = shift.closed_at or timezone.now()
    events: list[dict] = []

    def add(text: str, tone: str = "") -> None:
        events.append({"text": text, "tone": tone})

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

    # Новые позиции склада
    for item in InventoryItem.objects.filter(
        created_at__gte=start, created_at__lte=end
    ).order_by("name"):
        add(f"Новая позиция склада: {item.name} ({item.quantity} {item.unit})")

    # Движения по складу: приход — зелёным (+), расход/списание — красным (-)
    movements = (
        InventoryMovement.objects.filter(created_at__gte=start, created_at__lte=end)
        .select_related("item")
        .order_by("created_at")
    )
    for movement in movements:
        if movement.movement_type == MovementType.IN:
            add(f"Склад: {movement.item.name} +{movement.quantity}", "ok")
        elif movement.movement_type in (MovementType.OUT, MovementType.WRITE_OFF):
            add(f"Склад: {movement.item.name} -{movement.quantity}", "danger")
        else:
            add(
                f"Склад: {movement.item.name} — "
                f"{movement.get_movement_type_display()} ({movement.quantity})"
            )

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
