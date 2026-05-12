"""
セッション管理APIエンドポイント
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from pathlib import Path
from datetime import datetime
import traceback

from app.config import app_config
from app.models.session import Session, SessionStatus, StepStatus

router = APIRouter()

# セッション保存ディレクトリは ETHICS_DATA_DIR/sessions に統一
# (PyInstaller / Tauri バンドルでも永続化される)
SESSIONS_DIR = app_config.sessions_dir
print(f"[Session API] SESSIONS_DIR: {SESSIONS_DIR}")


class CreateSessionRequest(BaseModel):
    """セッション作成リクエスト"""
    research_plan: str = Field(..., alias="researchPlan")
    
    model_config = {"populate_by_name": True}


class SessionSummary(BaseModel):
    """セッション概要（一覧表示用）"""
    session_id: str = Field(alias="sessionId")
    title: Optional[str] = None
    status: SessionStatus
    current_step: str = Field(alias="currentStep")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    
    model_config = {"populate_by_name": True}


class SessionResponse(BaseModel):
    """セッション詳細レスポンス"""
    session_id: str = Field(alias="sessionId")
    title: Optional[str] = None
    status: SessionStatus
    current_step: str = Field(alias="currentStep")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    research_plan: dict = Field(alias="researchPlan")
    steps: dict
    rebuttal: dict
    
    model_config = {"populate_by_name": True}


@router.post("", response_model=SessionResponse)
async def create_session(request: CreateSessionRequest):
    """新規セッションを作成"""
    session = Session()
    session.research_plan.raw_input = request.research_plan
    session.save(SESSIONS_DIR)
    
    return SessionResponse(
        sessionId=session.session_id,
        title=session.title,
        status=session.status,
        currentStep=session.get_current_step(),
        createdAt=session.created_at,
        updatedAt=session.updated_at,
        researchPlan=session.research_plan.model_dump(mode="json"),
        steps=session.steps.model_dump(mode="json"),
        rebuttal=session.rebuttal.model_dump(mode="json"),
    )


@router.get("", response_model=List[SessionSummary])
async def list_sessions(
    status: Optional[SessionStatus] = Query(None, description="フィルタするステータス")
):
    """セッション一覧を取得"""
    try:
        print(f"[list_sessions] SESSIONS_DIR: {SESSIONS_DIR}", flush=True)
        sessions = Session.list_all(SESSIONS_DIR)
        print(f"[list_sessions] Found {len(sessions)} sessions", flush=True)
        
        if status:
            sessions = [s for s in sessions if s.status == status]
        
        return [
            SessionSummary(
                sessionId=s.session_id,
                title=s.title,
                status=s.status,
                currentStep=s.get_current_step(),
                createdAt=s.created_at,
                updatedAt=s.updated_at,
            )
            for s in sessions
        ]
    except Exception as e:
        print(f"[list_sessions] ERROR: {type(e).__name__}: {e}", flush=True)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)}")


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """セッション詳細を取得"""
    try:
        session = Session.load(SESSIONS_DIR, session_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return SessionResponse(
        sessionId=session.session_id,
        title=session.title,
        status=session.status,
        currentStep=session.get_current_step(),
        createdAt=session.created_at,
        updatedAt=session.updated_at,
        researchPlan=session.research_plan.model_dump(mode="json"),
        steps=session.steps.model_dump(mode="json"),
        rebuttal=session.rebuttal.model_dump(mode="json"),
    )


class UpdateSessionRequest(BaseModel):
    """セッション更新リクエスト"""
    title: Optional[str] = None
    status: Optional[SessionStatus] = None
    user_edits: Optional[dict] = Field(None, alias="userEdits")
    
    model_config = {"populate_by_name": True}


@router.put("/{session_id}", response_model=SessionResponse)
async def update_session(session_id: str, request: UpdateSessionRequest):
    """セッションを更新"""
    try:
        session = Session.load(SESSIONS_DIR, session_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if request.title is not None:
        session.title = request.title
    
    if request.status is not None:
        session.status = request.status
    
    if request.user_edits is not None:
        session.steps.confirm.user_edits.update(request.user_edits)
    
    session.save(SESSIONS_DIR)
    
    return SessionResponse(
        sessionId=session.session_id,
        title=session.title,
        status=session.status,
        currentStep=session.get_current_step(),
        createdAt=session.created_at,
        updatedAt=session.updated_at,
        researchPlan=session.research_plan.model_dump(mode="json"),
        steps=session.steps.model_dump(mode="json"),
        rebuttal=session.rebuttal.model_dump(mode="json"),
    )


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """セッションを削除"""
    file_path = SESSIONS_DIR / f"{session_id}.json"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Session not found")
    
    file_path.unlink()
    return {"message": "Session deleted", "sessionId": session_id}


@router.post("/{session_id}/resume")
async def resume_session(session_id: str):
    """セッションを中断位置から再開"""
    try:
        session = Session.load(SESSIONS_DIR, session_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    
    current_step = session.get_current_step()
    
    # エラー状態のステップをリセット
    if session.steps.analyze.status == StepStatus.ERROR:
        session.steps.analyze.status = StepStatus.PENDING
        session.steps.analyze.error = None
    
    if session.steps.generate.status == StepStatus.ERROR:
        session.steps.generate.status = StepStatus.PENDING
    
    if session.steps.review.status == StepStatus.ERROR:
        session.steps.review.status = StepStatus.PENDING
    
    session.save(SESSIONS_DIR)
    
    return {
        "message": "Session resumed",
        "sessionId": session_id,
        "currentStep": current_step,
        "chainOfThoughtCount": len(session.steps.analyze.chain_of_thought)
    }
