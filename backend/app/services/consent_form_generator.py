"""
同意書生成サービス（研究計画概要付き）

フォームデータから研究計画概要を含む同意書をdocx形式で生成します。
"""

from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from pathlib import Path
from typing import Dict, Any
from datetime import datetime


def generate_consent_form_with_plan(
    form_data: Dict[str, Any],
    output_dir: Path,
    lab_defaults: Dict[str, Any]
) -> Path:
    """
    研究計画概要を含む同意書を生成
    
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
    # 表面（基本情報）
    # ========================================
    
    # タイトル
    title = doc.add_paragraph()
    title_run = title.add_run('同意書')
    title_run.bold = True
    title_run.font.size = Pt(16)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    doc.add_paragraph()
    
    # 研究課題名
    doc.add_paragraph(f"研究課題名: {form_data.get('research_title', '')}")
    
    # 研究責任者
    pi_name = lab_defaults.get('lab_info', {}).get('pi_name', '')
    pi_affiliation = lab_defaults.get('lab_info', {}).get('pi_affiliation', '')
    pi_tel = lab_defaults.get('lab_info', {}).get('pi_phone', '')
    
    doc.add_paragraph(f"研究責任者: {pi_affiliation} {pi_name}")
    doc.add_paragraph(f"連絡先: {pi_tel}")
    
    doc.add_paragraph()
    
    # 同意文
    consent_text = doc.add_paragraph()
    consent_text.add_run(
        f"私は、上記の研究について十分な説明を受け、研究の内容を理解しました。\n"
        f"自分の自由意思に基づき、本研究に参加することに同意します。"
    )
    
    doc.add_paragraph()
    
    # 署名欄
    doc.add_paragraph(f"同意日: {datetime.now().strftime('%Y年%m月%d日')}")
    doc.add_paragraph("研究対象者氏名: ___________________________")
    doc.add_paragraph("署名: ___________________________")
    
    # ページブレーク
    doc.add_page_break()
    
    # ========================================
    # 裏面（研究の概要）
    # ========================================
    
    overview_title = doc.add_paragraph()
    overview_run = overview_title.add_run('研究の概要について')
    overview_run.bold = True
    overview_run.font.size = Pt(14)
    overview_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    doc.add_paragraph()
    
    # 研究対象者条件
    _add_section(doc, "研究対象者条件", form_data.get('participant_criteria', ''))
    
    # 目的
    _add_section(doc, "目的", form_data.get('research_purpose', ''))
    
    # 意義
    _add_section(doc, "意義", form_data.get('research_significance', ''))
    
    # 方法
    _add_section(doc, "方法", form_data.get('research_method', ''))
    
    # 実験内容（手順）
    if 'experiment_procedures' in form_data:
        procedures_heading = doc.add_paragraph()
        procedures_heading.add_run('[実験内容]').bold = True
        
        procedures = form_data['experiment_procedures']
        if isinstance(procedures, list):
            for i, proc in enumerate(procedures, 1):
                proc_text = proc if isinstance(proc, str) else proc.get('description', '')
                doc.add_paragraph(f"{i}. {proc_text}", style='List Number')
        else:
            doc.add_paragraph(str(procedures))
        
        doc.add_paragraph()
    
    # 所要時間
    duration = form_data.get('duration_minutes', '')
    if duration:
        _add_section(doc, "所要時間", f"約{duration}分")
    
    # 考えられるリスク
    _add_section(doc, "考えられるリスク", form_data.get('risks', ''))
    
    # 謝礼
    reward_amount = form_data.get('reward_amount', '')
    reward_type = form_data.get('reward_type', 'Amazonギフトカード（Eメールタイプ）')
    if reward_amount:
        _add_section(doc, "謝礼", 
                    f"実験終了時に謝金を{reward_type}にて{reward_amount}円お支払いいたします。")
    
    # 研究対象者の必要性、リスクと安全性
    _add_section(doc, "研究対象者の必要性，研究への参加におけるリスクと安全性，危険回避の方法について",
                form_data.get('safety_measures', ''))
    
    # 個人情報の保護
    privacy_heading = doc.add_paragraph()
    privacy_heading.add_run('個人情報の保護について').bold = True
    
    # データの匿名化
    anonymization = form_data.get('anonymization_method',
        '連結可能匿名化によるデータの匿名化を行います。研究対象者の氏名等の個人情報は研究データとは分離して管理します。')
    doc.add_paragraph(f"(1) データの匿名化について\n{anonymization}")
    
    # データの管理方法
    data_management = lab_defaults.get('data_management_defaults', {})
    management_location = data_management.get('management_location', '')
    management_method = data_management.get('management_method', '')
    disposal_method = data_management.get('disposal_method', '')
    
    doc.add_paragraph(
        f"(2) データの管理方法\n"
        f"研究データは{management_location}で保管します。{management_method}\n"
        f"{disposal_method}"
    )
    
    # 研究参加の任意性
    consent_withdrawal = form_data.get('consent_withdrawal_deadline', '同意書署名の日から90日後')
    doc.add_paragraph(
        f"(3) 研究参加の任意性\n"
        f"研究への参加は任意であり、参加しないことで不利益が生じることはありません。"
        f"実験の途中であっても不利益なく参加を取りやめることができます。"
        f"また、{consent_withdrawal}までであればデータ提供の同意撤回が可能です。"
    )
    
    # 保存
    output_path = output_dir / "03_同意書（サンプル）.docx"
    doc.save(output_path)
    
    return output_path


def _add_section(doc: Document, title: str, content: str):
    """セクションを追加するヘルパー関数"""
    if not content:
        return
    
    heading = doc.add_paragraph()
    heading.add_run(f'[{title}]').bold = True
    
    # 改行を保持してパラグラフ追加
    for line in content.split('\n'):
        if line.strip():
            doc.add_paragraph(line.strip())
    
    doc.add_paragraph()
