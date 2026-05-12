from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from docx import Document
from docx.document import Document as DocumentType
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph

from app.services.official_template_registry import get_official_templates_dir, load_template_manifest


class TemplateAnchorError(RuntimeError):
    pass


class TemplateValidationError(RuntimeError):
    pass


OLD_VALUE_DENYLIST = [
    "車両音の音場操作による危険知覚への影響に関する研究",
    "音場操作による環境認識への影響に関する実験",
    "粒状ジャミングバッグの剛性勾配による擬似傾斜知覚の基礎検討",
    "音響編集システムにおけるオノマトペと対話形式の導入効果",
    "temp",
    "affliation",
    "心理生理学的指標による懐疑心推定システムの開発に関する調査研究",
    "横山航大",
    "PUENTES Sandra",
    "対人サービスにおける共創価値",
    "22H03693",
    "Googleフォームによって収集される参加者",
]


def get_template_path(template_key: str) -> Path:
    manifest = load_template_manifest()
    template_info = manifest.get("templates", {}).get(template_key)
    if not template_info:
        raise FileNotFoundError(f"Template key not found in manifest: {template_key}")
    return get_official_templates_dir() / template_info["file"]


def iter_block_paragraphs(parent: DocumentType | _Cell):
    if isinstance(parent, _Cell):
        children = parent._tc.iterchildren()
    else:
        children = parent.element.body.iterchildren()

    for child in children:
        if child.tag.endswith("}p"):
            yield Paragraph(child, parent)
        elif child.tag.endswith("}tbl"):
            table = Table(child, parent)
            for row in table.rows:
                for cell in row.cells:
                    yield from iter_block_paragraphs(cell)


def all_paragraphs(document: DocumentType) -> list[Paragraph]:
    return list(iter_block_paragraphs(document))


def paragraph_text(document: DocumentType) -> str:
    return "\n".join(
        paragraph.text.strip()
        for paragraph in all_paragraphs(document)
        if paragraph.text and paragraph.text.strip()
    )


def validate_required_anchors(document: Document, template_key: str) -> None:
    manifest = load_template_manifest()
    template_info = manifest.get("templates", {}).get(template_key, {})
    required_anchors = template_info.get("required_anchors", [])
    full_text = paragraph_text(document)
    missing = [anchor for anchor in required_anchors if anchor not in full_text]
    if missing:
        raise TemplateAnchorError(f"Missing required anchors for {template_key}: {missing}")


def load_official_template(template_key: str) -> Document:
    template_path = get_template_path(template_key)
    document = Document(template_path)
    validate_required_anchors(document, template_key)
    return document


def set_paragraph_text(paragraph: Paragraph, text: str) -> None:
    if paragraph.runs:
        paragraph.runs[0].text = text
        for run in paragraph.runs[1:]:
            run.text = ""
    else:
        paragraph.add_run(text)


def first_nonempty(value: Any, default: str = "") -> str:
    if value in (None, "", [], {}):
        return default
    if isinstance(value, list):
        return "、".join(str(item) for item in value if item not in (None, ""))
    return str(value)


def get_path(context: dict[str, Any], dotted_path: str, default: Any = "") -> Any:
    current: Any = context
    for part in dotted_path.split("."):
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return default
        elif isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return default
    return current


def update_first_contains(paragraphs: list[Paragraph], needle: str, replacement: str) -> bool:
    for paragraph in paragraphs:
        if needle in paragraph.text:
            set_paragraph_text(paragraph, replacement)
            return True
    return False


def update_all_contains(paragraphs: list[Paragraph], needle: str, replacement: str) -> int:
    count = 0
    for paragraph in paragraphs:
        if needle in paragraph.text:
            set_paragraph_text(paragraph, replacement)
            count += 1
    return count


def require_first_contains(paragraphs: list[Paragraph], needle: str, replacement: str) -> None:
    if not update_first_contains(paragraphs, needle, replacement):
        raise TemplateAnchorError(f"Replacement target not found: {needle}")


def require_all_contains(paragraphs: list[Paragraph], needle: str, replacement: str) -> None:
    if update_all_contains(paragraphs, needle, replacement) == 0:
        raise TemplateAnchorError(f"Replacement target not found: {needle}")


