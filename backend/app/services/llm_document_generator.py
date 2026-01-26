"""
LLMベース書類生成サービス

Chain of Thoughtアプローチでアカデミックな研究倫理書類を生成します。
"""

from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

from app.services.llm_client import LLMClient
from app.logger import get_logger

logger = get_logger(__name__)


# アカデミックライティング基本ルール（実施計画書向け）
IMPLEMENTATION_PLAN_RULES = """
【実施計画書の執筆原則】

★★★ 最重要ルール ★★★
1. すべては「決定済み」の前提で書く
   - 「〜と考えられる」「〜の可能性がある」ではなく「〜である」「〜を行う」と断定する
   - 計画書は実施が決まった内容を記述するものである

2. 専門用語・テクニカルタームは使用しない
   - 使用する場合は必ず括弧内に平易な説明を付ける
   - 例: 「fMRI（脳の活動を画像で見る装置）」

3. 文体は「である調」で統一

4. 段落間の無駄な空白行は入れない
   - 各セクションは連続した文章として記述する

5. 避けるべき表現：
   - コロン（:）、波線（~~）、感嘆符（！）
   - 箇条書き記号の乱用
   - 「素晴らしい」「重要です」などの強調表現

6. 使用すべき表現：
   - 「本研究では〜を行う」「〜を明らかにする」
   - 「参加者は〜する」「実験者は〜を測定する」
   - 「〜に基づき」「〜を踏まえて」
"""


