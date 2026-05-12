"""
書類生成APIエンドポイント

オーケストレーターを使用して全書類を生成します。
"""
import time
from fastapi import APIRouter, HTTPException, Header, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from pathlib import Path
import uuid
import zipfile
import json

from app.services.orchestrator import orchestrate_document_generation, DocumentType
from app.services.llm_client import create_llm_client
from app.services.lab_defaults_manager import load_lab_defaults
from app.services.preset_manager import load_preset_bundle
from app.services.form_context_builder import build_generation_context
from app.services.context_text_enricher import enrich_generation_context_with_llm, flatten_context_for_llm_form_data
from app.services.generation_validator import error_issues, issue_payload, validate_generation_context
from app.models.session import Session, SessionStatus, StepStatus
from app.config import app_config, load_user_settings
from app.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()

# セッション保存ディレクトリ (ETHICS_DATA_DIR/sessions)
SESSIONS_DIR = app_config.sessions_dir


class GenerateRequest(BaseModel):
    """書類生成リクエスト"""
    form_data: Dict[str, Any]
    app_config: Optional[Dict[str, Any]] = None
    # 書類生成オプション（ケースバイケースで選択可能）
    include_questionnaire: bool = True     # アンケートを含めるか
    include_consent_forms: bool = True     # 同意書・同意撤回書を含めるか
    include_recruitment: bool = True       # 募集案内文を含めるか
    include_implementation_plan: bool = True  # 実施計画書を含めるか


class GenerateResponse(BaseModel):
    """書類生成レスポンス"""
    session_id: str
    status: str
    documents_generated: List[str]
    errors: List[str] = []
    download_url: str = ""  # ダウンロードURL


