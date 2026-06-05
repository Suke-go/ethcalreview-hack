"""
参加者への実験概要説明書 生成サービス

研究内容を平易な文章で説明する書類をLLMで生成します。
"""

from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from pathlib import Path
from typing import Dict, Any, List

from app.services.llm_client import LLMClient
from app.logger import get_logger

logger = get_logger(__name__)


EXPLANATION_PROMPT = """
あなたは研究倫理に詳しい研究者です。
以下の研究について、参加者向けの説明書を作成してください。

【研究情報】
研究タイトル: {research_title}
研究目的: {research_purpose}
研究方法: {research_method}
所要時間: 約{duration}分
使用機器: {devices}
謝礼: {reward}円

【リスクと対策情報】
{risks_with_countermeasures}

【重要な執筆ルール】
1. 一般の方にも分かりやすい平易な日本語で記述する
2. 「です・ます」調で丁寧に記述する
3. ★★★ 専門用語・テクニカルタームは絶対に使用しない ★★★
   - 使用せざるを得ない場合は、必ず括弧内に分かりやすい説明を付ける
   - 例: 「fMRI」→「fMRI（脳の活動を画像で見る装置）」
4. 難しい漢字やカタカナ語は避け、やさしい表現に置き換える
5. 1文は短く、読みやすくする
6. ★用語の制約：研究に協力する方を指す場合は必ず「研究対象者」または「参加者」と表記する。それ以外の旧来の呼称（健康状態を含意する語や、実験の語を含む対象側の旧来の呼称など）は絶対に使用しない。

【記述すべきセクション（この順序で）】
1. 【研究の目的】 - なぜこの研究をするのか
2. 【実験の内容】 - 何をしていただくか
3. 【所要時間】 - どれくらいかかるか
4. 【謝礼について】 - お礼の内容
5. 【リスクと安全対策】 - ★重要：専門外の方にも分かるよう、複数の文・複数の段落で厚く記述する★
   - まず、この研究に研究対象者として参加していただく必要性を1-2文で述べる
   - 次に、想定される負担やリスク（目の疲れ、肩こり、心理的負担など）を具体的に説明する
   - 続いて、それらを軽減するための工夫（休憩を取れること、短い単位で実施することなど）を説明する
   - さらに、機器の安全な配置や音量の調整などの安全への配慮を説明する
   - 最後に、体調不良や強い不快感が生じた場合の緊急時の対応（直ちに中止できること、医療機関への相談案内など）を説明する
   - 各リスクと対策は「[リスク名]」と「　　対策: [具体的な対策]」のペアでも示してよい
6. 【個人情報の取り扱い】 - ★複数の文・複数の段落で厚く記述する★
   - データを匿名化し、氏名等の個人情報と研究データを分けて管理すること
   - 取得したデータを何の目的（研究の分析）にのみ使用するか（利用目的）
   - 論文・学会発表・報告書等で公表する際に、個人が特定される形では公表しないこと（公表方針）
7. 【参加の任意性】 - いつでもやめられること、途中で辞退しても不利益がないこと

※【問い合わせ先】は含めないでください（システムで自動追加します）

見出しは必ず【】で囲んでください。
"""


