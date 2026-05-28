"""
tests/test_validation_rules.py

P0-1 用語ガード & P2-6 チェックリスト検証のユニットテスト。

テスト方針:
- generation_validator.py の検証関数を直接呼び出す。
- 必要最小限の context dict を手組みする (build_generation_context に依存しない)。
- ただし「正常な context でエラーが立たない」ことの確認には
  test_official_renderers.py と同様の手順で build_generation_context を利用する。
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from app.config import UserSettings, app_config, load_user_settings
from app.services.form_context_builder import build_generation_context
from app.services.generation_validator import (
    ValidationIssue,
    _check_forbidden_terminology,
    _check_checklist_required_fields,
    error_issues,
    validate_generation_context,
)
from app.services.preset_manager import PresetBundle, load_preset_bundle


# ---------------------------------------------------------------------------
# フィクスチャ: 正常な context (test_official_renderers.py の generation_context と同等)
# ---------------------------------------------------------------------------

@pytest.fixture
def valid_form_data() -> dict[str, Any]:
    """test_official_renderers.py の generation_context フィクスチャと同じ form_data。"""
    return {
        "title": "Validation Rules Test",
        "purpose": "研究参加者の反応時間を計測する",
        "methodology": "タスクおよびアンケート",
        "targetDescription": "成人の研究対象者",
        "inclusionCriteria": ["成人であること"],
        "exclusionCriteria": ["なし"],
        "expectedParticipants": 10,
        "participantsJustification": "統計的検出力の確保に必要な人数",
        "procedures": ["タスクおよびアンケートに回答する"],
        "risks": ["軽微な疲労"],
        "riskCountermeasures": ["適宜休憩をとる"],
        "duration": 60,
        "rewardAmount": 1000,
        "app_config": {
            "applicationType": "new",
            "researchPeriodEndText": "2027年3月31日",
            "domainName": "システム情報系",
            "domainHeadName": "矢野 博明",
            "subInvestigators": [
                {
                    "affiliation": "筑波大学",
                    "position": "助教",
                    "name": "山田 太郎",
                    "tel": "029-000-0000",
                }
            ],
            "facilityName": "3M211",
            "fundingSource": "運営費交付金",
            "fundingPI": "善甫 啓一",
            "fundingProjectName": "テスト研究",
            "dataTypes": "反応時間, アンケート",
            "storageLocation": "研究室 3M211",
            "dataManager": "善甫 啓一",
            "managementMethod": "暗号化ストレージ",
            "disposalMethod": "安全な削除",
            "videoRecording": False,
            "invasiveness": False,
            "conflictOfInterest": False,
        },
    }


@pytest.fixture
def valid_context(valid_form_data: dict[str, Any]) -> dict[str, Any]:
    settings = load_user_settings(app_config)
    presets = load_preset_bundle(app_config)
    context = build_generation_context(valid_form_data, settings, presets)
    return context


# ---------------------------------------------------------------------------
# ヘルパー: issue の field と severity を検索
# ---------------------------------------------------------------------------

def _issues_with_field(issues: list[ValidationIssue], field: str) -> list[ValidationIssue]:
    return [i for i in issues if i.field == field]


def _warning_fields(issues: list[ValidationIssue]) -> list[str]:
    return [i.field for i in issues if i.severity == "warning"]


def _error_fields(issues: list[ValidationIssue]) -> list[str]:
    return [i.field for i in issues if i.severity == "error"]


# ---------------------------------------------------------------------------
# P0-1 用語ガード: _check_forbidden_terminology
# ---------------------------------------------------------------------------

class TestForbiddenTerminology:
    """P0-1: 「健常者」「被験者」が含まれるとき warning Issue が立つ。"""

    def _ctx(self, overrides: dict[str, Any]) -> dict[str, Any]:
        """最小限のベース context に overrides を深くマージしたものを返す。"""
        base: dict[str, Any] = {
            "research": {},
            "participants": {},
            "risks": [],
            "risk_countermeasures": [],
            "procedures": [],
        }
        for key, value in overrides.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                base[key] = {**base[key], **value}
            else:
                base[key] = value
        return base

    # --- 健常者 ---

    def test_kenjousha_in_research_purpose_raises_warning(self) -> None:
        ctx = self._ctx({"research": {"purpose": "健常者を対象とする"}})
        issues = _check_forbidden_terminology(ctx)
        assert issues, "「健常者」で warning が立つべき"
        assert all(i.severity == "warning" for i in issues)
        assert any("健常者" in i.message for i in issues)

    def test_kenjousha_in_participants_criteria_raises_warning(self) -> None:
        ctx = self._ctx({"participants": {"criteria": "健常者であること"}})
        issues = _check_forbidden_terminology(ctx)
        assert issues
        assert any("健常者" in i.message for i in issues)
        assert all(i.severity == "warning" for i in issues)

    def test_kenjousha_in_risks_list_raises_warning(self) -> None:
        ctx = self._ctx({"risks": ["健常者への影響は軽微"]})
        issues = _check_forbidden_terminology(ctx)
        assert issues
        assert any("健常者" in i.message for i in issues)

    def test_kenjousha_in_procedures_list_raises_warning(self) -> None:
        ctx = self._ctx({"procedures": ["健常者に課題を実施する"]})
        issues = _check_forbidden_terminology(ctx)
        assert issues

    # --- 被験者 ---

    def test_hiken_in_research_method_raises_warning(self) -> None:
        ctx = self._ctx({"research": {"method": "被験者に課題を行わせる"}})
        issues = _check_forbidden_terminology(ctx)
        assert issues
        assert any("被験者" in i.message for i in issues)
        assert all(i.severity == "warning" for i in issues)

    def test_hiken_in_risk_countermeasures_raises_warning(self) -> None:
        ctx = self._ctx({"risk_countermeasures": ["被験者が疲労した場合は休憩する"]})
        issues = _check_forbidden_terminology(ctx)
        assert issues

    def test_hiken_in_participants_inclusion_criteria_raises_warning(self) -> None:
        ctx = self._ctx({"participants": {"inclusion_criteria": ["被験者であること"]}})
        issues = _check_forbidden_terminology(ctx)
        assert issues

    # --- 問題なし (正常系) ---

    def test_no_forbidden_terms_returns_empty(self) -> None:
        ctx = self._ctx({
            "research": {"purpose": "研究対象者の反応時間を計測する"},
            "participants": {"criteria": "成人の参加者であること"},
            "risks": ["軽微な疲労"],
            "procedures": ["参加者にタスクを実施する"],
        })
        issues = _check_forbidden_terminology(ctx)
        assert issues == []

    def test_kenkyou_taishousya_does_not_trigger(self) -> None:
        """「研究対象者」は禁止用語ではないのでゼロ件。"""
        ctx = self._ctx({"research": {"purpose": "研究対象者の参加を募集する"}})
        issues = _check_forbidden_terminology(ctx)
        assert issues == []

    def test_sanka_sha_does_not_trigger(self) -> None:
        """「参加者」は禁止用語ではない。"""
        ctx = self._ctx({"participants": {"criteria": "参加者は18歳以上であること"}})
        issues = _check_forbidden_terminology(ctx)
        assert issues == []


# ---------------------------------------------------------------------------
# P0-1 用語ガード: validate_generation_context 経由での統合確認
# ---------------------------------------------------------------------------

class TestForbiddenTerminologyViaValidate:
    """validate_generation_context の返り値に用語 Issue が含まれること。"""

    def test_forbidden_term_appears_in_validate_result(self, valid_context: dict[str, Any]) -> None:
        ctx = deepcopy(valid_context)
        ctx["research"]["purpose"] = "健常者を対象とした研究"
        issues = validate_generation_context(ctx)
        warning_msgs = [i.message for i in issues if i.severity == "warning"]
        assert any("健常者" in msg for msg in warning_msgs)

    def test_valid_context_has_no_forbidden_term_issue(self, valid_context: dict[str, Any]) -> None:
        issues = validate_generation_context(valid_context)
        # error は 0 件でなければならない
        assert error_issues(issues) == []
        # 禁止用語に関する warning がないこと
        term_warnings = [
            i for i in issues
            if i.severity == "warning" and ("健常者" in i.message or "被験者" in i.message)
        ]
        assert term_warnings == []


# ---------------------------------------------------------------------------
# P2-6 チェックリスト: 必須項目が空のとき Issue が立つ
# ---------------------------------------------------------------------------

class TestChecklistRequiredFields:
    """P2-6: 必須項目を欠いた context で該当 Issue が立つ。"""

    def _minimal_valid_ctx(self) -> dict[str, Any]:
        """validate_generation_context の既存 required_fields をすべて満たす最小 context。"""
        return {
            "research": {
                "title": "テスト研究",
                "method": "タスク法",
                "period_end_text": "2027年3月31日",
            },
            "submission": {
                "recipient": "システム情報系",
                "committee_name": "研究倫理委員会",
                "office_name": "事務局",
                "office_tel": "029-000-0000",
            },
            "principal_investigator": {
                "affiliation": "筑波大学",
                "position": "准教授",
                "name": "善甫 啓一",
                "tel": "029-853-5338",
                "email": "zempo@iit.tsukuba.ac.jp",
            },
            "conductors": [
                {
                    "affiliation": "筑波大学",
                    "name": "山田 太郎",
                }
            ],
            "facility": {
                "rooms": ["3M211"],
                "type": "single",
            },
            "data": {
                "types": ["反応時間"],
                "retention_period": "10年間",
                "storage_location": "研究室",
                "manager": "善甫 啓一",
                "management_method": "暗号化",
                "disposal_method": "安全削除",
            },
            "consent": {
                "withdrawal_deadline_text": "署名から90日後",
            },
            "domain_head": {
                "domain": "システム情報系",
                "name": "矢野 博明",
            },
            "participants": {
                "criteria": "成人の参加者",
                "count": 10,
                "recruitment_method": "掲示板",
                "inclusion_criteria": [],
                "exclusion_criteria": [],
            },
            "funding": {
                "source": "運営費交付金",
            },
            "reward": {
                "enabled": False,
                "amount": None,
                "rationale": "謝金なし（課外研究活動として実施）",
            },
            "application": {
                "type": "new",
                "is_new": True,
                "similar_exists": False,
            },
            "recording": {
                "enabled": False,
                "types": [],
            },
            "ethics": {
                "conflict_of_interest": False,
                "invasiveness": False,
            },
            "risks": [],
            "risk_countermeasures": [],
            "procedures": [],
        }

    def test_minimal_valid_context_has_zero_errors(self) -> None:
        ctx = self._minimal_valid_ctx()
        issues = validate_generation_context(ctx)
        errors = error_issues(issues)
        assert errors == [], f"エラーが立っている: {[e.model_dump() for e in errors]}"

    def test_missing_research_title_raises_error(self) -> None:
        ctx = self._minimal_valid_ctx()
        ctx["research"]["title"] = ""
        issues = validate_generation_context(ctx)
        assert any(i.field == "research.title" and i.severity == "error" for i in issues)

    def test_missing_pi_name_raises_error(self) -> None:
        ctx = self._minimal_valid_ctx()
        ctx["principal_investigator"]["name"] = ""
        issues = validate_generation_context(ctx)
        assert any(i.field == "principal_investigator.name" and i.severity == "error" for i in issues)

    def test_missing_withdrawal_deadline_raises_error(self) -> None:
        ctx = self._minimal_valid_ctx()
        ctx["consent"]["withdrawal_deadline_text"] = ""
        issues = validate_generation_context(ctx)
        assert any(i.field == "consent.withdrawal_deadline_text" and i.severity == "error" for i in issues)

    def test_missing_data_storage_location_raises_error(self) -> None:
        ctx = self._minimal_valid_ctx()
        ctx["data"]["storage_location"] = ""
        issues = validate_generation_context(ctx)
        assert any(i.field == "data.storage_location" and i.severity == "error" for i in issues)

    def test_missing_data_manager_raises_error(self) -> None:
        ctx = self._minimal_valid_ctx()
        ctx["data"]["manager"] = ""
        issues = validate_generation_context(ctx)
        assert any(i.field == "data.manager" and i.severity == "error" for i in issues)

    def test_missing_data_management_method_raises_error(self) -> None:
        ctx = self._minimal_valid_ctx()
        ctx["data"]["management_method"] = ""
        issues = validate_generation_context(ctx)
        assert any(i.field == "data.management_method" and i.severity == "error" for i in issues)

    def test_missing_data_disposal_method_raises_error(self) -> None:
        ctx = self._minimal_valid_ctx()
        ctx["data"]["disposal_method"] = ""
        issues = validate_generation_context(ctx)
        assert any(i.field == "data.disposal_method" and i.severity == "error" for i in issues)

    def test_missing_participants_criteria_raises_warning(self) -> None:
        """participants.criteria は warning_fields に含まれる。"""
        ctx = self._minimal_valid_ctx()
        ctx["participants"]["criteria"] = ""
        issues = validate_generation_context(ctx)
        assert any(i.field == "participants.criteria" and i.severity == "warning" for i in issues)

    def test_reward_enabled_without_amount_raises_error(self) -> None:
        """謝礼ありで金額が空なら error。"""
        ctx = self._minimal_valid_ctx()
        ctx["reward"] = {
            "enabled": True,
            "amount": "",
            "type": "Amazonギフトカード",
            "estimated_minutes": 60,
            "estimated_participants": 10,
            "total_amount": 0,
            "hourly_rate": 1000,
            "rationale": "",
        }
        ctx["funding"]["source"] = "運営費交付金"
        issues = validate_generation_context(ctx)
        assert any(i.field == "reward.amount" and i.severity == "error" for i in issues)

    def test_reward_disabled_with_positive_amount_raises_warning(self) -> None:
        """reward.enabled=False で amount が正の値なら整合性 warning。"""
        ctx = self._minimal_valid_ctx()
        ctx["reward"]["enabled"] = False
        ctx["reward"]["amount"] = 500
        ctx["reward"]["rationale"] = "謝金なし"
        issues = validate_generation_context(ctx)
        assert any(i.field == "reward.enabled" and i.severity == "warning" for i in issues)


# ---------------------------------------------------------------------------
# build_generation_context を使った統合テスト (正常系・エラー 0 件)
# ---------------------------------------------------------------------------

class TestValidContextViaBuilder:
    """build_generation_context で作った context は error が立たないこと。"""

    def test_valid_form_data_produces_no_errors(self, valid_context: dict[str, Any]) -> None:
        issues = validate_generation_context(valid_context)
        errors = error_issues(issues)
        assert errors == [], f"予期しないエラー: {[e.model_dump() for e in errors]}"

    def test_valid_form_data_has_no_forbidden_term_warnings(self, valid_context: dict[str, Any]) -> None:
        issues = validate_generation_context(valid_context)
        term_warnings = [
            i for i in issues
            if i.severity == "warning" and ("健常者" in i.message or "被験者" in i.message)
        ]
        assert term_warnings == []

    def test_inserting_forbidden_term_in_procedures_raises_warning(self, valid_context: dict[str, Any]) -> None:
        ctx = deepcopy(valid_context)
        ctx["procedures"] = ["被験者にタスクを行わせる"]
        issues = validate_generation_context(ctx)
        term_warnings = [
            i for i in issues
            if i.severity == "warning" and "被験者" in i.message
        ]
        assert term_warnings, "被験者 を含む手順で warning が立つべき"

    def test_inserting_forbidden_term_in_risks_raises_warning(self, valid_context: dict[str, Any]) -> None:
        ctx = deepcopy(valid_context)
        ctx["risks"] = ["健常者には影響がない"]
        issues = validate_generation_context(ctx)
        term_warnings = [
            i for i in issues
            if i.severity == "warning" and "健常者" in i.message
        ]
        assert term_warnings