class LLMDocumentGenerator:
    """
    LLMベースの書類生成器
    
    Chain of Thought (CoT) アプローチで各セクションを順次生成し、
    アカデミックライティングの原則に準拠した文章を生成します。
    """
    
    def __init__(self, llm_client: LLMClient, lab_defaults: Dict[str, Any]):
        self.llm = llm_client
        self.defaults = lab_defaults
    
    async def generate_implementation_plan(
        self,
        form_data: Dict[str, Any],
        output_dir: Path
    ) -> Path:
        """
        実施計画書をLLMで生成
        
        Chain of Thoughtで各セクションを順次生成：
        1. 研究背景（10行以上、関連研究を含む）
        2. 研究目的
        3. 実験の目的
        4. 実験参加者
        5. 謝金について
        6. 実験装置
        7. 実験手順
        8. 想定される精神的・物理的負荷
        """
        logger.info("=" * 60)
        logger.info("LLM実施計画書生成 開始")
        
        # コンテキスト準備
        context = {
            "research_title": form_data.get("title", form_data.get("research_title", "")),
            "brief_description": form_data.get("purpose", form_data.get("research_purpose", "")),
            "methodology": form_data.get("methodology", form_data.get("research_method", "")),
            "target_participants": form_data.get("targetDescription", ""),
            "duration": form_data.get("duration", form_data.get("duration_minutes", 0)),
            "participant_count": form_data.get("expectedParticipants", form_data.get("participant_count", 30)),
            "devices": form_data.get("devices", []),
            "risks": form_data.get("risks", []),
            "risk_countermeasures": form_data.get("riskCountermeasures", []),
            "reward_amount": form_data.get("rewardAmount", form_data.get("reward_amount", 800)),
        }
        
        logger.info(f"  研究タイトル: {context['research_title'][:50]}...")
        
        # 中間ファイル保存用
        intermediate_file = output_dir / "_intermediate_plan.json"
        
        # Chain of Thought: 各セクションを順次生成
        sections = {}
        
        # 1. 研究背景（10行以上）
        logger.info("  [1/8] 研究背景 生成中...")
        sections["background"] = await self._generate_background(context)
        self._save_intermediate(intermediate_file, sections, "background完了")
        logger.info(f"    -> {len(sections['background'])} 文字生成")
        
        # 2. 研究目的
        logger.info("  [2/8] 研究目的 生成中...")
        sections["purpose"] = await self._generate_purpose(context)
        self._save_intermediate(intermediate_file, sections, "purpose完了")
        logger.info(f"    -> {len(sections['purpose'])} 文字生成")
        
        # 3. 実験の目的
        logger.info("  [3/8] 実験の目的 生成中...")
        sections["experiment_objective"] = await self._generate_experiment_objective(context)
        self._save_intermediate(intermediate_file, sections, "experiment_objective完了")
        logger.info(f"    -> {len(sections['experiment_objective'])} 文字生成")
        
        # 4. 実験参加者
        logger.info("  [4/8] 実験参加者 生成中...")
        sections["participants"] = await self._generate_participants(context)
        self._save_intermediate(intermediate_file, sections, "participants完了")
        logger.info(f"    -> {len(sections['participants'])} 文字生成")
        
        # 5. 謝金について
        logger.info("  [5/8] 謝金について 生成中...")
        sections["reward"] = await self._generate_reward(context)
        self._save_intermediate(intermediate_file, sections, "reward完了")
        logger.info(f"    -> {len(sections['reward'])} 文字生成")
        
        # 6. 実験装置
        logger.info("  [6/8] 実験装置 生成中...")
        sections["equipment"] = await self._generate_equipment(context)
        self._save_intermediate(intermediate_file, sections, "equipment完了")
        logger.info(f"    -> {len(sections['equipment'])} 文字生成")
        
        # 7. 実験手順
        logger.info("  [7/8] 実験手順 生成中...")
        sections["procedures"] = await self._generate_procedures(context)
        self._save_intermediate(intermediate_file, sections, "procedures完了")
        logger.info(f"    -> {len(sections['procedures'])} 文字生成")
        
        # 8. 想定される負荷
        logger.info("  [8/8] 想定される負荷 生成中...")
        sections["risks"] = await self._generate_risks(context)
        self._save_intermediate(intermediate_file, sections, "risks完了")
        logger.info(f"    -> {len(sections['risks'])} 文字生成")
        
        # DOCXファイル生成
        output_path = self._build_implementation_plan_docx(
            sections=sections,
            context=context,
            output_dir=output_dir
        )
        
        logger.info(f"LLM実施計画書生成 完了: {output_path.name}")
        logger.info("=" * 60)
        
        return output_path
    
    def _save_intermediate(self, path: Path, sections: Dict[str, str], status: str):
        """中間結果を保存"""
        import json
        data = {
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "sections": sections
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"    中間保存: {status}")
    
    async def _generate_background(self, context: Dict[str, Any]) -> str:
        """研究背景を生成（10行以上、関連研究を含む）"""
        prompt = f"""
{IMPLEMENTATION_PLAN_RULES}

【タスク】
以下の研究の「背景」セクションを執筆してください。

研究タイトル: {context['research_title']}
研究概要: {context['brief_description']}
研究方法: {context['methodology']}

【重要な要件】
★ 最低10行以上（400文字以上）で執筆すること
★ 入力を拡大解釈し、関連しそうな研究領域・技術・知見を積極的に言及すること
★ 以下の内容を含めること：
  1. この研究分野の現状（2-3文）
  2. 関連する先行研究や技術の動向（3-4文）
  3. 現在の課題や未解決の問題（2-3文）
  4. なぜこの研究が必要か、どのようなギャップを埋めるか（2-3文）

【執筆スタイル】
- すべて断定形で書く（「〜と考えられる」ではなく「〜である」）
- 関連研究は具体的な技術名や概念を挙げる（論文引用は不要）
- 段落間の空行は入れない、連続した文章として記述する

見出しは含めず、本文のみを出力してください。
"""
        return await self._call_llm(prompt)
    
    async def _generate_purpose(self, context: Dict[str, Any]) -> str:
        """研究目的を生成"""
        prompt = f"""
{IMPLEMENTATION_PLAN_RULES}

【タスク】
以下の研究の「目的」セクションを執筆してください。

研究タイトル: {context['research_title']}
研究概要: {context['brief_description']}
研究方法: {context['methodology']}

【記述すべき内容】
1. 本研究の主目的（何を明らかにするか、何を検証するか）
2. 具体的な検討項目（どの変数を比較するか、どんな関係性を調べるか）
3. 期待される成果や応用可能性

【執筆スタイル】
- 「本研究の目的は〜を明らかにすることである」のような断定形で開始
- 2-3段落（200-300文字）で記述
- 段落間の空行は入れない

見出しは含めず、本文のみを出力してください。
"""
        return await self._call_llm(prompt)
    
    async def _generate_experiment_objective(self, context: Dict[str, Any]) -> str:
        """実験の目的を生成"""
        prompt = f"""
{IMPLEMENTATION_PLAN_RULES}

【タスク】
「実験の目的」セクションを執筆してください。
これは「研究目的」とは異なり、具体的な実験手続きの目的を説明するものです。

研究タイトル: {context['research_title']}
研究方法: {context['methodology']}
使用機器: {', '.join(context['devices']) if context['devices'] else '特になし'}

【記述すべき内容】
1. この実験で何を測定・観察するか
2. どのような条件を設定し比較するか
3. 参加者にどのような回答・行動を求めるか

【執筆スタイル】
- 「本実験は〜を測定することで〜を明らかにすることを目的とする」のような形式
- 1段落（100-150文字）で簡潔に記述

見出しは含めず、本文のみを出力してください。
"""
        return await self._call_llm(prompt)
    
    async def _generate_participants(self, context: Dict[str, Any]) -> str:
        """実験参加者を生成"""
        prompt = f"""
{IMPLEMENTATION_PLAN_RULES}

【タスク】
「実験参加者」セクションを執筆してください。

研究タイトル: {context['research_title']}
対象者概要: {context['target_participants']}
予定参加者数: {context['participant_count']}名
想定されるリスク: {', '.join(context['risks']) if context['risks'] else '特になし'}

【記述すべき内容（順番通りに）】
1. 対象者の条件（年齢、所属、健康要件など）と参加者数
2. 自由意志による参加であること、不参加でも不利益がないこと
3. 除外基準（リスクに関連する健康状態、既往歴など）
4. 募集方法（学内掲示、研究室広報など）

【執筆スタイル】
- 「実験参加者は〜とする」のような断定形
- 3-4段落で記述
- 段落間の空行は入れない

見出しは含めず、本文のみを出力してください。
"""
        return await self._call_llm(prompt)
    
    async def _generate_reward(self, context: Dict[str, Any]) -> str:
        """謝金についてを生成"""
        duration = context.get('duration', 60)
        reward = context.get('reward_amount', 800)
        
        prompt = f"""
{IMPLEMENTATION_PLAN_RULES}

【タスク】
「謝金について」セクションを執筆してください。

所要時間: 約{duration}分
謝金額: {reward}円

【記述すべき内容】
1. 謝礼の形式と金額
2. 算出根拠（最低賃金または大学規定に基づく計算根拠）

【参考フォーマット】
本研究の参加者への謝礼として、Amazonギフトカード（Eメールタイプ）{reward}円分を配布する。
【算出根拠】本学の規定に基づき、実験所要時間（{duration}分）相当額を算出した。

1段落で簡潔に記述してください。
見出しは含めず、本文のみを出力してください。
"""
        return await self._call_llm(prompt)
    
    async def _generate_equipment(self, context: Dict[str, Any]) -> str:
        """実験装置を生成"""
        devices = context.get('devices', [])
        devices_str = ', '.join(devices) if devices else '特になし'
        
        prompt = f"""
{IMPLEMENTATION_PLAN_RULES}

【タスク】
「実験装置」セクションを執筆してください。

研究方法: {context['methodology']}
使用機器: {devices_str}

【記述すべき内容】
- 使用する装置・機器を「第一に」「第二に」と列挙して説明
- 各装置の仕様や役割を具体的に記述
- 安全性に関わる配置や設定があれば記述

【執筆スタイル】
- 「実験装置は以下から構成される。」で開始
- 各装置を「第一に、〜である。」「第二に、〜である。」の形式で説明
- 段落間の空行は入れない

見出しは含めず、本文のみを出力してください。
"""
        return await self._call_llm(prompt)
    
    async def _generate_procedures(self, context: Dict[str, Any]) -> str:
        """実験手順を生成"""
        duration = context.get('duration', 60)
        
        prompt = f"""
{IMPLEMENTATION_PLAN_RULES}

【タスク】
「実験手順」セクションを執筆してください。

研究方法: {context['methodology']}
所要時間: 約{duration}分
使用機器: {', '.join(context['devices']) if context['devices'] else '特になし'}

【記述すべき手順（サブセクションとして）】
1. 研究の目的・内容・倫理的配慮の説明と同意取得（約10分）
   - 何を説明するか、参加者の権利をどう伝えるか
2. 実験準備および姿勢の調整（約5分）
   - 機器の設定、参加者の準備
3. 実験試行（約X分 × 条件数）
   - 各試行で何を行うか、休憩の有無
4. 機器の取り外し・終了処理（約5分）
   - 終了確認、体調確認

【執筆スタイル】
- 各手順のサブ見出しは太字で「手順名（約X分）」の形式
- 実施分担者（研究者）と参加者の行動を具体的に記述
- いつでも中断可能であること、不快時の対応を明記
- 段落間の空行は入れない

見出しは含めず、本文のみを出力してください。
"""
        return await self._call_llm(prompt)
    
    async def _generate_risks(self, context: Dict[str, Any]) -> str:
        """想定される負荷を生成"""
        risks = context.get('risks', [])
        countermeasures = context.get('risk_countermeasures', [])
        risks_str = '\n'.join(f"- {r}" for r in risks) if risks else "特になし"
        countermeasures_str = '\n'.join(f"- {c}" for c in countermeasures) if countermeasures else ""
        
        prompt = f"""
{IMPLEMENTATION_PLAN_RULES}

【タスク】
「想定される精神的・物理的負荷」セクションを執筆してください。

研究方法: {context['methodology']}
使用機器: {', '.join(context['devices']) if context['devices'] else '特になし'}
想定されるリスク:
{risks_str}
対策:
{countermeasures_str}

【記述すべき内容】
1. 精神的負荷
   - どのような心理的負担が生じうるか
   - 対処法（事前説明、中断可能性など）
2. 物理的負荷
   - 「第一に」「第二に」と列挙してリスクを説明
   - 各リスクへの対処法
3. 実験装置の安全性およびリスク管理について（見出し付き）
   - 常時監視体制
   - 機器配置による安全確保

【執筆スタイル】
- 「本研究では、以下の精神的負荷が生じる可能性がある。」で開始
- 具体的な対策を必ず記述
- 段落間の空行は入れない

見出しは含めず、本文のみを出力してください。
"""
        return await self._call_llm(prompt)
    
    async def _call_llm(self, prompt: str) -> str:
        """LLM呼び出し（共通処理）"""
        try:
            response = await self.llm.generate_content_async(
                prompt=prompt,
                system_instruction=(
                    "あなたは日本の大学で研究倫理審査申請書を作成する経験豊富な研究者です。"
                    "実施計画書は「これから行う」計画ではなく「決定済み」の内容を記述するものです。"
                    "すべて断定形で書き、曖昧な表現は避けてください。"
                    "専門用語は使用せず、一般の方にも分かりやすい日本語で記述してください。"
                    "である調で統一してください。"
                )
            )
            return self._post_process(response)
        except Exception as e:
            logger.error(f"LLM呼び出しエラー: {e}")
            return ""
    
    def _post_process(self, text: str) -> str:
        """AIライクな表現を除去する後処理"""
        if not text:
            return ""
        
        # 不要な記号を削除
        replacements = {
            ":": "。",
            "!": "。",
            "~~": "",
            "**": "",
            "##": "",
            "###": "",
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # 断定的表現を柔らかく→逆に断定を維持
        academic_replacements = {
            "素晴らしい": "",
            "ことができます": "ことが可能である",
            "を行います": "を行う",
            "と思われます": "である",
            "かもしれません": "である",
            "と考えられます": "である",
        }
        
        for old, new in academic_replacements.items():
            text = text.replace(old, new)
        
        # 連続する空行を削除
        while "\n\n\n" in text:
            text = text.replace("\n\n\n", "\n\n")
        
        return text.strip()
    
    def _build_implementation_plan_docx(
        self,
        sections: Dict[str, str],
        context: Dict[str, Any],
        output_dir: Path
    ) -> Path:
        """実施計画書DOCXを構築"""
        doc = Document()
        
        # スタイル設定
        style = doc.styles['Normal']
        style.font.name = 'Yu Gothic'
        style.font.size = Pt(11)
        
        # タイトル（字間あり）
        title = doc.add_paragraph()
        title_run = title.add_run('実　施　計　画　書')
        title_run.bold = True
        title_run.font.size = Pt(14)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        doc.add_paragraph()
        
        # 課題名
        self._add_heading(doc, '課題名')
        doc.add_paragraph(context.get('research_title', ''))
        
        # 申請研究の概要
        self._add_heading(doc, '申請研究の概要')
        
        # 背景
        self._add_subheading(doc, '背景')
        self._add_text_no_blank(doc, sections.get('background', ''))
        
        # 目的
        self._add_subheading(doc, '目的')
        self._add_text_no_blank(doc, sections.get('purpose', ''))
        
        # 実験方法
        self._add_heading(doc, '実験方法')
        
        # 実験の目的
        self._add_subheading(doc, '実験の目的')
        self._add_text_no_blank(doc, sections.get('experiment_objective', ''))
        
        # 実験参加者
        self._add_subheading(doc, '実験参加者')
        self._add_text_no_blank(doc, sections.get('participants', ''))
        
        # 謝金について
        self._add_subheading(doc, '謝金について')
        self._add_text_no_blank(doc, sections.get('reward', ''))
        
        # 実験装置
        self._add_subheading(doc, '実験装置')
        self._add_text_no_blank(doc, sections.get('equipment', ''))
        
        # 実験手順
        self._add_subheading(doc, '実験手順')
        self._add_text_no_blank(doc, sections.get('procedures', ''))
        
        # 想定される負荷
        self._add_heading(doc, '想定される精神的・物理的負荷')
        self._add_text_no_blank(doc, sections.get('risks', ''))
        
        # 保存
        output_path = output_dir / "実施計画書.docx"
        doc.save(output_path)
        
        return output_path
    
    def _add_heading(self, doc: Document, text: str):
        """見出しを追加（太字、前に空行）"""
        # 見出し前に空行を追加
        doc.add_paragraph()
        p = doc.add_paragraph()
        run = p.add_run(text)
        run.bold = True
        run.font.size = Pt(12)
        # 段落の後に少しスペース
        p.paragraph_format.space_after = Pt(6)
    
    def _add_subheading(self, doc: Document, text: str):
        """サブ見出しを追加（太字、わずかにインデント）"""
        p = doc.add_paragraph()
        run = p.add_run(f"▶ {text}")
        run.bold = True
        run.font.size = Pt(11)
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(3)
    
    def _add_text_no_blank(self, doc: Document, text: str):
        """テキストを追加（適切な段落間隔）"""
        if not text:
            return
        
        # 改行で分割
        paragraphs = text.split('\n')
        for para_text in paragraphs:
            para_text = para_text.strip()
            if para_text:
                p = doc.add_paragraph()
                
                # 「対策:」で始まる行はインデント
                if para_text.startswith("対策:") or para_text.startswith("　対策:") or para_text.startswith("  対策:"):
                    p.paragraph_format.left_indent = Cm(1)
                    p.paragraph_format.first_line_indent = Cm(-0.5)
                
                run = p.add_run(para_text)
                run.font.size = Pt(10.5)
                
                # 行間を少し広げて読みやすく
                p.paragraph_format.line_spacing = 1.3
                p.paragraph_format.space_after = Pt(3)


async def generate_implementation_plan_with_llm(
    form_data: Dict[str, Any],
    output_dir: Path,
    llm_client: LLMClient,
    lab_defaults: Dict[str, Any]
) -> Path:
    """
    実施計画書をLLMで生成（エントリーポイント）
    """
    generator = LLMDocumentGenerator(llm_client, lab_defaults)
    return await generator.generate_implementation_plan(form_data, output_dir)

