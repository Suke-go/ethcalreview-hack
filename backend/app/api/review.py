"""
マルチエージェントレビューAPIエンドポイント
"""
import time
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import List, Dict, Any
from app.services.gemini_client import GeminiClient
from app.services.multi_agent import MultiAgentReviewer
from app.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


class ReviewRequest(BaseModel):
    """レビューリクエスト"""
    form_data: Dict[str, Any]
    research_plan: str


class ReviewIssue(BaseModel):
    """レビュー指摘事項"""
    id: str
    category: str  # "risk", "consent", "privacy", "procedure", "ethics"
    severity: str  # "critical", "major", "minor"
    description: str
    suggestion: str
    field_id: str  # 該当するフォームフィールドID


class ReviewResponse(BaseModel):
    """レビューレスポンス"""
    status: str
    round: int  # 1 or 2
    issues: List[ReviewIssue]
    revised_data: Dict[str, Any]  # 修正後のデータ
    summary: str


@router.post("", response_model=ReviewResponse)
async def run_multi_agent_review(
    request: ReviewRequest,
    x_api_key: str = Header(..., alias="X-API-Key")
):
    """マルチエージェントレビューを実行（2回応酬）"""
    logger.info("=" * 60)
    logger.info("レビューAPI リクエスト受信")
    logger.info(f"  研究計画: {len(request.research_plan)} 文字")
    logger.info(f"  フォームデータ: {len(request.form_data)} フィールド")
    start_time = time.time()
    
    try:
        logger.info("Gemini クライアント作成中...")
        client = GeminiClient(api_key=x_api_key)
        reviewer = MultiAgentReviewer(client)
        
        result = await reviewer.run_full_review(
            form_data=request.form_data,
            research_plan=request.research_plan
        )
        
        elapsed = time.time() - start_time
        logger.info(f"レビューAPI 完了 ({elapsed:.2f}秒)")
        logger.info("=" * 60)
        return result
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"レビューAPI 失敗 ({elapsed:.2f}秒): {type(e).__name__}: {e}")
        logger.info("=" * 60)
        raise HTTPException(status_code=500, detail=str(e))

