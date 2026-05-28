"""
実施計画書 DOCX生成

研究倫理審査用の実施計画書をdocx形式で生成します。
章立ては公式参考様式（【記載例】01-2.実施計画書（参考様式）260127）に準拠:
    1.課題名 / 2.研究の概要 /
    3.実験方法（3-1.実験の目的 / 3-2.実験参加者 / 3-3.実験装置・実験タスク / 3-4.実験手順）
アンケート調査の場合は 3.アンケートの実施方法（3-1.目的 / 3-2.研究対象者 / 3-3.実施内容）に分岐。

用語制約: 本文・見出しでは研究に協力する人を必ず「研究対象者」「参加者」と表記し、旧来の呼称は用いない。
"""

from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime


def build_implementation_plan_outline(is_questionnaire: bool = False) -> List[Dict[str, Any]]:
    """実施計画書の章立て（見出し構成）を公式参考様式 260127 に沿って構築する。

    Returns:
        各セクションの dict（number, title, level, key）のリスト。
        level=1 が大見出し、level=2 が小見出し。
    """
    outline: List[Dict[str, Any]] = [
        {"number": "1", "title": "課題名", "level": 1, "key": "research_title"},
        {"number": "2", "title": "研究の概要", "level": 1, "key": "overview"},
    ]
    if is_questionnaire:
        outline += [
            {"number": "3", "title": "アンケートの実施方法", "level": 1, "key": None},
            {"number": "3-1", "title": "アンケートの目的", "level": 2, "key": "experiment_objective"},
            {"number": "3-2", "title": "研究対象者", "level": 2, "key": "participant_info"},
            {"number": "3-3", "title": "実施内容", "level": 2, "key": "procedures"},
        ]
    else:
        outline += [
            {"number": "3", "title": "実験方法", "level": 1, "key": None},
            {"number": "3-1", "title": "実験の目的", "level": 2, "key": "experiment_objective"},
            {"number": "3-2", "title": "実験参加者", "level": 2, "key": "participant_info"},
            {"number": "3-3", "title": "実験装置・実験タスク", "level": 2, "key": "equipment_description"},
            {"number": "3-4", "title": "実験手順", "level": 2, "key": "procedures"},
        ]
    return outline


def generate_implementation_plan_docx(
    form_data: Dict[str, Any],
    output_dir: Path,
    lab_defaults: Dict[str, Any]
) -> Path:
    """
    実施計画書を生成（公式参考様式 260127 の章立て）

    Args:
        form_data: フォームデータ
        output_dir: 出力ディレクトリ
        lab_defaults: 研究室デフォルト設定

    Returns:
        生成されたファイルのパス
    """
    doc = Document()

    # スタイル設定（11pt統一）
    style = doc.styles['Normal']
    style.font.name = 'Yu Gothic'
    style.font.size = Pt(11)

    # ========================================
    # タイトル
    # ========================================
    title = doc.add_paragraph()
    title_run = title.add_run('実施計画書')
    title_run.bold = True
    title_run.font.size = Pt(14)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph()

    is_questionnaire = bool(form_data.get('is_questionnaire', False))
    outline = build_implementation_plan_outline(is_questionnaire)

    # 「研究の概要」は overview があれば優先し、なければ背景＋目的から組み立てる
    overview = form_data.get('overview', '')
    if not overview:
        overview = "\n".join(
            part for part in [form_data.get('background', ''), form_data.get('purpose', '')] if part
        )

    for item in outline:
        number = item["number"]
        label = f"{number}.{item['title']}"
        if item["level"] == 1:
            _add_heading(doc, label)
        else:
            _add_subheading(doc, label)

        key = item.get("key")
        if key == "research_title":
            doc.add_paragraph(form_data.get('research_title', ''))
        elif key == "overview":
            _add_paragraphs(doc, overview)
        elif key == "procedures":
            _add_procedures(doc, form_data.get('procedures', []))
        elif key:
            _add_paragraphs(doc, form_data.get(key, ''))

    # 保存
    output_path = output_dir / "実施計画書.docx"
    doc.save(output_path)

    return output_path


def _add_procedures(doc: Document, procedures: Any):
    """手順（リスト or 文字列）を描画"""
    if isinstance(procedures, list):
        for proc in procedures:
            if isinstance(proc, dict):
                step_name = proc.get('name', '')
                duration = proc.get('duration', '')
                description = proc.get('description', '')

                p = doc.add_paragraph()
                if step_name:
                    p.add_run(f"{step_name}").bold = True
                    if duration:
                        p.add_run(f"（約{duration}分）")

                if description:
                    _add_paragraphs(doc, description)
            else:
                doc.add_paragraph(str(proc))
    else:
        _add_paragraphs(doc, str(procedures))


def _add_heading(doc: Document, text: str):
    """見出しを追加（太字）"""
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(11)


def _add_subheading(doc: Document, text: str):
    """サブ見出しを追加"""
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(11)


def _add_paragraphs(doc: Document, text: str):
    """複数段落を追加（改行で分割）"""
    if not text:
        return
    
    paragraphs = text.split('\n')
    for para_text in paragraphs:
        if para_text.strip():
            p = doc.add_paragraph()
            run = p.add_run(para_text.strip())
            run.font.size = Pt(11)
