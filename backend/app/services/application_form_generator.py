"""
研究倫理審査申請書 生成サービス

申請書の各項目をLLMで生成し、JSONスキーマに沿ったデータを出力します。
最終的にDOCX形式で出力します。
"""

from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel
import json

from app.services.llm_client import LLMClient
from app.logger import get_logger

logger = get_logger(__name__)


# ========================================
# Pydanticスキーマ定義
# ========================================

class Applicant(BaseModel):
    """申請者情報"""
    affiliation: str = "システム情報系"
    position: str = ""
    name: str = ""


class Collaborator(BaseModel):
    """実施分担者"""
    affiliation: str
    position: str
    name: str


class DomainHead(BaseModel):
    """関係組織の長"""
    domain: str = ""
    name: str = ""


class Facility(BaseModel):
    """実施施設"""
    type: str = "single"  # single, multi_tsukuba, multi_other
    names: List[str] = []


class Funding(BaseModel):
    """費用の出所"""
    source: str = ""
    pi: str = ""
    project_title: str = ""


class Reward(BaseModel):
    """謝金"""
    has_reward: bool = True
    amount: int = 0
    unit: str = "1/回"


class Insurance(BaseModel):
    """保険"""
    has_insurance: bool = True
    type: str = "国立大学法人総合損害保険"


class Consent(BaseModel):
    """同意書"""
    age_group: str = "18歳以上"
    can_confirm_will: bool = True


class EthicsConsiderations(BaseModel):
    """倫理的配慮"""
    voluntary_participation: bool = True
    withdrawal_possible: bool = True
    withdrawal_deadline_specified: bool = True
    insurance: Insurance = Insurance()
    consent: Consent = Consent()
    video_recording: bool = False
    invasiveness: bool = False


class Anonymization(BaseModel):
    """匿名化"""
    enabled: bool = True
    has_correspondence_table: bool = True


class DataStorage(BaseModel):
    """データ管理"""
    location: str = ""
    manager: str = ""
    method: str = ""
    disposal: str = ""


class DataManagement(BaseModel):
    """研究データ等の保存"""
    data_types: List[str] = []
    retention_period: str = "発表後10年間"
    anonymization: Anonymization = Anonymization()
    storage: DataStorage = DataStorage()


class DataDisclosure(BaseModel):
    """データ開示"""
    to_subject: bool = True
    to_proxy: bool = False


class Publication(BaseModel):
    """研究成果の公開"""
    will_publish: bool = True
    identifiable_data_disclosed: bool = False


class Attachments(BaseModel):
    """添付書類"""
    conflict_of_interest_form: bool = True
    implementation_plan: bool = True
    explanation_document: bool = True
    consent_form: bool = True
    consent_withdrawal_form: bool = True
    video_consent_form: bool = False
    other: str = ""


class Contact(BaseModel):
    """問い合わせ先"""
    affiliation: str = ""
    position: str = ""
    name: str = ""
    extension: str = ""
    email: str = ""


class ApplicationType(BaseModel):
    """申請種別"""
    is_new: bool = True
    previous_approval_number: Optional[str] = None


class SimilarApplication(BaseModel):
    """類似申請"""
    exists: bool = False
    details: Optional[str] = None


class ApplicationForm(BaseModel):
    """研究倫理審査申請書 全体スキーマ"""
    application_date: str = ""
    applicant: Applicant = Applicant()
    research_title: str = ""
    category: str = "人情報"  # 社会調査/医工研究/自作デバイス/人情報/他機関で承認済み
    application_type: ApplicationType = ApplicationType()
    similar_application: SimilarApplication = SimilarApplication()
    collaborators: List[Collaborator] = []
    domain_head: DomainHead = DomainHead()
    facility: Facility = Facility()
    epidemiology_genome: bool = False
    funding: Funding = Funding()
    reward: Reward = Reward()
    conflict_of_interest: bool = False
    research_period_start: str = "倫理委員会承認後"
    research_period_end: str = ""
    ethics_considerations: EthicsConsiderations = EthicsConsiderations()
    data_management: DataManagement = DataManagement()
    data_disclosure: DataDisclosure = DataDisclosure()
    publication: Publication = Publication()
    attachments: Attachments = Attachments()
    contact: Contact = Contact()


