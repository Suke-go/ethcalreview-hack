"""
検出・分析APIエンドポイント

アンケート検出、研究室デフォルト取得などの機能を提供
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List

from app.services.questionnaire_detector import (
    detect_questionnaire_requirements,
    QuestionnaireDetectionResult
)
from app.services.lab_defaults_manager import (
    load_lab_defaults,
    update_domain_head,
    LabDefaults,
    DomainHead
)
from app.services.llm_dependency import get_llm_client
from app.services.llm_client import LLMClient
from app.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


# ========================================
# リクエスト/レスポンスモデル
# ========================================

class DetectQuestionnaireRequest(BaseModel):
    """アンケート検出リクエスト"""
    implementation_plan: str


class DomainHeadUpdateRequest(BaseModel):
    """域長情報更新リクエスト"""
    title: str
    name: str


# ========================================
# アンケート検出エンドポイント
# ========================================

@router.post("/detect-questionnaire", response_model=QuestionnaireDetectionResult)
async def detect_questionnaire(
    request: DetectQuestionnaireRequest,
    llm_client: LLMClient = Depends(get_llm_client)
):
    """
    実施計画書からアンケート必要性をLLMで検出
    
    Args:
        request: 実施計画書を含むリクエスト
        llm_client: LLMクライアント (依存性注入)
    
    Returns:
        QuestionnaireDetectionResult
    """
    logger.info(f"[API] アンケート検出リクエスト受信 (計画書: {len(request.implementation_plan)} 文字)")
    
    if len(request.implementation_plan.strip()) < 50:
        raise HTTPException(
            status_code=400,
            detail="実施計画書が短すぎます (最低50文字必要)"
        )
    
    try:
        result = await detect_questionnaire_requirements(
            request.implementation_plan,
            llm_client
        )
        return result
    
    except Exception as e:
        logger.error(f"アンケート検出エラー: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"アンケート検出中にエラーが発生しました: {str(e)}"
        )


# ========================================
# 研究室デフォルト取得エンドポイント
# ========================================

@router.get("/lab-defaults", response_model=LabDefaults)
async def get_lab_defaults():
    """
    研究室のデフォルト設定を取得
    
    Returns:
        LabDefaults
    """
    logger.info("[API] 研究室デフォルト取得")
    
    try:
        defaults = load_lab_defaults()
        return defaults
    
    except Exception as e:
        logger.error(f"デフォルト取得エラー: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"デフォルト設定の取得に失敗しました: {str(e)}"
        )


# ========================================
# 域長情報更新エンドポイント
# ========================================

@router.put("/domain-head", response_model=DomainHead)
async def update_domain_head_endpoint(request: DomainHeadUpdateRequest):
    """
    域長情報を更新
    
    Args:
        request: 域長情報
    
    Returns:
        更新後のDomainHead
    """
    logger.info(f"[API] 域長情報更新: {request.title} - {request.name}")
    
    try:
        updated = update_domain_head(request.title, request.name)
        return updated
    
    except Exception as e:
        logger.error(f"域長情報更新エラー: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"域長情報の更新に失敗しました: {str(e)}"
        )
