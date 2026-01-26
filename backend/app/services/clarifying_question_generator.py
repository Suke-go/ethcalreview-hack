"""
研究計画 明確化質問生成サービス

研究計画の曖昧な部分を特定し、選択肢形式の質問を生成します。
ユーザーとの対話を通じて研究計画を精緻化します。
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from enum import Enum

from app.services.llm_client import LLMClient
from app.logger import get_logger

logger = get_logger(__name__)


class QuestionType(str, Enum):
    """質問タイプ"""
    SINGLE_CHOICE = "single_choice"  # 単一選択
    MULTIPLE_CHOICE = "multiple_choice"  # 複数選択
    YES_NO = "yes_no"  # はい/いいえ
    SCALE = "scale"  # 段階評価
    TEXT = "text"  # 自由記述（最小限）


class ClarifyingQuestion(BaseModel):
    """明確化質問"""
    id: str
    field: str  # 関連するフィールド
    question: str
    question_type: QuestionType
    options: List[str] = []  # 選択肢
    default: Optional[str] = None
    reason: str  # 質問が必要な理由
    priority: int = 1  # 1=高, 2=中, 3=低


class ClarificationResult(BaseModel):
    """明確化結果"""
    has_ambiguity: bool
    questions: List[ClarifyingQuestion]
    analysis_summary: str


CLARIFICATION_PROMPT = """
あなたは研究倫理審査の専門家です。
以下の研究計画を分析し、曖昧または不足している情報を特定してください。

【研究計画】
タイトル: {research_title}
目的: {research_purpose}
方法: {research_method}
対象者: {target_participants}
所要時間: {duration}分
使用機器: {devices}
リスク: {risks}
リスク対策: {risk_countermeasures}

【分析の観点】
1. 対象者条件
   - 年齢範囲が明確か？
   - 除外基準が明確か？
   - 人数と根拠が明確か？

2. 研究方法
   - 実験手順が具体的か？
   - 測定項目が明確か？
   - 条件設定が適切か？

3. リスク
   - 想定されるリスクが網羅されているか？
   - 対策が具体的か？

4. データ管理
   - 匿名化方法が明確か？
   - 保存期間が適切か？

【出力形式】
曖昧な点について、以下の形式で質問を生成してください。
できる限り選択肢を提供し、ユーザーが選ぶだけで済むようにしてください。

各質問を以下のJSONライクな形式で出力：
---
QUESTION_START
field: [関連フィールド名]
type: [single_choice/multiple_choice/yes_no/scale]
question: [質問文]
options: [選択肢1, 選択肢2, ...]
reason: [質問が必要な理由]
priority: [1/2/3]
QUESTION_END
---

