"""
研究計画解析 SSEストリーミングエンドポイント
"""
from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator, Optional

from app.services.llm_client import create_llm_client
from app.services.plan_analyzer import PlanAnalyzer
from app.utils.sse import sse_progress, sse_result, sse_error
from app.schemas.progress import AnalyzeStreamRequest
from app.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post("/stream")
async def analyze_research_plan_stream(
    request: AnalyzeStreamRequest,
    x_api_key: str = Header(None, alias="X-API-Key"),
    x_llm_provider: str = Header("openai", alias="X-LLM-Provider"),
    x_llm_model: Optional[str] = Header(None, alias="X-LLM-Model")
):
    """
    研究計画を解析してフィールドを自動抽出（SSEストリーミング）
    
    イベント:
        - progress: 処理進捗
        - result: 最終結果
        - error: エラー発生時
    
    Headers:
        X-API-Key: LLMプロバイダーのAPIキー
        X-LLM-Provider: "openai" or "gemini" (default: openai)
        X-LLM-Model: モデル名（省略時はプロバイダーのデフォルト）
    """
    import os
    
    # APIキー取得（ヘッダー > 環境変数）
    api_key = x_api_key
    provider = x_llm_provider
    model = x_llm_model
    
    if not api_key:
        if provider.lower() == "openai":
            api_key = os.environ.get("OPENAI_API_KEY")
        else:
            api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    
    # 自動判定
    if not api_key:
        openai_key = os.environ.get("OPENAI_API_KEY")
        gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        
        if openai_key:
            api_key = openai_key
            provider = "openai"
        elif gemini_key:
            api_key = gemini_key
            provider = "gemini"
    
    if not api_key:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="APIキーが必要です")
    
    async def event_generator() -> AsyncGenerator[str, None]:
        logger.info(f"=== SSE Analyze Stream Started (model: {model or 'default'}) ===")
        
        try:
            # Step 1: Request received
            yield sse_progress(
                step="receive",
                status="completed",
                message=f"Research plan received ({len(request.research_plan)} chars)",
                detail={"chars": len(request.research_plan)}
            )
            
            # Step 2: LLM client creation
            model_display = model or ("gpt-4o-mini" if provider == "openai" else "gemini-2.0-flash")
            yield sse_progress(
                step="init_client",
                status="running",
                message=f"{provider.upper()} ({model_display}) 初期化中..."
            )
            
            client = create_llm_client(provider=provider, api_key=api_key, model=model)
            
            yield sse_progress(
                step="init_client",
                status="completed",
                message=f"{provider.upper()} ({model_display}) 準備完了"
            )
            
            # Step 3: AI解析開始
            yield sse_progress(
                step="analyze",
                status="running",
                message="AI解析中... (10-30秒程度かかります)"
            )
            
            analyzer = PlanAnalyzer(client)
            result = await analyzer.analyze(request.research_plan)
            
            # Step 4: 解析完了
            yield sse_progress(
                step="analyze",
                status="completed",
                message=f"解析完了: {result.get('research_title', '(タイトル未取得)')}",
                detail={
                    "title": result.get("research_title", ""),
                    "risks_count": len(result.get("risks", [])),
                    "clarification_needed": result.get("clarification_needed", False)
                }
            )
            
            # 最終結果を送信
            yield sse_result(result)
            
            logger.info("=== SSE Analyze Stream Completed ===")
            
        except ValueError as e:
            # 認証エラーなど
            logger.error(f"SSE Analyze Error (ValueError): {e}")
            yield sse_error(str(e), {"type": "auth_error"})
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logger.error(f"SSE Analyze Error: {type(e).__name__}: {e}\n{tb}")
            yield sse_error(f"{type(e).__name__}: {str(e)}", {"traceback": tb})
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "X-Accel-Buffering": "no"  # Nginx向け
        }
    )
