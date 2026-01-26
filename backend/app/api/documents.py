"""
ドキュメント生成 統合APIエンドポイント

募集案内文、実施計画書などを生成するエンドポイント
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional
from pathlib import Path
import uuid
import shutil

from app.services.recruitment_notice_generator import generate_recruitment_notice
from app.services.implementation_plan_generator import generate_implementation_plan_docx
from app.services.text_post_processor import post_process_academic_text
from app.services.lab_defaults_manager import load_lab_defaults
from app.config import app_config
from app.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


class GenerateDocumentRequest(BaseModel):
    """ドキュメント生成リクエスト"""
    document_type: str  # "recruitment_notice" | "implementation_plan"
    form_data: Dict[str, Any]
    apply_post_processing: bool = True


def cleanup_temp_dir(dir_path: Path):
    """一時ディレクトリを削除"""
    try:
        if dir_path.exists():
            shutil.rmtree(dir_path)
            logger.info(f"一時ディレクトリを削除: {dir_path}")
    except Exception as e:
        logger.warning(f"一時ディレクトリ削除エラー: {e}")


@router.post("/document")
async def generate_document(
    request: GenerateDocumentRequest,
    background_tasks: BackgroundTasks
):
    """
    指定されたドキュメントを生成してダウンロード
    
    Args:
        request: ドキュメント種類とフォームデータ
        background_tasks: バックグラウンドタスク（クリーンアップ用）
    
    Returns:
        FileResponse: 生成されたdocx
    """
    logger.info("=" * 60)
    logger.info(f"ドキュメント生成開始: {request.document_type}")
    
    try:
        # 一時出力ディレクトリ
        session_id = str(uuid.uuid4())
        output_dir = app_config.output_dir / session_id
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 研究室デフォルト読み込み
        lab_defaults = load_lab_defaults().model_dump()
        
        # 後処理適用
        form_data = request.form_data
        if request.apply_post_processing:
            form_data = apply_post_processing_to_form(form_data)
        
        # ドキュメント生成
        if request.document_type == "recruitment_notice":
            output_path = generate_recruitment_notice(
                form_data=form_data,
                output_dir=output_dir,
                lab_defaults=lab_defaults
            )
            filename = "募集案内文.docx"
            
        elif request.document_type == "implementation_plan":
            output_path = generate_implementation_plan_docx(
                form_data=form_data,
                output_dir=output_dir,
                lab_defaults=lab_defaults
            )
            filename = "実施計画書.docx"
            
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown document type: {request.document_type}"
            )
        
        logger.info(f"ドキュメント生成完了: {output_path}")
        logger.info("=" * 60)
        
        # ダウンロード後に一時ディレクトリを削除
        background_tasks.add_task(cleanup_temp_dir, output_dir)
        
        return FileResponse(
            path=output_path,
            filename=filename,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    
    except Exception as e:
        logger.error(f"ドキュメント生成エラー: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"ドキュメントの生成に失敗しました: {str(e)}"
        )


def apply_post_processing_to_form(form_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    フォームデータ内のテキストフィールドに後処理を適用
    """
    text_fields = [
        'background',
        'purpose',
        'experiment_objective',
        'participant_info',
        'equipment_description',
        'mental_load',
        'physical_load',
        'safety_measures',
        'research_overview',
        'cautions',
    ]
    
    processed = form_data.copy()
    
    for field in text_fields:
        if field in processed and isinstance(processed[field], str):
            processed[field] = post_process_academic_text(processed[field])
    
    return processed
