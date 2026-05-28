from __future__ import annotations

import copy
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from docx import Document
from docx.document import Document as DocumentType
from docx.oxml import OxmlElement
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
    """研究倫理審査申請書（2026/04/22 改訂・新公式様式 1.x/2.x/3.x… 構成）を描画する。

    旧 `１〜１４` 番号体系の様式は退役し、本レンダラは新章番号のラベルをアンカーとして
    値段落・チェックボックス（■/□）を上書きする。レイアウトと固定文は変更しない。
    """
    paragraphs = all_paragraphs(document)
    application = get_path(context, "application", {})
    research = get_path(context, "research", {})
    submission = get_path(context, "submission", {})
    pi = get_path(context, "principal_investigator", {})
    conductors = get_path(context, "conductors", []) or []
    facility = get_path(context, "facility", {})
    funding = get_path(context, "funding", {})
    reward = get_path(context, "reward", {})
    data = get_path(context, "data", {})
    participants = get_path(context, "participants", {})
    recording = get_path(context, "recording", {})
    ethics = get_path(context, "ethics", {})
    publication = get_path(context, "publication", {})
    attachments = get_path(context, "attachments", {})
    consent = get_path(context, "consent", {})
    risks = get_path(context, "risks", []) or []
    countermeasures = get_path(context, "risk_countermeasures", []) or []

    cb = checkbox
    pi_name = first_nonempty(pi.get("name"))
    title = first_nonempty(research.get("title"), "（課題名未入力）")
    recipient = first_nonempty(submission.get("recipient"))
    application_type = first_nonempty(application.get("type"), "new")
    is_new = to_bool(application.get("is_new"), True) and application_type != "change"
    similar_exists = to_bool(application.get("similar_exists"), False)
    reward_enabled = to_bool(reward.get("enabled"))
    coi = to_bool(ethics.get("conflict_of_interest"), False)
    invasiveness = to_bool(ethics.get("invasiveness"), False)
    recording_enabled = to_bool(recording.get("enabled"), False)
    recording_public = to_bool(recording.get("public_release"), False)
    anonymization = to_bool(data.get("anonymization_enabled"), True)
    correspondence = to_bool(data.get("correspondence_table_enabled"), True)
    publication_enabled = to_bool(publication.get("enabled"), True)
    identifiable = to_bool(publication.get("identifiable_data_disclosed"), False)
    disclose_participant = to_bool(data.get("disclosure_to_participant"), True)
    disclose_proxy = to_bool(data.get("disclosure_to_proxy"), False)
    facility_type = first_nonempty(facility.get("type"), "single")
    rooms = join_text(facility.get("rooms"), first_nonempty(data.get("storage_location")))
    target_age = first_nonempty(consent.get("target_age"), "18歳以上")

    # ---- ヘッダ ----
    set_relative_to_anchor(paragraphs, "別記様式第１", 1, f"　　{format_reiwa_date()}")
    if recipient:
        set_relative_to_anchor(paragraphs, "申請者（実施責任者又は指導教員）", -1, recipient)
    set_relative_to_anchor(paragraphs, "申請者（実施責任者又は指導教員）", 1, f"　　　　　　所　属　{first_nonempty(pi.get('affiliation'))}")
    set_relative_to_anchor(paragraphs, "申請者（実施責任者又は指導教員）", 2, f"職　名　{first_nonempty(pi.get('position'))}")
    set_relative_to_anchor(paragraphs, "申請者（実施責任者又は指導教員）", 3, f"氏　名　{pi_name}　　　印")

    # ---- 1.1 課題名 ----
    require_first_contains(paragraphs, "課題名", f"1.1　課題名　{title}")

    # ---- 1.2 研究等を行う期間 ----
    period_start = first_nonempty(research.get("period_start_text"), "研究倫理委員会承認後")
    period_end = first_nonempty(research.get("period_end_text"))
    update_first_contains(paragraphs, "研究倫理委員会承認後", f"　　　　　　{period_start}　　　～　　　{period_end}")

    # ---- 1.3 類似申請 ----
    update_first_contains(paragraphs, "新規申請", f"　{cb(is_new)}新規申請")
    update_first_contains(
        paragraphs,
        "変更申請",
        f"      {cb(not is_new)}変更申請（審査承認番号：{first_nonempty(application.get('approval_number'))}）　　",
    )
    set_relative_to_anchor(paragraphs, "今回の申請に類似した内容", 2, f"　　　{cb(not similar_exists)}無")
    set_relative_to_anchor(
        paragraphs,
        "今回の申請に類似した内容",
        3,
        f"　　　{cb(similar_exists)}有（申請者（機関名）、申請課題、研究期間）{first_nonempty(application.get('similar_details'))}",
    )

    # ---- 1.5 関係組織の長 ----
    domain = first_nonempty(get_path(context, "domain_head.domain"))
    domain_head = first_nonempty(get_path(context, "domain_head.name"))
    update_first_contains(paragraphs, "域名・域長名", f"　　　　（域名・域長名）　{domain}・{domain_head}")

    # ---- 1.6 実施施設名 ----
    update_first_contains(paragraphs, "筑波大学単独施設での研究", f"{cb(facility_type == 'single')}a. 筑波大学単独施設での研究")
    update_first_contains(paragraphs, "実験実施場所、研究データの保存場所", f"　　（実施施設名：{rooms}）")
    update_first_contains(paragraphs, "筑波大学を代表施設とする多施設共同研究", f"　　　{cb(facility_type == 'multi_tsukuba')}b. 筑波大学を代表施設とする多施設共同研究")
    update_first_contains(paragraphs, "他施設を代表施設とする多施設共同研究", f"　　　{cb(facility_type == 'multi_other')}c. 他施設を代表施設とする多施設共同研究　　　　")
    external_facility = first_nonempty(facility.get("external_facility"))
    if external_facility:
        set_relative_to_anchor(paragraphs, "筑波大学を代表施設とする多施設共同研究", 1, f"　　　　　（実施施設名：{external_facility}）")

    # ---- 1.8 謝金 ----
    unit = first_nonempty(reward.get("unit"), "回")
    amount_disp = format_amount(reward.get("amount"))  # 3桁区切り（例「1,000円」）
    hourly_disp = format_amount(reward.get("hourly_rate"))
    reward_line = f"1.8　謝金（{cb(reward_enabled)}有 {cb(not reward_enabled)}無）"
    if reward_enabled and amount_disp:
        reward_line += f"　被験者謝金単価：{amount_disp}/{unit}"
        if hourly_disp:
            reward_line += f"（{hourly_disp}/時）"
    update_first_contains(paragraphs, "1.8　謝金", reward_line)
    update_first_contains(
        paragraphs,
        "謝金単価表における被験者謝金単価",
        f"{cb(reward_enabled)}謝金単価表における被験者謝金単価（短期雇用と同じ額）を適用、またはそれ以下の単価で打ち切り",
    )
    # 外部委託しない場合、テンプレの例文「例：〇〇株式会社 2000円/1回」を残すと金額が紛らわしいので消す
    update_first_contains(
        paragraphs,
        "外部へ委託（会社概要",
        f"{cb(False)}外部へ委託（会社概要とプライバシーポリシーを「その他添付資料」に添付すること）",
    )

    # ---- 1.9 利益相反 ----
    update_first_contains(paragraphs, "1.9　利益相反", f"1.9　利益相反（{cb(coi)}有 {cb(not coi)}無）　")

    # ---- 1.11 研究区分 ----
    update_first_contains(paragraphs, "臨床研究ではない", f"　　　　　　{cb(True)}臨床研究ではない")
    update_first_contains(paragraphs, "介入（", f"介入（{cb(False)}有 {cb(True)}無）")
    update_first_contains(
        paragraphs,
        "侵襲性（",
        f"侵襲性（{cb(False)}軽微でない　{cb(invasiveness)}軽微　{cb(not invasiveness)}無）",
    )

    # ---- 1.10 参照するべき倫理指針・研究の区分（未入力なら提案値で補完） ----
    update_first_contains(
        paragraphs,
        "参照するべき倫理指針",
        f"1.10 参照するべき倫理指針・研究の区分　{first_nonempty(get_path(context, 'ethics.guideline'))}",
    )

    # ---- 1.12 健康被害の補償（既定：国大協保険あり） ----
    set_relative_to_anchor(paragraphs, "研究対象者への健康被害の補償", 1, f"　 {cb(True)}有")
    update_first_contains(paragraphs, "国立大学法人総合損害保険", f"　　　{cb(True)}国立大学法人総合損害保険（国大協保険）")
    update_first_contains(paragraphs, "□無 (理由：", f"　 {cb(False)}無 (理由：　　　　　　　　　　　　　　　　　　　　　　　　　　　　)")

    # ---- 2 取得データに関する情報 ----
    update_first_contains(paragraphs, "データの種類（記入）", f"データの種類：{join_text(data.get('types'))}")
    update_first_contains(paragraphs, "新規に収集する", f"{cb(True)}新規に収集する")
    update_first_contains(
        paragraphs,
        "個人が特定出来る音声・画像等の記録",
        f"2.4 個人が特定出来る音声・画像等の記録　{cb(recording_enabled)}有 {cb(not recording_enabled)}無",
    )
    update_first_contains(
        paragraphs,
        "ヒト由来資料の取得",
        f"2.5 血液・唾液などのヒト由来資料の取得（{cb(False)}有{cb(True)}無） ",
    )
    # 2.3 付加的に取得する個人情報：謝礼をメールで送る場合は連絡先(メール)を取得する＝同意書の記載と整合させる
    reward_type_text = first_nonempty(reward.get("type"))
    collects_email = reward_enabled and ("メール" in reward_type_text or "Ｅメール" in reward_type_text)
    update_first_contains(paragraphs, "□電子メール", f"{cb(collects_email)}電子メール")

    # ---- 2.6 データの取り扱い ----
    retention = first_nonempty(data.get("retention_period"), "当該論文等の発表後10年間")
    update_first_contains(paragraphs, "取得したデータ等の保管期間", f"取得したデータ等の保管期間　：{retention}")
    update_first_contains(paragraphs, "管理場所　：", f"　　　管理場所　：{first_nonempty(data.get('storage_location'), rooms)}")
    update_first_contains(paragraphs, "管理責任者：", f"　　　　管理責任者：{first_nonempty(data.get('manager'), pi_name)}")
    update_first_contains(paragraphs, "管理方法　：", f"　　　　管理方法　：{first_nonempty(data.get('management_method'))}")
    update_first_contains(paragraphs, "処分方法　：", f"　　　　処分方法　：{first_nonempty(data.get('disposal_method'))}")
    update_first_contains(paragraphs, "データの匿名化（", f"データの匿名化（{cb(anonymization)}有　{cb(not anonymization)}無） ")
    update_first_contains(
        paragraphs,
        "対応表を□作成する",
        f"　　　　有：匿名化する場合：対応表を{cb(correspondence)}作成する　{cb(not correspondence)}しない",
    )

    # ---- 2.7 データの開示 ----
    update_first_contains(paragraphs, "本人への開示（", f"　　　本人への開示（{cb(disclose_participant)}有　{cb(not disclose_participant)}無）")
    update_first_contains(paragraphs, "代諾者への開示（", f"　　　代諾者への開示（{cb(disclose_proxy)}有　{cb(not disclose_proxy)}無）")

    # ---- 2.8 研究の公開 ----
    publication_methods = get_path(context, "publication.methods", []) or []
    has_thesis = any("学位" in str(method) for method in publication_methods)
    update_first_contains(
        paragraphs,
        "研究の公開（有：",
        f"2.8 研究の公開（有：{cb(has_thesis)}学位論文、{cb(publication_enabled)}学会発表、{cb(publication_enabled)}学術論文 ,{cb(not publication_enabled)}無）",
    )
    update_first_contains(paragraphs, "対象者の特定（□できる", f"対象者の特定（{cb(identifiable)}できる　{cb(not identifiable)}できない）")

    # ---- 3 実験対象者 ----
    count = first_nonempty(participants.get("count"))
    update_first_contains(paragraphs, "人数の見積もり", f"3.1 期間内に実施する対象者の人数の見積もり：{count}人")
    update_first_contains(paragraphs, "妥当性の根拠", f"　　妥当性の根拠：{first_nonempty(participants.get('count_rationale'))}")
    inclusion = participants.get("inclusion_criteria") or []
    exclusion = participants.get("exclusion_criteria") or []
    selection = "、".join(str(item) for item in inclusion) if inclusion else first_nonempty(participants.get("criteria"))
    # 3.3 年齢層：年齢を抽出して補完（捏造はしない）。選択基準(inclusion)が最も信頼できるので優先し、
    # 無ければ対象者条件・対象年齢から拾う（複数ソースを混ぜて誤った範囲にしない）。
    def _extract_ages(text: str) -> list[int]:
        return [int(value) for value in re.findall(r"(\d+)\s*歳", text)]

    ages = _extract_ages("、".join(str(item) for item in inclusion))
    if not ages:
        ages = _extract_ages(f"{first_nonempty(participants.get('criteria'))}　{target_age}")
    if ages and min(ages) != max(ages):
        age_range = f"{min(ages)} ～ {max(ages)} 歳"
    elif ages:
        age_range = f"{min(ages)}歳以上"
    else:
        age_range = ""
    if age_range:
        update_first_contains(paragraphs, "3.3 年齢層", f"3.3 年齢層　{age_range}")
    # 3.2 性別：未指定なら提案値（男女指定しない）で補完
    update_first_contains(paragraphs, "3.2 性別", f"3.2 性別　{first_nonempty(participants.get('gender'), '男女指定しない')}")
    update_first_contains(paragraphs, "3.4 選択基準", f"3.4 選択基準　{selection}")
    update_first_contains(paragraphs, "除外基準　記入", f"　　除外基準　{('、'.join(str(item) for item in exclusion))}")
    update_first_contains(paragraphs, "3.5 募集方法", f"3.5 募集方法　{first_nonempty(participants.get('recruitment_method'))}")

    # ---- 4 研究に伴う危害発生の可能性・安全性 ----
    harm = "、".join(str(item) for item in risks)
    if countermeasures:
        harm = (harm + "。回避策：" if harm else "回避策：") + "、".join(str(item) for item in countermeasures)
    update_first_contains(paragraphs, "研究に伴う危害発生の可能性・安全性", f"4. 研究に伴う危害発生の可能性・安全性　{harm}")
    update_first_contains(paragraphs, "新規開発デバイスの試用", f"4.1 新規開発デバイスの試用が {cb(False)}有 {cb(True)}無")
    update_first_contains(paragraphs, "不可避的な侵襲の", f"4.2 不可避的な侵襲の({cb(invasiveness)}有　{cb(not invasiveness)}無)")
    update_first_contains(paragraphs, "回避可能な侵襲の", f"4.3 回避可能な侵襲の({cb(False)}有　{cb(True)}無)")
    update_first_contains(paragraphs, "医療費が発生した場合の負担", f"4.4 医療費が発生した場合の負担の{cb(False)}有　{cb(True)}無")

    # ---- 5 インフォームドコンセント ----
    update_first_contains(
        paragraphs,
        "対象者から文章によるインフォームド・コンセントを得る",
        f"5.1 　{cb(True)}対象者から文章によるインフォームド・コンセントを得る",
    )
    update_first_contains(paragraphs, "対象者の属性：", f"対象者の属性：{target_age}")
    update_first_contains(paragraphs, "同意能力のある成人", f"{cb('18' in target_age or '成人' in target_age)}同意能力のある成人")
    method_oral = "口頭" in first_nonempty(consent.get("method"), "文書を添えて口頭にて説明する")
    update_first_contains(paragraphs, "文章を添えて口頭にて説明する", f"{cb(method_oral)}文章を添えて口頭にて説明する・")

    # ---- 7 添付書類 ----
    update_first_contains(
        paragraphs,
        "利益相反自己申告書",
        f"　　　{cb(coi and to_bool(attachments.get('conflict_of_interest_form'), True))}利益相反自己申告書（利益相反が有る場合のみ提出すること）",
    )
    update_first_contains(paragraphs, "実施計画書（様式は任意）", f"{cb(to_bool(attachments.get('implementation_plan'), True))}実施計画書（様式は任意）")
    update_first_contains(
        paragraphs,
        "研究概要、同意書等の説明文書",
        f"{cb(to_bool(attachments.get('explanation_document'), True))}研究対象者あるいは代諾者への研究概要、同意書等の説明文書",
    )
    update_first_contains(
        paragraphs,
        "同意書および同意撤回書",
        f"{cb(to_bool(attachments.get('consent_form'), True))}研究対象者あるいは代諾者の同意書および同意撤回書",
    )
    update_first_contains(
        paragraphs,
        "ビデオ画像の公開についての承諾書",
        f"{cb(to_bool(attachments.get('video_consent_form'), False) or recording_public)}研究対象者のビデオ画像の公開についての承諾書・承諾変更書",
    )
    other_attachment = first_nonempty(attachments.get("other"))
    set_relative_to_anchor(paragraphs, "共同研究施設の役割分担", 1, f"  {cb(bool(other_attachment))}その他（{other_attachment}）")

    # ---- 8 実施責任者の問い合わせ先 ----
    require_first_contains(
        paragraphs,
        "所属・職名・氏名",
        f"　　　　所属・職名・氏名　　{first_nonempty(pi.get('affiliation'))}・{first_nonempty(pi.get('position'))}・{pi_name}",
    )
    update_first_contains(paragraphs, "内線番号", f"　　　　内線番号　　　　　{first_nonempty(pi.get('tel'))}")
    update_first_contains(paragraphs, "メールアドレス", f"　　　　メールアドレス　　　{first_nonempty(pi.get('email'))}")

    # ---- 1.7 費用の出所（資金情報を見出し直後に挿入） ----
    funding_lines = _nonempty_lines(
        f"　{first_nonempty(funding.get('source'))}" if first_nonempty(funding.get("source")) else "",
        f"　研究代表者：{first_nonempty(funding.get('pi_name'), pi_name)}",
        f"　研究課題名：{first_nonempty(funding.get('project_title'), title)}",
        f"　課題番号：{first_nonempty(funding.get('project_code'))}" if first_nonempty(funding.get("project_code")) else "",
    )
    try:
        funding_anchor_index = find_paragraph_index(paragraphs, "資金の種類と、研究代表者")
        insert_paragraphs_after(paragraphs[funding_anchor_index], funding_lines)
    except TemplateAnchorError:
        pass

    # ---- 1.4 実施分担者（責任者と異なる分担者のみ、見出し直後に挿入） ----
    conductor_lines = [
        f"　　{first_nonempty(member.get('affiliation'))}　{first_nonempty(member.get('position'))}　{first_nonempty(member.get('name'))}".rstrip()
        for member in conductors
        if first_nonempty(member.get("name")) and first_nonempty(member.get("name")) != pi_name
    ]
    if conductor_lines:
        try:
            conductor_anchor_index = find_paragraph_index(paragraphs, "職名等")
            insert_paragraphs_after(paragraphs[conductor_anchor_index], conductor_lines)
        except TemplateAnchorError:
            pass


