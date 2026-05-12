from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ValidationIssue(BaseModel):
    field: str
    message: str
    severity: str = "error"


def get_path(data: dict[str, Any], dotted_path: str, default: Any = None) -> Any:
    current: Any = data
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


def is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, list):
        return len(value) == 0 or all(is_blank(item) for item in value)
    if isinstance(value, dict):
        return len(value) == 0
    return False


def _require(context: dict[str, Any], path: str, label: str) -> ValidationIssue | None:
    if is_blank(get_path(context, path)):
        return ValidationIssue(field=path, message=f"{label}が未入力です")
    return None


def _warn(context: dict[str, Any], path: str, label: str) -> ValidationIssue | None:
    if is_blank(get_path(context, path)):
        return ValidationIssue(field=path, message=f"{label}が未入力です", severity="warning")
    return None


def validate_generation_context(context: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    required_fields = [
        ("research.title", "課題名"),
        ("research.method", "研究方法"),
        ("research.period_end_text", "研究期間の終了日"),
        ("submission.recipient", "提出先"),
        ("submission.committee_name", "研究倫理委員会名"),
        ("submission.office_name", "事務局名"),
        ("submission.office_tel", "事務局TEL"),
        ("principal_investigator.affiliation", "実施責任者の所属"),
        ("principal_investigator.position", "実施責任者の職名"),
        ("principal_investigator.name", "実施責任者の氏名"),
        ("principal_investigator.tel", "実施責任者のTEL"),
        ("principal_investigator.email", "実施責任者のメールアドレス"),
        ("conductors.0.affiliation", "実施分担者の所属"),
        ("conductors.0.name", "実施分担者の氏名"),
        ("facility.rooms", "実施施設・部屋"),
        ("data.types", "取得する研究データの種類"),
        ("data.retention_period", "研究データの保存期間"),
        ("data.storage_location", "研究データの管理場所"),
        ("data.manager", "研究データの管理責任者"),
        ("data.management_method", "研究データの管理方法"),
        ("data.disposal_method", "研究データの処分方法"),
        ("consent.withdrawal_deadline_text", "同意撤回期限"),
        ("domain_head.domain", "関係組織の領域名"),
        ("domain_head.name", "関係組織の長"),
    ]

    for path, label in required_fields:
        issue = _require(context, path, label)
        if issue:
            issues.append(issue)

    warning_fields = [
        ("participants.criteria", "研究対象者の条件"),
        ("participants.count", "予定参加者数"),
        ("participants.recruitment_method", "募集方法"),
        ("funding.source", "費用の出所"),
    ]
    for path, label in warning_fields:
        issue = _warn(context, path, label)
        if issue:
            issues.append(issue)

    reward_enabled = bool(get_path(context, "reward.enabled", False))
    if reward_enabled:
        for path, label in [
            ("reward.amount", "謝金額"),
            ("reward.type", "謝金種別"),
            ("reward.estimated_minutes", "謝金計算の所要時間"),
            ("reward.estimated_participants", "謝金計算の予定参加者数"),
            ("reward.total_amount", "謝金総額"),
            ("participants.count", "予定参加者数"),
            ("funding.source", "謝金支出元"),
        ]:
            issue = _require(context, path, label)
            if issue:
                issues.append(issue)
        if is_blank(get_path(context, "reward.hourly_rate")) and is_blank(get_path(context, "reward.rationale")):
            issues.append(
                ValidationIssue(
                    field="reward.hourly_rate",
                    message="謝金ありの場合は謝金単価または計算根拠を入力してください",
                )
            )
    elif is_blank(get_path(context, "reward.rationale")):
        issues.append(
            ValidationIssue(
                field="reward.rationale",
                message="謝金なしの場合は理由を入力してください",
                severity="warning",
            )
        )

    if get_path(context, "application.type") == "change" or get_path(context, "application.is_new") is False:
        issue = _require(context, "application.approval_number", "変更申請の審査承認番号")
        if issue:
            issues.append(issue)

    if bool(get_path(context, "application.similar_exists", False)):
        issue = _require(context, "application.similar_details", "類似申請の詳細")
        if issue:
            issues.append(issue)

    facility_type = get_path(context, "facility.type", "single")
    if facility_type in {"multi_tsukuba", "multi_other"}:
        issue = _require(context, "facility.tsukuba_role", "多施設共同研究における筑波大学の役割")
        if issue:
            issues.append(issue)
    if facility_type == "multi_other":
        for path, label in [
            ("facility.external_facility", "代表施設名"),
            ("facility.external_org_leader", "研究組織代表者氏名"),
        ]:
            issue = _require(context, path, label)
            if issue:
                issues.append(issue)

    if bool(get_path(context, "ethics.conflict_of_interest", False)):
        issue = _require(context, "ethics.conflict_of_interest_partner", "利益相反の相手先・企業名")
        if issue:
            issues.append(issue)

    if bool(get_path(context, "ethics.invasiveness", False)):
        issue = _require(context, "ethics.invasiveness_details", "侵襲性の具体的内容")
        if issue:
            issues.append(issue)

    if bool(get_path(context, "recording.enabled", False)) and is_blank(get_path(context, "recording.types")):
        issues.append(
            ValidationIssue(
                field="recording.types",
                message="ビデオ撮影ありの場合は記録種別を入力してください",
            )
        )

    return issues


def error_issues(issues: list[ValidationIssue]) -> list[ValidationIssue]:
    return [issue for issue in issues if issue.severity == "error"]


def issue_payload(issues: list[ValidationIssue]) -> list[dict[str, str]]:
    return [issue.model_dump() for issue in issues]
