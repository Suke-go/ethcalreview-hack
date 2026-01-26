"""
アンケート検出サービス (LLMベース)

実施計画書を分析してアンケートの必要性を自動検出します。
"""

from typing import Dict, List, Optional
from pydantic import BaseModel
import json
from app.services.llm_client import LLMClient
from app.logger import get_logger

logger = get_logger(__name__)


class QuestionnaireDetectionResult(BaseModel):
    """アンケート検出結果"""
    pre_questionnaire_needed: bool
    pre_questionnaire_reason: str
    pre_questionnaire_items: List[str] = []
    post_questionnaire_needed: bool
    post_questionnaire_reason: str
    post_questionnaire_items: List[str] = []
    confidence: float


QUESTIONNAIRE_DETECTION_PROMPT = """
以下の実施計画書を分析し、アンケートの必要性を判定してください。

実施計画書:
{implementation_plan}

以下のJSON形式で回答してください:
{{
  "pre_questionnaire_needed": true/false,
  "pre_questionnaire_reason": "実験前アンケートが必要/不要な理由（日本語で簡潔に）",
  "pre_questionnaire_items": ["項目1", "項目2", ...],
  
  "post_questionnaire_needed": true/false,
  "post_questionnaire_reason": "実験後アンケートが必要/不要な理由（日本語で簡潔に）",
  "post_questionnaire_items": ["項目1", "項目2", ...],
  
  "confidence": 0.0-1.0
}}

判定基準:
- 実験前アンケート: 参加者属性（年齢、性別など）、事前知識、スクリーニング、基礎情報の収集が必要な場合
- 実験後アンケート: 主観評価、満足度、使用感、NASA-TLX、SUS、フィードバックなどの収集が必要な場合

注意:
- 実施計画書に明示的に記載されていない場合は不要と判定してください
- システムログのみの収集など、人による回答が不要な場合はアンケート不要です
- confidenceは検出の確実性を0.0-1.0で示してください
"""


async def detect_questionnaire_requirements(
    implementation_plan: str,
    llm_client: LLMClient
) -> QuestionnaireDetectionResult:
    """
    LLMを使用してアンケート必要性を検出
    
    Args:
        implementation_plan: 実施計画書のテキスト
        llm_client: LLMクライアント
    
    Returns:
        QuestionnaireDetectionResult
    """
    logger.info("=" * 60)
    logger.info("アンケート検出開始")
    logger.info(f"  計画書長: {len(implementation_plan)} 文字")
    
    try:
        prompt = QUESTIONNAIRE_DETECTION_PROMPT.format(
            implementation_plan=implementation_plan[:2000]  # 最大2000文字
        )
        
        # LLMに問い合わせ
        response = await llm_client.generate_json(
            prompt=prompt
        )
        
        # JSON解析
        result_data = json.loads(response) if isinstance(response, str) else response
        
        result = QuestionnaireDetectionResult(**result_data)
        
        logger.info("-" * 40)
        logger.info(f"検出結果:")
        logger.info(f"  実験前: {result.pre_questionnaire_needed}")
        if result.pre_questionnaire_needed:
            logger.info(f"    理由: {result.pre_questionnaire_reason}")
            logger.info(f"    項目: {', '.join(result.pre_questionnaire_items[:5])}")
        logger.info(f"  実験後: {result.post_questionnaire_needed}")
        if result.post_questionnaire_needed:
            logger.info(f"    理由: {result.post_questionnaire_reason}")
            logger.info(f"    項目: {', '.join(result.post_questionnaire_items[:5])}")
        logger.info(f"  信頼度: {result.confidence:.2f}")
        logger.info("=" * 60)
        
        return result
        
    except Exception as e:
        logger.error(f"アンケート検出エラー: {type(e).__name__}: {e}")
        # デフォルト値を返す
        return QuestionnaireDetectionResult(
            pre_questionnaire_needed=False,
            pre_questionnaire_reason="検出エラーのためデフォルト値",
            post_questionnaire_needed=False,
            post_questionnaire_reason="検出エラーのためデフォルト値",
            confidence=0.0
        )