@router.post("", response_model=GenerateResponse)
async def generate_documents(
    request: GenerateRequest,
    background_tasks: BackgroundTasks,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_llm_provider: str = Header("gemini", alias="X-LLM-Provider")
):
    """
    書類一式を生成
    
    オーケストレーターが以下の書類を並列生成します：
    - 研究倫理審査申請書
    - 実施計画書
    - 同意書（テンプレートコピー）
    - 同意撤回書（テンプレートコピー）
    - 参加者説明書
    - 事前アンケート（オプション）
    - 事後アンケート（オプション）
    """
    # ========================================
    # セッション作成
    # ========================================
    session = Session()
    session.research_plan.raw_input = request.form_data.get('research_plan', '')
    session.title = request.form_data.get('research_title', request.form_data.get('title', '無題'))
    session.status = SessionStatus.IN_PROGRESS
    session.steps.generate.status = StepStatus.IN_PROGRESS
    
    # セッションディレクトリ確保
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    session.save(SESSIONS_DIR)
    
    session_id = session.session_id
    
    logger.info("=" * 60)
    logger.info(f"書類生成API 開始 (session: {session_id[:8]}...)")
    logger.info(f"  LLMプロバイダー: {x_llm_provider}")
    logger.info(f"  アンケート含む: {request.include_questionnaire}")
    start_time = time.time()
    
    output_dir = app_config.output_dir / session_id
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # APIキーを取得（ヘッダー > 環境変数）
    import os
    api_key = x_api_key
    
    if not api_key:
        if x_llm_provider.lower() == "openai":
            api_key = os.environ.get("OPENAI_API_KEY")
        else:  # gemini
            api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    
    # プロバイダー自動判定
    if not api_key:
        openai_key = os.environ.get("OPENAI_API_KEY")
        gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        
        if openai_key:
            api_key = openai_key
            x_llm_provider = "openai"
            logger.info("  OpenAI APIキーを自動検出")
        elif gemini_key:
            api_key = gemini_key
            x_llm_provider = "gemini"
            logger.info("  Gemini APIキーを自動検出")
    
    if not api_key:
        logger.error("APIキーが設定されていません")
        session.steps.generate.status = StepStatus.ERROR
        session.steps.generate.error = "APIキーが必要です"
        session.save(SESSIONS_DIR)
        raise HTTPException(
            status_code=400, 
            detail="APIキーが必要です。環境変数 OPENAI_API_KEY または GEMINI_API_KEY を設定してください。"
        )
    
    # LLMクライアント作成
    try:
        llm_client = create_llm_client(provider=x_llm_provider, api_key=api_key)
        logger.info(f"  LLMクライアント: {x_llm_provider} 初期化完了")
    except Exception as e:
        logger.error(f"LLMクライアント初期化失敗: {e}")
        session.steps.generate.status = StepStatus.ERROR
        session.steps.generate.error = str(e)
        session.save(SESSIONS_DIR)
        raise HTTPException(status_code=400, detail=f"LLMクライアント初期化エラー: {str(e)}")
    
    # lab_defaultsを読み込み
    try:
        lab_defaults_obj = load_lab_defaults()
        lab_defaults = json.loads(lab_defaults_obj.model_dump_json())
    except Exception as e:
        logger.warning(f"lab_defaults読み込み失敗: {e}, デフォルト値を使用")
        lab_defaults = {}

    try:
        settings = load_user_settings(app_config)
        preset_bundle = load_preset_bundle(app_config)
        merged_form_data = {**request.form_data}
        if request.app_config:
            merged_form_data["app_config"] = request.app_config
        generation_context = build_generation_context(
            form_data=merged_form_data,
            settings=settings,
            preset_bundle=preset_bundle,
        )
        generation_context = await enrich_generation_context_with_llm(generation_context, llm_client)
        session.steps.generate.preset_snapshot = generation_context.get("meta", {}).get("preset_snapshot", {})
        session.steps.generate.context_snapshot = generation_context
        session.save(SESSIONS_DIR)
    except Exception as e:
        logger.error(f"context build failed: {e}")
        session.steps.generate.status = StepStatus.ERROR
        session.steps.generate.error = f"context build failed: {e}"
        session.save(SESSIONS_DIR)
        raise HTTPException(status_code=500, detail=f"生成コンテキストの構築に失敗しました: {str(e)}")

    validation_issues = validate_generation_context(generation_context)
    validation_errors = error_issues(validation_issues)
    if validation_errors:
        session.steps.generate.status = StepStatus.ERROR
        session.steps.generate.error = "入力不足があります"
        session.save(SESSIONS_DIR)
        raise HTTPException(
            status_code=422,
            detail={
                "message": "入力不足があるため、提出用DOCXは生成しません。",
                "issues": issue_payload(validation_issues),
            },
        )

    orchestrator_form_data = {
        **flatten_context_for_llm_form_data(merged_form_data, generation_context),
        "_generation_context": generation_context,
    }
    
    # オーケストレーター実行（並列生成）
    try:
        result = await orchestrate_document_generation(
            form_data=orchestrator_form_data,
            output_dir=output_dir,
            templates_dir=app_config.templates_dir,
            llm_client=llm_client,
            lab_defaults=lab_defaults,
            include_questionnaire=request.include_questionnaire
        )
    except Exception as e:
        logger.error(f"オーケストレーションエラー: {e}")
        import traceback
        traceback.print_exc()
        session.steps.generate.status = StepStatus.ERROR
        session.steps.generate.error = str(e)
        session.save(SESSIONS_DIR)
        raise HTTPException(status_code=500, detail=f"書類生成エラー: {str(e)}")
    
    total_elapsed = time.time() - start_time
    logger.info("-" * 40)
    logger.info(f"書類生成API 完了 ({total_elapsed:.2f}秒)")
    logger.info(f"  生成: {len(result.generated_documents)}, エラー: {len(result.errors)}")
    logger.info("=" * 60)
    
    # ========================================
    # セッション更新・保存
    # ========================================
    session.steps.generate.status = StepStatus.DONE if result.success else StepStatus.ERROR
    session.steps.generate.output_dir = str(output_dir)
    session.steps.generate.generated_documents = result.generated_documents
    if result.errors:
        session.steps.generate.error = "; ".join(result.errors)
    session.status = SessionStatus.COMPLETED if result.success else SessionStatus.IN_PROGRESS
    session.save(SESSIONS_DIR)
    
    return GenerateResponse(
        session_id=session_id,
        status="completed" if result.success else "partial",
        documents_generated=result.generated_documents,
        errors=result.errors,
        download_url=f"/api/generate/download/{session_id}"
    )


