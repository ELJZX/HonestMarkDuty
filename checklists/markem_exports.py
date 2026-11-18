"""Формирование Excel-файла чеклиста принтеров Markem Image 9450."""

from __future__ import annotations

import math
from io import BytesIO

from django.core.files.base import ContentFile
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.properties import PageSetupProperties

from checklists.models import MarkemParameter, MarkemPrinter

TITLE = "Чек лист технического осмотра и обслуживания принтеров Markem Image 9450"

ROW_HEIGHT_MIN = 34.95
ROW_LINE_HEIGHT = 20.25
NAME_CHARS_PER_LINE = 40
VALUE_CHARS_PER_LINE = 12


def _data_row_height(name: str, values) -> float:
    """Высота строки под длинный текст: переносим наименование параметра и значения."""
    lines = max(1, math.ceil(len(name) / NAME_CHARS_PER_LINE))
    for value in values:
        if value:
            lines = max(lines, math.ceil(len(value) / VALUE_CHARS_PER_LINE))
    return max(ROW_HEIGHT_MIN, round(lines * ROW_LINE_HEIGHT, 2))


def _layout():
    printers = list(MarkemPrinter.objects.order_by("sort_order", "id"))
    parameters = list(MarkemParameter.objects.order_by("sort_order", "id"))
    return printers, parameters, max(2 + len(printers), 3)


def build_markem_workbook(checklist) -> Workbook:
    printers, parameters, last_col = _layout()

    thin = Side(style="thin", color="000000")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left = Alignment(horizontal="left", vertical="center", wrap_text=True)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Markem 9450"

    # Заголовок
    sheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=last_col)
    title_cell = sheet.cell(1, 1, TITLE)
    title_cell.font = Font(size=22, bold=True)
    title_cell.alignment = center
    sheet.row_dimensions[1].height = 32.4

    # Дата и подпись правого блока
    sheet.merge_cells("A2:B2")
    date_cell = sheet.cell(2, 1, f"Дата: {checklist.date:%d.%m.%Y}")
    date_cell.font = Font(size=12, bold=True)
    date_cell.alignment = center
    sheet.row_dimensions[2].height = 30.6
    if last_col >= 3:
        sheet.merge_cells(start_row=2, start_column=3, end_row=2, end_column=last_col)
        head_cell = sheet.cell(2, 3, "Принтер / серийный номер")
        head_cell.font = Font(size=12, bold=True)
        head_cell.alignment = center

    # Шапка таблицы
    sheet.merge_cells("A3:A4")
    sheet.cell(3, 1, "№").font = Font(size=12, bold=True)
    sheet.cell(3, 1).alignment = center
    sheet.merge_cells("B3:B4")
    sheet.cell(3, 2, "Проводимые работы и проверка параметров").font = Font(size=12, bold=True)
    sheet.cell(3, 2).alignment = center
    sheet.row_dimensions[3].height = 20.4

    for index, printer in enumerate(printers, start=3):
        if index <= last_col:
            number_cell = sheet.cell(3, index, index - 2)
            number_cell.font = Font(size=12, bold=True)
            number_cell.alignment = center
        serial_cell = sheet.cell(4, index, printer.name)
        serial_cell.font = Font(size=12, bold=True)
        serial_cell.alignment = center
    sheet.row_dimensions[4].height = 37.8

    for row in (2, 3, 4):
        for column in range(1, last_col + 1):
            sheet.cell(row, column).border = border

    sheet.column_dimensions["A"].width = 5
    sheet.column_dimensions["B"].width = 44
    for column in range(3, last_col + 1):
        sheet.column_dimensions[get_column_letter(column)].width = 13

    values = {
        (item.printer_id, item.parameter_id): item.value for item in checklist.values.all()
    }

    row = 5
    for number, parameter in enumerate(parameters, start=1):
        sheet.cell(row, 1, number).font = Font(size=12)
        sheet.cell(row, 1).alignment = center
        sheet.cell(row, 2, parameter.name).font = Font(size=12)
        sheet.cell(row, 2).alignment = left
        row_values = []
        for index, printer in enumerate(printers, start=3):
            value = values.get((printer.id, parameter.id)) or None
            row_values.append(str(value) if value else "")
            cell = sheet.cell(row, index, value)
            cell.font = Font(size=11)
            cell.alignment = center
        for column in range(1, last_col + 1):
            sheet.cell(row, column).border = border
        sheet.row_dimensions[row].height = _data_row_height(parameter.name, row_values)
        row += 1

    # Пустая строка-разделитель и строки подписей — как в эталонном бланке
    sheet.row_dimensions[row].height = 34.95
    row += 1
    sheet.row_dimensions[row].height = 39
    sheet.cell(row, 2, "Выполнил:  Специалист по цифровой маркировке").font = Font(size=14, bold=True)
    row += 1
    sheet.row_dimensions[row].height = 54.6
    row += 1
    sheet.row_dimensions[row].height = 34.8
    sheet.cell(row, 2, "Проверил:  Ведущий инженер по цифровой маркировке").font = Font(size=14, bold=True)
    sheet.row_dimensions[row + 1].height = 34.95

    # Печать: альбомная A4, масштаб 61 % — как в эталонном бланке
    sheet.print_area = f"A1:{get_column_letter(last_col)}{sheet.max_row}"
    sheet.print_title_rows = "3:4"
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.paperSize = sheet.PAPERSIZE_A4
    sheet.page_setup.scale = 61
    sheet.page_setup.fitToWidth = None
    sheet.page_setup.fitToHeight = None
    sheet.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    sheet.page_margins.left = 0.75
    sheet.page_margins.right = 0.75
    sheet.page_margins.top = 1.0
    sheet.page_margins.bottom = 1.0
    sheet.page_margins.header = 0.5
    sheet.page_margins.footer = 0.5

    return workbook


def save_markem_file(checklist):
    workbook = build_markem_workbook(checklist)
    buffer = BytesIO()
    workbook.save(buffer)
    filename = f"markem_{checklist.date:%Y%m%d}_{checklist.pk}.xlsx"
    # Перегенерация заменяет прежний файл, чтобы не плодить копии в media/
    if checklist.file:
        checklist.file.delete(save=False)
    checklist.file.save(filename, ContentFile(buffer.getvalue(), name=filename), save=False)
    checklist.save()
    return checklist.file
