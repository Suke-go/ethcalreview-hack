"""
研究計画解析サービス
"""
import time
from typing import Dict, Any, List
from app.services.llm_client import LLMClient
from app.logger import get_logger

logger = get_logger(__name__)


class PlanAnalyzer:
    """研究計画を解析してフォームフィールドを自動抽出"""
    
    SYSTEM_INSTRUCTION = """あなたは筑波大学の倫理審査書類作成を支援するAIアシスタントです。
研究計画から倫理審査申請書に必要な情報を抽出し、構造化されたデータとして出力してください。
情報が不足している場合は、研究内容から妥当な推測を行い、それでも不明な場合は明示的に質問を生成してください。
VR/HCI研究に特化した知識を持っており、この分野特有のリスク（VR酔い、視覚疲労等）を把握しています。"""

    def __init__(self, client: LLMClient):
        self.client = client
    
    async def analyze(self, research_plan: str) -> Dict[str, Any]:
        """研究計画を解析"""
        logger.info(f"研究計画解析 開始 (入力: {len(research_plan)} 文字)")
        start_time = time.time()
        
        prompt = f"""以下の研究計画を解析し、倫理審査申請書に必要な情報を抽出してください。

# 研究計画
{research_plan}

# 出力形式（JSON）
{{
    "research_title": "研究課題名",
    "research_purpose": "研究目的（2-3文で簡潔に）",
    "research_method": "研究方法の概要",
    "target_participants": "実験参加者の条件",
    "participant_count": 30,
    "participant_count_reason": "人数設定の統計的根拠",
    "age_range": "18〜65歳の成人",
    "selection_criteria": "選択基準",
    "exclusion_criteria": "除外基準（VRなら光過敏症等を含める）",
    "risks": ["リスク1", "リスク2"],
    "risk_countermeasures": ["対策1", "対策2"],
    "duration_minutes": 60,
    "devices": ["使用するデバイス"],
    "clarification_needed": false,
    "clarification_questions": []
}}

除外基準は厳格に設定し、研究方法から想定されるすべてのリスクを列挙してください。
VR研究の場合は必ず以下を含めてください：
- VR酔いを起こしやすい方
- 光過敏症の方
- 視覚・平衡感覚に異常のある方"""

        try:
            result = await self.client.generate_json(prompt, self.SYSTEM_INSTRUCTION)
            elapsed = time.time() - start_time
            logger.info(f"研究計画解析 完了 (所要時間: {elapsed:.2f}秒)")
            logger.info(f"  研究課題名: {result.get('research_title', 'N/A')}")
            logger.info(f"  抽出リスク数: {len(result.get('risks', []))}")
            logger.info(f"  要確認: {result.get('clarification_needed', False)}")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"研究計画解析 失敗 ({elapsed:.2f}秒): {type(e).__name__}: {e}")
            raise

