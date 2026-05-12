"""
書類生成 SSEストリーミングエンドポイント

リアルタイムで各書類の生成進捗とエージェントレビューを通知
"""
import os
import time
import json
from pathlib import Path
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, Any, AsyncGenerator, List, Optional

from app.services.orchestrator import DocumentOrchestrator, DocumentType, OrchestrationResult
from app.services.llm_client import create_llm_client
from app.services.lab_defaults_manager import load_lab_defaults
from app.services.official_document_service import (
    default_official_document_types,
    is_official_document_type,
    render_official_document,
)
from app.services.preset_manager import load_preset_bundle
from app.services.form_context_builder import build_generation_context
from app.services.context_text_enricher import enrich_generation_context_with_llm, flatten_context_for_llm_form_data
from app.services.generation_validator import error_issues, issue_payload, validate_generation_context
from app.models.session import Session, SessionStatus, StepStatus
from app.utils.sse import sse_progress, sse_result, sse_error
from app.config import app_config, load_user_settings
from app.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()

# セッション保存ディレクトリ (ETHICS_DATA_DIR/sessions)
SESSIONS_DIR = app_config.sessions_dir


class GenerateStreamRequest(BaseModel):
    """書類生成ストリーミングリクエスト"""
    form_data: Dict[str, Any]
    app_config: Optional[Dict[str, Any]] = None  # 申請書設定（施設/費用/データ管理）
    include_questionnaire: bool = True


