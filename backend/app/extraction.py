"""
Extracts text + light structure from uploaded requirement documents.

Returns a flat list of (section_title, text, location_label) tuples so the
chunker downstream doesn't care which file format it came from.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class ExtractionError(Exception):
    pass


@dataclass
class ExtractedSection:
    section_title: str
    text: str
    location: str  # e.g. "page 3", "sheet 'Login Flow'"


def extract_pdf(path: str) -> list[ExtractedSection]:
    import fitz  # PyMuPDF

    sections: list[ExtractedSection] = []
    try:
        doc = fitz.open(path)
    except Exception as exc:
        raise ExtractionError(f"Could not open PDF: {exc}") from exc

    try:
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text").strip()
            if text:
                sections.append(
                    ExtractedSection(
                        section_title=f"Page {page_num + 1}",
                        text=text,
                        location=f"page {page_num + 1}",
                    )
                )
    finally:
        doc.close()

    if not sections:
        raise ExtractionError("No extractable text found in PDF (it may be scanned/image-only).")
    return sections


def extract_docx(path: str) -> list[ExtractedSection]:
    import docx

    try:
        document = docx.Document(path)
    except Exception as exc:
        raise ExtractionError(f"Could not open DOCX: {exc}") from exc

    sections: list[ExtractedSection] = []
    current_title = "Introduction"
    current_text: list[str] = []

    def flush() -> None:
        joined = "\n".join(current_text).strip()
        if joined:
            sections.append(ExtractedSection(section_title=current_title, text=joined, location=current_title))

    for para in document.paragraphs:
        style = (para.style.name or "").lower() if para.style else ""
        text = para.text.strip()
        if not text:
            continue
        if style.startswith("heading"):
            flush()
            current_title = text
            current_text = []
        else:
            current_text.append(text)
    flush()

    # Tables often carry business rules / field validation specs
    for t_idx, table in enumerate(document.tables):
        rows_text = []
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if any(cells):
                rows_text.append(" | ".join(cells))
        if rows_text:
            sections.append(
                ExtractedSection(
                    section_title=f"Table {t_idx + 1}",
                    text="\n".join(rows_text),
                    location=f"table {t_idx + 1}",
                )
            )

    if not sections:
        raise ExtractionError("No extractable text found in DOCX.")
    return sections


def extract_xlsx(path: str) -> list[ExtractedSection]:
    import openpyxl

    try:
        wb = openpyxl.load_workbook(path, data_only=True)
    except Exception as exc:
        raise ExtractionError(f"Could not open Excel file: {exc}") from exc

    sections: list[ExtractedSection] = []
    for sheet in wb.worksheets:
        rows_text = []
        for row in sheet.iter_rows(values_only=True):
            cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
            if cells:
                rows_text.append(" | ".join(cells))
        if rows_text:
            sections.append(
                ExtractedSection(
                    section_title=f"Sheet: {sheet.title}",
                    text="\n".join(rows_text),
                    location=f"sheet '{sheet.title}'",
                )
            )

    if not sections:
        raise ExtractionError("No data found in any sheet of the Excel file.")
    return sections


def extract_document(path: str) -> list[ExtractedSection]:
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        return extract_pdf(path)
    if suffix == ".docx":
        return extract_docx(path)
    if suffix in (".xlsx", ".xls"):
        return extract_xlsx(path)
    raise ExtractionError(f"Unsupported file type: {suffix}")
