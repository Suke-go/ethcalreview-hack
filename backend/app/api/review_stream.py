"""
マルチエージェントレビュー SSEストリーミングエンドポイント
"""
from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator, Dict, Any

from app.services.gemini_client import GeminiClient
from app.services.llm_client import create_llm_client, LLMClient
from app.utils.sse import sse_progress, sse_result, sse_error
from app.schemas.progress import ReviewStreamRequest
from app.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


class StreamingMultiAgentReviewer:
    """SSEストリーミング対応のマルチエージェントレビュワー"""
    
    AGENT_A_INSTRUCTION = """あなたは倫理審査書類を作成するAIエージェントです。
以下の役割を持ちます：
- インフォームドコンセントの妥当性チェック
- リスクと対策の整合性確認
- 個人情報保護の適切性チェック
- 除外基準の明確さ確認
- 書類間の一貫性確保

Agent B（倫理審査委員シミュレート）からの指摘を受けて、書類を改善してください。
標準より厳しめの基準で書類を作成し、承認率を高めることが目標です。"""

    AGENT_B_INSTRUCTION = """あなたは筑波大学の倫理審査委員会の委員をシミュレートするAIエージェントです。
以下の視点で厳格に審査してください：
- 研究計画の妥当性（目的・方法・仮説の論理的整合性）
- 実験工程の安全性（危険な手順がないか）
- 対象者保護（不当なリスクを負わせていないか）
- 倫理的問題点（見落としがちな問題の指摘）

特に以下の厳格審査基準（SR1-SR6）を確認してください：
- SR1: リスク記述の網羅性
- SR2: 対策の具体性
- SR3: 緊急時対応
- SR4: 除外基準の妥当性
- SR5: 同意撤回手続き
- SR6: 参加者保護"""

    def __init__(self, client: LLMClient):
        self.client = client
    
    async def agent_b_review(self, form_data: Dict[str, Any], research_plan: str) -> Dict[str, Any]:
        """Agent B: 倫理審査委員としてレビュー"""
        prompt = f"""以下の倫理審査申請書を審査してください。

# 研究計画
{research_plan}

# 申請書データ
{form_data}

# 出力形式（JSON）
{{
    "issues": [
        {{
            "id": "issue_1",
            "category": "risk",
            "severity": "major",
            "description": "指摘内容",
            "suggestion": "改善提案"
        }}
    ],
    "summary": "総評"
}}

category: risk, consent, privacy, procedure, ethics のいずれか
severity: critical, major, minor のいずれか"""

        return await self.client.generate_json(prompt, self.AGENT_B_INSTRUCTION)
    
    async def agent_a_revise(self, form_data: Dict[str, Any], issues: list) -> Dict[str, Any]:
        """Agent A: 指摘を反映して修正"""
        prompt = f"""以下の指摘事項を反映して、申請書データを修正してください。

# 現在の申請書データ
{form_data}

# 指摘事項
{issues}

# 出力形式（JSON）
修正後の申請書データ全体をJSON形式で出力してください。
修正した箇所には "_revised": true を追加してください。"""

        return await self.client.generate_json(prompt, self.AGENT_A_INSTRUCTION)


