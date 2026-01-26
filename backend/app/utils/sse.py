"""
SSEユーティリティ関数
"""
import json
from typing import Any, Dict


def sse_event(event_type: str, data: Dict[str, Any]) -> str:
    """
    SSE形式のイベント文字列を生成
    
    Args:
        event_type: イベントタイプ (例: "progress", "result", "error")
        data: 送信するデータ
    
    Returns:
        SSE形式の文字列
    """
    json_data = json.dumps(data, ensure_ascii=False)
    return f"event: {event_type}\ndata: {json_data}\n\n"


def sse_progress(step: str, status: str, message: str, detail: Dict[str, Any] = None) -> str:
    """
    進捗イベントを生成するヘルパー
    
    Args:
        step: ステップ識別子 (例: "analyze_start", "agent_b_review")
        status: ステータス ("running", "completed", "error")
        message: 表示用メッセージ
        detail: 追加情報
    
    Returns:
        SSE形式の進捗イベント文字列
    """
    data = {
        "step": step,
        "status": status,
        "message": message,
        "detail": detail or {}
    }
    return sse_event("progress", data)


def sse_result(result: Dict[str, Any]) -> str:
    """
    結果イベントを生成
    """
    return sse_event("result", result)


def sse_error(message: str, detail: Dict[str, Any] = None) -> str:
    """
    エラーイベントを生成
    """
    data = {
        "message": message,
        "detail": detail or {}
    }
    return sse_event("error", data)
