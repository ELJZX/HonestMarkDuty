"""Выгрузка сменного журнала в Excel (архив при сдаче смены)."""
from __future__ import annotations

from io import BytesIO

from django.core.files.base import ContentFile
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from journal.models import JournalExport

HEADERS = [
    ("№", 6),
    ("Время обращения", 20),
    ("Место заявки", 26),
    ("Цех", 18),
    ("Кто обратился", 20),
    ("Проблема", 42),
    ("Решение", 42),
    ("Статус", 14),
    ("Приоритет", 14),
    ("Исполнитель", 22),
    ("Время решения", 20),
    ("Длительность", 16),
]

THIN = Side(style="thin", color="B7B7B7")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def _local(value):
    if value is None:
        return ""
    if hasattr(value, "tzinfo"):
        return timezone.localtime(value).replace(tzinfo=None)
    return value


def _format_delta(delta) -> str:
    if not delta:
        return ""
    total = int(delta.total_seconds())
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def build_workbook(entries, title: str) -> Workbook:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Сменный журнал"

    sheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(HEADERS))
    title_cell = sheet.cell(row=1, column=1, value=title)
    title_cell.font = Font(size=14, bold=True)
    title_cell.alignment = Alignment(horizontal="center")

    sheet.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(HEADERS))
    subtitle = sheet.cell(
        row=2, column=1, value=f"Сформировано: {timezone.localtime():%d.%m.%Y %H:%M}"
    )
    subtitle.font = Font(size=9, italic=True, color="666666")
    subtitle.alignment = Alignment(horizontal="right")

    header_row = 3
    fill = PatternFill("solid", fgColor="1F1F1F")
    for index, (header, width) in enumerate(HEADERS, start=1):
        cell = sheet.cell(row=header_row, column=index, value=header)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = BORDER
        sheet.column_dimensions[get_column_letter(index)].width = width

    for row_index, entry in enumerate(entries, start=1):
        row = header_row + row_index
        values = [
            row_index,
            _local(entry.received_at),
            entry.source_location,
            entry.workshop.name if entry.workshop else "",
            entry.reported_by,
            entry.problem,
            entry.solution,
            entry.get_status_display(),
            entry.get_priority_display(),
            entry.assigned_to.full_name if entry.assigned_to else "",
            _local(entry.resolved_at),
            _format_delta(entry.response_time) if entry.resolved_at else "",
        ]
        for column, value in enumerate(values, start=1):
            cell = sheet.cell(row=row, column=column, value=value)
            cell.alignment = Alignment(vertical="top", wrap_text=column in (6, 7))
            cell.border = BORDER
        if row_index % 2 == 0:
            for column in range(1, len(HEADERS) + 1):
                sheet.cell(row=row, column=column).fill = PatternFill("solid", fgColor="F5F5F5")

    sheet.freeze_panes = sheet.cell(row=header_row + 1, column=1)
    return workbook


def _save(workbook: Workbook, filename: str) -> ContentFile:
    buffer = BytesIO()
    workbook.save(buffer)
    return ContentFile(buffer.getvalue(), name=filename)


def export_shift_to_excel(shift, user) -> JournalExport | None:
    entries = (
        shift.journal_entries.select_related("workshop", "assigned_to")
        .order_by("received_at")
    )
    if not entries.exists():
        return None

    title = f"Сменный журнал за {shift.date:%d.%m.%Y} ({shift.get_kind_display()})"
    workbook = build_workbook(entries, title)
    filename = f"journal_shift_{shift.date:%Y%m%d}_{shift.pk}.xlsx"

    export = JournalExport(
        shift=shift,
        entries_count=entries.count(),
        period_start=shift.opened_at,
        period_end=shift.closed_at,
        created_by=user,
    )
    export.file.save(filename, _save(workbook, filename), save=True)
    return export


def export_entries_to_excel(entries, user, title: str = "Сменный журнал") -> JournalExport:
    workbook = build_workbook(entries, title)
    filename = f"journal_export_{timezone.localtime():%Y%m%d_%H%M%S}.xlsx"
    export = JournalExport(
        entries_count=len(entries) if hasattr(entries, "__len__") else entries.count(),
        created_by=user,
    )
    export.file.save(filename, _save(workbook, filename), save=True)
    return export