def require_any_contains(paragraphs: list[Paragraph], needles: list[str], replacement: str) -> None:
    count = 0
    for needle in needles:
        count += update_all_contains(paragraphs, needle, replacement)
    if count == 0:
        raise TemplateAnchorError(f"Replacement target not found: {needles}")


def set_paragraph_at(paragraphs: list[Paragraph], index: int, text: str) -> None:
    if index >= len(paragraphs):
        raise TemplateAnchorError(f"Paragraph index out of range: {index}")
    set_paragraph_text(paragraphs[index], text)


def find_paragraph_index(paragraphs: list[Paragraph], needle: str, occurrence: int = 1) -> int:
    if occurrence < 1:
        raise ValueError("occurrence must be >= 1")
    matches = 0
    for index, paragraph in enumerate(paragraphs):
        if needle in paragraph.text:
            matches += 1
            if matches == occurrence:
                return index
    raise TemplateAnchorError(f"Anchor not found: {needle}")


def set_relative_to_anchor(
    paragraphs: list[Paragraph],
    anchor: str,
    offset: int,
    text: str,
    occurrence: int = 1,
) -> None:
    set_paragraph_at(paragraphs, find_paragraph_index(paragraphs, anchor, occurrence) + offset, text)


def set_relative_group(
    paragraphs: list[Paragraph],
    anchor: str,
    replacements: list[tuple[int, str]],
    occurrence: int = 1,
) -> None:
    base_index = find_paragraph_index(paragraphs, anchor, occurrence)
    for offset, text in replacements:
        set_paragraph_at(paragraphs, base_index + offset, text)


def checkbox(value: bool) -> str:
    return "■" if value else "□"


def to_bool(value: Any, default: bool = False) -> bool:
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "on", "有", "あり", "する"}:
            return True
        if normalized in {"false", "0", "no", "n", "off", "無", "なし", "しない"}:
            return False
    return bool(value)


def join_text(value: Any, default: str = "") -> str:
    if value in (None, "", [], {}):
        return default
    if isinstance(value, list):
        return "、".join(str(item) for item in value if item not in (None, ""))
    return str(value)


def format_reiwa_date(now: datetime | None = None) -> str:
    now = now or datetime.now()
    reiwa_year = now.year - 2018
    year_text = "元" if reiwa_year == 1 else str(reiwa_year)
    return f"令和{year_text}年{now.month}月{now.day}日"


def get_primary_conductor(context: dict[str, Any]) -> dict[str, Any]:
    conductors = get_path(context, "conductors", [])
    if isinstance(conductors, list) and conductors:
        return conductors[0] or {}
    return {}


def consent_explanation_label(context: dict[str, Any]) -> str:
    if get_path(context, "recording.enabled", False):
        return "ビデオ録画を含めた個人情報の保護"
    return "個人情報の保護およびデータ管理"


def format_amount(value: Any, suffix: str = "円") -> str:
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, (int, float)):
        return f"{int(value):,}{suffix}"
    text = str(value).strip()
    if not text:
        return ""
    if suffix and text.replace(",", "").isdigit() and suffix not in text:
        return f"{int(text.replace(',', '')):,}{suffix}"
    return text


