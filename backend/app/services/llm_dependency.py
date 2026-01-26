"""
LLMクライアント依存性注入

FastAPI Dependsで使用するためのLLMクライアント取得関数
"""

import json
from pathlib import Path
from app.services.llm_client import create_llm_client, LLMClient
from app.config import app_config


def get_llm_client() -> LLMClient:
    """
    LLMクライアントを取得（依存性注入用）
    
    settings.jsonからプロバイダーとAPI Keyを読み込み、
    適切なLLMClientインスタンスを返す
    
    Returns:
        LLMClient instance
    """
    settings_path = app_config.settings_file
    
    if not settings_path.exists():
        raise ValueError(f"Settings file not found: {settings_path}")
    
    with open(settings_path, "r", encoding="utf-8") as f:
        settings_data = json.load(f)
    
    # settings.jsonから直接読み込み
    provider = settings_data.get('llm_provider', 'gemini')
    
    if provider == 'gemini':
        api_key = settings_data.get('gemini_api_key', '')
    else:
        api_key = settings_data.get('openai_api_key', '')
    
    if not api_key:
        raise ValueError(f"API key not found for provider: {provider}")
    
    return create_llm_client(provider=provider, api_key=api_key)
