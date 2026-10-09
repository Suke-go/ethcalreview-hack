from __future__ import annotations

from app.config import app_config, load_user_settings
from app.services.editable_context import apply_editable_fields
from app.services.ethics_policy import compensation_policy, withdrawal_policy
from app.services.form_context_builder import build_generation_context
from app.services.preset_manager import load_preset_bundle


def test_withdrawal_policy_uses_signature_date_and_separates_participation() -> None:
    deadline, notice = withdrawal_policy(90)

    assert deadline == "同意書署名日から90日以内"
    assert "実験への参加はいつでも中止でき" in notice
    assert "データ提供の同意は同意書署名日から90日以内であれば撤回できます" in notice
    assert "既に仮名加工したうえで集計・公表したデータ" in notice
    assert "個別に特定して削除できません" in notice


def test_withdrawal_policy_without_fixed_day_count() -> None:
    deadline, notice = withdrawal_policy(None)

    assert deadline == "研究成果の公表前まで"
    assert "研究成果の公表前まで撤回できます" in notice
    assert "同意書署名日から90日" not in notice


def test_compensation_policy_has_one_shared_wording() -> None:
    assert "国立大学法人総合損害保険（国大協保険）" in compensation_policy(True)
    assert compensation_policy(False, "研究の性質上、健康被害が想定されないため") == (
        "本研究では健康被害に対する補償は行いません（理由：研究の性質上、健康被害が想定されないため）。"
    )


def test_generation_context_uses_withdrawal_and_compensation_settings() -> None:
    settings = load_user_settings(app_config)
    presets = load_preset_bundle(app_config)
    context = build_generation_context(
        {
            "title": "設定の反映確認",
            "app_config": {
                "withdrawalPeriodDays": None,
                "hasCompensation": False,
                "noCompensationReason": "補償を行わない理由",
            },
        },
        settings,
        presets,
    )

    assert context["consent"]["withdrawal_period_days"] is None
    assert context["consent"]["withdrawal_deadline_text"] == "研究成果の公表前まで"
    assert "研究成果の公表前まで撤回できます" in context["consent"]["withdrawal_notice"]
    assert context["safety"]["has_compensation"] is False
    assert context["safety"]["compensation_text"] == "本研究では健康被害に対する補償は行いません（理由：補償を行わない理由）。"


def test_editing_withdrawal_period_rebuilds_shared_notice() -> None:
    context = {
        "consent": {
            "withdrawal_period_days": 90,
            "withdrawal_deadline_text": "同意書署名日から90日以内",
            "withdrawal_notice": "old wording",
        },
        "reward": {},
        "participants": {},
    }

    updated = apply_editable_fields(context, {"withdrawal_period_days": "30"})

    assert updated["consent"]["withdrawal_period_days"] == 30
    assert updated["consent"]["withdrawal_deadline_text"] == "同意書署名日から30日以内"
    assert "同意書署名日から30日以内であれば撤回できます" in updated["consent"]["withdrawal_notice"]
    assert context["consent"]["withdrawal_notice"] == "old wording"