def render_application_form(document: DocumentType, context: dict[str, Any]) -> None:
    paragraphs = all_paragraphs(document)
    application = get_path(context, "application", {})
    research = get_path(context, "research", {})
    submission = get_path(context, "submission", {})
    pi = get_path(context, "principal_investigator", {})
    conductor = get_primary_conductor(context)
    facility = get_path(context, "facility", {})
    funding = get_path(context, "funding", {})
    reward = get_path(context, "reward", {})
    data = get_path(context, "data", {})
    participants = get_path(context, "participants", {})
    recording = get_path(context, "recording", {})
    consent = get_path(context, "consent", {})
    publication = get_path(context, "publication", {})
    attachments = get_path(context, "attachments", {})
    ethics = get_path(context, "ethics", {})

    title = first_nonempty(research.get("title"), "（課題名未入力）")
    rooms = join_text(facility.get("rooms"), first_nonempty(data.get("storage_location")))
    reward_enabled = to_bool(reward.get("enabled"))
    recording_enabled = to_bool(recording.get("enabled"))
    recording_public_release = to_bool(recording.get("public_release"))
    anonymization_enabled = to_bool(data.get("anonymization_enabled"), True)
    correspondence_enabled = to_bool(data.get("correspondence_table_enabled"), True)
    publication_enabled = to_bool(publication.get("enabled"), True)
    identifiable_disclosed = to_bool(publication.get("identifiable_data_disclosed"), False)
    application_type = first_nonempty(application.get("type"), "new")
    is_new_application = to_bool(application.get("is_new"), True) and application_type != "change"
    similar_exists = to_bool(application.get("similar_exists"), False)
    genome_related = to_bool(ethics.get("genome_related"), False)
    conflict_of_interest = to_bool(ethics.get("conflict_of_interest"), False)
    invasiveness = to_bool(ethics.get("invasiveness"), False)

    put = set_relative_to_anchor

    put(paragraphs, "別記様式第１", 1, f"　　{format_reiwa_date()}")
    put(paragraphs, "研　究　倫　理　審　査　申　請　書", 2, first_nonempty(submission.get("recipient"), "（提出先未設定）"))
    put(paragraphs, "申請者（実施責任者又は指導教員）", 1, f"　　　　　　所　属　{first_nonempty(pi.get('affiliation'))}")
    put(paragraphs, "申請者（実施責任者又は指導教員）", 2, f"職　名　{first_nonempty(pi.get('position'))}")
    put(paragraphs, "申請者（実施責任者又は指導教員）", 3, f"氏　名　{first_nonempty(pi.get('name'))}   印　　　　")
    put(paragraphs, "１　課題名", 1, f"　　{title}")

    set_relative_group(
        paragraphs,
        "■新規申請",
        [
            (0, f"２　　{checkbox(is_new_application)}新規申請"),
            (1, f"      {checkbox(not is_new_application)}変更申請（審査承認番号：{first_nonempty(application.get('approval_number'))}）　　"),
        ],
    )
    put(paragraphs, "本学、あるいは他機関", 1, f"　　{checkbox(not similar_exists)}なし")
    put(paragraphs, "本学、あるいは他機関", 2, f"　　{checkbox(similar_exists)}ある（申請者（機関名）、申請課題、研究期間）{first_nonempty(application.get('similar_details'))}")

    conductor_affiliation = first_nonempty(conductor.get("affiliation"))
    conductor_position = first_nonempty(conductor.get("position"))
    conductor_name = first_nonempty(conductor.get("name"))
    put(paragraphs, "３　実施分担者", 1, f"　　{conductor_affiliation}")
    put(paragraphs, "３　実施分担者", 2, f"　{conductor_position}　{conductor_name}".strip())
    put(paragraphs, "３　実施分担者", 4, "")
    put(paragraphs, "３　実施分担者", 5, "")

    domain = first_nonempty(get_path(context, "domain_head.domain"))
    domain_head = first_nonempty(get_path(context, "domain_head.name"))
    put(paragraphs, "４　関係組織の長", 1, f"　　　　（域名・域長名）　{domain}・{domain_head}" if domain or domain_head else "　　　　（域名・域長名）")

    facility_type = first_nonempty(facility.get("type"), "single")
    put(paragraphs, "５　実施施設名", 1, f"{checkbox(facility_type == 'single')}a. 筑波大学単独施設での研究")
    put(paragraphs, "５　実施施設名", 2, f"　　（実施施設名：{rooms}）")
    put(paragraphs, "５　実施施設名", 3, f"　　{checkbox(facility_type == 'multi_tsukuba')}b. 筑波大学を代表施設とする多施設共同研究")
    put(paragraphs, "５　実施施設名", 4, f"　　　（実施施設名：{first_nonempty(facility.get('external_facility'))}）")
    put(paragraphs, "５　実施施設名", 5, f"　　{checkbox(facility_type == 'multi_other')}c. 他施設を代表施設とする多施設共同研究　　")
    put(paragraphs, "５　実施施設名", 6, f"　　 （代表施設名：{first_nonempty(facility.get('external_facility'))}　研究組織代表者氏名：{first_nonempty(facility.get('external_org_leader'))}　）")
    put(paragraphs, "５　実施施設名", 7, f"　　　筑波大学：{rooms}")
    put(paragraphs, "５　実施施設名", 8, f"b.またはc.の場合、筑波大学の役割　{first_nonempty(facility.get('tsukuba_role'))}")

    put(paragraphs, "疫学研究", 1, f"{checkbox(genome_related)}関係する")
    put(paragraphs, "疫学研究", 2, f"{checkbox(not genome_related)}関係しない")

    put(paragraphs, "資金の種類", 1, f"　{first_nonempty(funding.get('source'))}")
    put(paragraphs, "資金の種類", 2, f"　研究代表者：{first_nonempty(funding.get('pi_name'), first_nonempty(pi.get('name')))}")
    put(paragraphs, "資金の種類", 3, f"　研究課題名：{first_nonempty(funding.get('project_title'))}")
    put(paragraphs, "資金の種類", 4, f"　課題番号：{first_nonempty(funding.get('project_code'))}")

    put(paragraphs, "(1)　謝金について", 1, f"{checkbox(reward_enabled)}有")
    put(paragraphs, "(1)　謝金について", 2, f"{checkbox(reward_enabled)} 具体的な金額　{first_nonempty(reward.get('amount'))}　円　/{first_nonempty(reward.get('unit'), '回')}")
    put(paragraphs, "(1)　謝金について", 3, f"{checkbox(bool(reward.get('hourly_rate')))} {first_nonempty(reward.get('hourly_rate'))}円/時（筑波大学謝金単価に基づく）")
    put(paragraphs, "(1)　謝金について", 4, "□ 外部へ委託する")
    put(paragraphs, "(1)　謝金について", 5, f"{checkbox(not reward_enabled)}無（理由：{first_nonempty(reward.get('rationale'))})")

    put(paragraphs, "(2)　利益相反について", 1, f"　　　{checkbox(conflict_of_interest)}有（相手先企業名：{first_nonempty(ethics.get('conflict_of_interest_partner'))}）")
    put(paragraphs, "(2)　利益相反について", 2, f"　　　{checkbox(not conflict_of_interest)}無")

    put(
        paragraphs,
        "８　研究等を行う期間",
        1,
        f"　　{first_nonempty(research.get('period_start_text'), '研究倫理委員会承認後')}　～　{first_nonempty(research.get('period_end_text'))}",
    )

    put(paragraphs, "研究対象者に対する人権擁護", 1, " ■研究対象者および代諾者は、研究の参加・不参加について何ら不利益を受けること")
    put(paragraphs, "研究対象者に対する人権擁護", 2, "なく、自由意思で決めることができる。")
    put(paragraphs, "研究対象者に対する人権擁護", 3, " ■研究参加の意思表示をいつでも不利益を受けることなく撤回することができる。")
    put(paragraphs, "研究対象者に対する人権擁護", 4, "■同意書の同意撤回期限は、実験実施日から一か月以上先を記載している。")
    put(paragraphs, "上記すべてを満たさない場合の理由", 1, "　　（　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　 　　）")

    put(paragraphs, "健康被害の補償", 1, "　 ■有")
    put(paragraphs, "健康被害の補償", 2, "　　　■国立大学法人総合損害保険（国大協保険）")
    put(paragraphs, "健康被害の補償", 3, "　　　□臨床研究保険")
    put(paragraphs, "健康被害の補償", 4, "□その他（　　　　　　　　　　　　　　　　　　　　　　　　　）")
    put(paragraphs, "健康被害の補償", 5, "　　  □無 (理由：                                                     )")

    put(paragraphs, "同意書について", 1, "　　 □18歳未満12歳以上　□12歳未満")
    require_first_contains(paragraphs, "■18歳以上", f"{checkbox('18' in first_nonempty(consent.get('target_age'), '18歳以上'))}18歳以上")
    require_first_contains(paragraphs, "本人の意思が確認できる者", f"　　　 {checkbox(to_bool(consent.get('can_confirm_will'), True))}本人の意思が確認できる者")
    require_first_contains(paragraphs, "認知症その他の事情", f"　　　 {checkbox(not to_bool(consent.get('can_confirm_will'), True))}認知症その他の事情により本人の意思が確認できない者")
    require_first_contains(paragraphs, "同意書を必要としない", "□同意書を必要としない")

    put(
        paragraphs,
        "研究対象者をビデオ撮影する必要性",
        1,
        f"　　　{checkbox(recording_enabled)}有（ビデオ画像公開についての承諾書・承諾変更書の取得　{checkbox(recording_public_release)}有　{checkbox(not recording_public_release)}無）",
    )
    put(paragraphs, "研究対象者をビデオ撮影する必要性", 2, f"　　　{checkbox(not recording_enabled)}無")
    put(paragraphs, "侵襲性について", 1, f"　　　{checkbox(invasiveness)}有（具体的な内容：{first_nonempty(ethics.get('invasiveness_details'))}）")
    put(paragraphs, "侵襲性について", 2, f"　　　{checkbox(not invasiveness)}無")

    put(paragraphs, "１０　研究データ等の保存", 1, f"どのようなデータか（具体的な内容：{join_text(data.get('types'), join_text(participants.get('criteria')))}）")
    put(paragraphs, "取得した研究データ等の保存期間", 1, f"　　　■{first_nonempty(data.get('retention_period'), '当該論文等の発表後10年間（研究資料等の保存に関するガイドラインに基づく）')}")
    put(paragraphs, "取得した研究データ等の保存期間", 2, "　　　□10年以下（理由：　　　　　　　　　　　　　　　　）")
    put(paragraphs, "取得した研究データ等の匿名化", 1, f"　　　{checkbox(anonymization_enabled)}有（対応表の作成　{checkbox(correspondence_enabled)}有　{checkbox(not correspondence_enabled)}無）")
    put(paragraphs, "取得した研究データ等の匿名化", 2, f"　　　{checkbox(not anonymization_enabled)}無（理由：　　　　　　　　　　　　　　）")
    put(paragraphs, "管理場所、管理責任者、管理方法、処分方法", 1, f"　　　管理場所　：{first_nonempty(data.get('storage_location'), rooms)}")
    put(paragraphs, "管理場所、管理責任者、管理方法、処分方法", 2, f"　　　管理責任者：{first_nonempty(data.get('manager'), first_nonempty(pi.get('name')))}")
    put(paragraphs, "管理場所、管理責任者、管理方法、処分方法", 3, f"　　　管理方法　：{first_nonempty(data.get('management_method'))}")
    put(paragraphs, "管理場所、管理責任者、管理方法、処分方法", 4, f"　　　処分方法　：{first_nonempty(data.get('disposal_method'))}")

    disclose_to_participant = to_bool(data.get("disclosure_to_participant"), True)
    disclose_to_proxy = to_bool(data.get("disclosure_to_proxy"), False)
    put(paragraphs, "(1)本人への開示", 1, f"　　　{checkbox(disclose_to_participant)}希望があれば、対象者本人が提供した研究データを本人に開示する　")
    put(paragraphs, "(1)本人への開示", 2, f"　　　{checkbox(not disclose_to_participant)}希望しても、研究データを本人に開示しない")
    put(paragraphs, "代諾者【代理人】への開示", 1, f"　　　{checkbox(disclose_to_proxy)}希望があれば、本人の研究データを代諾者【代理人】に開示する")
    put(paragraphs, "代諾者【代理人】への開示", 2, f"　　　{checkbox(not disclose_to_proxy)}希望しても、本人の研究データを代諾者【代理人】に開示しない")

    put(paragraphs, "公開の有無と公開の方法", 1, f"　　　{checkbox(publication_enabled)}研究成果を公開する（論文発表、学会発表、インターネット掲載などを含む）")
    put(paragraphs, "公開の有無と公開の方法", 2, f"　　　　□その他（{join_text(publication.get('methods'))}）")
    put(paragraphs, "公開の有無と公開の方法", 3, f"    {checkbox(not publication_enabled)}研究成果を公開しない")
    put(paragraphs, "(2) 研究データ等", 1, f"　　　{checkbox(not identifiable_disclosed)}研究成果公開の際、研究対象者を特定できる研究データを開示しない")
    put(paragraphs, "(2) 研究データ等", 2, f"　　　{checkbox(identifiable_disclosed)}研究成果公開の際、研究対象者を特定できる研究データ等を開示する")

    put(paragraphs, "１３　添付書類", 1, f"　　　{checkbox(to_bool(attachments.get('conflict_of_interest_form'), True))}利益相反自己申告書")
    put(paragraphs, "１３　添付書類", 2, f"{checkbox(to_bool(attachments.get('implementation_plan'), True))}実施計画書（様式任意）")
    put(paragraphs, "１３　添付書類", 3, f"{checkbox(to_bool(attachments.get('explanation_document'), True))}研究対象者あるいは代諾者への研究概要、同意書等の説明文書")
    put(paragraphs, "１３　添付書類", 4, f"{checkbox(to_bool(attachments.get('consent_form'), True))}研究対象者あるいは代諾者の同意書および同意撤回書")
    put(paragraphs, "１３　添付書類", 5, f"{checkbox(to_bool(attachments.get('video_consent_form'), False) or recording_public_release)}研究対象者のビデオ画像の公開についての承諾書・承諾変更書")
    put(paragraphs, "１３　添付書類", 9, f"  {checkbox(bool(attachments.get('other')))}その他（{first_nonempty(attachments.get('other'))}）")

    put(paragraphs, "１４　実施責任者の問い合わせ先", 1, f"　　　　所属・職名・氏名　　{first_nonempty(pi.get('affiliation'))}・{first_nonempty(pi.get('position'))}・{first_nonempty(pi.get('name'))}")
    put(paragraphs, "１４　実施責任者の問い合わせ先", 2, f"　　　　内線番号　　　　　{first_nonempty(pi.get('tel'))}")
    put(paragraphs, "１４　実施責任者の問い合わせ先", 3, f"　　　　メールアドレス　　　{first_nonempty(pi.get('email'))}")


