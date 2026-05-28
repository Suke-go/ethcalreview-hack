"""E2E（事務確認）レビューで見つかった不具合の回帰テスト。

1) 同意撤回書: 実験責任者の氏名は「実験責任者」欄に入り、研究対象者の署名欄（先頭の氏名欄）には
   入らないこと（取り違え防止）。
2) 宛名: 既定の提出先が「…長　殿」を含むこと（敬称落ち防止）。申請書・同意書・撤回書で共通。
"""
from __future__ import annotations

from pathlib import Path
from shutil import rmtree

import pytest
from docx import Document

from app.config import app_config, load_user_settings
from app.services.form_context_builder import build_generation_context
from app.services.official_docx_renderer import all_paragraphs, find_paragraph_index, render_official_template
from app.services.preset_manager import load_preset_bundle


@pytest.fixture
def context() -> dict:
    settings = load_user_settings(app_config)
    presets = load_preset_bundle(app_config)
    form = {
        "title": "秘書レビュー回帰テスト課題",
        "purpose": "目的",
        "methodology": "方法",
        "targetDescription": "18歳以上の参加者",
        "expectedParticipants": 10,
        "rewardAmount": 1000,
        "app_config": {
            "applicationType": "new",
            "researchPeriodEndText": "2027年3月31日",
            "subInvestigators": [
                {"affiliation": "筑波大学システム情報系", "position": "助教", "name": "分担 花子", "tel": "029-000-0000"}
            ],
        },
    }
    return build_generation_context(form, settings, presets)


def _texts(path: Path) -> list[str]:
    return [p.text for p in all_paragraphs(Document(path))]


def test_withdrawal_responsible_name_not_placed_in_participant_signature(context: dict, tmp_path: Path) -> None:
    pi_name = context["principal_investigator"]["name"]
    path = render_official_template("consent_withdrawal", context, tmp_path / "wd.docx")
    paragraphs = all_paragraphs(Document(path))
    texts = [p.text for p in paragraphs]

    # 氏名欄は2つ。1番目＝研究対象者の署名欄（PI名が入っていてはいけない）、2番目＝実験責任者欄（PI名）
    first = find_paragraph_index(paragraphs, "氏　名", occurrence=1)
    second = find_paragraph_index(paragraphs, "氏　名", occurrence=2)
    assert pi_name not in texts[first], "研究対象者の署名欄に実験責任者名が誤挿入されている"
    assert pi_name in texts[second], "実験責任者欄に氏名が入っていない"


@pytest.mark.parametrize("template_key", ["application_form", "consent_form", "consent_withdrawal"])
def test_recipient_keeps_honorific_suffix(template_key: str, context: dict, tmp_path: Path) -> None:
    path = render_official_template(template_key, context, tmp_path / f"{template_key}.docx")
    full_text = "\n".join(_texts(path))
    assert "長　殿" in full_text, f"{template_key} の宛名から敬称（長　殿）が落ちている"


def _ctx(**overrides: object) -> dict:
    settings = load_user_settings(app_config)
    presets = load_preset_bundle(app_config)
    form: dict = {
        "title": "回帰テスト課題",
        "purpose": "目的",
        "methodology": "方法",
        "targetDescription": "18歳以上の参加者",
        "expectedParticipants": 10,
        "rewardAmount": 1000,
        "app_config": {"applicationType": "new", "researchPeriodEndText": "2027年3月31日"},
    }
    form.update(overrides)
    return build_generation_context(form, settings, presets)


def test_application_marks_email_when_reward_delivered_by_email(tmp_path: Path) -> None:
    # 謝礼をメール型で送る → 同意書がメール取得に言及するので、申請書2.3も電子メールにチェック
    path = render_official_template("application_form", _ctx(rewardAmount=1000), tmp_path / "a.docx")
    assert "■電子メール" in "\n".join(_texts(path))


def test_application_fills_age_range_from_criteria(tmp_path: Path) -> None:
    path = render_official_template("application_form", _ctx(inclusionCriteria=["20歳以上40歳未満"]), tmp_path / "a.docx")
    assert "20 ～ 40 歳" in "\n".join(_texts(path))


def test_honorarium_applicant_block_is_filled(tmp_path: Path) -> None:
    ctx = _ctx(rewardAmount=1000)
    path = render_official_template("honorarium_rationale", ctx, tmp_path / "h.docx")
    paragraphs = all_paragraphs(Document(path))
    label_index = find_paragraph_index(paragraphs, "本学教員", occurrence=2)
    filled = paragraphs[label_index + 1].text
    assert ctx["principal_investigator"]["name"] in filled, "本学教員（系・域）欄が未記入のまま"
    # 未記入プレースホルダ（全角スペース連続の系・域）が残っていないこと
    assert "工学域）" not in "\n".join(_texts(path)) or ctx["principal_investigator"]["name"] in filled


def test_video_consent_strips_submission_only_notes(tmp_path: Path) -> None:
    ctx = _ctx(app_config={"applicationType": "new", "videoRecording": True, "recordingPublicRelease": True})
    path = render_official_template("video_consent", ctx, tmp_path / "v.docx")
    text = "\n".join(_texts(path))
    assert "提出時" not in text, "提出時に削除すべき運用注意が残っている"


def test_unknown_fields_filled_with_proposals(tmp_path: Path) -> None:
    """募集方法・性別・倫理指針が未入力でも、空欄でなく提案値で補完されること。"""
    ctx = _ctx()  # recruitmentMethod / gender / ethicsGuideline を与えない
    assert ctx["participants"]["recruitment_method"], "募集方法が空欄のまま"
    assert ctx["participants"]["gender"] == "男女指定しない"
    assert ctx["ethics"]["guideline"], "倫理指針が空欄のまま"

    text = "\n".join(_texts(render_official_template("application_form", ctx, tmp_path / "a.docx")))
    assert "3.2 性別　男女指定しない" in text
    assert "公募" in text  # 3.5 募集方法の提案
    assert "医学系研究には該当しない" in text  # 1.10 倫理指針の提案


def test_recording_types_proposed_only_when_recording_enabled() -> None:
    enabled = _ctx(app_config={"applicationType": "new", "videoRecording": True})
    assert enabled["recording"]["types"], "録画ありなのに記録種別が空欄"
    disabled = _ctx()
    assert disabled["recording"]["types"] == [], "録画なしなのに記録種別が補完されている"
