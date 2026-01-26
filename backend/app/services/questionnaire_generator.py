"""
アンケート生成サービス

実験内容に応じてLLMが質問項目を提案し、アンケートを生成します。
事前アンケート・事後アンケートの両方に対応。
"""

from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from pathlib import Path
from typing import Dict, Any, List, Literal
from pydantic import BaseModel

from app.services.llm_client import LLMClient
from app.logger import get_logger

logger = get_logger(__name__)


class QuestionItem(BaseModel):
    """質問項目"""
    text: str
    type: Literal["likert", "text", "choice", "number"]
    scale: int = 5  # リカート尺度の場合
    options: List[str] = []  # 選択式の場合
    labels: List[str] = []  # リカート尺度のラベル


PRE_QUESTIONNAIRE_PROMPT = """
あなたは心理学・人間工学の研究者で、アンケート設計の専門家です。
以下の研究内容を深く理解し、この研究に特化した事前アンケートを設計してください。

【研究情報】
研究タイトル: {research_title}
研究目的: {research_purpose}
研究方法: {research_method}
対象者: {target_participants}
使用機器: {devices}
想定されるリスク: {risks}

【★★★ 重要：質問文の書き方 ★★★】
- 専門用語・テクニカルタームは絶対に使用しない
- 中学生でも理解できるやさしい日本語で書く
- 難しい漢字やカタカナ語は避ける
- 1文は短く、明確に書く

【事前アンケート設計の原則】
1. デモグラフィック情報
   - 年齢、性別、利き手など基本情報
   - 研究に関連する属性（例：VR経験、運動習慣など）

2. 除外基準の確認
   - 健康状態（研究のリスクに関連するもの）
   - 過去の経験（研究内容に影響を与えるもの）
   - 例：VR実験なら「VR酔いの経験」、聴覚実験なら「聴力の問題」

3. ベースライン測定
   - 研究の測定項目に関連する事前状態
   - 例：疲労度、気分、身体状態など

【この研究に特化した質問のポイント】
- {research_method}に関連する経験や適性
- {devices}を使用した経験
- {risks}に関連する健康状態の確認

【出力形式】
各質問を以下の形式で出力してください：
- Q1: [質問文] (type: likert/text/choice/number)
- Q2: [質問文] (type: likert/text/choice/number)
...

この研究に最適化された6-10問を提案してください。
汎用的な質問ではなく、この研究でしか使わないような具体的な質問を含めてください。
"""


POST_QUESTIONNAIRE_PROMPT = """
あなたは心理学・人間工学の研究者で、アンケート設計の専門家です。
以下の研究内容を深く理解し、この研究に特化した事後アンケートを設計してください。

【研究情報】
研究タイトル: {research_title}
研究目的: {research_purpose}
研究方法: {research_method}
所要時間: 約{duration}分
使用機器: {devices}
想定されるリスク: {risks}

【★★★ 重要：質問文の書き方 ★★★】
- 専門用語・テクニカルタームは絶対に使用しない
- 中学生でも理解できるやさしい日本語で書く
- 難しい漢字やカタカナ語は避ける
- 1文は短く、明確に書く

【事後アンケート設計の原則】
1. 実験体験の評価
   - 実験内容の理解度
   - 指示の明確さ
   - 実験環境の快適さ

2. 主観的評価（研究目的に関連）
   - 研究で測定したい主観的な感覚や印象
   - 例：VR実験なら「没入感」「リアリティ」
   - 例：音声実験なら「聞き取りやすさ」「自然さ」

3. 負担・不快感の確認
   - {risks}に関連する実際の体験
   - 疲労度、不快感、ストレス

4. 自由記述
   - 気づいた点、改善提案

【この研究に特化した質問のポイント】
- {research_purpose}の達成度を測る主観評価
- {research_method}の体験に関する具体的な感想
- {devices}使用時の感覚（違和感、操作性など）

【出力形式】
各質問を以下の形式で出力してください：
- Q1: [質問文] (type: likert/text/choice/number)
- Q2: [質問文] (type: likert/text/choice/number)
...

この研究の目的に直結する主観評価質問を中心に、6-10問を提案してください。
リカート尺度（5段階）と自由記述を適切に組み合わせてください。
"""