def render_consent_form(document: DocumentType, context: dict[str, Any]) -> None:
    paragraphs = all_paragraphs(document)
    title = first_nonempty(get_path(context, "research.title"))
    recipient = first_nonempty(get_path(context, "submission.recipient"))
    pi = get_path(context, "principal_investigator", {})
    conductor = get_primary_conductor(context)
    office_name = first_nonempty(get_path(context, "submission.office_name"))
    office_tel = first_nonempty(get_path(context, "submission.office_tel"))
    withdrawal_deadline = first_nonempty(get_path(context, "consent.withdrawal_deadline_text"))

    if recipient:
        require_first_contains(paragraphs, "筑波大学", recipient)

    explanation_label = consent_explanation_label(context)
    require_any_contains(
        paragraphs,
        ["私は，", "私は、"],
        f"私は，「課題名：{title}」について，研究概要，方法，研究対象者の必要性，研究対象者に対するリスクと安全性，研究に参加する上で想定される危険の回避，{explanation_label}について充分な説明を受けました。",
    )
    require_first_contains(
        paragraphs,
        "説明を行い",
        f"「課題名：{title}」の研究について，次の内容について令和　　年　　月　　日に説明を行い，上記のとおり同意を得ました。",
    )

    require_first_contains(
        paragraphs,
        "実施責任者　所　属",
        f"実施責任者　所　属  {first_nonempty(pi.get('affiliation'))}",
    )
    require_first_contains(
        paragraphs,
        "氏　名   善甫",
        f"氏　名   {first_nonempty(pi.get('name'))}  （署名又は記名押印）",
    )
    require_first_contains(
        paragraphs,
        "データ提供の同意撤回の期限",
        f"データ提供の同意撤回の期限は{withdrawal_deadline}までとさせて頂きます。",
    )
    require_first_contains(
        paragraphs,
        "実施分担者",
        f"実施分担者　（所属：{first_nonempty(conductor.get('affiliation'))}\n　　　　　　　氏名：{first_nonempty(conductor.get('name'))}　TEL：{first_nonempty(conductor.get('tel'))}）",
    )
    require_first_contains(
        paragraphs,
        "実施責任者　（所属：",
        f"実施責任者　（所属：{first_nonempty(pi.get('affiliation'))}　氏名：{first_nonempty(pi.get('name'))}　TEL：{first_nonempty(pi.get('tel'))}）",
    )
    if office_name:
        require_first_contains(paragraphs, "研究倫理委員会 事務局", f"{first_nonempty(get_path(context, 'submission.committee_name'))} 事務局")
    if office_tel:
        require_first_contains(paragraphs, "システム情報エリア支援室", f"（{office_name}　 TEL：{office_tel}）")