def insert_paragraphs_after(anchor: Paragraph, lines: list[str]) -> None:
    """アンカー段落の直後に本文段落を順に挿入する。

    段落書式（インデント等）はアンカー段落から引き継ぎ、レイアウトを崩さない。
    空文字の行は挿入せず、無駄な空段落が増えないようにする。
    """
    ref = anchor._p
    parent = anchor._parent
    for line in lines:
        text = "" if line is None else str(line)
        if not text.strip():
            continue
        new_p = OxmlElement("w:p")
        if anchor._p.pPr is not None:
            new_p.append(copy.deepcopy(anchor._p.pPr))
        ref.addnext(new_p)
        Paragraph(new_p, parent).add_run(text)
        ref = new_p


def _nonempty_lines(*values: Any) -> list[str]:
    lines: list[str] = []
    for value in values:
        if value in (None, "", [], {}):
            continue
        text = str(value).strip()
        if text:
            lines.append(text)
    return lines


def build_consent_overview_sections(context: dict[str, Any]) -> list[dict[str, Any]]:
    """同意書裏面「研究の概要について」(別紙) に流し込むセクションを順序付きで構築する。

    申請書・実施計画書と同じ正規化 context を参照するため、ここに項目を足す/並べ替える
    だけで裏面へ反映できる（同意書固有の内容に限らず、研究内容・実験手順・補償/安全対策など
    他書類と共通の情報も載せられる拡張設計）。

    各セクション:
      - anchor: 公式テンプレ裏面に存在する固定ラベル（部分一致）
      - mode:   "insert_after"（ラベル直後に本文段落を挿入）/ "replace_next"（直後の段落を上書き）
      - lines:  本文行（空行は描画時に除外）
    """
    research = get_path(context, "research", {})
    participants = get_path(context, "participants", {})
    reward = get_path(context, "reward", {})
    data = get_path(context, "data", {})
    safety = get_path(context, "safety", {})  # 将来拡張: 補償・安全対策の詳細
    procedures = get_path(context, "procedures", []) or []
    risks = get_path(context, "risks", []) or []
    countermeasures = get_path(context, "risk_countermeasures", []) or []

    # [参加者条件]
    participant_lines = _nonempty_lines(participants.get("criteria"))
    inclusion = participants.get("inclusion_criteria") or []
    exclusion = participants.get("exclusion_criteria") or []
    if inclusion:
        participant_lines.append("選択基準：" + "、".join(str(item) for item in inclusion))
    if exclusion:
        participant_lines.append("除外基準：" + "、".join(str(item) for item in exclusion))

    # [方法]（+ 実験手順 procedures）
    method_lines = _nonempty_lines(research.get("method"))
    if procedures:
        method_lines.append("【実験手順】")
        method_lines.extend(f"{index}. {proc}" for index, proc in enumerate(procedures, 1))

    # [所要時間]
    minutes = first_nonempty(reward.get("estimated_minutes"))
    duration_lines = [f"約{minutes}分"] if minutes else []

    # [考えられるリスク]
    risk_lines: list[str] = []
    if risks:
        risk_lines.append("、".join(str(item) for item in risks))
    if countermeasures:
        risk_lines.append("（対策）" + "、".join(str(item) for item in countermeasures))

    # [謝礼]
    if to_bool(reward.get("enabled")):
        reward_type = first_nonempty(reward.get("type"), "Amazonギフトカード（Eメールタイプ）")
        amount = format_amount(reward.get("amount"))
        reward_lines = [f"謝礼として{reward_type}にて{amount}をお支払いします。"] if amount else []
    else:
        reward_lines = ["謝礼はありません。"]

    # ② 研究対象者の必要性，研究への参加におけるリスクと安全性，危険回避の方法（+ 安全配慮・緊急時対応・補償）
    #    お手本（参考同意書）に倣い、必要性→リスク→危険回避（軽減策）→安全配慮→緊急時対応を複数行で記述する。
    def _end_sentence(text: str) -> str:
        text = str(text).strip()
        if not text:
            return ""
        return text if text[-1] in "。．." else text + "。"

    necessity_lines: list[str] = []
    purpose = first_nonempty(research.get("purpose"))
    significance = first_nonempty(research.get("significance"))
    necessity = first_nonempty(participants.get("count_rationale"))
    criteria_text = first_nonempty(participants.get("criteria"))

    # (1) 研究対象者の必要性：なぜこの研究対象者が必要か
    necessity_sentences: list[str] = []
    if purpose:
        necessity_sentences.append(_end_sentence(f"本研究では、{purpose}"))
    if criteria_text:
        necessity_sentences.append(
            f"そのため、{criteria_text}に研究へご参加いただき、その反応や回答を分析する必要があります。"
        )
    if necessity:
        necessity_sentences.append(_end_sentence(f"研究対象者を必要とする理由は、{necessity}"))
    if necessity_sentences:
        necessity_lines.append("".join(necessity_sentences))

    # (2) 想定されるリスク
    if risks:
        necessity_lines.append(
            "研究への参加に伴い想定される負担・リスクとして、"
            + "、".join(str(item) for item in risks)
            + "が生じる可能性があります。"
        )

    # (3) 危険回避の方法・安全配慮・緊急時対応
    #    safety.measures は別エージェントが populate する複数文の安全説明文（休憩・中断の自由、
    #    緊急時対応等を含む）。存在すればそのまま用い、無ければ risk_countermeasures から組み立てる。
    safety_measures = first_nonempty(safety.get("measures"))
    if safety_measures:
        necessity_lines.append(_end_sentence(safety_measures))
    elif countermeasures:
        necessity_lines.append(
            "これらの負担を軽減するため、"
            + "、".join(str(item) for item in countermeasures)
            + "を行います。"
            "研究参加中はいつでも休憩を取ることができ、不快感や体調不良を感じた場合は研究対象者自身の判断で直ちに中断または終了することができます。"
            "研究参加を取りやめた場合にも、不利益を受けることはありません。"
        )
    else:
        necessity_lines.append(
            "研究参加中はいつでも休憩を取ることができ、不快感や体調不良を感じた場合は研究対象者自身の判断で"
            "直ちに中断または終了することができます。研究参加を取りやめた場合にも、不利益を受けることはありません。"
        )

    # (4) 健康被害の補償（任意フィールド。無ければ省略）
    compensation = first_nonempty(safety.get("compensation_text"))
    if compensation:
        necessity_lines.append(_end_sentence(f"健康被害の補償：{compensation}"))

    # ③(1) データの匿名化について
    #    お手本に倣い、取得するデータ種類 → 匿名化（識別番号・分離管理） → 利用目的を複数行で記述する。
    anon_lines: list[str] = []
    data_types = join_text(data.get("types"))
    if data_types:
        anon_lines.append(
            f"本研究では、参加者から{data_types}等のデータを取得します。"
            "また、謝礼の送付に必要な場合には、電子メールアドレス等の連絡先情報を取得することがあります。"
        )

    if to_bool(data.get("anonymization_enabled"), True):
        anon = (
            "取得したデータには、氏名の代わりに研究用の識別番号を付与します。"
            "回答内容や実験結果に関するデータと、氏名・連絡先等の個人を特定し得る情報は分けて管理します。"
        )
        if to_bool(data.get("correspondence_table_enabled"), True):
            anon += "個人情報と研究データの対応表を作成し、研究データとは別に厳重に保管します。"
        anon += "研究成果を論文、学会発表、報告書等で公表する際には、個人が特定される形でデータを公表することはありません。"
        anon_lines.append(anon)
    else:
        anon_lines.append("取得したデータの匿名化は行いません。")

    # 利用目的
    purpose_for_data = purpose or significance
    if purpose_for_data:
        anon_lines.append(
            f"取得したデータは、本研究の目的（{purpose_for_data}）の分析のためにのみ使用します。"
        )

    # ③(2) データの管理方法
    storage = first_nonempty(data.get("storage_location"))
    manager = first_nonempty(data.get("manager"))
    management_method = first_nonempty(data.get("management_method"))
    disposal = first_nonempty(data.get("disposal_method"))
    retention = first_nonempty(data.get("retention_period"), "当該論文等の発表後10年間")
    management_sentences: list[str] = []
    if storage and manager:
        management_sentences.append(f"研究データは{storage}にて{manager}が管理します。")
    elif storage:
        management_sentences.append(f"研究データは{storage}にて管理します。")
    elif manager:
        management_sentences.append(f"研究データは{manager}が管理します。")
    if management_method:
        management_sentences.append(management_method if management_method.endswith("。") else management_method + "。")
    management_sentences.append(f"データは{retention}保管します。")
    if disposal:
        management_sentences.append(disposal if disposal.endswith("。") else disposal + "。")
    management_text = "".join(management_sentences)

    # ③(3) 研究参加の任意性（固定文 + 撤回期限）
    withdrawal = first_nonempty(get_path(context, "consent.withdrawal_deadline_text"), "同意書署名の日から90日後")
    voluntariness_text = (
        "研究への参加は任意であり、参加しないことで不利益が生じることはありません。"
        f"{withdrawal}までであればデータ提供の同意を撤回でき、破棄の申し出があった場合は直ちに破棄します。"
        "実験の途中であっても不利益なく参加を取りやめることができます。"
    )

    return [
        {"anchor": "[参加者条件]", "mode": "insert_after", "lines": participant_lines},
        {"anchor": "[目的]", "mode": "insert_after", "lines": _nonempty_lines(research.get("purpose"))},
        {"anchor": "[意義]", "mode": "insert_after", "lines": _nonempty_lines(research.get("significance"))},
        {"anchor": "[方法]", "mode": "insert_after", "lines": method_lines},
        {"anchor": "[所要時間]", "mode": "insert_after", "lines": duration_lines},
        {"anchor": "[考えられるリスク]", "mode": "insert_after", "lines": risk_lines},
        {"anchor": "[謝礼]", "mode": "insert_after", "lines": reward_lines},
        {"anchor": "研究への参加におけるリスクと安全性，危険回避", "mode": "insert_after", "lines": necessity_lines},
        {"anchor": "(1) データの匿名化について", "mode": "insert_after", "lines": anon_lines},
        {"anchor": "(2) データの管理方法", "mode": "replace_next", "lines": [management_text]},
        {"anchor": "(3) 研究参加の任意性", "mode": "replace_next", "lines": [voluntariness_text]},
    ]


