"""
マルチエージェントレビューサービス
"""
import time
from typing import Dict, Any, List
from app.services.gemini_client import GeminiClient
from app.logger import get_logger

logger = get_logger(__name__)


class MultiAgentReviewer:
    """Agent A（書類生成）とAgent B（倫理審査委員）の2回応酬を制御"""
    
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
- SR1: リスク記述の網羅性（「無」選択時も想定外リスクの記述があるか）
- SR2: 対策の具体性（回避策が具体的なステップで記述されているか）
- SR3: 緊急時対応（緊急停止手順、連絡先、対応フローの明記）
- SR4: 除外基準の妥当性（妊婦、持病等の除外が適切か）
- SR5: 同意撤回手続き（同意撤回時のデータ削除手順が明確か）
- SR6: 参加者保護（不利益を被らない旨が明記されているか）"""

    def __init__(self, client: GeminiClient):
        self.client = client
    
    async def _agent_b_review(
        self, 
        form_data: Dict[str, Any], 
        research_plan: str
    ) -> Dict[str, Any]:
        """Agent B: 倫理審査委員としてレビュー"""
        logger.info("Agent B (審査委員): レビュー開始")
        start_time = time.time()
        
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
            "suggestion": "改善提案",
            "field_id": "4.1"
        }}
    ],
    "summary": "総評"
}}

category: risk, consent, privacy, procedure, ethics のいずれか
severity: critical, major, minor のいずれか"""

        result = await self.client.generate_json(prompt, self.AGENT_B_INSTRUCTION)
        elapsed = time.time() - start_time
        issues = result.get("issues", [])
        logger.info(f"Agent B (審査委員): レビュー完了 ({elapsed:.2f}秒)")
        logger.info(f"  指摘件数: {len(issues)}")
        for issue in issues[:3]:  # 最初の3件のみログ出力
            logger.info(f"  - [{issue.get('severity', 'N/A')}] {issue.get('category', 'N/A')}: {issue.get('description', '')[:50]}...")
        return result
    
    async def _agent_a_revise(
        self,
        form_data: Dict[str, Any],
        issues: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Agent A: 指摘を反映して修正"""
        logger.info(f"Agent A (起案者): 修正開始 (指摘: {len(issues)}件)")
        start_time = time.time()
        
        prompt = f"""以下の指摘事項を反映して、申請書データを修正してください。

# 現在の申請書データ
{form_data}

# 指摘事項
{issues}

# 出力形式（JSON）
修正後の申請書データ全体をJSON形式で出力してください。
修正した箇所には "_revised": true を追加してください。"""

        result = await self.client.generate_json(prompt, self.AGENT_A_INSTRUCTION)
        elapsed = time.time() - start_time
        logger.info(f"Agent A (起案者): 修正完了 ({elapsed:.2f}秒)")
        return result
    
    async def run_full_review(
        self,
        form_data: Dict[str, Any],
        research_plan: str
    ) -> Dict[str, Any]:
        """2回応酬の完全レビューを実行"""
        logger.info("=" * 60)
        logger.info("マルチエージェントレビュー 開始 (2ラウンド)")
        total_start = time.time()
        all_issues = []
        
        # Round 1
        logger.info("-" * 40)
        logger.info("[ラウンド 1/2] 開始")
        round1_review = await self._agent_b_review(form_data, research_plan)
        all_issues.extend(round1_review.get("issues", []))
        revised_data = await self._agent_a_revise(form_data, round1_review.get("issues", []))
        logger.info(f"[ラウンド 1/2] 完了 (累計指摘: {len(all_issues)}件)")
        
        # Round 2
        logger.info("-" * 40)
        logger.info("[ラウンド 2/2] 開始")
        round2_review = await self._agent_b_review(revised_data, research_plan)
        all_issues.extend(round2_review.get("issues", []))
        final_data = await self._agent_a_revise(revised_data, round2_review.get("issues", []))
        logger.info(f"[ラウンド 2/2] 完了 (累計指摘: {len(all_issues)}件)")
        
        total_elapsed = time.time() - total_start
        logger.info("-" * 40)
        logger.info(f"マルチエージェントレビュー 完了 (合計: {total_elapsed:.2f}秒, 指摘: {len(all_issues)}件)")
        logger.info("=" * 60)
        
        return {
            "status": "completed",
            "round": 2,
            "issues": all_issues,
            "revised_data": final_data,
            "summary": round2_review.get("summary", "レビュー完了")
        }
