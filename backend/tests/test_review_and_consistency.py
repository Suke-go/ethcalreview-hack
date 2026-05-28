from __future__ import annotations

from pathlib import Path

from app.config import app_config, load_user_settings
from app.services.form_context_builder import build_generation_context
from app.services.generation_validator import validate_generation_context
from app.services.preset_manager import load_preset_bundle
from app.services.review_summary import build_review_notes, render_review_notes_markdown, write_review_notes_file


def _ctx(**overrides: object) -> dict:
    settings = load_user_settings(app_config)
    presets = load_preset_bundle(app_config)
    form: dict = {
        "title": "整合チェック検証課題",
        "purpose": "目的",
        "methodology": "参加者は短い映像を視聴し選択式で回答する。",
        "targetDescription": "18歳以上の参加者",
        "expectedParticipants": 10,
        "rewardAmount": 1000,
        "app_config": {"applicationType": "new", "researchPeriodEndText": "2027年3月31日"},
    }
    form.update(overrides)
    return build_generation_context(form, settings, presets)


def _messages(context: dict) -> list[str]:
    return [issue.message for issue in validate_generation_context(context)]


def test_recording_enabled_but_method_lacks_recording_warns() -> None:
    ctx = _ctx(app_config={"applicationType": "new", "videoRecording": True, "recordingPublicRelease": True})
    assert any("録画" in m and "見当たりません" in m for m in _messages(ctx)), "録画フラグ×本文の不整合が検出されていない"


def test_recording_with_recording_in_method_does_not_warn() -> None:
    ctx = _ctx(
        methodology="参加者の課題遂行の様子をビデオで録画し、後で分析する。",
        app_config={"applicationType": "new", "videoRecording": True, "recordingTypes": ["実験中の映像"], "recordingPublicRelease": False},
    )
    assert not any("見当たりません" in m for m in _messages(ctx))


def test_build_review_notes_collects_assumptions_and_missing() -> None:
    ctx = _ctx()
    ctx.setdefault("meta", {})["llm_assumptions"] = [{"field": "duration", "value": "60分", "reason": "標準的な所要時間"}]
    ctx["meta"]["llm_missing_items"] = [{"field": "funding", "question": "財源は？", "blocking": True}]
    notes = build_review_notes(ctx)
    assert notes["counts"]["assumptions"] == 1
    assert notes["counts"]["missing_items"] == 1
    markdown = render_review_notes_markdown(notes, "テスト課題")
    assert "レビュー指摘リスト" in markdown
    assert "60分" in markdown
    assert "財源は？" in markdown


def test_write_review_notes_file_creates_markdown(tmp_path: Path) -> None:
    path = write_review_notes_file(_ctx(), tmp_path)
    assert path.exists()
    assert path.suffix == ".md"
    assert "レビュー指摘リスト" in path.read_text(encoding="utf-8")
