"""
統一ロガー設定
"""
import logging
import sys
from datetime import datetime

# ログフォーマット設定
LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    統一されたロガーを作成
    
    Args:
        name: ロガー名（通常はモジュール名）
        level: ログレベル
    
    Returns:
        設定済みのロガー
    """
    logger = logging.getLogger(name)
    
    # 既に設定済みの場合はそのまま返す
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    
    # コンソールハンドラー
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    
    logger.addHandler(console_handler)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    既存のロガーを取得、なければ作成
    """
    return setup_logger(name)


# 一般的なログメッセージテンプレート
class LogMessages:
    """ログメッセージのテンプレート"""
    
    # API エンドポイント
    REQUEST_RECEIVED = "Request received: {endpoint}"
    REQUEST_COMPLETED = "Request completed: {endpoint} ({duration:.2f}s)"
    REQUEST_FAILED = "Request failed: {endpoint} - {error}"
    
    # LLM クライアント
    LLM_CALL_START = "LLM API call started (provider: {provider}, prompt: {chars} chars)"
    LLM_CALL_SUCCESS = "LLM API call succeeded (response: {chars} chars, {duration:.2f}s)"
    LLM_CALL_FAILED = "LLM API call failed: {error}"
    LLM_RETRY = "Retrying LLM API call (attempt {attempt})"
    
    # ドキュメント生成
    DOC_GEN_START = "Document generation started: {doc_type}"
    DOC_GEN_SUCCESS = "Document generated: {doc_type} -> {path}"
    DOC_GEN_FAILED = "Document generation failed: {doc_type} - {error}"
    
    # マルチエージェント
    REVIEW_ROUND_START = "Review round {round} started"
    REVIEW_ROUND_END = "Review round {round} completed ({issues} issues found)"
    AGENT_ACTION = "Agent {agent}: {action}"