class QuestionnaireGenerator:
    """アンケート生成器"""
    
    def __init__(self, llm_client: LLMClient, lab_defaults: Dict[str, Any]):
        self.llm = llm_client
        self.defaults = lab_defaults
    
    async def generate_pre_questionnaire(
        self,
        form_data: Dict[str, Any],
        output_dir: Path
    ) -> Path:
        """事前アンケートを生成"""
        logger.info("事前アンケート生成 開始")
        
        questions = await self._generate_questions(form_data, "pre")
        output_path = self._generate_docx(
            questions=questions,
            title="事前アンケート",
            research_title=form_data.get("title", form_data.get("research_title", "")),
            output_dir=output_dir,
            filename="事前アンケート.docx"
        )
        
        logger.info(f"事前アンケート生成 完了: {output_path.name}")
        return output_path
    
    async def generate_post_questionnaire(
        self,
        form_data: Dict[str, Any],
        output_dir: Path
    ) -> Path:
        """事後アンケートを生成"""
        logger.info("事後アンケート生成 開始")
        
        questions = await self._generate_questions(form_data, "post")
        output_path = self._generate_docx(
            questions=questions,
            title="事後アンケート",
            research_title=form_data.get("title", form_data.get("research_title", "")),
            output_dir=output_dir,
            filename="事後アンケート.docx"
        )
        
        logger.info(f"事後アンケート生成 完了: {output_path.name}")
        return output_path
    
    async def _generate_questions(
        self,
        form_data: Dict[str, Any],
        questionnaire_type: Literal["pre", "post"]
    ) -> List[QuestionItem]:
        """LLMで質問項目を生成"""
        
        context = {
            "research_title": form_data.get("title", form_data.get("research_title", "")),
            "research_purpose": form_data.get("purpose", form_data.get("research_purpose", "")),
            "research_method": form_data.get("methodology", form_data.get("research_method", "")),
            "target_participants": form_data.get("targetDescription", ""),
            "duration": form_data.get("duration", form_data.get("duration_minutes", 60)),
            "devices": ", ".join(form_data.get("devices", [])) if form_data.get("devices") else "特になし",
            "risks": ", ".join(form_data.get("risks", [])) if form_data.get("risks") else "特になし",
        }
        
        if questionnaire_type == "pre":
            prompt = PRE_QUESTIONNAIRE_PROMPT.format(**context)
        else:
            prompt = POST_QUESTIONNAIRE_PROMPT.format(**context)
        
        try:
            response = await self.llm.generate_content_async(
                prompt=prompt,
                system_instruction=(
                    "あなたは研究者向けアンケート設計の専門家です。"
                    "実験内容に適した質問項目を提案してください。"
                )
            )
            
            return self._parse_questions(response)
            
        except Exception as e:
            logger.error(f"質問生成エラー: {e}")
            return self._get_default_questions(questionnaire_type)
    
    def _parse_questions(self, response: str) -> List[QuestionItem]:
        """LLMレスポンスをパース"""
        questions = []
        lines = response.strip().split("\n")
        
        for line in lines:
            line = line.strip()
            if not line or not line.startswith("-"):
                continue
            
            # "- Q1: [質問文] (type: xxx)" 形式をパース
            try:
                # Q番号を除去
                if ": " in line:
                    _, rest = line.split(": ", 1)
                else:
                    rest = line[2:]  # "- " を除去
                
                # タイプを抽出
                q_type = "text"
                if "(type:" in rest:
                    text_part, type_part = rest.rsplit("(type:", 1)
                    q_type = type_part.replace(")", "").strip()
                    text = text_part.strip()
                else:
                    text = rest.strip()
                
                # Q番号が残っていれば除去
                if text.startswith("Q") and text[1].isdigit():
                    text = text.split(":", 1)[-1].strip() if ":" in text else text[3:].strip()
                
                questions.append(QuestionItem(
                    text=text,
                    type=q_type if q_type in ["likert", "text", "choice", "number"] else "text"
                ))
                
            except Exception:
                continue
        
        return questions if questions else self._get_default_questions("post")
    
    def _get_default_questions(self, questionnaire_type: str) -> List[QuestionItem]:
        """デフォルトの質問項目"""
        if questionnaire_type == "pre":
            return [
                QuestionItem(text="年齢を教えてください。", type="number"),
                QuestionItem(text="性別を教えてください。", type="choice", options=["男性", "女性", "その他", "回答しない"]),
                QuestionItem(text="利き手を教えてください。", type="choice", options=["右", "左", "両利き"]),
                QuestionItem(text="現在、健康上の問題はありますか？", type="text"),
                QuestionItem(text="本日の体調を教えてください。", type="likert", labels=["非常に悪い", "", "普通", "", "非常に良い"]),
            ]
        else:
            return [
                QuestionItem(text="実験内容は分かりやすかったですか？", type="likert", labels=["全くそう思わない", "", "どちらでもない", "", "非常にそう思う"]),
                QuestionItem(text="実験中に不快に感じた点はありましたか？", type="likert", labels=["全くなかった", "", "どちらでもない", "", "非常にあった"]),
                QuestionItem(text="疲労を感じましたか？", type="likert", labels=["全く感じなかった", "", "どちらでもない", "", "非常に感じた"]),
                QuestionItem(text="不快に感じた点があれば具体的に教えてください。", type="text"),
                QuestionItem(text="改善点やご意見があれば教えてください。", type="text"),
            ]
    
    def _generate_docx(
        self,
        questions: List[QuestionItem],
        title: str,
        research_title: str,
        output_dir: Path,
        filename: str
    ) -> Path:
        """アンケートDOCXを生成"""
        doc = Document()
        
        # スタイル設定
        style = doc.styles['Normal']
        style.font.name = 'Yu Gothic'
        style.font.size = Pt(11)
        
        # タイトル
        title_para = doc.add_paragraph()
        title_run = title_para.add_run(title)
        title_run.bold = True
        title_run.font.size = Pt(14)
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # 研究タイトル
        subtitle = doc.add_paragraph()
        subtitle.add_run(f"研究課題名: {research_title}")
        subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        doc.add_paragraph()
        
        # 説明文
        intro = doc.add_paragraph()
        intro.add_run("以下の質問にお答えください。回答に正解・不正解はありません。")
        
        doc.add_paragraph()
        
        # 質問項目
        for i, q in enumerate(questions, 1):
            # 質問文
            q_para = doc.add_paragraph()
            q_para.add_run(f"Q{i}. {q.text}").bold = True
            
            if q.type == "likert":
                # リカート尺度
                self._add_likert_scale(doc, q.scale, q.labels)
            elif q.type == "choice":
                # 選択式
                for opt in q.options:
                    doc.add_paragraph(f"　□ {opt}")
            elif q.type == "number":
                # 数値入力
                doc.add_paragraph("　回答: _______________")
            else:
                # 自由記述
                doc.add_paragraph("　")
                doc.add_paragraph("　" + "_" * 50)
                doc.add_paragraph("　" + "_" * 50)
            
            doc.add_paragraph()
        
        # 保存
        output_path = output_dir / filename
        doc.save(output_path)
        
        return output_path
    
    def _add_likert_scale(self, doc: Document, scale: int, labels: List[str]):
        """リカート尺度を追加"""
        # ラベルが不足している場合は補完
        if len(labels) < scale:
            labels = labels + [""] * (scale - len(labels))
        
        # テーブル作成
        table = doc.add_table(rows=2, cols=scale)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        
        # ラベル行
        for j in range(scale):
            cell = table.rows[0].cells[j]
            if j < len(labels):
                cell.text = labels[j]
            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # 選択肢行
        for j in range(scale):
            cell = table.rows[1].cells[j]
            cell.text = f"□ {j + 1}"
            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER


async def generate_questionnaire(
    form_data: Dict[str, Any],
    output_dir: Path,
    llm_client: LLMClient,
    lab_defaults: Dict[str, Any],
    questionnaire_type: Literal["pre", "post", "both"] = "both"
) -> List[Path]:
    """
    アンケート生成エントリーポイント
    
    Returns:
        List[Path]: 生成されたファイルのリスト
    """
    generator = QuestionnaireGenerator(llm_client, lab_defaults)
    paths = []
    
    if questionnaire_type in ["pre", "both"]:
        pre_path = await generator.generate_pre_questionnaire(form_data, output_dir)
        paths.append(pre_path)
    
    if questionnaire_type in ["post", "both"]:
        post_path = await generator.generate_post_questionnaire(form_data, output_dir)
        paths.append(post_path)
    
    return paths