3-7個の質問を優先度順に生成してください。
曖昧な点がない場合は「NO_AMBIGUITY」と出力してください。
"""


class ClarifyingQuestionGenerator:
    """明確化質問生成器"""
    
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
    
    async def analyze_and_generate_questions(
        self,
        form_data: Dict[str, Any]
    ) -> ClarificationResult:
        """
        研究計画を分析し、明確化質問を生成
        """
        logger.info("=" * 60)
        logger.info("明確化質問生成 開始")
        
        # コンテキスト準備
        context = self._build_context(form_data)
        
        # LLMで分析
        prompt = CLARIFICATION_PROMPT.format(**context)
        
        try:
            response = await self.llm.generate_content_async(
                prompt=prompt,
                system_instruction=(
                    "あなたは研究倫理審査の専門家です。"
                    "研究計画の曖昧な点を特定し、選択肢形式の質問を生成してください。"
                    "ユーザーの負担を減らすため、できる限り選択肢を提供してください。"
                )
            )
            
            # レスポンスをパース
            questions = self._parse_questions(response)
            
            has_ambiguity = len(questions) > 0 and "NO_AMBIGUITY" not in response
            
            logger.info(f"明確化質問生成 完了: {len(questions)}件")
            logger.info("=" * 60)
            
            return ClarificationResult(
                has_ambiguity=has_ambiguity,
                questions=questions,
                analysis_summary=self._generate_summary(questions)
            )
            
        except Exception as e:
            logger.error(f"明確化質問生成エラー: {e}")
            return ClarificationResult(
                has_ambiguity=False,
                questions=[],
                analysis_summary="分析中にエラーが発生しました。"
            )
    
    def _build_context(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """コンテキストを構築"""
        devices = form_data.get("devices", [])
        risks = form_data.get("risks", [])
        countermeasures = form_data.get("riskCountermeasures", form_data.get("risk_countermeasures", []))
        
        return {
            "research_title": form_data.get("title", form_data.get("research_title", "")),
            "research_purpose": form_data.get("purpose", form_data.get("research_purpose", "")),
            "research_method": form_data.get("methodology", form_data.get("research_method", "")),
            "target_participants": form_data.get("targetDescription", form_data.get("target_participants", "")),
            "duration": form_data.get("duration", form_data.get("duration_minutes", 60)),
            "devices": ", ".join(devices) if isinstance(devices, list) else str(devices),
            "risks": ", ".join(risks) if isinstance(risks, list) else str(risks),
            "risk_countermeasures": ", ".join(countermeasures) if isinstance(countermeasures, list) else str(countermeasures),
        }
    
    def _parse_questions(self, response: str) -> List[ClarifyingQuestion]:
        """LLMレスポンスをパース"""
        questions = []
        
        # QUESTION_START ... QUESTION_END ブロックを抽出
        import re
        pattern = r"QUESTION_START\s*(.*?)\s*QUESTION_END"
        matches = re.findall(pattern, response, re.DOTALL)
        
        for i, match in enumerate(matches):
            try:
                q_data = self._parse_question_block(match)
                q_data["id"] = f"q_{i+1}"
                questions.append(ClarifyingQuestion(**q_data))
            except Exception as e:
                logger.warning(f"質問パースエラー: {e}")
                continue
        
        # 優先度でソート
        questions.sort(key=lambda q: q.priority)
        
        return questions
    
    def _parse_question_block(self, block: str) -> Dict[str, Any]:
        """質問ブロックをパース"""
        lines = block.strip().split("\n")
        data = {}
        
        for line in lines:
            line = line.strip()
            if ": " in line:
                key, value = line.split(": ", 1)
                key = key.strip().lower()
                value = value.strip()
                
                if key == "type":
                    # QuestionTypeにマッピング
                    type_map = {
                        "single_choice": QuestionType.SINGLE_CHOICE,
                        "multiple_choice": QuestionType.MULTIPLE_CHOICE,
                        "yes_no": QuestionType.YES_NO,
                        "scale": QuestionType.SCALE,
                        "text": QuestionType.TEXT,
                    }
                    data["question_type"] = type_map.get(value, QuestionType.SINGLE_CHOICE)
                elif key == "options":
                    # 選択肢をパース
                    options = value.strip("[]").split(", ")
                    data["options"] = [o.strip().strip("'\"") for o in options]
                elif key == "priority":
                    data["priority"] = int(value) if value.isdigit() else 2
                else:
                    data[key] = value
        
        return data
    
    def _generate_summary(self, questions: List[ClarifyingQuestion]) -> str:
        """サマリーを生成"""
        if not questions:
            return "研究計画は十分に明確です。"
        
        fields = set(q.field for q in questions)
        return f"以下の{len(fields)}つの領域で確認が必要です: {', '.join(fields)}"
    
    async def apply_answers(
        self,
        form_data: Dict[str, Any],
        answers: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        ユーザーの回答を適用してフォームデータを更新
        """
        updated_data = form_data.copy()
        
        for question_id, answer in answers.items():
            # 質問IDからフィールドを特定して更新
            # 実際の実装では質問のfield属性を使用
            pass
        
        return updated_data


# デフォルトの質問テンプレート
DEFAULT_CLARIFYING_QUESTIONS = {
    "participant_age": ClarifyingQuestion(
        id="default_age",
        field="target_participants",
        question="対象者の年齢範囲を選択してください",
        question_type=QuestionType.SINGLE_CHOICE,
        options=["18-25歳（大学生）", "18-65歳（成人）", "全年齢", "その他"],
        reason="倫理審査で年齢範囲の明示が必要です",
        priority=1
    ),
    "participant_count": ClarifyingQuestion(
        id="default_count",
        field="expected_participants",
        question="予定している参加者数を選択してください",
        question_type=QuestionType.SINGLE_CHOICE,
        options=["10名以下", "11-20名", "21-50名", "51名以上"],
        reason="サンプルサイズの根拠が必要です",
        priority=1
    ),
    "data_anonymization": ClarifyingQuestion(
        id="default_anon",
        field="data_management",
        question="データの匿名化方法を選択してください",
        question_type=QuestionType.SINGLE_CHOICE,
        options=["連結可能匿名化（対応表あり）", "連結不可能匿名化", "匿名化しない"],
        reason="個人情報保護の観点から明示が必要です",
        priority=2
    ),
    "video_recording": ClarifyingQuestion(
        id="default_video",
        field="video_recording",
        question="実験中の動画撮影は行いますか？",
        question_type=QuestionType.YES_NO,
        options=["はい", "いいえ"],
        reason="動画撮影には追加の同意書が必要です",
        priority=2
    ),
}


async def generate_clarifying_questions(
    form_data: Dict[str, Any],
    llm_client: LLMClient
) -> ClarificationResult:
    """
    明確化質問生成エントリーポイント
    """
    generator = ClarifyingQuestionGenerator(llm_client)
    return await generator.analyze_and_generate_questions(form_data)
