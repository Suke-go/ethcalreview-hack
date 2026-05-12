from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.official_docx_renderer import render_official_template
from app.services.official_xlsx_renderer import render_official_xlsx_template


OFFICIAL_OUTPUTS: dict[str, tuple[str, str, str]] = {
    "application_form": ("docx", "application_form", "01-1_研究倫理審査申請書.docx"),
    "consent_form": ("docx", "consent_form", "03_同意書.docx"),
    "consent_withdrawal": ("docx", "consent_withdrawal", "04_同意撤回書.docx"),
    "honorarium_rationale": ("docx", "honorarium_rationale", "02_謝金単価の根拠について.docx"),
    "participant_list": ("xlsx", "participant_list", "実験参加者リスト.xlsx"),
}


BASE_OFFICIAL_DOCUMENT_TYPES = [
    "application_form",
    "consent_form",
    "consent_withdrawal",
    "participant_list",
]


def default_official_document_types(context: dict[str, Any]) -> list[str]:
    document_types = list(BASE_OFFICIAL_DOCUMENT_TYPES)
    if bool(context.get("reward", {}).get("enabled")):
        document_types.append("honorarium_rationale")
    return document_types


def is_official_document_type(document_type: str) -> bool:
    return document_type in OFFICIAL_OUTPUTS


def render_official_document(document_type: str, context: dict[str, Any], output_dir: Path) -> Path:
    try:
        kind, template_key, filename = OFFICIAL_OUTPUTS[document_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported official document type: {document_type}") from exc

    output_path = output_dir / filename
    if kind == "docx":
        return render_official_template(template_key, context, output_path)
    if kind == "xlsx":
        return render_official_xlsx_template(template_key, context, output_path)
    raise ValueError(f"Unsupported official template kind: {kind}")
