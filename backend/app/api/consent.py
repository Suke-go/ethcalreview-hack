"""
同意書生成APIエンドポイント
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, Any
from pathlib import Path
import uuid

from app.services.consent_form_generator import generate_consent_form_with_plan
from app.services.lab_defaults_manager import load_lab_defaults
from app.config import app_config
from app.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


class GenerateConsentFormRequest(BaseModel):
    """同意書生成リクエスト"""
    form_data: Dict[str, Any]


@router.post("/consent-form")
async def generate_consent_form(request: GenerateConsentFormRequest):
    """
    研究計画概要を含む同意書を生成してダウンロード
    
    Args:
        request: フォームデータ
    
    Returns:
        FileResponse: 生成された同意書docx
    """
    logger.info("=" * 60)
    logger.info("同意書生成開始")
    
    try:
        # 一時出力ディレクトリ
        session_id = str(uuid.uuid4())
        output_dir = app_config.output_dir / session_id
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 研究室デフォルト読み込み
        lab_defaults = load_lab_defaults().model_dump()
        
        # 同意書生成
        consent_path = generate_consent_form_with_plan(
            form_data=request.form_data,
            output_dir=output_dir,
            lab_defaults=lab_defaults
        )
        
        logger.info(f"同意書生成完了: {consent_path}")
        logger.info("=" * 60)
        
        return FileResponse(
            path=consent_path,
            filename="同意書.docx",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    
    except Exception as e:
        logger.error(f"同意書生成エラー: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"同意書の生成に失敗しました: {str(e)}"
        )
