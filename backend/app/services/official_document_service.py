from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from app.services.official_docx_renderer import render_official_template
from app.services.official_template_registry import get_official_templates_dir
from app.services.official_xlsx_renderer import render_official_xlsx_template


# (kind, template_key, output_filename)
#   kind="docx"/"xlsx" … 値を差し込んで描画する。 kind="copy" … 公式様式をそのまま同梱する
#   （マクロ・ボタン・数式付きブック等、書き換えるとレイアウトが壊れる様式は copy で配布する）。
OFFICIAL_OUTPUTS: dict[str, tuple[str, str, str]] = {
    "application_form": ("docx", "application_form", "01-1_研究倫理審査申請書.docx"),
    "consent_form": ("docx", "consent_form", "03_同意書.docx"),
    "consent_withdrawal": ("docx", "consent_withdrawal", "04_同意撤回書.docx"),
    "honorarium_rationale": ("docx", "honorarium_rationale", "02_謝金単価の根拠について.docx"),
    "video_consent": ("docx", "video_consent", "05_ビデオ画像公開承諾書.docx"),
    "participant_list": ("xlsx", "participant_list", "実験参加者リスト.xlsx"),
    # 謝金関連の管理様式（支払・実施時に手記入。記入例シート同梱）。そのまま同梱する。
    "honorarium_request": ("copy", "謝金・旅費実施伺.xlsm", "謝金・旅費実施伺.xlsm"),
    "honorarium_payment_request": ("copy", "謝金支出依頼書.docx", "謝金支出依頼書.docx"),
    # 申請後フェーズの参考様式（変更時・終了時に使う）。参考として常時同梱する。
    "plan_change_notification": ("copy", "06_研究倫理実施計画変更届.doc", "参考様式_06_研究倫理実施計画変更届.doc"),
    "implementation_report": ("copy", "実施報告書.docx", "参考様式_実施報告書.docx"),
}


BASE_OFFICIAL_DOCUMENT_TYPES = [
    "application_form",
    "consent_form",
    "consent_withdrawal",
    "participant_list",
]

# 申請後（承認後の変更・研究終了時）に使う参考様式。提出物ではないが一式に同梱する。
REFERENCE_FORM_TYPES = [
    "plan_change_notification",
    "implementation_report",
]


def default_official_document_types(context: dict[str, Any]) -> list[str]:
    document_types = list(BASE_OFFICIAL_DOCUMENT_TYPES)
    if bool(context.get("reward", {}).get("enabled")):
        # 謝金ありのとき、根拠書に加えて支払・実施の管理様式も同梱する
        document_types.append("honorarium_rationale")
        document_types.append("honorarium_request")
        document_types.append("honorarium_payment_request")
    if bool(context.get("recording", {}).get("public_release")):
        document_types.append("video_consent")
    # 参考様式（変更届・実施報告書）は出力名に「参考様式_」を付けて常時同梱
    document_types.extend(REFERENCE_FORM_TYPES)
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
    if kind == "copy":
        # 公式様式をそのままコピー（マクロ・数式・書式を保持。template_key はソースファイル名）
        source = get_official_templates_dir() / template_key
        if not source.exists():
            raise FileNotFoundError(f"Bundled official form not found: {source}")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, output_path)
        return output_path
    raise ValueError(f"Unsupported official template kind: {kind}")
