"""Формирование документов по цехам (техническое заключение, служебная записка).

Файл-образец ищется в папке ``documents/samples/`` по имени ``<код>_<тип>.docx``
(например, ``ceh1_tz.docx``). Если образца нет — формируется документ-заглушка.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from docx import Document as DocxDocument
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

from documents.services import date_long, render_text

WORKSHOP_DOCUMENTS = [
    {"name": "Цех №1", "code": "ceh1"},
    {"name": "Кисломолочный цех", "code": "kmc"},
    {"name": "Цельномолочный цех", "code": "cm"},
    {"name": "Цех стерильного молока", "code": "csm"},
    {"name": "Творожный цех", "code": "tv"},
    {"name": "Малыш моцарелла", "code": "mc"},
    {"name": "Малыш сырки", "code": "ms"},
]

DOC_KINDS = {
    "tz": "Техническое заключение",
    "sl": "Служебная записка",
}

WORKSHOP_BY_CODE = {item["code"]: item["name"] for item in WORKSHOP_DOCUMENTS}


def samples_dir() -> Path:
    configured = getattr(settings, "DOCUMENT_SAMPLES_DIR", None)
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parent / "samples"


def sample_path(code: str, kind: str) -> Path:
    return samples_dir() / f"{code}_{kind}.docx"


def document_context(name: str, code: str) -> dict:
    today = timezone.localdate()
    return {
        "organization": getattr(settings, "ORGANIZATION_NAME", ""),
        "city": getattr(settings, "ORGANIZATION_CITY", ""),
        "workshop_name": name,
        "workshop_code": code,
        "date": today.strftime("%d.%m.%Y"),
        "date_long": date_long(today),
    }


def _replace_in_paragraph(paragraph, context: dict) -> None:
    if not paragraph.runs:
        return
    original = "".join(run.text for run in paragraph.runs)
    rendered = render_text(original, context)
    if rendered == original:
        return
    for run in paragraph.runs:
        run.text = ""
    paragraph.runs[0].text = rendered


def _replace_in_container(container, context: dict) -> None:
    for paragraph in container.paragraphs:
        _replace_in_paragraph(paragraph, context)
    for table in container.tables:
        for row in table.rows:
            for cell in row.cells:
                _replace_in_container(cell, context)


def _fill_sample(path: Path, context: dict) -> BytesIO:
    docx = DocxDocument(str(path))
    _replace_in_container(docx, context)
    for section in docx.sections:
        _replace_in_container(section.header, context)
        _replace_in_container(section.footer, context)
    buffer = BytesIO()
    docx.save(buffer)
    buffer.seek(0)
    return buffer


def _build_placeholder(name: str, code: str, kind: str) -> BytesIO:
    docx = DocxDocument()

    style = docx.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(12)

    title = docx.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title.add_run(DOC_KINDS[kind])
    title_run.bold = True
    title_run.font.size = Pt(14)

    docx.add_paragraph()
    docx.add_paragraph(f"Цех: {name} (код {code})")
    docx.add_paragraph(f"Дата: {document_context(name, code)['date']}")
    docx.add_paragraph()

    note = docx.add_paragraph(
        "Образец документа не загружен. Поместите файл "
        f"«{code}_{kind}.docx» в папку documents/samples/, чтобы использовать его как шаблон."
    )
    note.alignment = WD_ALIGN_PARAGRAPH.CENTER

    buffer = BytesIO()
    docx.save(buffer)
    buffer.seek(0)
    return buffer


def build_workshop_document(name: str, code: str, kind: str) -> BytesIO:
    """Возвращает поток DOCX по образцу (или заглушку, если образца нет)."""
    context = document_context(name, code)
    path = sample_path(code, kind)
    if path.exists():
        return _fill_sample(path, context)
    return _build_placeholder(name, code, kind)