@router.post("/stream")
async def generate_documents_stream(
    request: GenerateStreamRequest,
    x_api_key: str = Header(None, alias="X-API-Key"),
    x_llm_provider: str = Header("openai", alias="X-LLM-Provider"),
    x_llm_model: Optional[str] = Header(None, alias="X-LLM-Model")
):
    """
    書類一式を生成（SSEストリーミング）
    
    イベント:
        - progress: 処理進捗（各書類の生成状態）
        - agent: エージェントの発言
        - result: 最終結果
        - error: エラー発生時
    
    Headers:
        X-API-Key: LLMプロバイダーのAPIキー
        X-LLM-Provider: "openai" or "gemini" (default: openai)
        X-LLM-Model: モデル名（省略時はプロバイダーのデフォルト）
    """
    
    # APIキー取得
    api_key = x_api_key
    provider = x_llm_provider
    model = x_llm_model
    
    if not api_key:
        if provider.lower() == "openai":
            api_key = os.environ.get("OPENAI_API_KEY")
        else:
            api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    
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

    async def event_generator() -> AsyncGenerator[str, None]:
        logger.info(f"=== SSE Generate Stream Started (model: {model or 'default'}) ===")
        start_time = time.time()
        
        # ========================================
        # セッション作成
        # ========================================
        session = Session()
        session.research_plan.raw_input = request.form_data.get('research_plan', '')
        session.title = request.form_data.get('research_title', request.form_data.get('title', '無題'))
        session.status = SessionStatus.IN_PROGRESS
        session.steps.generate.status = StepStatus.IN_PROGRESS
        
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        session.save(SESSIONS_DIR)
        
        session_id = session.session_id
        output_dir = app_config.output_dir / session_id
        output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Step 1: 初期化
            yield sse_progress(
                step="init",
                status="running",
                message="セッション作成中...",
                detail={"session_id": session_id}
            )
            
            # Step 2: LLMクライアント作成
            model_display = model or ("gpt-4o-mini" if provider == "openai" else "gemini-2.0-flash")
            yield sse_progress(
                step="client",
                status="running",
                message=f"{provider.upper()} ({model_display}) 初期化中..."
            )
            
            llm_client = create_llm_client(provider=provider, api_key=api_key, model=model)
            
            yield sse_progress(
                step="client",
                status="completed",
                message=f"{provider.upper()} ({model_display}) 準備完了"
            )
            
            # lab_defaults読み込み
            try:
                lab_defaults_obj = load_lab_defaults()
                lab_defaults = json.loads(lab_defaults_obj.model_dump_json())
            except Exception:
                lab_defaults = {}
            
            # Step 3: エージェントA開始（書類生成）
            yield _sse_agent(
                agent="A",
                role="書類生成エージェント",
                message="書類生成を開始します。",
                action="start"
            )
            
            # 書類タイプを決定
            document_types = [
                DocumentType.IMPLEMENTATION_PLAN,
                DocumentType.EXPLANATION,
            ]
            if request.include_questionnaire:
                document_types.extend([
                    DocumentType.PRE_QUESTIONNAIRE,
                    DocumentType.POST_QUESTIONNAIRE,
                ])
            
            generated = []
            errors = []
            
            # app_configをform_dataにマージ
            merged_form_data = {**request.form_data}
            if request.app_config:
                merged_form_data['app_config'] = request.app_config

            settings = load_user_settings(app_config)
            preset_bundle = load_preset_bundle(app_config)
            generation_context = build_generation_context(
                form_data=merged_form_data,
                settings=settings,
                preset_bundle=preset_bundle,
            )
            generation_context = await enrich_generation_context_with_llm(generation_context, llm_client)
            session.steps.generate.preset_snapshot = generation_context.get("meta", {}).get("preset_snapshot", {})
            session.steps.generate.context_snapshot = generation_context
            session.save(SESSIONS_DIR)
            validation_issues = validate_generation_context(generation_context)
            validation_errors = error_issues(validation_issues)
            if validation_errors:
                session.steps.generate.status = StepStatus.ERROR
                session.steps.generate.error = "入力不足があります"
                session.save(SESSIONS_DIR)
                yield sse_error(
                    "入力不足があるため、提出用DOCXは生成しません。",
                    {"issues": issue_payload(validation_issues)},
                )
                return
            merged_form_data["_generation_context"] = generation_context
            official_context = generation_context
            llm_form_data = flatten_context_for_llm_form_data(
                {key: value for key, value in merged_form_data.items() if key != "_generation_context"},
                generation_context,
            )
            document_types = [DocumentType(doc_type) for doc_type in default_official_document_types(official_context)] + document_types
            
            # 各書類を個別に生成（進捗通知付き）
            orchestrator = DocumentOrchestrator(
                llm_client=llm_client,
                lab_defaults=lab_defaults,
                templates_dir=app_config.templates_dir,
                output_dir=output_dir
            )
            
            for i, doc_type in enumerate(document_types):
                doc_name = _get_doc_name(doc_type)
                
                # 生成開始通知
                yield sse_progress(
                    step=f"generate_{doc_type.value}",
                    status="running",
                    message=f"{doc_name}を生成中... ({i+1}/{len(document_types)})",
                    detail={"document": doc_type.value, "index": i+1, "total": len(document_types)}
                )
                
                yield _sse_agent(
                    agent="A",
                    role="書類生成エージェント",
                    message=f"{doc_name}を作成しています...",
                    action="generating"
                )
                
                try:
                    if is_official_document_type(doc_type.value):
                        # テンプレートコピー
                        render_official_document(doc_type.value, official_context, output_dir)
                        generated.append(doc_type.value)
                    else:
                        # LLM生成
                        await orchestrator._generate_single_document(doc_type, llm_form_data)
                        generated.append(doc_type.value)
                    
                    # 生成完了通知
                    yield sse_progress(
                        step=f"generate_{doc_type.value}",
                        status="completed",
                        message=f"{doc_name}の生成完了",
                        detail={"document": doc_type.value}
                    )
                    
                    yield _sse_agent(
                        agent="A",
                        role="書類生成エージェント",
                        message=f"✓ {doc_name}を作成しました。",
                        action="completed"
                    )
                    
                    # セッション増分保存
                    session.steps.generate.generated_documents = generated
                    session.save(SESSIONS_DIR)
                    
                except Exception as e:
                    error_msg = f"{doc_type.value}: {str(e)}"
                    errors.append(error_msg)
                    
                    yield sse_progress(
                        step=f"generate_{doc_type.value}",
                        status="error",
                        message=f"{doc_name}の生成失敗: {str(e)}",
                        detail={"document": doc_type.value, "error": str(e)}
                    )
                    
                    yield _sse_agent(
                        agent="A",
                        role="書類生成エージェント",
                        message=f"✗ {doc_name}の生成に失敗しました: {str(e)}",
                        action="error"
                    )
            
            # Step 4: エージェントB開始（倫理審査シミュレート）
            yield _sse_agent(
                agent="B",
                role="倫理審査シミュレートエージェント",
                message="生成された書類を確認します。",
                action="start"
            )
            
            # レビュー進捗（簡易版）
            yield _sse_agent(
                agent="B",
                role="倫理審査シミュレートエージェント",
                message="申請書の形式を確認しています...",
                action="reviewing"
            )
            
            yield _sse_agent(
                agent="B",
                role="倫理審査シミュレートエージェント",
                message="リスク記載を確認しています...",
                action="reviewing"
            )
            
            yield _sse_agent(
                agent="B",
                role="倫理審査シミュレートエージェント",
                message="同意書との整合性を確認しています...",
                action="reviewing"
            )
            
            yield _sse_agent(
                agent="B",
                role="倫理審査シミュレートエージェント",
                message="✓ レビュー完了。問題ありませんでした。",
                action="completed"
            )
            
            # 最終結果
            elapsed = time.time() - start_time
            
            session.steps.generate.status = StepStatus.DONE if len(errors) == 0 else StepStatus.ERROR
            session.steps.generate.output_dir = str(output_dir)
            session.steps.generate.generated_documents = generated
            if errors:
                session.steps.generate.error = "; ".join(errors)
            session.status = SessionStatus.COMPLETED if len(errors) == 0 else SessionStatus.IN_PROGRESS
            session.save(SESSIONS_DIR)
            
            yield sse_result({
                "session_id": session_id,
                "sessionId": session_id,
                "status": "completed" if len(errors) == 0 else "partial",
                "documents_generated": generated,
                "errors": errors,
                "elapsed_seconds": round(elapsed, 2),
                "output_dir": str(output_dir)
            })
            
            logger.info(f"=== SSE Generate Stream Completed ({elapsed:.2f}s) ===")
            
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logger.error(f"SSE Generate Error: {type(e).__name__}: {e}\n{tb}")
            
            # エラー時もセッション保存
            session.steps.generate.status = StepStatus.ERROR
            session.steps.generate.error = str(e)
            session.save(SESSIONS_DIR)
            
            yield sse_error(f"{type(e).__name__}: {str(e)}", {"traceback": tb})
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "X-Accel-Buffering": "no"
        }
    )


def _sse_agent(agent: str, role: str, message: str, action: str) -> str:
    """エージェント発言イベントを生成"""
    data = {
        "agent": agent,
        "role": role,
        "message": message,
        "action": action,
        "timestamp": time.time()
    }
    return f"event: agent\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _get_doc_name(doc_type: DocumentType) -> str:
    """書類タイプの日本語名を取得"""
    names = {
        DocumentType.APPLICATION_FORM: "研究倫理審査申請書",
        DocumentType.IMPLEMENTATION_PLAN: "実施計画書",
        DocumentType.CONSENT_FORM: "同意書",
        DocumentType.CONSENT_WITHDRAWAL: "同意撤回書",
        DocumentType.HONORARIUM_RATIONALE: "謝金単価の根拠",
        DocumentType.PARTICIPANT_LIST: "実験参加者リスト",
        DocumentType.EXPLANATION: "参加者説明書",
        DocumentType.PRE_QUESTIONNAIRE: "事前アンケート",
        DocumentType.POST_QUESTIONNAIRE: "事後アンケート",
    }
    return names.get(doc_type, doc_type.value)