class ExplanationGenerator:
    """参加者説明書 生成器"""
    
    def __init__(self, llm_client: LLMClient, lab_defaults: Dict[str, Any]):
        self.llm = llm_client
        self.defaults = lab_defaults
    
    async def generate(
        self,
        form_data: Dict[str, Any],
        output_dir: Path
    ) -> Path:
        """
        参加者説明書を生成
        """
        logger.info("=" * 60)
        logger.info("参加者説明書生成 開始")
        
        # コンテキスト準備
        context = self._build_context(form_data)
        
        # LLMで説明文を生成
        explanation_text = await self._generate_explanation(context)
        
        # DOCXファイル生成
        output_path = self._generate_docx(explanation_text, context, output_dir)
        
        logger.info(f"参加者説明書生成 完了: {output_path.name}")
        logger.info("=" * 60)
        
        return output_path
    
    def _build_context(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """フォームデータからコンテキストを構築"""
        lab_info = self.defaults.get("lab_info", {})
        # 問い合わせ先（研究責任者）は設定/プリセット由来で context に解決済み。
        # flatten 経由で渡される principalInvestigator を最優先し、無ければ lab_defaults を使う。
        pi = form_data.get("principalInvestigator") or form_data.get("principal_investigator") or {}
        if not isinstance(pi, dict):
            pi = {}

        devices = form_data.get("devices", [])
        risks = form_data.get("risks", [])
        risk_countermeasures = form_data.get("riskCountermeasures", form_data.get("risk_countermeasures", []))
        
        # リスクと対策をペアにしたテキストを生成
        risks_with_countermeasures = self._format_risks_with_countermeasures(risks, risk_countermeasures)
        
        return {
            "research_title": form_data.get("title", form_data.get("research_title", "")),
            "research_purpose": form_data.get("purpose", form_data.get("research_purpose", "")),
            "research_method": form_data.get("methodology", form_data.get("research_method", "")),
            "duration": form_data.get("duration", form_data.get("duration_minutes", 60)),
            "devices": ", ".join(devices) if devices else "特になし",
            "risks": risks,
            "risk_countermeasures": risk_countermeasures,
            "risks_with_countermeasures": risks_with_countermeasures,
            "reward": form_data.get("rewardAmount", form_data.get("reward_amount", 0)),
            # 問い合わせ先（研究責任者）: context 解決済みの principalInvestigator を最優先、lab_defaults はフォールバック
            "pi_name": pi.get("name") or lab_info.get("pi_name", ""),
            "pi_affiliation": pi.get("affiliation") or lab_info.get("pi_affiliation", ""),
            "pi_position": pi.get("position") or lab_info.get("pi_position", ""),
            "pi_email": pi.get("email") or lab_info.get("pi_email", ""),
            "pi_phone": pi.get("phone") or pi.get("tel") or lab_info.get("pi_phone", ""),
            "ethics_committee": form_data.get("ethicsCommittee") or self.defaults.get("ethics_committee", {}).get("name", ""),
            "ethics_phone": form_data.get("ethicsCommitteePhone") or self.defaults.get("ethics_committee", {}).get("phone", ""),
        }
    
    def _format_risks_with_countermeasures(self, risks: List[str], countermeasures: List[str]) -> str:
        """リスクと対策をフォーマット"""
        if not risks:
            return "特に想定されるリスクはありません。"
        
        lines = []
        for i, risk in enumerate(risks):
            lines.append(f"- リスク{i+1}: {risk}")
            if i < len(countermeasures) and countermeasures[i]:
                lines.append(f"  対策: {countermeasures[i]}")
        
        return "\n".join(lines)
    
    async def _generate_explanation(self, context: Dict[str, Any]) -> str:
        """LLMで説明文を生成"""
        prompt = EXPLANATION_PROMPT.format(**context)
        
        try:
            response = await self.llm.generate_content_async(
                prompt=prompt,
                system_instruction=(
                    "あなたは研究参加者向けの説明書を作成する専門家です。"
                    "一般の方にも分かりやすく、丁寧な日本語で説明してください。"
                    "専門用語は使用せず、平易な表現を心がけてください。"
                    "研究に協力する方を指す場合は必ず「研究対象者」または「参加者」と表記し、"
                    "それ以外の旧来の呼称は使用しないでください。"
                )
            )
            return response.strip()
        except Exception as e:
            logger.error(f"説明書生成エラー: {e}")
            return self._generate_fallback(context)
    
    def _generate_fallback(self, context: Dict[str, Any]) -> str:
        """LLM失敗時のフォールバック"""
        return f"""
【研究の目的】
本研究は、{context['research_title']}を実施するものです。
{context['research_purpose']}

【実験の内容】
{context['research_method']}

【所要時間】
約{context['duration']}分を予定しています。

【謝礼について】
実験終了後、{context['reward']}円相当の謝礼をお渡しします。

【リスクと安全対策】
{context['risks_with_countermeasures']}
安全対策を十分に講じた上で実験を実施いたします。

【個人情報の取り扱い】
取得したデータは匿名化され、研究目的以外には使用いたしません。

【参加の任意性】
参加は任意であり、理由を問わずいつでも辞退することができます。
途中で辞退された場合でも、不利益を受けることは一切ありません。
"""
    
    def _generate_docx(
        self,
        explanation_text: str,
        context: Dict[str, Any],
        output_dir: Path
    ) -> Path:
        """説明書DOCXを生成"""
        doc = Document()
        
        # スタイル設定
        style = doc.styles['Normal']
        style.font.name = 'Yu Gothic'
        style.font.size = Pt(11)
        
        # タイトル
        title = doc.add_paragraph()
        title_run = title.add_run("研究参加者への説明書")
        title_run.bold = True
        title_run.font.size = Pt(14)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        doc.add_paragraph()
        
        # 研究課題名
        subtitle = doc.add_paragraph()
        subtitle.add_run(f"研究課題名: {context['research_title']}")
        subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        doc.add_paragraph()
        
        # 説明文をパースして追加
        lines = explanation_text.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 見出しの検出
            if line.startswith("【") and "】" in line:
                heading = doc.add_paragraph()
                heading_run = heading.add_run(line)
                heading_run.bold = True
            # インデントされた対策行の検出
            elif line.startswith("対策:") or line.startswith("　対策:") or line.startswith("  対策:"):
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Cm(1)  # インデント追加
                p.add_run(line.strip())
            else:
                doc.add_paragraph(line)
        
        # 問い合わせ先セクション（lab_defaultsから）
        doc.add_paragraph()
        heading = doc.add_paragraph()
        heading_run = heading.add_run("【問い合わせ先】")
        heading_run.bold = True
        
        doc.add_paragraph(f"本研究に関するご質問やご相談は、以下までお問い合わせください。")
        doc.add_paragraph()
        
        # 研究責任者
        doc.add_paragraph("■ 研究責任者")
        pi_info = []
        if context['pi_affiliation']:
            pi_info.append(context['pi_affiliation'])
        if context['pi_position']:
            pi_info.append(context['pi_position'])
        if context['pi_name']:
            pi_info.append(context['pi_name'])
        doc.add_paragraph("　" + " ".join(pi_info))
        
        if context['pi_email']:
            doc.add_paragraph(f"　メール: {context['pi_email']}")
        if context['pi_phone']:
            doc.add_paragraph(f"　電話: {context['pi_phone']}")
        
        # 倫理委員会（設定されている場合）
        if context.get('ethics_committee'):
            doc.add_paragraph()
            doc.add_paragraph("■ 研究倫理に関する問い合わせ先")
            doc.add_paragraph(f"　{context['ethics_committee']}")
            if context.get('ethics_phone'):
                doc.add_paragraph(f"　電話: {context['ethics_phone']}")
        
        # 保存
        output_path = output_dir / "参加者説明書.docx"
        doc.save(output_path)
        
        return output_path


async def generate_explanation_document(
    form_data: Dict[str, Any],
    output_dir: Path,
    llm_client: LLMClient,
    lab_defaults: Dict[str, Any]
) -> Path:
    """
    参加者説明書生成エントリーポイント
    """
    generator = ExplanationGenerator(llm_client, lab_defaults)
    return await generator.generate(form_data, output_dir)