@router.get("/download/{session_id}")
async def download_documents(session_id: str):
    """生成した書類一式をZIPでダウンロード"""
    output_dir = app_config.output_dir / session_id
    
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="Session not found")
    
    zip_path = output_dir / "ethics_documents.zip"
    
    # サンプルファイルのディレクトリ
    sample_dir = app_config.project_root / "sample"
    
    # ZIPファイル作成
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # 生成されたドキュメント
        for file in output_dir.iterdir():
            if file.suffix in ['.docx', '.xlsx', '.json']:
                zipf.write(file, file.name)
        
        # サンプル同意書・同意撤回書を追加
        sample_files = [
            "03_同意書(sample).docx",
            "04_同意撤回書(sample).docx",
        ]
        for sample_file in sample_files:
            sample_path = sample_dir / sample_file
            if sample_path.exists():
                zipf.write(sample_path, f"sample/{sample_file}")
    
    return FileResponse(
        path=zip_path,
        filename="ethics_documents.zip",
        media_type="application/zip"
    )


@router.post("/check-info")
async def check_required_info(
    form_data: Dict[str, Any]
):
    """
    必須情報の充足をチェック
    
    Returns:
        不足している情報のリスト
    """
    settings = load_user_settings(app_config)
    preset_bundle = load_preset_bundle(app_config)
    generation_context = build_generation_context(
        form_data=form_data,
        settings=settings,
        preset_bundle=preset_bundle,
    )
    issues = validate_generation_context(generation_context)
    errors = error_issues(issues)
    
    return {
        "complete": len(errors) == 0,
        "missing_fields": issue_payload(errors),
        "issues": issue_payload(issues),
    }


@router.post("/clarify")
async def get_clarifying_questions(
    form_data: Dict[str, Any],
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_llm_provider: str = Header("gemini", alias="X-LLM-Provider")
):
    """
    研究計画の曖昧な部分を分析し、明確化質問を生成
    
    選択肢形式の質問を返すので、ユーザーは選ぶだけで研究計画を精緻化できます。
    """
    import os
    from app.services.clarifying_question_generator import generate_clarifying_questions
    from app.services.llm_client import create_llm_client
    
    # APIキー取得（プロバイダーに応じて）
    api_key = x_api_key
    provider = x_llm_provider
    
    if not api_key:
        if provider.lower() == "openai":
            api_key = os.environ.get("OPENAI_API_KEY")
        else:
            api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    
    # 自動判定
    if not api_key:
        openai_key = os.environ.get("OPENAI_API_KEY")
        gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        
        if openai_key:
            api_key = openai_key
            provider = "openai"
        elif gemini_key:
            api_key = gemini_key
            provider = "gemini"
    
    if not api_key:
        raise HTTPException(status_code=400, detail="APIキーが必要です")
    
    llm_client = create_llm_client(provider=provider, api_key=api_key)
    
    result = await generate_clarifying_questions(form_data, llm_client)
    
    return {
        "has_ambiguity": result.has_ambiguity,
        "questions": [q.model_dump() for q in result.questions],
        "summary": result.analysis_summary
    }



@router.post("/apply-answers")
async def apply_clarifying_answers(
    form_data: Dict[str, Any],
    answers: Dict[str, Any]
):
    """
    明確化質問への回答を適用してフォームデータを更新
    """
    # 回答をフォームデータにマージ
    updated_data = form_data.copy()
    
    # フィールドマッピングに基づいて更新
    field_mapping = {
        "participant_age": "target_participants",
        "participant_count": "expected_participants",
        "data_anonymization": "anonymization_method",
        "video_recording": "video_recording",
    }
    
    for question_id, answer in answers.items():
        # フィールドに直接マッピング
        field = field_mapping.get(question_id, question_id)
        updated_data[field] = answer
    
    return {
        "form_data": updated_data,
        "applied_count": len(answers)
    }

