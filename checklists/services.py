from __future__ import annotations

from decimal import Decimal, InvalidOperation

from checklists.exports import save_checklist_file
from checklists.markem_exports import save_markem_file
from checklists.models import (
    ChecklistCheck,
    ChecklistGroup,
    ChecklistMileage,
    ChecklistResult,
    ChecklistStatus,
    EquipmentChecklist,
    MarkemChecklist,
    MarkemParameter,
    MarkemPrinter,
    MarkemValue,
)


def matrix_machines_and_checks():
    groups = list(
        ChecklistGroup.objects.prefetch_related("machines").order_by("sort_order", "name")
    )
    checks = list(ChecklistCheck.objects.order_by("sort_order", "id"))
    return groups, checks


def build_matrix(checklist: EquipmentChecklist | None) -> dict:
    """Собирает структуру для отрисовки матрицы чеклиста."""
    groups, checks = matrix_machines_and_checks()
    results: dict[tuple[int, int], int] = {}
    mileages: dict[int, object] = {}
    if checklist is not None:
        results = {
            (item.machine_id, item.check_item_id): item.score for item in checklist.results.all()
        }
        mileages = {item.machine_id: item.value for item in checklist.mileages.all()}

    machine_columns = []
    all_machines = []
    for group in groups:
        machines = list(group.machines.order_by("sort_order", "name"))
        for machine in machines:
            all_machines.append(machine)
        machine_columns.append({"group": group, "machines": machines})

    rows = []
    for check in checks:
        cells = [
            {"machine": machine, "score": results.get((machine.id, check.id))}
            for machine in all_machines
        ]
        rows.append({"check": check, "cells": cells})

    mileage_cells = [
        {"machine": machine, "value": mileages.get(machine.id)} for machine in all_machines
    ]

    return {
        "machine_columns": machine_columns,
        "rows": rows,
        "mileage_cells": mileage_cells,
        "all_machines": all_machines,
        "checks_count": len(checks),
    }


def apply_matrix(checklist: EquipmentChecklist, data) -> None:
    """Сохраняет оценки и пробеги из POST-запроса."""
    checklist.results.all().delete()
    checklist.mileages.all().delete()

    for key, value in data.items():
        if not value:
            continue
        if key.startswith("score__"):
            try:
                _, machine_id, check_id = key.split("__")
                score = int(value)
            except (ValueError, TypeError):
                continue
            if 1 <= score <= 3:
                ChecklistResult.objects.create(
                    checklist=checklist,
                    machine_id=int(machine_id),
                    check_item_id=int(check_id),
                    score=score,
                )
        elif key.startswith("mileage__"):
            try:
                _, machine_id = key.split("__")
                mileage = Decimal(str(value).replace(",", "."))
            except (ValueError, InvalidOperation, TypeError):
                continue
            ChecklistMileage.objects.create(
                checklist=checklist, machine_id=int(machine_id), value=mileage
            )


def finalize_checklist(checklist: EquipmentChecklist) -> EquipmentChecklist:
    save_checklist_file(checklist)
    checklist.status = ChecklistStatus.FINAL
    checklist.save()
    return checklist


def finalize_shift_checklists(shift, user=None) -> int:
    """Формирует файлы по всем черновикам чеклистов смены. Возвращает количество."""
    queryset = EquipmentChecklist.objects.filter(shift=shift, status=ChecklistStatus.DRAFT)
    count = 0
    for checklist in queryset:
        save_checklist_file(checklist)
        checklist.status = ChecklistStatus.FINAL
        checklist.save()
        count += 1
    return count


# --- Чеклист принтеров Markem Image 9450 ----------------------------------


def markem_matrix(checklist: MarkemChecklist | None) -> dict:
    """Собирает структуру матрицы чеклиста Markem (принтеры × параметры)."""
    printers = list(MarkemPrinter.objects.order_by("sort_order", "id"))
    parameters = list(MarkemParameter.objects.order_by("sort_order", "id"))
    values: dict[tuple[int, int], str] = {}
    if checklist is not None:
        values = {
            (item.printer_id, item.parameter_id): item.value
            for item in checklist.values.all()
        }
    rows = [
        {
            "parameter": parameter,
            "cells": [
                {"printer": printer, "value": values.get((printer.id, parameter.id), "")}
                for printer in printers
            ],
        }
        for parameter in parameters
    ]
    return {"printers": printers, "parameters": parameters, "rows": rows}


def apply_markem_values(checklist: MarkemChecklist, data) -> None:
    """Сохраняет значения параметров чеклиста Markem из POST-запроса."""
    checklist.values.all().delete()
    for key, value in data.items():
        if not key.startswith("val__"):
            continue
        try:
            _, printer_id, parameter_id = key.split("__")
        except ValueError:
            continue
        text = str(value or "").strip()
        if not text:
            continue
        MarkemValue.objects.create(
            checklist=checklist,
            printer_id=int(printer_id),
            parameter_id=int(parameter_id),
            value=text[:300],
        )


def finalize_markem_checklist(checklist: MarkemChecklist) -> MarkemChecklist:
    save_markem_file(checklist)
    checklist.status = ChecklistStatus.FINAL
    checklist.save()
    return checklist
