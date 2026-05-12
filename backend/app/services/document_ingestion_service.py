from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Iterable

from docx import Document
from fastapi import UploadFile
from openpyxl import load_workbook


MAX_EXTRACTED_CHARS_PER_FILE = 80_000


@dataclass
class ExtractedDocument:
    filename: str
    content_type: str
    text: str
    warnings: list[str]

    def as_prompt_section(self) -> str:
        return f"--- source: {self.filename} ---\n{self.text.strip()}"


def _trim_text(text: str, filename: str) -> tuple[str, list[str]]:
    normalized = "\n".join(line.rstrip() for line in text.splitlines())
    normalized = "\n".join(line for line in normalized.splitlines() if line.strip())
    if len(normalized) <= MAX_EXTRACTED_CHARS_PER_FILE:
        return normalized, []
    return (
        normalized[:MAX_EXTRACTED_CHARS_PER_FILE],
        [f"{filename}: 抽出テキストが長いため先頭{MAX_EXTRACTED_CHARS_PER_FILE}文字に切り詰めました。"],
    )


def _extract_text_document(raw: bytes, filename: str) -> tuple[str, list[str]]:
    for encoding in ("utf-8-sig", "utf-8", "cp932"):
        try:
            text = raw.decode(encoding)
            return _trim_text(text, filename)
        except UnicodeDecodeError:
            continue
    return "", [f"{filename}: テキストエンコーディングを判定できませんでした。"]


def _extract_docx(raw: bytes, filename: str) -> tuple[str, list[str]]:
    document = Document(BytesIO(raw))
    parts: list[str] = []
    for paragraph in document.paragraphs:
        if paragraph.text.strip():
            parts.append(paragraph.text.strip())
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return _trim_text("\n".join(parts), filename)


def _extract_xlsx(raw: bytes, filename: str) -> tuple[str, list[str]]:
    workbook = load_workbook(BytesIO(raw), data_only=True, read_only=True)
    parts: list[str] = []
    for sheet in workbook.worksheets:
        parts.append(f"[sheet: {sheet.title}]")
        for row in sheet.iter_rows(values_only=True):
            cells = [str(value).strip() for value in row if value not in (None, "")]
            if cells:
                parts.append(" | ".join(cells))
    return _trim_text("\n".join(parts), filename)


def _extract_pdf(raw: bytes, filename: str) -> tuple[str, list[str]]:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        return "", [f"{filename}: PDF抽出には pypdf が必要です。現時点では本文を取り込めません。"]

    reader = PdfReader(BytesIO(raw))
    pages = []
    for index, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            pages.append(f"[page {index + 1}]\n{text.strip()}")
    return _trim_text("\n\n".join(pages), filename)


async def extract_upload_file(upload: UploadFile) -> ExtractedDocument:
    raw = await upload.read()
    filename = upload.filename or "uploaded-file"
    suffix = Path(filename).suffix.lower()
    content_type = upload.content_type or ""

    if suffix in {".txt", ".md", ".markdown", ".csv"}:
        text, warnings = _extract_text_document(raw, filename)
    elif suffix == ".docx":
        text, warnings = _extract_docx(raw, filename)
    elif suffix == ".xlsx":
        text, warnings = _extract_xlsx(raw, filename)
    elif suffix == ".pdf":
        text, warnings = _extract_pdf(raw, filename)
    else:
        text = ""
        warnings = [f"{filename}: 未対応のファイル形式です。対応形式は .txt, .md, .docx, .xlsx, .pdf です。"]

    return ExtractedDocument(
        filename=filename,
        content_type=content_type,
        text=text,
        warnings=warnings,
    )


async def extract_upload_files(files: Iterable[UploadFile]) -> tuple[list[ExtractedDocument], str, list[str]]:
    documents: list[ExtractedDocument] = []
    warnings: list[str] = []

    for upload in files:
        extracted = await extract_upload_file(upload)
        documents.append(extracted)
        warnings.extend(extracted.warnings)

    combined_text = "\n\n".join(doc.as_prompt_section() for doc in documents if doc.text.strip())
    return documents, combined_text, warnings
