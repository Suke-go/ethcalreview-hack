"""
研究計画解析APIエンドポイント
"""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field
from typing import Optional, List
from app.services.llm_client import create_llm_client
from app.services.plan_analyzer import PlanAnalyzer

router = APIRouter()


class AnalyzeRequest(BaseModel):
    """研究計画解析リクエスト"""
    research_plan: str = Field(..., alias="researchPlan")
    
    model_config = {"populate_by_name": True}
    

class AnalyzeResponse(BaseModel):
    """研究計画解析レスポンス"""
    research_title: str
    research_purpose: str
    research_method: str
    target_participants: str
    participant_count: int
    participant_count_reason: str
    age_range: str
    selection_criteria: str
    exclusion_criteria: str
    risks: List[str]
    risk_countermeasures: List[str]
    duration_minutes: int
    devices: List[str]
    clarification_needed: bool
    clarification_questions: List[str]


@router.post("", response_model=AnalyzeResponse)
async def analyze_research_plan(
    request: AnalyzeRequest,
    x_api_key: str = Header(..., alias="X-API-Key"),
    x_llm_provider: str = Header("openai", alias="X-LLM-Provider")
):
    """研究計画を解析してフィールドを自動抽出
    
    Headers:
        X-API-Key: LLMプロバイダーのAPIキー
        X-LLM-Provider: "openai" or "gemini" (default: openai)
    """
    print("=" * 50, flush=True)
    print(f"[ANALYZE] Request received (provider: {x_llm_provider})", flush=True)
    print(f"   Research plan: {len(request.research_plan)} chars", flush=True)
    print(f"   API Key: {x_api_key[:8]}...", flush=True)
    
    try:
        print(f"[ANALYZE] Creating {x_llm_provider.upper()} client...", flush=True)
        client = create_llm_client(provider=x_llm_provider, api_key=x_api_key)
        
        print("[ANALYZE] Starting PlanAnalyzer...", flush=True)
        analyzer = PlanAnalyzer(client)
        
        print("[ANALYZE] Sending to LLM API...", flush=True)
        result = await analyzer.analyze(request.research_plan)
        
        print("[ANALYZE] Success!", flush=True)
        print(f"   Title: {result.get('research_title', 'N/A')}", flush=True)
        print("=" * 50, flush=True)
        return result
    except Exception as e:
        print(f"[ANALYZE] ERROR: {type(e).__name__}: {str(e)}", flush=True)
        print("=" * 50, flush=True)
        raise HTTPException(status_code=500, detail=str(e))
