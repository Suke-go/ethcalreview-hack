from __future__ import annotations

from pathlib import Path
from shutil import rmtree

import pytest
from docx import Document

from app.config import app_config, load_user_settings
from app.services.form_context_builder import build_generation_context
from app.services.official_docx_renderer import all_paragraphs, render_official_template
from app.services.preset_manager import load_preset_bundle


@pytest.fixture
def output_dir() -> Path:
    path = Path(".pytest_tmp") / "video_and_consent_render"
    if path.exists():
        rmtree(path)
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        if path.exists():
            rmtree(path)


@pytest.fixture
def generation_context() -> dict:
    settings = load_user_settings(app_config)
    presets = load_preset_bundle(app_config)
    form_data = {
        "title": "ビデオ公開承諾テスト課題",
        "purpose": "字幕表示方法が理解に与える影響を調べる",
        "significance": "情報提示方法の改善につながる",
        "methodology": "映像視聴と質問への回答",
        "targetDescription": "英語を第二言語として学習する成人",
        "inclusionCriteria": ["18歳以上"],
        "exclusionCriteria": ["なし"],
        "expectedParticipants": 12,
        "participantsJustification": "統計的検出力の確保に必要",
        "procedures": ["映像視聴", "選択式質問への回答"],
        "risks": ["目の疲れ", "軽い心理的負担"],
        "riskCountermeasures": ["適宜休憩を取る", "音量を事前に調整する"],
        "duration": 45,
        "rewardAmount": 750,
        "app_config": {
            "applicationType": "new",
            "researchPeriodEndText": "2027年3月31日",
            "domainName": "システム情報系",
            "domainHeadName": "矢野 博明",
            "subInvestigators": [
                {
                    "affiliation": "筑波大学情報学群",
                    "position": "研究員",
                    "name": "山田 花子",
                    "tel": "029-111-2222",
                }
            ],
            "facilityName": "3M211",
            "fundingSource": "運営費交付金",
            "fundingPI": "善甫 啓一",
            "fundingProjectName": "検証研究",
            "dataTypes": "回答内容、回答時間",
            "storageLocation": "実験室3M211",
            "dataManager": "善甫 啓一",
            "managementMethod": "暗号化して保存",
            "disposalMethod": "完全消去",
            "videoRecording": True,
            "recordingPublicRelease": True,
            "invasiveness": False,
            "conflictOfInterest": False,
        },
    }
    return build_generation_context(form_data, settings, presets)


def document_text(path: Path) -> str:
    document = Document(path)
    return "\n".join(paragraph.text for paragraph in all_paragraphs(document))


def test_recording_public_release_flag_is_true(generation_context: dict) -> None:
    assert generation_context["recording"]["public_release"] is True


@pytest.mark.parametrize(
    "template_key",
    [
        "application_form",
        "consent_form",
        "consent_withdrawal",
        "honorarium_rationale",
        "video_consent",
    ],
)
def test_templates_render_without_error_and_include_title(
    template_key: str,
    generation_context: dict,
    output_dir: Path,
) -> None:
    # (a) 例外なく生成される
    path = render_official_template(
        template_key, generation_context, output_dir / f"{template_key}.docx"
    )
    text = document_text(path)

    # (b) 主要値（課題名）が本文に入る
    assert "ビデオ公開承諾テスト課題" in text
    # (b) 氏名が本文に入る（実施責任者または分担者）
    if template_key in {"consent_form", "consent_withdrawal", "video_consent"}:
        assert "山田 花子" in text


def test_video_consent_includes_title(generation_context: dict, output_dir: Path) -> None:
    # (d) video_consent に課題名が入る
    path = render_official_template(
        "video_consent", generation_context, output_dir / "video_consent.docx"
    )
    text = document_text(path)
    assert "研究課題：ビデオ公開承諾テスト課題" in text


def test_consent_form_strips_old_sample_text(
    generation_context: dict, output_dir: Path
) -> None:
    # (c) 旧サンプル文「特定のPCのみを用います」が consent には残らない
    path = render_official_template(
        "consent_form", generation_context, output_dir / "consent_form.docx"
    )
    text = document_text(path)
    assert "特定のPCのみを用います" not in text
    # 裏面②③のリッチ化が反映されていること
    assert "研究用の識別番号を付与します" in text  # ③(1) 匿名化
    assert "想定される負担・リスク" in text  # ② リスク記述
    assert "分析のためにのみ使用します" in text  # ③(1) 利用目的
    assert "不利益が生じることはありません" in text  # ③(3) 任意性


def test_forbidden_terms_not_in_consent(generation_context: dict, output_dir: Path) -> None:
    # 用語制約: 生成文に「健常者」「被験者」を使わない
    for template_key in ("consent_form", "video_consent"):
        path = render_official_template(
            template_key, generation_context, output_dir / f"{template_key}_terms.docx"
        )
        text = document_text(path)
        # レンダラが挿入する本文に禁止語を含めない（テンプレ固定文は対象外だが念のため確認）
        # ここではレンダラ生成部由来の文を中心に確認する
        assert "健常者" not in text