def render_consent_withdrawal(document: DocumentType, context: dict[str, Any]) -> None:
    paragraphs = all_paragraphs(document)
    title = first_nonempty(get_path(context, "research.title"))
    recipient = first_nonempty(get_path(context, "submission.recipient"))
    pi = get_path(context, "principal_investigator", {})
    conductor = get_primary_conductor(context)
    office_name = first_nonempty(get_path(context, "submission.office_name"))
    office_tel = first_nonempty(get_path(context, "submission.office_tel"))

    if recipient:
        require_first_contains(paragraphs, "筑波大学", recipient)
    require_any_contains(
        paragraphs,
        ["私は、", "私は，"],
        f"私は、「課題名：{title}」について、研究対象者になることへの同意を撤回いたします。",
    )
    require_first_contains(
        paragraphs,
        "上記のとおり同意撤回の申し出を受けました",
        f"「課題名：{title}」の研究について、上記のとおり同意撤回の申し出を受けました。",
    )
    require_first_contains(
        paragraphs,
        "実験責任者　所　属",
        f"実験責任者　所　属   {first_nonempty(pi.get('affiliation'))}",
    )
    require_first_contains(
        paragraphs,
        "氏　名",
        f"氏　名     {first_nonempty(pi.get('name'))}　　   （署名）",
    )
    require_first_contains(
        paragraphs,
        "実施分担者",
        f"実施分担者　（所属：{first_nonempty(conductor.get('affiliation'))}\n　　　　　　　氏名：{first_nonempty(conductor.get('name'))}　TEL：{first_nonempty(conductor.get('tel'))}）",
    )
    require_first_contains(
        paragraphs,
        "実施責任者　（所属：",
        f"実施責任者　（所属：{first_nonempty(pi.get('affiliation'))}　氏名：{first_nonempty(pi.get('name'))}　TEL：{first_nonempty(pi.get('tel'))}）",
    )
    if office_name:
        require_first_contains(paragraphs, "研究倫理委員会 事務局", f"{first_nonempty(get_path(context, 'submission.committee_name'))} 事務局")
        update_first_contains(paragraphs, "研究倫理委員会事務局", f"{first_nonempty(get_path(context, 'submission.committee_name'))} 事務局")
    if office_tel:
        require_first_contains(paragraphs, "システム情報エリア支援室", f"（{office_name}　 TEL：{office_tel}）")