@router.post("/stream")
async def run_multi_agent_review_stream(
    request: ReviewStreamRequest,
    x_api_key: str = Header(..., alias="X-API-Key"),
    x_llm_provider: str = Header("gemini", alias="X-LLM-Provider")
):
    """
    マルチエージェントレビューを実行（SSEストリーミング）
    
    イベント:
        - progress: 処理進捗（各ラウンド、各エージェントのアクション）
        - result: 最終結果
        - error: エラー発生時
    """
    
    async def event_generator() -> AsyncGenerator[str, None]:
        logger.info("=== SSE Review Stream Started ===")
        
        try:
            # Step 1: 初期化
            yield sse_progress(
                step="init",
                status="completed",
                message="レビューリクエストを受信しました",
                detail={
                    "form_fields": len(request.form_data),
                    "plan_chars": len(request.research_plan)
                }
            )
            
            # Step 2: クライアント作成
            yield sse_progress(
                step="init_client",
                status="running",
                message=f"{x_llm_provider.upper()} クライアントを初期化中..."
            )
            
            client = create_llm_client(provider=x_llm_provider, api_key=x_api_key)
            reviewer = StreamingMultiAgentReviewer(client)
            
            yield sse_progress(
                step="init_client",
                status="completed",
                message=f"{x_llm_provider.upper()} クライアント準備完了"
            )
            
            all_issues = []
            current_data = request.form_data
            
            # ===== Round 1 =====
            yield sse_progress(
                step="round_1",
                status="running",
                message="【ラウンド 1/2】開始"
            )
            
            # Agent B Review (Round 1)
            yield sse_progress(
                step="round_1_agent_b",
                status="running",
                message="Agent B (審査委員): レビュー中..."
            )
            
            round1_review = await reviewer.agent_b_review(current_data, request.research_plan)
            round1_issues = round1_review.get("issues", [])
            all_issues.extend(round1_issues)
            
            yield sse_progress(
                step="round_1_agent_b",
                status="completed",
                message=f"Agent B: {len(round1_issues)}件の指摘を検出",
                detail={
                    "issues_count": len(round1_issues),
                    "issues": [{"severity": i.get("severity"), "category": i.get("category")} for i in round1_issues[:3]]
                }
            )
            
            # Agent A Revise (Round 1)
            yield sse_progress(
                step="round_1_agent_a",
                status="running",
                message="Agent A (起案者): 修正中..."
            )
            
            revised_data = await reviewer.agent_a_revise(current_data, round1_issues)
            
            yield sse_progress(
                step="round_1_agent_a",
                status="completed",
                message="Agent A: 修正完了"
            )
            
            yield sse_progress(
                step="round_1",
                status="completed",
                message=f"【ラウンド 1/2】完了 (累計指摘: {len(all_issues)}件)"
            )
            
            # ===== Round 2 =====
            yield sse_progress(
                step="round_2",
                status="running",
                message="【ラウンド 2/2】開始"
            )
            
            # Agent B Review (Round 2)
            yield sse_progress(
                step="round_2_agent_b",
                status="running",
                message="Agent B (審査委員): 再レビュー中..."
            )
            
            round2_review = await reviewer.agent_b_review(revised_data, request.research_plan)
            round2_issues = round2_review.get("issues", [])
            all_issues.extend(round2_issues)
            
            yield sse_progress(
                step="round_2_agent_b",
                status="completed",
                message=f"Agent B: {len(round2_issues)}件の追加指摘",
                detail={
                    "issues_count": len(round2_issues),
                    "issues": [{"severity": i.get("severity"), "category": i.get("category")} for i in round2_issues[:3]]
                }
            )
            
            # Agent A Revise (Round 2)
            yield sse_progress(
                step="round_2_agent_a",
                status="running",
                message="Agent A (起案者): 最終修正中..."
            )
            
            final_data = await reviewer.agent_a_revise(revised_data, round2_issues)
            
            yield sse_progress(
                step="round_2_agent_a",
                status="completed",
                message="Agent A: 最終修正完了"
            )
            
            yield sse_progress(
                step="round_2",
                status="completed",
                message=f"【ラウンド 2/2】完了"
            )
            
            # 完了
            yield sse_progress(
                step="complete",
                status="completed",
                message=f"レビュー完了 (合計指摘: {len(all_issues)}件)",
                detail={"total_issues": len(all_issues)}
            )
            
            # 最終結果
            result = {
                "status": "completed",
                "round": 2,
                "issues": all_issues,
                "revised_data": final_data,
                "summary": round2_review.get("summary", "レビュー完了")
            }
            
            yield sse_result(result)
            
            logger.info("=== SSE Review Stream Completed ===")
            
        except ValueError as e:
            logger.error(f"SSE Review Error (ValueError): {e}")
            yield sse_error(str(e), {"type": "auth_error"})
        except Exception as e:
            logger.error(f"SSE Review Error: {type(e).__name__}: {e}")
            yield sse_error(f"{type(e).__name__}: {str(e)}")
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "X-Accel-Buffering": "no"
        }
    )
