"""
実施計画書 DOCX生成

研究倫理審査用の実施計画書をdocx形式で生成します。
"""

from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime


def generate_implementation_plan_docx(
    form_data: Dict[str, Any],
    output_dir: Path,
    lab_defaults: Dict[str, Any]
) -> Path:
    """
    実施計画書を生成
    
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
    
    # ========================================
    # 課題名
    # ========================================
    _add_heading(doc, '課題名')
    doc.add_paragraph(form_data.get('research_title', ''))
    doc.add_paragraph()
    
    # ========================================
    # 申請研究の概要
    # ========================================
    _add_heading(doc, '申請研究の概要')
    
    # 背景
    _add_subheading(doc, '背景')
    background = form_data.get('background', '')
    _add_paragraphs(doc, background)
    
    # 目的
    _add_subheading(doc, '目的')
    purpose = form_data.get('purpose', '')
    _add_paragraphs(doc, purpose)
    
    doc.add_paragraph()
    
    # ========================================
    # 実験方法
    # ========================================
    _add_heading(doc, '実験方法')
    
    # 実験の目的
    _add_subheading(doc, '実験の目的')
    experiment_objective = form_data.get('experiment_objective', '')
    _add_paragraphs(doc, experiment_objective)
    
    # 実験参加者
    _add_subheading(doc, '実験参加者')
    participant_info = form_data.get('participant_info', '')
    _add_paragraphs(doc, participant_info)
    
    # 謝金について
    _add_subheading(doc, '謝金について')
    reward_info = form_data.get('reward_info', '')
    _add_paragraphs(doc, reward_info)
    
    # 実験装置
    _add_subheading(doc, '実験装置')
    equipment = form_data.get('equipment_description', '')
    _add_paragraphs(doc, equipment)
    
    # 実験手順
    _add_subheading(doc, '実験手順')
    procedures = form_data.get('procedures', [])
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
    
    doc.add_paragraph()
    
    # ========================================
    # 想定される負荷
    # ========================================
    _add_heading(doc, '想定される精神的・物理的負荷')
    
    # 精神的負荷
    mental_load = form_data.get('mental_load', '')
    if mental_load:
        _add_paragraphs(doc, mental_load)
    
    # 物理的負荷
    physical_load = form_data.get('physical_load', '')
    if physical_load:
        _add_paragraphs(doc, physical_load)
    
    # 安全対策
    safety = form_data.get('safety_measures', '')
    if safety:
        doc.add_paragraph()
        _add_subheading(doc, '実験装置の安全性およびリスク管理について')
        _add_paragraphs(doc, safety)
    
    # 保存
    output_path = output_dir / "実施計画書.docx"
    doc.save(output_path)
    
    return output_path


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