def render_honorarium_rationale(document: DocumentType, context: dict[str, Any]) -> None:
    paragraphs = all_paragraphs(document)
    research = get_path(context, "research", {})
    pi = get_path(context, "principal_investigator", {})
    facility = get_path(context, "facility", {})
    funding = get_path(context, "funding", {})
    reward = get_path(context, "reward", {})
    participants = get_path(context, "participants", {})

    title = first_nonempty(research.get("title"))
    rooms = join_text(facility.get("rooms"), first_nonempty(get_path(context, "data.storage_location")))
    period = " ～ ".join(
        value
        for value in [
            first_nonempty(research.get("period_start_text")),
            first_nonempty(research.get("period_end_text")),
        ]
        if value
    )
    target = first_nonempty(participants.get("criteria"))
    count = first_nonempty(participants.get("count"))
    minutes = first_nonempty(reward.get("estimated_minutes"))
    amount = format_amount(reward.get("amount"))
    hourly_rate = format_amount(reward.get("hourly_rate"), "円/時間")
    total_amount = format_amount(reward.get("total_amount"))
    procedures = join_text(get_path(context, "procedures", []), first_nonempty(research.get("method")))

    set_relative_group(
        paragraphs,
        "本学教員",
        [
            (1, f"（{first_nonempty(pi.get('affiliation'))}　{first_nonempty(pi.get('position'))}　{first_nonempty(pi.get('name'))}）"),
        ],
    )
    set_relative_group(
        paragraphs,
        "研究課題名",
        [
            (1, f"　{title}"),
        ],
    )
    set_relative_group(
        paragraphs,
        "経費",
        [
            (1, f"　経費名：{first_nonempty(funding.get('source'))}"),
            (2, f"　研究代表者：{first_nonempty(funding.get('pi_name'), first_nonempty(pi.get('name')))}　研究課題名：{first_nonempty(funding.get('project_title'))}"),
        ],
    )
    set_relative_group(
        paragraphs,
        "【場所】",
        [
            (1, f"　{rooms}"),
        ],
    )
    set_relative_group(
        paragraphs,
        "【期間】",
        [
            (1, f"　{period}"),
        ],
    )
    set_relative_group(
        paragraphs,
        "【謝金対象者】",
        [
            (1, f"　{target}（予定人数：{count}名）"),
        ],
    )
    set_relative_group(
        paragraphs,
        "【内容等】",
        [
            (1, f"　{procedures}"),
            (2, f"　所要時間：{minutes}分、謝金単価：{hourly_rate}、1人あたり謝金：{amount}"),
        ],
    )
    set_relative_group(
        paragraphs,
        "謝金支出案",
        [
            (1, f"　謝金形式：{first_nonempty(reward.get('type'))}"),
            (2, f"　単価：{amount} × 予定人数：{count}名 = 総額：{total_amount}"),
            (3, f"　算出根拠：{first_nonempty(reward.get('rationale'), '筑波大学の謝金単価および研究計画上の所要時間に基づき算出する。')}"),
        ],
    )


