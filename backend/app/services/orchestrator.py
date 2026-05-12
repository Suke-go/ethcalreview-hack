"""
書類生成オーケストレーター

全ての書類生成を統括し、情報の充足判定・質問生成・書類生成を行います。
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
from enum import Enum
from pydantic import BaseModel
import shutil

from app.services.llm_client import LLMClient
from app.services.llm_document_generator import generate_implementation_plan_with_llm
from app.services.application_form_generator import generate_application_form
from app.services.explanation_generator import generate_explanation_document
from app.services.questionnaire_generator import generate_questionnaire
from app.services.device_description_generator import generate_device_description
from app.services.official_document_service import (
    default_official_document_types,
    is_official_document_type,
    render_official_document,
)
from app.logger import get_logger

logger = get_logger(__name__)


class DocumentType(str, Enum):
    """書類タイプ"""
    APPLICATION_FORM = "application_form"  # 申請書
    IMPLEMENTATION_PLAN = "implementation_plan"  # 実施計画書
    CONSENT_FORM = "consent_form"  # 同意書（既存DOCXコピー）
    CONSENT_WITHDRAWAL = "consent_withdrawal"  # 同意撤回書（既存DOCXコピー）
    HONORARIUM_RATIONALE = "honorarium_rationale"  # 謝金単価の根拠
    PARTICIPANT_LIST = "participant_list"  # 実験参加者リスト
    EXPLANATION = "explanation"  # 参加者説明書
    PRE_QUESTIONNAIRE = "pre_questionnaire"  # 事前アンケート
    POST_QUESTIONNAIRE = "post_questionnaire"  # 事後アンケート
    RECRUITMENT = "recruitment"  # 募集シート
    DEVICE_DESCRIPTION = "device_description"  # 新規開発デバイス説明書


class MissingInfo(BaseModel):
    """不足情報"""
    field: str
    question: str
    required: bool = True


class OrchestrationResult(BaseModel):
    """オーケストレーション結果"""
    success: bool
    generated_documents: List[str]
    errors: List[str]
    output_dir: str


# 必須フィールドと質問のマッピング
REQUIRED_FIELDS = {
    "research_title": "研究タイトルを入力してください。",
    "research_purpose": "研究目的を説明してください。",
    "research_method": "研究方法（実験手順）を説明してください。",
    "target_participants": "対象となる参加者の条件を説明してください。",
    "duration": "実験の所要時間（分）を教えてください。",
    "risks": "想定されるリスク（身体的・精神的）を教えてください。",
}

OPTIONAL_FIELDS = {
    "devices": "使用する機器・装置はありますか？",
    "risk_countermeasures": "リスクへの対策を教えてください。",
    "exclusion_criteria": "除外基準はありますか？",
    "reward_amount": "謝礼金額を教えてください。",
}


class DocumentOrchestrator:
    """書類生成オーケストレーター"""
    
    def __init__(
        self,
        llm_client: LLMClient,
        lab_defaults: Dict[str, Any],
        templates_dir: Path,
        output_dir: Path
    ):
        self.llm = llm_client
        self.defaults = lab_defaults
        self.templates_dir = templates_dir
        self.output_dir = output_dir
    
    def check_required_info(self, form_data: Dict[str, Any]) -> List[MissingInfo]:
        """
        必須情報の充足をチェック
        
        Returns:
            不足している情報のリスト
        """
        missing = []
        
        # フィールド名の正規化（camelCase と snake_case の両方をチェック）
        normalized_data = self._normalize_field_names(form_data)
        
        for field, question in REQUIRED_FIELDS.items():
            value = normalized_data.get(field, "")
            if not value or (isinstance(value, list) and len(value) == 0):
                missing.append(MissingInfo(
                    field=field,
                    question=question,
                    required=True
                ))
        
        return missing
    
    def _normalize_field_names(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """フィールド名を正規化"""
        # camelCase → snake_case マッピング
        mapping = {
            "title": "research_title",
            "purpose": "research_purpose",
            "methodology": "research_method",
            "targetDescription": "target_participants",
            "duration": "duration",
            "durationMinutes": "duration",
            "risks": "risks",
            "riskCountermeasures": "risk_countermeasures",
            "rewardAmount": "reward_amount",
            "devices": "devices",
        }
        
        normalized = {}
        for key, value in form_data.items():
            # 元のキーをそのまま保持
            normalized[key] = value
            # マッピングがあれば追加
            if key in mapping:
                normalized[mapping[key]] = value
        
        return normalized
    
    def _detect_new_device(self, form_data: Dict[str, Any]) -> bool:
        """
        新規開発デバイスの使用を検出
        
        民生品（スマホ、市販HMDなど）は新規開発とみなさない。
        自作・開発デバイスの場合のみTrueを返す。
        """
        # 明示的なフラグ
        if form_data.get("has_new_device") in [True, "有", "true", "True"]:
            return True
        if form_data.get("has_new_device") in [False, "無", "false", "False"]:
            return False
        
        # 民生品・市販品のキーワード（これらは新規開発デバイスとみなさない）
        commercial_device_keywords = [
            # HMD
            "quest", "oculus", "vive", "pico", "hololens", "varjo", "pimax",
            "meta quest", "htc vive", "valve index", "playstation vr", "psvr",
            # スマートフォン・タブレット
            "iphone", "android", "スマホ", "スマートフォン", "タブレット", "ipad",
            # ウェアラブル
            "apple watch", "fitbit", "garmin",
            # オーディオ
            "ヘッドホン", "イヤホン", "スピーカー", "airpods",
            # 入力デバイス
            "マウス", "キーボード", "コントローラー", "ゲームパッド",
            # ディスプレイ
            "モニター", "ディスプレイ", "プロジェクター",
            # センサー（市販品）
            "kinect", "leap motion", "tobii", "アイトラッカー",
            # PC
            "パソコン", "pc", "ノートpc", "ラップトップ",
        ]
        
        # 新規開発を示すキーワード
        custom_device_keywords = [
            "自作", "試作", "開発", "プロトタイプ", "prototype",
            "新規開発", "独自開発", "オリジナル", "改造", "カスタム",
            "ジャミング", "触覚", "ハプティクス", "haptic",
            "アクチュエータ", "actuator", "振動子",
            "arduino", "raspberry", "ラズパイ", "マイコン",
            "3dプリント", "レーザーカット",
        ]
        
        devices = form_data.get("devices", [])
        methodology = form_data.get("methodology", form_data.get("research_method", "")).lower()
        
        # デバイスリストがない場合
        if not devices or len(devices) == 0:
            # 研究方法に新規開発キーワードがあるかチェック
            for keyword in custom_device_keywords:
                if keyword in methodology:
                    return True
            return False
        
        # 各デバイスをチェック
        has_custom_device = False
        for device in devices:
            device_lower = device.lower()
            
            # 民生品かどうか
            is_commercial = any(kw in device_lower for kw in commercial_device_keywords)
            
            # 新規開発かどうか
            is_custom = any(kw in device_lower for kw in custom_device_keywords)
            
            if is_custom:
                has_custom_device = True
            elif not is_commercial:
                # 民生品でも新規開発でもない = 不明なので確認が必要
                # 研究方法を見て判断
                for keyword in custom_device_keywords:
                    if keyword in methodology:
                        has_custom_device = True
                        break
        
        return has_custom_device
    
    async def generate_all_documents(
        self,
        form_data: Dict[str, Any],
        document_types: Optional[List[DocumentType]] = None,
        include_questionnaire: bool = True,
        progress_callback: Optional[callable] = None
    ) -> OrchestrationResult:
        """
        全書類を並列生成
        
        Args:
            form_data: フォームデータ
            document_types: 生成する書類タイプのリスト（Noneの場合は全て）
            include_questionnaire: アンケートを含めるか
            progress_callback: 進捗コールバック関数
        
        Returns:
            OrchestrationResult
        """
        import asyncio
        import json
        from datetime import datetime
        
        logger.info("=" * 60)
        logger.info("オーケストレーター起動: 書類一式【並列】生成開始")
        
        # 出力ディレクトリ作成
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 進捗ファイル
        progress_file = self.output_dir / "_generation_progress.json"
        
        def save_progress(status: str, generated: List[str], errors: List[str], current: str = ""):
            progress_data = {
                "status": status,
                "timestamp": datetime.now().isoformat(),
                "current_document": current,
                "generated_documents": generated,
                "errors": errors,
                "total_planned": len(document_types) if document_types else 0
            }
            with open(progress_file, "w", encoding="utf-8") as f:
                json.dump(progress_data, f, ensure_ascii=False, indent=2)
            
            if progress_callback:
                progress_callback(progress_data)

        official_context = form_data.get("_generation_context", form_data)
        llm_form_data = {key: value for key, value in form_data.items() if key != "_generation_context"}
        
        # デフォルトの書類タイプ
        if document_types is None:
            document_types = [
                DocumentType.IMPLEMENTATION_PLAN,
                DocumentType.EXPLANATION,
                *(DocumentType(doc_type) for doc_type in default_official_document_types(official_context)),
            ]
            if include_questionnaire:
                document_types.extend([
                    DocumentType.PRE_QUESTIONNAIRE,
                    DocumentType.POST_QUESTIONNAIRE,
                ])
            
            # 新規開発デバイスがある場合はデバイス説明書を追加
            has_new_device = self._detect_new_device(llm_form_data)
            if has_new_device:
                document_types.append(DocumentType.DEVICE_DESCRIPTION)
                logger.info("  新規開発デバイスを検出: デバイス説明書を生成対象に追加")
        
        generated = []
        errors = []
        
        save_progress("started", generated, errors)
        
        # ========================================
        # LLM依存の書類（並列実行）
        # ========================================
        llm_tasks = []
        llm_doc_types = []
        
        for doc_type in document_types:
            if doc_type in [
                DocumentType.IMPLEMENTATION_PLAN,
                DocumentType.EXPLANATION,
                DocumentType.PRE_QUESTIONNAIRE,
                DocumentType.POST_QUESTIONNAIRE,
                DocumentType.DEVICE_DESCRIPTION,
            ]:
                task = self._generate_single_document(doc_type, llm_form_data)
                llm_tasks.append(task)
                llm_doc_types.append(doc_type)
        
        if llm_tasks:
            logger.info(f"  LLM並列生成開始: {len(llm_tasks)}件")
            save_progress("parallel_generating", generated, errors, "LLM並列処理中")
            
            # 並列実行
            results = await asyncio.gather(*llm_tasks, return_exceptions=True)
            
            for doc_type, result in zip(llm_doc_types, results):
                if isinstance(result, Exception):
                    error_msg = f"{doc_type.value}: {type(result).__name__}: {result}"
                    errors.append(error_msg)
                    logger.error(f"    ✗ {error_msg}")
                else:
                    generated.append(doc_type.value)
                    logger.info(f"    ✓ {doc_type.value} 完了")
        
        # ========================================
        # テンプレートコピー（同期処理）
        # ========================================
        for doc_type in document_types:
            if is_official_document_type(doc_type.value):
                render_official_document(doc_type.value, official_context, self.output_dir)
                generated.append(doc_type.value)
                logger.info(f"    ✓ {doc_type.value} 公式テンプレート生成完了")
        
        logger.info("-" * 40)
        logger.info(f"生成完了: {len(generated)}/{len(document_types)}")
        logger.info("=" * 60)
        
        final_status = "completed" if len(errors) == 0 else "partial"
        save_progress(final_status, generated, errors)
        
        return OrchestrationResult(
            success=len(errors) == 0,
            generated_documents=generated,
            errors=errors,
            output_dir=str(self.output_dir)
        )
    
    async def _generate_single_document(
        self,
        doc_type: DocumentType,
        form_data: Dict[str, Any]
    ) -> Path:
        """単一書類を生成（並列実行用）"""
        logger.info(f"  生成開始: {doc_type.value}")
        
        if doc_type == DocumentType.APPLICATION_FORM:
            path, _ = await generate_application_form(
                form_data, self.output_dir, self.llm, self.defaults
            )
            return path
            
        elif doc_type == DocumentType.IMPLEMENTATION_PLAN:
            path = await generate_implementation_plan_with_llm(
                form_data, self.output_dir, self.llm, self.defaults
            )
            return path
            
        elif doc_type == DocumentType.EXPLANATION:
            path = await generate_explanation_document(
                form_data, self.output_dir, self.llm, self.defaults
            )
            return path
            
        elif doc_type == DocumentType.PRE_QUESTIONNAIRE:
            paths = await generate_questionnaire(
                form_data, self.output_dir, self.llm, self.defaults,
                questionnaire_type="pre"
            )
            return paths
            
        elif doc_type == DocumentType.POST_QUESTIONNAIRE:
            paths = await generate_questionnaire(
                form_data, self.output_dir, self.llm, self.defaults,
                questionnaire_type="post"
            )
            return paths
        
        elif doc_type == DocumentType.DEVICE_DESCRIPTION:
            path = await generate_device_description(
                form_data, self.output_dir, self.llm, self.defaults
            )
            return path
        
        raise ValueError(f"Unknown document type: {doc_type}")
    
    def _copy_template(self, template_name: str, output_name: str):
        """テンプレートをコピー"""
        src = self.templates_dir / template_name
        dst = self.output_dir / output_name
        
        if src.exists():
            shutil.copy(src, dst)
        else:
            logger.warning(f"テンプレートが見つかりません: {template_name}")
            # 空のDOCXを作成
            from docx import Document
            doc = Document()
            doc.add_paragraph(f"[このファイルはテンプレートから生成されます: {template_name}]")
            doc.save(dst)


async def orchestrate_document_generation(
    form_data: Dict[str, Any],
    output_dir: Path,
    templates_dir: Path,
    llm_client: LLMClient,
    lab_defaults: Dict[str, Any],
    include_questionnaire: bool = True
) -> OrchestrationResult:
    """
    書類生成オーケストレーション エントリーポイント
    """
    orchestrator = DocumentOrchestrator(
        llm_client=llm_client,
        lab_defaults=lab_defaults,
        templates_dir=templates_dir,
        output_dir=output_dir
    )
    
    return await orchestrator.generate_all_documents(
        form_data=form_data,
        include_questionnaire=include_questionnaire
    )
