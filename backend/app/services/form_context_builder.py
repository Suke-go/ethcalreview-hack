from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from app.config import UserSettings
from app.services.preset_manager import PresetBundle, get_preset_by_id


def _get_nested(data: dict[str, Any], key: str) -> Any:
    if key in data:
        return data[key]
    if "." not in key:
        return None
    current: Any = data
    for part in key.split("."):
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def _pick(form_data: dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        value = _get_nested(form_data, key)
        if value not in (None, "", [], {}):
            return value
    return default


def _normalize_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        normalized = value.replace("、", "\n").replace(",", "\n")
        items = [item.strip() for item in normalized.splitlines() if item.strip()]
        return items or [value]
    return [value]


def _to_bool(value: Any, default: bool = False) -> bool:
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


def _has_amount(value: Any) -> bool:
    number = _to_number(value)
    if number is not None:
        return number > 0
    return bool(str(value).strip()) if value not in (None, [], {}) else False


def _to_number(value: Any) -> float | None:
    if value in (None, "", [], {}):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", "").strip())
        except ValueError:
            return None
    return None


def _normalize_facility_type(value: Any) -> str:
    mapping = {
        "a": "single",
        "b": "multi_tsukuba",
        "c": "multi_other",
        "single": "single",
        "multi_tsukuba": "multi_tsukuba",
        "multi_other": "multi_other",
    }
    return mapping.get(str(value or "single"), "single")


def _default_storage_location(rooms: list[str]) -> str:
    room_text = rooms[0] if rooms else "3M211"
    return f"研究室({room_text})にて管理されたノートパソコン"


DEFAULT_DATA_MANAGEMENT_METHOD = (
    "ノートパソコンの使用を関係者のみに限定し、結果の解析はネットワークに接続されていない状態で行う。"
    "また、暗号化およびパスワード保護を用いることによりデータを保護する。"
    "同意書等の紙媒体については研究室の鍵付き棚に保管し、鍵は管理責任者が管理する。"
)

DEFAULT_DATA_DISPOSAL_METHOD = (
    "研究対象者から実験に関するデータの破棄が申請された場合は、直ちに当該研究対象者のデータを破棄する。"
    "また、研究成果発表から10年が経過した場合、データを保存している媒体を初期化し、"
    "データの復元ができないように処分する。同意書等の紙媒体についてはシュレッダーにかけた上で破棄する。"
)


def _domain_head_from_submission(submission_preset: Any) -> tuple[str, str]:
    if not submission_preset:
        return "", ""
    domain = getattr(submission_preset, "label", "") or getattr(submission_preset, "default_affiliation_label", "")
    candidates = getattr(submission_preset, "domain_head_candidates", []) or []
    if not candidates:
        return domain, ""
    first = candidates[0]
    if isinstance(first, dict):
        return domain, str(first.get("name", ""))
    return domain, str(getattr(first, "name", ""))


def build_generation_context(
    form_data: dict[str, Any],
    settings: UserSettings,
    preset_bundle: PresetBundle,
) -> dict[str, Any]:
    investigator_preset_id = _pick(
        form_data,
        "principal_investigator_preset_id",
        "principalInvestigatorPresetId",
        "app_config.principalInvestigatorPresetId",
        "principalInvestigator.presetId",
        "principal_investigator.preset_id",
    )
    investigator_preset = get_preset_by_id(preset_bundle, "investigator_presets", investigator_preset_id) if investigator_preset_id else None

    submission_preset_id = _pick(
        form_data,
        "submission_preset_id",
        "submissionPresetId",
        "app_config.submissionPresetId",
        "submission.presetId",
        "submission.preset_id",
        default=(investigator_preset.default_submission_preset_id if investigator_preset else ""),
    )
    budget_preset_id = _pick(
        form_data,
        "budget_preset_id",
        "budgetPresetId",
        "app_config.budgetPresetId",
        "budget.presetId",
        default=(investigator_preset.default_budget_ids[0] if investigator_preset and investigator_preset.default_budget_ids else ""),
    )
    room_preset_id = _pick(form_data, "room_preset_id", "roomPresetId", "app_config.roomPresetId", "facility.presetId")

    submission_preset = get_preset_by_id(preset_bundle, "submission_presets", submission_preset_id) if submission_preset_id else None
    budget_preset = get_preset_by_id(preset_bundle, "budget_presets", budget_preset_id) if budget_preset_id else None
    room_preset = get_preset_by_id(preset_bundle, "room_presets", room_preset_id) if room_preset_id else None
    default_domain, default_domain_head = _domain_head_from_submission(submission_preset)

    principal_investigator = {
        "preset_id": investigator_preset_id or "",
        "affiliation": _pick(
            form_data,
            "principalInvestigator.affiliation",
            "principal_investigator.affiliation",
            default=(investigator_preset.affiliation if investigator_preset else settings.principal_investigator.affiliation),
        ),
        "position": _pick(
            form_data,
            "principalInvestigator.position",
            "principal_investigator.position",
            default=(investigator_preset.position if investigator_preset else settings.principal_investigator.position),
        ),
        "name": _pick(
            form_data,
            "principalInvestigator.name",
            "principal_investigator.name",
            default=(investigator_preset.name if investigator_preset else settings.principal_investigator.name),
        ),
        "email": _pick(
            form_data,
            "principalInvestigator.email",
            "principal_investigator.email",
            default=(investigator_preset.email if investigator_preset else settings.principal_investigator.email),
        ),
        "tel": _pick(
            form_data,
            "principalInvestigator.phone",
            "principal_investigator.phone",
            "principal_investigator.tel",
            default=(investigator_preset.tel if investigator_preset else settings.principal_investigator.phone),
        ),
    }

    reward_amount = _pick(
        form_data,
        "rewardAmount",
        "reward_amount",
        default=(budget_preset.reward_per_person if budget_preset and budget_preset.reward_per_person is not None else settings.budget.reward_per_person),
    )
    reward_type = _pick(
        form_data,
        "rewardType",
        "reward_type",
        default=(budget_preset.reward_type if budget_preset else settings.budget.reward_type),
    )
    hourly_rate = _pick(
        form_data,
        "hourlyRate",
        "hourly_rate",
        default=(budget_preset.hourly_rate if budget_preset and budget_preset.hourly_rate is not None else settings.budget.hourly_rate),
    )
    participant_count = _pick(form_data, "expectedParticipants", "participant_count", default=None)
    reward_total_amount = _pick(form_data, "rewardTotalAmount", "app_config.rewardTotalAmount", default=None)
    if reward_total_amount in (None, ""):
        amount_number = _to_number(reward_amount)
        participant_number = _to_number(participant_count)
        if amount_number is not None and participant_number is not None:
            reward_total_amount = int(amount_number * participant_number)

    rooms = _normalize_list(
        _pick(
            form_data,
            "facilityRooms",
            "rooms",
            default=(room_preset.rooms if room_preset else (investigator_preset.default_rooms if investigator_preset else [settings.laboratory.room])),
        )
    )
    application_type = _pick(form_data, "applicationType", "app_config.applicationType", "application.type", default="new")
    retention_period_choice = _pick(form_data, "retentionPeriod", "app_config.retentionPeriod", default="10years")

    context = {
        "meta": {
            "generated_at": datetime.now().isoformat(),
            "source_text": _pick(form_data, "research_plan", "researchPlan", "rawResearchInput", default=""),
            "followup_answers": _pick(form_data, "followupAnswers", "followup_answers", default={}),
            "preset_snapshot": {
                "submission_preset_id": submission_preset_id or "",
                "principal_investigator_preset_id": investigator_preset_id or "",
                "budget_preset_id": budget_preset_id or "",
                "room_preset_id": room_preset_id or "",
            },
        },
        "application": {
            "type": application_type,
            "is_new": application_type != "change"
            and _to_bool(_pick(form_data, "isNewApplication", "app_config.isNewApplication", "application.is_new", default=True), True),
            "approval_number": _pick(form_data, "previousApprovalNumber", "app_config.previousApprovalNumber", "application.approval_number", default=""),
            "similar_exists": _to_bool(_pick(form_data, "similarApplicationExists", "app_config.similarApplicationExists", "similar_application.exists", default=False)),
            "similar_details": _pick(form_data, "similarApplicationDetails", "app_config.similarApplicationDetails", "similar_application.details", default=""),
        },
        "research": {
            "title": _pick(form_data, "title", "research_title"),
            "background": _pick(form_data, "background", "research_background"),
            "purpose": _pick(form_data, "purpose", "research_purpose"),
            "significance": _pick(form_data, "significance", "research_significance"),
            "method": _pick(form_data, "methodology", "research_method"),
            "period_start_text": _pick(form_data, "researchPeriodStartText", "app_config.researchPeriodStartText", "research_period_start", default="研究倫理委員会承認後"),
            "period_end_text": _pick(form_data, "researchPeriodEndText", "app_config.researchPeriodEndText", "research_period_end"),
        },
        "submission": {
            "preset_id": submission_preset_id or "",
            "recipient": _pick(form_data, "submissionRecipient", default=(submission_preset.recipient if submission_preset else settings.submission_destination)),
            "committee_name": _pick(form_data, "committeeName", default=(submission_preset.committee_name if submission_preset else settings.ethics_committee.name)),
            "office_name": _pick(form_data, "committeeOfficeName", default=(submission_preset.office_name if submission_preset else settings.ethics_committee.office)),
            "office_tel": _pick(form_data, "committeeOfficeTel", default=(submission_preset.office_tel if submission_preset else settings.ethics_committee.phone)),
        },
        "principal_investigator": principal_investigator,
        "conductors": [
            {
                "affiliation": _pick(form_data, "experimentConductorAffiliation", "app_config.subInvestigators.0.affiliation", default="筑波大学システム情報系"),
                "position": _pick(form_data, "experimentConductorPosition", "app_config.subInvestigators.0.position", default=""),
                "name": _pick(form_data, "experimentConductorName", "app_config.subInvestigators.0.name", default=principal_investigator["name"]),
                "tel": _pick(form_data, "experimentConductorTel", "app_config.subInvestigators.0.tel", default=settings.experiment_conductor.phone),
            }
        ],
        "domain_head": {
            "domain": _pick(form_data, "domainName", "app_config.domainName", default=default_domain),
            "name": _pick(form_data, "domainHeadName", "app_config.domainHeadName", default=default_domain_head),
        },
        "facility": {
            "type": _normalize_facility_type(_pick(form_data, "facilityType", "app_config.facilityType", default="single")),
            "rooms": _normalize_list(_pick(form_data, "facilityRooms", "rooms", "app_config.facilityName", default=rooms)),
            "external_facility": _pick(form_data, "externalFacility", "app_config.externalFacilityName", default=""),
            "external_org_leader": _pick(form_data, "externalOrgLeader", "app_config.externalOrgLeader", default=""),
            "tsukuba_role": _pick(form_data, "tsukubaRole", "app_config.tsukubaRole", default=""),
        },
        "funding": {
            "source": _pick(form_data, "fundingSource", "app_config.fundingSource", default=(budget_preset.source if budget_preset else settings.budget.source)),
            "pi_name": _pick(form_data, "fundingPiName", "app_config.fundingPI", default=principal_investigator["name"]),
            "project_title": _pick(form_data, "fundingProjectTitle", "app_config.fundingProjectName", default=(budget_preset.project_name if budget_preset else settings.budget.project_name)),
            "project_code": _pick(form_data, "fundingProjectCode", "app_config.fundingProjectCode", default=""),
        },
        "reward": {
            "enabled": _has_amount(reward_amount),
            "amount": reward_amount,
            "unit": _pick(form_data, "rewardUnit", "app_config.rewardUnit", default="回"),
            "type": reward_type,
            "rationale": _pick(form_data, "rewardRationale", default=""),
            "estimated_minutes": _pick(form_data, "duration", "duration_minutes", default=None),
            "estimated_participants": participant_count,
            "total_amount": reward_total_amount,
            "hourly_rate": hourly_rate,
        },
        "participants": {
            "criteria": _pick(form_data, "targetDescription", "target_participants"),
            "inclusion_criteria": _normalize_list(_pick(form_data, "inclusionCriteria", default=[])),
            "exclusion_criteria": _normalize_list(_pick(form_data, "exclusionCriteria", default=[])),
            "count": participant_count,
            "count_rationale": _pick(form_data, "participantsJustification", "participant_count_reason"),
            "recruitment_method": _pick(form_data, "recruitmentMethod", default=""),
        },
        "participant_list": {
            "planned_count": participant_count,
            "reward_per_person": reward_amount,
            "total_reward": reward_total_amount,
            "leave_personal_rows_blank": True,
        },
        "procedures": _normalize_list(_pick(form_data, "procedures", default=[])),
        "risks": _normalize_list(_pick(form_data, "risks", default=[])),
        "risk_countermeasures": _normalize_list(_pick(form_data, "riskCountermeasures", default=[])),
        "recording": {
            "enabled": _to_bool(_pick(form_data, "videoRecording", "recordingEnabled", "app_config.videoRecording", "app_config.recordingEnabled", default=False)),
            "types": _normalize_list(_pick(form_data, "recordingTypes", "app_config.recordingTypes", default=[])),
            "public_release": _to_bool(_pick(form_data, "recordingPublicRelease", "app_config.recordingPublicRelease", default=False)),
        },
        "ethics": {
            "genome_related": _to_bool(_pick(form_data, "genomeRelated", "app_config.genomeRelated", "ethics.genome_related", default=False)),
            "conflict_of_interest": _to_bool(_pick(form_data, "conflictOfInterest", "app_config.conflictOfInterest", "ethics.conflict_of_interest", default=False)),
            "conflict_of_interest_partner": _pick(form_data, "conflictOfInterestPartner", "app_config.conflictOfInterestPartner", "ethics.conflict_of_interest_partner", default=""),
            "invasiveness": _to_bool(_pick(form_data, "invasiveness", "app_config.invasiveness", "ethics.invasiveness", default=False)),
            "invasiveness_details": _pick(form_data, "invasivenessDetails", "app_config.invasivenessDetails", "ethics.invasiveness_details", default=""),
        },
        "data": {
            "types": _normalize_list(_pick(form_data, "dataTypes", "app_config.dataTypes", default=[])),
            "retention_period_choice": retention_period_choice,
            "retention_period": _pick(form_data, "retentionPeriodText", "app_config.retentionReason", default=("" if retention_period_choice == "less" else "当該論文等の発表後10年間")),
            "anonymization_enabled": _to_bool(_pick(form_data, "hasAnonymization", "app_config.hasAnonymization", default=True), True),
            "correspondence_table_enabled": _to_bool(_pick(form_data, "hasCorrespondenceTable", "app_config.hasCorrespondenceTable", default=True), True),
            "storage_location": _pick(form_data, "storageLocation", "app_config.storageLocation", default=_default_storage_location(rooms)),
            "manager": _pick(form_data, "dataManager", "app_config.dataManager", default=principal_investigator["name"]),
            "management_method": _pick(form_data, "managementMethod", "app_config.managementMethod", default=DEFAULT_DATA_MANAGEMENT_METHOD),
            "disposal_method": _pick(form_data, "disposalMethod", "app_config.disposalMethod", default=DEFAULT_DATA_DISPOSAL_METHOD),
            "disclosure_to_participant": _to_bool(_pick(form_data, "dataDisclosureToParticipant", default=True), True),
            "disclosure_to_proxy": _to_bool(_pick(form_data, "dataDisclosureToProxy", default=False)),
        },
        "consent": {
            "target_age": _pick(form_data, "consentTargetAge", default="18歳以上"),
            "can_confirm_will": _to_bool(_pick(form_data, "consentCanConfirmWill", default=True), True),
            "method": _pick(form_data, "consentMethod", default="文書を添えて口頭にて説明する"),
            "withdrawal_deadline_text": _pick(form_data, "consentWithdrawalDeadlineText", default="同意書署名の日から90日後"),
        },
        "publication": {
            "enabled": _to_bool(_pick(form_data, "publicationEnabled", default=True), True),
            "methods": _normalize_list(_pick(form_data, "publicationMethods", default=[])),
            "identifiable_data_disclosed": _to_bool(_pick(form_data, "identifiableDataDisclosed", default=False)),
        },
        "attachments": {
            "conflict_of_interest_form": _to_bool(_pick(form_data, "attachmentConflictOfInterestForm", default=True), True),
            "implementation_plan": _to_bool(_pick(form_data, "attachmentImplementationPlan", default=True), True),
            "explanation_document": _to_bool(_pick(form_data, "attachmentExplanationDocument", default=True), True),
            "consent_form": _to_bool(_pick(form_data, "attachmentConsentForm", default=True), True),
            "consent_withdrawal_form": _to_bool(_pick(form_data, "attachmentConsentWithdrawalForm", default=True), True),
            "video_consent_form": _to_bool(_pick(form_data, "attachmentVideoConsentForm", default=False)),
            "other": _pick(form_data, "attachmentOther", default=""),
        },
    }
    return deepcopy(context)