# ========================================
# 申請書生成クラス
# ========================================

class ApplicationFormGenerator:
    """研究倫理審査申請書 生成器"""
    
    def __init__(self, llm_client: LLMClient, lab_defaults: Dict[str, Any]):
        self.llm = llm_client
        self.defaults = lab_defaults
    
    async def generate(
        self,
        form_data: Dict[str, Any],
        output_dir: Path
    ) -> tuple[Path, ApplicationForm]:
        """
        申請書を生成
        
        Returns:
            tuple[Path, ApplicationForm]: (DOCXファイルパス, 生成されたデータ)
        """
        logger.info("=" * 60)
        logger.info("申請書生成 開始")
        
        # フォームデータから申請書データを構築
        app_form = await self._build_application_form(form_data)
        
        # DOCXファイル生成
        output_path = self._generate_docx(app_form, output_dir)
        
        # JSONも出力（デバッグ用）
        json_path = output_dir / "application_form.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(app_form.model_dump(), f, ensure_ascii=False, indent=2)
        
        logger.info(f"申請書生成 完了: {output_path.name}")
        logger.info("=" * 60)
        
        return output_path, app_form
    
    async def _build_application_form(self, form_data: Dict[str, Any]) -> ApplicationForm:
        """フォームデータから申請書データを構築"""
        
        # lab_defaultsから研究者情報を取得
        lab_info = self.defaults.get("lab_info", {})
        
        # フロントエンドからのapp_config取得
        app_config = form_data.get("app_config", {})
        
        # 申請日
        application_date = datetime.now().strftime("%Y年%m月%d日")
        
        # 申請者情報
        applicant = Applicant(
            affiliation=lab_info.get("pi_affiliation", "システム情報系"),
            position=lab_info.get("pi_position", ""),
            name=lab_info.get("pi_name", "")
        )
        
        # 研究タイトル
        research_title = form_data.get("title", form_data.get("research_title", ""))
        
        # 研究期間
        research_period_end = form_data.get("research_period_end", "")
        if not research_period_end:
            # デフォルト: 来年度末
            next_year = datetime.now().year + 1
            research_period_end = f"{next_year}年3月31日"
        
        # 謝金
        reward_amount = form_data.get("rewardAmount", form_data.get("reward_amount", 0))
        reward = Reward(
            has_reward=reward_amount > 0,
            amount=reward_amount,
            unit="1/回"
        )
        
        # 実施施設（app_configから優先取得）
        facility_type_map = {
            'a': 'single',
            'b': 'multi_tsukuba',
            'c': 'multi_other'
        }
        facility_type = facility_type_map.get(
            app_config.get("facilityType", "a"), 
            "single"
        )
        facility_name = app_config.get("facilityName") or lab_info.get("lab_room", "")
        facility = Facility(type=facility_type, names=[facility_name] if facility_name else [])
        
        # 実施分担者（app_configから取得）
        collaborators = []
        for sub_inv in app_config.get("subInvestigators", []):
            if sub_inv.get("name"):
                collaborators.append(Collaborator(
                    affiliation=sub_inv.get("affiliation", ""),
                    position=sub_inv.get("position", ""),
                    name=sub_inv.get("name", "")
                ))
        
        # データ管理（app_configから優先取得）
        data_mgmt_defaults = self.defaults.get("data_management_defaults", {})
        
        # 保存期間
        retention_period = "発表後10年間"
        if app_config.get("retentionPeriod") == "less":
            retention_period = app_config.get("retentionReason", "10年以下")
        
        # 匿名化
        anonymization = Anonymization(
            enabled=app_config.get("hasAnonymization", True),
            has_correspondence_table=app_config.get("hasCorrespondenceTable", True)
        )
        
        data_storage = DataStorage(
            location=app_config.get("storageLocation") or data_mgmt_defaults.get("storage_location", "研究室"),
            manager=app_config.get("dataManager") or data_mgmt_defaults.get("manager", lab_info.get("pi_name", "")),
            method=app_config.get("managementMethod") or data_mgmt_defaults.get("management_method", "暗号化およびパスワード保護"),
            disposal=app_config.get("disposalMethod") or data_mgmt_defaults.get("disposal_method", "SSD初期化、紙媒体はシュレッダー")
        )
        
        # データタイプをLLMで推定
        data_types = await self._infer_data_types(form_data)
        
        data_management = DataManagement(
            data_types=data_types,
            retention_period=retention_period,
            anonymization=anonymization,
            storage=data_storage
        )
        
        # 問い合わせ先
        contact = Contact(
            affiliation=lab_info.get("pi_affiliation", ""),
            position=lab_info.get("pi_position", ""),
            name=lab_info.get("pi_name", ""),
            extension=lab_info.get("pi_phone", "").replace("029-853-", ""),
            email=lab_info.get("pi_email", "")
        )
        
        # 関係組織の長
        domain_head_info = self.defaults.get("domain_head", {})
        domain_head = DomainHead(
            domain=domain_head_info.get("domain_name", "知能情報工学域"),
            name=domain_head_info.get("name", "")
        )
        
        # 費用の出所（app_configから優先取得）
        funding_info = self.defaults.get("funding", {})
        funding_source = app_config.get("fundingSource") or funding_info.get("source", "")
        funding_pi = app_config.get("fundingPI") or funding_info.get("pi_name", lab_info.get("pi_name", ""))
        funding_project = app_config.get("fundingProjectName") or ""
        
        funding = Funding(
            source=funding_source,
            pi=funding_pi,
            project_title=funding_project
        )
        
        return ApplicationForm(
            application_date=application_date,
            applicant=applicant,
            research_title=research_title,
            research_period_end=research_period_end,
            reward=reward,
            facility=facility,
            collaborators=collaborators,
            data_management=data_management,
            contact=contact,
            domain_head=domain_head,
            funding=funding
        )
    
    async def _infer_data_types(self, form_data: Dict[str, Any]) -> List[str]:
        """研究内容からデータタイプを推定"""
        research_method = form_data.get("methodology", form_data.get("research_method", ""))
        devices = form_data.get("devices", [])
        
        prompt = f"""
以下の研究方法から、収集されるデータの種類を推定してください。

研究方法: {research_method}
使用機器: {', '.join(devices) if devices else '特になし'}

【出力形式】
箇条書きで2-4項目を出力してください。
例:
- デモグラフィックデータ（性別・年齢）
- 実験データ（反応時間）
"""
        
        try:
            response = await self.llm.generate_content_async(
                prompt=prompt,
                system_instruction="データ収集の観点から簡潔に回答してください。"
            )
            
            # 箇条書きをパース
            lines = response.strip().split("\n")
            data_types = []
            for line in lines:
                line = line.strip()
                if line.startswith("-") or line.startswith("・"):
                    data_types.append(line[1:].strip())
                elif line:
                    data_types.append(line)
            
            return data_types[:4]  # 最大4項目
            
        except Exception as e:
            logger.error(f"データタイプ推定エラー: {e}")
            return ["デモグラフィックデータ（性別・年齢）", "実験データ"]
    
    def _generate_docx(self, app_form: ApplicationForm, output_dir: Path) -> Path:
        """申請書DOCXを生成"""
        doc = Document()
        
        # スタイル設定
        style = doc.styles['Normal']
        style.font.name = 'Yu Gothic'
        style.font.size = Pt(10.5)
        
        # ヘッダー
        header = doc.add_paragraph()
        header.add_run("別記様式第１（第８条関係）")
        header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        
        # 日付
        date_para = doc.add_paragraph()
        date_para.add_run(app_form.application_date)
        date_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        
        # タイトル
        title = doc.add_paragraph()
        title_run = title.add_run("研究倫理審査申請書")
        title_run.bold = True
        title_run.font.size = Pt(14)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        doc.add_paragraph()
        
        # 宛先
        doc.add_paragraph("システム情報系長　殿")
        
        # 申請者情報
        doc.add_paragraph("申請者（実施責任者又は指導教員）")
        doc.add_paragraph(f"　　所　属　{app_form.applicant.affiliation}")
        doc.add_paragraph(f"　　職　名　{app_form.applicant.position}")
        doc.add_paragraph(f"　　氏　名　{app_form.applicant.name}")
        
        doc.add_paragraph()
        doc.add_paragraph("下記により実施したいので、申請します。")
        doc.add_paragraph()
        
        # 記
        center_para = doc.add_paragraph()
        center_para.add_run("記")
        center_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        doc.add_paragraph()
        
        # 1. 課題名
        self._add_section(doc, "１　課題名")
        doc.add_paragraph(f"　　　{app_form.research_title}")
        doc.add_paragraph(f"　　　（カテゴリー：{app_form.category}）")
        
        # 2. 申請種別
        self._add_section(doc, "２　申請種別")
        new_check = "■" if app_form.application_type.is_new else "□"
        change_check = "□" if app_form.application_type.is_new else "■"
        doc.add_paragraph(f"　　　{new_check}新規申請")
        doc.add_paragraph(f"　　　{change_check}変更申請")
        
        # 3. 実施分担者
        self._add_section(doc, "３　実施分担者")
        if app_form.collaborators:
            for collab in app_form.collaborators:
                doc.add_paragraph(f"　　　{collab.affiliation}　{collab.position}　{collab.name}")
        else:
            doc.add_paragraph("　　　（なし）")
        
        # 4. 関係組織の長
        self._add_section(doc, "４　関係組織の長")
        doc.add_paragraph(f"　　　（域名・域長名）　{app_form.domain_head.domain}長・{app_form.domain_head.name}")
        
        # 5. 実施施設
        self._add_section(doc, "５　実施施設名")
        facility_names = "、".join(app_form.facility.names)
        doc.add_paragraph(f"　　■a. 筑波大学単独施設での研究（{facility_names}）")
        
        # 6. 疫学研究
        self._add_section(doc, "６　疫学研究、ヒトゲノム・遺伝子解析研究との関わり")
        epi_check = "■" if not app_form.epidemiology_genome else "□"
        doc.add_paragraph(f"　　{epi_check}関係しない")
        
        # 7. 費用の出所
        self._add_section(doc, "７　費用の出所")
        doc.add_paragraph(f"　　{app_form.funding.source}")
        doc.add_paragraph(f"　　研究代表者：{app_form.funding.pi}")
        doc.add_paragraph(f"　　研究課題名：{app_form.funding.project_title}")
        
        # 謝金
        reward_check = "■" if app_form.reward.has_reward else "□"
        doc.add_paragraph(f"　　(1)謝金について　{reward_check}有")
        if app_form.reward.has_reward:
            doc.add_paragraph(f"　　　　具体的な金額　{app_form.reward.amount}円　{app_form.reward.unit}")
        
        # 8. 研究期間
        self._add_section(doc, "８　研究等を行う期間")
        doc.add_paragraph(f"　　{app_form.research_period_start}　～　{app_form.research_period_end}")
        
        # 9-13は省略（長いため）
        self._add_section(doc, "９　研究等における倫理的配慮")
        doc.add_paragraph("　　（詳細は添付の実施計画書を参照）")
        
        # 14. 問い合わせ先
        self._add_section(doc, "１４　実施責任者の問い合わせ先")
        doc.add_paragraph(f"　　所属・職名・氏名　{app_form.contact.affiliation}・{app_form.contact.position}・{app_form.contact.name}")
        doc.add_paragraph(f"　　内線番号　{app_form.contact.extension}")
        doc.add_paragraph(f"　　メールアドレス　{app_form.contact.email}")
        
        # 保存
        output_path = output_dir / "01-1_研究倫理審査申請書.docx"
        doc.save(output_path)
        
        return output_path
    
    def _add_section(self, doc: Document, title: str):
        """セクション見出しを追加"""
        para = doc.add_paragraph()
        run = para.add_run(title)
        run.bold = True


async def generate_application_form(
    form_data: Dict[str, Any],
    output_dir: Path,
    llm_client: LLMClient,
    lab_defaults: Dict[str, Any]
) -> tuple[Path, ApplicationForm]:
    """
    申請書生成エントリーポイント
    """
    generator = ApplicationFormGenerator(llm_client, lab_defaults)
    return await generator.generate(form_data, output_dir)