def rendered_expected_values(template_key: str, context: dict[str, Any]) -> list[str]:
    if template_key == "honorarium_rationale":
        values = [
            first_nonempty(get_path(context, "research.title")),
            first_nonempty(get_path(context, "principal_investigator.name")),
            first_nonempty(get_path(context, "funding.source")),
            format_amount(get_path(context, "reward.amount")),
            format_amount(get_path(context, "reward.hourly_rate"), "円/時間"),
            format_amount(get_path(context, "reward.total_amount")),
            first_nonempty(get_path(context, "participants.count")),
        ]
        return [value for value in values if value]

    values = [
        first_nonempty(get_path(context, "research.title")),
        first_nonempty(get_path(context, "submission.recipient")),
        first_nonempty(get_path(context, "principal_investigator.name")),
        first_nonempty(get_path(context, "principal_investigator.tel")),
    ]

    if template_key == "application_form":
        values.extend(
            [
                first_nonempty(get_path(context, "principal_investigator.email")),
                first_nonempty(get_path(context, "conductors.0.name")),
                join_text(get_path(context, "facility.rooms", [])),
                join_text(get_path(context, "data.types", [])),
                first_nonempty(get_path(context, "data.storage_location")),
                first_nonempty(get_path(context, "data.manager")),
                first_nonempty(get_path(context, "data.management_method")),
                first_nonempty(get_path(context, "data.disposal_method")),
            ]
        )
        if get_path(context, "reward.enabled", False):
            values.append(first_nonempty(get_path(context, "reward.amount")))
    elif template_key in {"consent_form", "consent_withdrawal"}:
        values.extend(
            [
                first_nonempty(get_path(context, "conductors.0.name")),
                first_nonempty(get_path(context, "submission.office_tel")),
            ]
        )
        if template_key == "consent_form":
            values.append(first_nonempty(get_path(context, "consent.withdrawal_deadline_text")))

    return [value for value in values if value]