def render_consent_back_side(document: DocumentType, context: dict[str, Any]) -> None:
    """同意書裏面（別紙「研究の概要について」①②③）を context から流し込む。"""
    for section in build_consent_overview_sections(context):
        lines = [line for line in section["lines"] if line and str(line).strip()]
        if not lines:
            continue
        paragraphs = all_paragraphs(document)
        try:
            index = find_paragraph_index(paragraphs, section["anchor"])
        except TemplateAnchorError:
            # アンカーが存在しない裏面項目はスキップ（テンプレ差異に強くする）
            continue
        if section["mode"] == "replace_next":
            # 見出し直後の段落（テンプレに残るサンプル本文）を上書きする
            target_index = index + 1
            if target_index < len(paragraphs):
                set_paragraph_text(paragraphs[target_index], "".join(lines))
            else:
                insert_paragraphs_after(paragraphs[index], lines)
        else:
            insert_paragraphs_after(paragraphs[index], lines)


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
    # 「私は，…説明を受けました。」の同意本文だけを置換する。
    # 直後の「説明の際，…同意します。」段落も "私は，" を含むため、全置換すると
    # その内容が失われる（重複・省略の原因）。説明受領文に固有の "説明を受け" を錨にする。
    require_first_contains(
        paragraphs,
        "説明を受け",
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

    # 裏面（別紙「研究の概要について」①②③）を流し込む
    render_consent_back_side(document, context)


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
    # 氏名欄は2つある（1つ目＝研究対象者の署名欄／2つ目＝実験責任者欄）。
    # 実験責任者欄（2番目）だけを更新し、研究対象者の署名欄は空欄のまま残す。
    responsible_name_text = f"氏　名     {first_nonempty(pi.get('name'))}　　   （署名）"
    try:
        responsible_name_index = find_paragraph_index(paragraphs, "氏　名", occurrence=2)
        set_paragraph_at(paragraphs, responsible_name_index, responsible_name_text)
    except TemplateAnchorError:
        require_first_contains(paragraphs, "氏　名", responsible_name_text)
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


def render_video_consent(document: DocumentType, context: dict[str, Any]) -> None:
    """ビデオ画像公開承諾書・承諾変更書（P2-5）を context から流し込む。

    既存の render_consent_form / render_consent_withdrawal と同じアンカー置換スタイルで、
    研究課題名・実施責任者の所属/宛名・問い合わせ先などの固定ラベルを上書きする。
    テンプレのレイアウト（選択肢チェックボックス等）は変更しない。
    """
    paragraphs = all_paragraphs(document)
    title = first_nonempty(get_path(context, "research.title"))
    pi = get_path(context, "principal_investigator", {})
    conductor = get_primary_conductor(context)
    office_name = first_nonempty(get_path(context, "submission.office_name"))
    office_tel = first_nonempty(get_path(context, "submission.office_tel"))

    pi_affiliation = first_nonempty(pi.get("affiliation"), "筑波大学システム情報系")
    pi_name = first_nonempty(pi.get("name"))

    # 宛先（所属）行: '筑波大学システム情報系' -> 実施責任者の所属
    require_first_contains(paragraphs, "筑波大学システム情報系", pi_affiliation)
    # 宛名行: '（実施責任者）……殿' -> 実施責任者氏名（承諾書は実施責任者宛て）
    if pi_name:
        require_first_contains(
            paragraphs,
            "（実施責任者）",
            f"（実施責任者）　{pi_name}　殿",
        )

    # 研究課題名
    require_first_contains(
        paragraphs,
        "研究課題：",
        f"私は、｢研究課題：{title}｣におけるビデオ画像が公開されることについて",
    )

    # 問い合わせ先（注意書きの直前に実施責任者・分担者・事務局を挿入）
    contact_lines = _nonempty_lines(
        f"実施責任者　（所属：{pi_affiliation}　氏名：{pi_name}　TEL：{first_nonempty(pi.get('tel'))}）",
        f"実施分担者　（所属：{first_nonempty(conductor.get('affiliation'))}　氏名：{first_nonempty(conductor.get('name'))}　TEL：{first_nonempty(conductor.get('tel'))}）"
        if first_nonempty(conductor.get("name"))
        else "",
        f"{first_nonempty(get_path(context, 'submission.committee_name'))} 事務局" if office_name else "",
        f"（{office_name}　 TEL：{office_tel}）" if office_name and office_tel else "",
    )
    if contact_lines:
        try:
            notice_index = find_paragraph_index(paragraphs, "注意：提出時は")
            insert_paragraphs_after(paragraphs[notice_index - 1] if notice_index > 0 else paragraphs[notice_index], contact_lines)
        except TemplateAnchorError:
            pass

    # 提出版では運用上の注意（「提出時はこの注意を削除…」「2通作成し…」）を消す（消し忘れ防止）
    for paragraph in all_paragraphs(document):
        text = paragraph.text
        if ("提出時" in text and "削除" in text) or "通作成" in text:
            set_paragraph_text(paragraph, "")


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

    # 「本学教員」ラベル（申請者ブロック）直下の「（○○系　○○域）」欄を、所属・職名・氏名で埋める。
    # 本文の「本学教員の研究費について…」が occurrence 1 なので、ラベルは occurrence 2。
    applicant_line = f"（{first_nonempty(pi.get('affiliation'))}　{first_nonempty(pi.get('position'))}　{first_nonempty(pi.get('name'))}）"
    try:
        applicant_label_index = find_paragraph_index(paragraphs, "本学教員", occurrence=2)
        set_paragraph_at(paragraphs, applicant_label_index + 1, applicant_line)
    except TemplateAnchorError:
        set_relative_group(paragraphs, "本学教員", [(1, applicant_line)])
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

    if template_key == "video_consent":
        # 承諾書は実施責任者宛て。課題名・実施責任者氏名・所属・TEL が差し込まれていること。
        values = [
            first_nonempty(get_path(context, "research.title")),
            first_nonempty(get_path(context, "principal_investigator.name")),
            first_nonempty(get_path(context, "principal_investigator.affiliation")),
            first_nonempty(get_path(context, "principal_investigator.tel")),
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
            values.append(format_amount(get_path(context, "reward.amount")))
    elif template_key in {"consent_form", "consent_withdrawal"}:
        values.extend(
            [
                first_nonempty(get_path(context, "conductors.0.name")),
                first_nonempty(get_path(context, "submission.office_tel")),
            ]
        )
        if template_key == "consent_form":
            values.append(first_nonempty(get_path(context, "consent.withdrawal_deadline_text")))
            # 裏面（別紙）が空のまま出力されることを防ぐため、目的・方法の本文を必須化する
            values.append(first_nonempty(get_path(context, "research.purpose")))
            values.append(first_nonempty(get_path(context, "research.method")))

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
    elif template_key == "video_consent":
        render_video_consent(document, context)
    validate_rendered_document(document, context, template_key)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(output_path)
    return output_path
