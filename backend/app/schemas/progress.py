"""
進捗イベント用スキーマ
"""
from pydantic import BaseModel
from typing import Dict, Any, Optional, List


class ProgressEvent(BaseModel):
    """SSE進捗イベント"""
    step: str           # ステップ識別子
    status: str         # "running", "completed", "error"
    message: str        # 表示用メッセージ
    detail: Dict[str, Any] = {}  # 追加情報


class AnalyzeStreamRequest(BaseModel):
    """研究計画解析ストリーミングリクエスト"""
    research_plan: str
    
    model_config = {"populate_by_name": True}


class ReviewStreamRequest(BaseModel):
    """レビューストリーミングリクエスト"""
    form_data: Dict[str, Any]
    research_plan: str
