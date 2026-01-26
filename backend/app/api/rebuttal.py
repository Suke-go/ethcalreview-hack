"""
Rebuttal（修正対応）APIエンドポイント
"""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime

from app.models.session import Session, StepStatus, RebuttalRound
from app.services.gemini_client import GeminiClient

router = APIRouter()

# セッション保存ディレクトリ（絶対パスに解決）
SESSIONS_DIR = Path(__file__).parent.parent.parent.resolve() / "sessions"


class CreateRebuttalRequest(BaseModel):
    """Rebuttal作成リクエスト"""
    feedback_text: str = Field(..., alias="feedbackText", description="委員会からの指摘事項テキスト")
    
    model_config = {"populate_by_name": True}


class RebuttalSuggestion(BaseModel):
    """AI修正提案"""
    field: str
    original_value: str = Field(alias="originalValue")
    suggested_value: str = Field(alias="suggestedValue")
    reason: str
    
    model_config = {"populate_by_name": True}


class RebuttalResponse(BaseModel):
    """Rebuttalレスポンス"""
    round_number: int = Field(alias="roundNumber")
    feedback_text: str = Field(alias="feedbackText")
    suggestions: List[RebuttalSuggestion]
    response_draft: str = Field(alias="responseDraft")
    status: StepStatus
    
    model_config = {"populate_by_name": True}


REBUTTAL_SYSTEM_INSTRUCTION = """あなたは倫理審査委員会への対応を支援するアシスタントです。
委員会からの指摘事項を分析し、適切な修正提案を行ってください。

出力は必ず以下のJSON形式で返してください：
{
  "suggestions": [
    {
      "field": "修正が必要なフィールド名",
      "original_value": "現在の記載内容（推測）",
      "suggested_value": "修正後の記載内容",
      "reason": "この修正が必要な理由"
    }
  ],
  "response_draft": "委員会への回答文案（丁寧な文面で）"
}
"""


@router.post("/{session_id}", response_model=RebuttalResponse)
async def create_rebuttal(
    session_id: str,
    request: CreateRebuttalRequest,
    x_api_key: str = Header(..., alias="X-API-Key")
):
    """新しいRebuttalラウンドを作成し、AI修正提案を生成"""
    try:
        session = Session.load(SESSIONS_DIR, session_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Rebuttalを有効化
    session.rebuttal.enabled = True
    session.status = "rebuttal"
    
    # 新しいラウンドを作成
    round_number = len(session.rebuttal.rounds) + 1
    rebuttal_round = RebuttalRound(
        round_number=round_number,
        feedback_text=request.feedback_text,
        status=StepStatus.RUNNING
    )
    session.rebuttal.rounds.append(rebuttal_round)
    session.save(SESSIONS_DIR)
    
    try:
        # Gemini APIで修正提案を生成
        client = GeminiClient(api_key=x_api_key)
        
        # 解析結果と指摘事項を含むプロンプト
        analyze_result = session.steps.analyze.result or {}
        
        prompt = f"""## 元の研究計画
{session.research_plan.raw_input}

## AI解析結果
{analyze_result}

## 委員会からの指摘事項
{request.feedback_text}

上記の指摘事項に対する修正提案を生成してください。"""

        # Chain of Thought保存
        session.add_chain_of_thought(
            step="rebuttal",
            prompt=prompt
        )
        session.save(SESSIONS_DIR)
        
        result = await client.generate_json(prompt, REBUTTAL_SYSTEM_INSTRUCTION)
        
        # Chain of Thought保存
        session.add_chain_of_thought(
            step="rebuttal",
            response=str(result)
        )
        
        # 結果を保存
        rebuttal_round.ai_suggestions = result
        rebuttal_round.status = StepStatus.COMPLETED
        session.rebuttal.rounds[-1] = rebuttal_round
        session.save(SESSIONS_DIR)
        
        suggestions = [
            RebuttalSuggestion(
                field=s.get("field", ""),
                originalValue=s.get("original_value", ""),
                suggestedValue=s.get("suggested_value", ""),
                reason=s.get("reason", "")
            )
            for s in result.get("suggestions", [])
        ]
        
        return RebuttalResponse(
            roundNumber=round_number,
            feedbackText=request.feedback_text,
            suggestions=suggestions,
            responseDraft=result.get("response_draft", ""),
            status=StepStatus.COMPLETED
        )
        
    except Exception as e:
        # エラー保存
        session.add_chain_of_thought(
            step="rebuttal",
            error=str(e)
        )
        rebuttal_round.status = StepStatus.ERROR
        session.rebuttal.rounds[-1] = rebuttal_round
        session.save(SESSIONS_DIR)
        
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/rounds", response_model=List[dict])
async def get_rebuttal_rounds(session_id: str):
    """Rebuttalラウンド一覧を取得"""
    try:
        session = Session.load(SESSIONS_DIR, session_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return [
        {
            "roundNumber": r.round_number,
            "feedbackText": r.feedback_text,
            "status": r.status,
            "createdAt": r.created_at,
            "hasSuggestions": r.ai_suggestions is not None
        }
        for r in session.rebuttal.rounds
    ]


class ApplyRebuttalRequest(BaseModel):
    """Rebuttal適用リクエスト"""
    user_response: str = Field(..., alias="userResponse", description="ユーザーが編集した回答")
    accepted_suggestions: List[int] = Field(default_factory=list, alias="acceptedSuggestions")
    
    model_config = {"populate_by_name": True}


@router.post("/{session_id}/rounds/{round_number}/apply")
async def apply_rebuttal(
    session_id: str,
    round_number: int,
    request: ApplyRebuttalRequest
):
    """Rebuttal修正を適用"""
    try:
        session = Session.load(SESSIONS_DIR, session_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # 該当ラウンドを検索
    target_round = None
    for i, r in enumerate(session.rebuttal.rounds):
        if r.round_number == round_number:
            target_round = r
            break
    
    if not target_round:
        raise HTTPException(status_code=404, detail="Rebuttal round not found")
    
    # ユーザー回答を保存
    target_round.user_response = request.user_response
    session.save(SESSIONS_DIR)
    
    return {
        "message": "Rebuttal applied",
        "roundNumber": round_number,
        "acceptedCount": len(request.accepted_suggestions)
    }