def validate_rendered_document(document: DocumentType, context: dict[str, Any], template_key: str) -> None:
    text = paragraph_text(document)
    title = first_nonempty(get_path(context, "research.title"))
    denylist = [value for value in OLD_VALUE_DENYLIST if value and value != title]
    leftovers = [value for value in denylist if value in text]
    if "{{" in text or "{%" in text:
        leftovers.append("jinja placeholder")
    missing_values = [value for value in rendered_expected_values(template_key, context) if value not in text]
    if missing_values:
        leftovers.append(f"missing expected values: {missing_values}")
    if leftovers:
        raise TemplateValidationError(f"Rendered document contains stale values: {leftovers}")


def render_official_template(template_key: str, context: dict[str, Any], output_path: Path) -> Path:
    """
    Render an official DOCX template without changing its document structure.

    The LLM is expected to provide text values upstream; this renderer only
    writes normalized context fields into fixed template locations.
    """
    document = load_official_template(template_key)
    if template_key == "application_form":
        render_application_form(document, context)
    elif template_key == "consent_form":
        render_consent_form(document, context)
    elif template_key == "consent_withdrawal":
        render_consent_withdrawal(document, context)
    elif template_key == "honorarium_rationale":
        render_honorarium_rationale(document, context)
    validate_rendered_document(document, context, template_key)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(output_path)
    return output_path
