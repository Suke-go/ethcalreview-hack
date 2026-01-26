"""
設定APIエンドポイント
"""
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.config import UserSettings, app_config, load_user_settings, save_user_settings

router = APIRouter()

# .envファイルのパス
ENV_FILE_PATH = Path(__file__).parent.parent.parent.resolve() / ".env"


class EnvStatus(BaseModel):
    """環境変数の状態"""
    openai_key_set: bool
    gemini_key_set: bool
    default_provider: str
    env_file_exists: bool


class EnvUpdateRequest(BaseModel):
    """環境変数更新リクエスト"""
    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    default_provider: Optional[str] = None


@router.get("", response_model=UserSettings)
async def get_settings():
    """デフォルト設定を取得"""
    return load_user_settings(app_config)


@router.put("", response_model=UserSettings)
async def update_settings(settings: UserSettings):
    """デフォルト設定を更新"""
    save_user_settings(settings, app_config)
    return settings


@router.get("/env-status", response_model=EnvStatus)
async def get_env_status():
    """
    環境変数の設定状態を取得
    
    APIキーがマスクされた状態で設定状況を返します。
    """
    return EnvStatus(
        openai_key_set=bool(os.environ.get("OPENAI_API_KEY")),
        gemini_key_set=bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")),
        default_provider=os.environ.get("DEFAULT_LLM_PROVIDER", "openai"),
        env_file_exists=ENV_FILE_PATH.exists()
    )


@router.post("/env")
async def update_env(request: EnvUpdateRequest):
    """
    環境変数を更新（.envファイルに保存 + メモリにも即時反映）
    
    変更は即座に反映されます（サーバー再起動不要）。
    """
    # 既存の.envを読み込み
    env_content = {}
    if ENV_FILE_PATH.exists():
        with open(ENV_FILE_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_content[key.strip()] = value.strip()
    
    updated_keys = []
    
    # 更新（ファイル + メモリ両方）
    if request.openai_api_key is not None:
        env_content["OPENAI_API_KEY"] = request.openai_api_key
        os.environ["OPENAI_API_KEY"] = request.openai_api_key
        updated_keys.append("OPENAI_API_KEY")
    if request.gemini_api_key is not None:
        env_content["GEMINI_API_KEY"] = request.gemini_api_key
        os.environ["GEMINI_API_KEY"] = request.gemini_api_key
        updated_keys.append("GEMINI_API_KEY")
    if request.default_provider is not None:
        env_content["DEFAULT_LLM_PROVIDER"] = request.default_provider
        os.environ["DEFAULT_LLM_PROVIDER"] = request.default_provider
        updated_keys.append("DEFAULT_LLM_PROVIDER")
    
    # 書き込み
    with open(ENV_FILE_PATH, "w", encoding="utf-8") as f:
        f.write("# EthicalReviewHacker 環境変数設定\n")
        f.write("# 自動生成されたファイル\n\n")
        for key, value in env_content.items():
            f.write(f"{key}={value}\n")
    
    return {
        "message": "環境変数を更新しました。変更は即座に反映されました。",
        "env_file": str(ENV_FILE_PATH),
        "updated_keys": updated_keys
    }



@router.get("/reward-calculation")
async def calculate_reward(duration_minutes: int):
    """謝金を計算（大学規定による）"""
    settings = load_user_settings(app_config)
    hourly_rate = settings.budget.hourly_rate
    
    # 基準額 = 時給 × (所要時間 / 60)
    base_amount = hourly_rate * (duration_minutes / 60)
    
    # 100円単位で切り上げ
    import math
    recommended_amount = math.ceil(base_amount / 100) * 100
    
    return {
        "duration_minutes": duration_minutes,
        "hourly_rate": hourly_rate,
        "base_amount": base_amount,
        "recommended_amount": recommended_amount,
        "basis": "大学規定による"
    }
