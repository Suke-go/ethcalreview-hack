"""各 generator のプロンプト・章立て・context の検証。

LLM API は実際に呼ばず、必要な箇所はモッククライアントを用いる。
検証観点:
 (a) プロンプト/システム指示が「研究対象者」を含み「健常者」「被験者」を含まない
 (b) 実施計画書の章立てが公式参考様式 260127 の見出し（3-1 等／研究の概要）を含む
 (c) form_context_builder が safety.* を追加し、既存キーが消えていない
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Optional

import pytest

from app.config import app_config, load_user_settings
from app.services.preset_manager import load_preset_bundle
from app.services.form_context_builder import build_generation_context

from app.services import implementation_plan_generator as ipg
from app.services import llm_document_generator as ldg
from app.services.llm_document_generator import LLMDocumentGenerator, IMPLEMENTATION_PLAN_RULES, TERMINOLOGY_RULE
from app.services.plan_analyzer import PlanAnalyzer
from app.services.explanation_generator import ExplanationGenerator, EXPLANATION_PROMPT
from app.services import questionnaire_generator as qg
from app.services import recruitment_notice_generator as rnotice


FORBIDDEN_TERMS = ["健常者", "被験者"]
REQUIRED_TERM = "研究対象者"


class CapturingLLMClient:
    """generate_content_async / generate_json の呼び出し（prompt, system_instruction）を記録するモック。"""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def generate_content_async(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        self.calls.append({"prompt": prompt, "system_instruction": system_instruction})
        return "（テスト用ダミー本文）"

    async def generate_json(self, prompt: str, system_instruction: Optional[str] = None) -> dict[str, Any]:
        self.calls.append({"prompt": prompt, "system_instruction": system_instruction})
        # questionnaire 用に最低限のスキーマを返す
        return {}


def _assert_terminology(text: str, label: str) -> None:
    assert REQUIRED_TERM in text, f"{label}: '{REQUIRED_TERM}' を含むこと"
    for term in FORBIDDEN_TERMS:
        assert term not in text, f"{label}: '{term}' を含まないこと"


# ---------------------------------------------------------------------------
# (a) 用語制約
# ---------------------------------------------------------------------------

def test_terminology_rule_constant() -> None:
    _assert_terminology(TERMINOLOGY_RULE, "TERMINOLOGY_RULE")


def test_implementation_plan_rules_terminology() -> None:
    _assert_terminology(IMPLEMENTATION_PLAN_RULES, "IMPLEMENTATION_PLAN_RULES")


def test_plan_analyzer_system_instruction_terminology() -> None:
    _assert_terminology(PlanAnalyzer.SYSTEM_INSTRUCTION, "PlanAnalyzer.SYSTEM_INSTRUCTION")


def test_questionnaire_system_instruction_terminology() -> None:
    _assert_terminology(qg.QUESTIONNAIRE_SYSTEM_INSTRUCTION, "QUESTIONNAIRE_SYSTEM_INSTRUCTION")


def test_explanation_prompt_terminology() -> None:
    _assert_terminology(EXPLANATION_PROMPT, "EXPLANATION_PROMPT")


def test_recruitment_terminology_rule() -> None:
    _assert_terminology(rnotice.TERMINOLOGY_RULE, "recruitment TERMINOLOGY_RULE")


def test_llm_document_generator_prompts_terminology() -> None:
    """各セクション生成プロンプト＋system_instruction に用語制約が伝播していること。"""
    generator = LLMDocumentGenerator(CapturingLLMClient(), lab_defaults={})
    context = {
        "research_title": "字幕に関する研究",
        "brief_description": "字幕の見やすさを調べる",
        "methodology": "映像を視聴し回答する",
        "target_participants": "成人",
        "duration": 45,
        "participant_count": 30,
        "devices": ["パソコン"],
        "risks": ["目の疲れ"],
        "risk_countermeasures": ["休憩を取る"],
        "reward_amount": 750,
    }

    async def run() -> dict[str, str]:
        return {
            "overview": await generator._generate_overview(context),
            "objective_exp": await generator._generate_experiment_objective(context, False),
            "objective_q": await generator._generate_experiment_objective(context, True),
            "participants_exp": await generator._generate_participants(context, False),
            "participants_q": await generator._generate_participants(context, True),
            "equipment": await generator._generate_equipment(context),
            "procedures_exp": await generator._generate_procedures(context, False),
            "procedures_q": await generator._generate_procedures(context, True),
        }

    asyncio.run(run())
    calls = generator.llm.calls
    assert calls, "LLM が少なくとも一度は呼ばれること"
    for call in calls:
        # 全プロンプトに用語制約（IMPLEMENTATION_PLAN_RULES 経由）が入る
        for term in FORBIDDEN_TERMS:
            assert term not in call["prompt"], f"プロンプトに '{term}' が含まれてはならない"
        assert REQUIRED_TERM in call["prompt"]
        # system_instruction にも用語制約が伝播
        assert call["system_instruction"] is not None
        _assert_terminology(call["system_instruction"], "system_instruction")


# ---------------------------------------------------------------------------
# (b) 実施計画書の章立て（公式参考様式 260127）
# ---------------------------------------------------------------------------

def _outline_titles(outline: list[dict[str, Any]]) -> list[str]:
    return [f"{item['number']}.{item['title']}" for item in outline]


def test_outline_experiment_layout() -> None:
    for builder in (ipg.build_implementation_plan_outline, ldg.build_implementation_plan_outline):
        titles = _outline_titles(builder(is_questionnaire=False))
        joined = "\n".join(titles)
        assert "1.課題名" in joined
        assert "2.研究の概要" in joined
        assert "3.実験方法" in joined
        assert "3-1.実験の目的" in joined
        assert "3-2.実験参加者" in joined
        assert "3-3.実験装置・実験タスク" in joined
        assert "3-4.実験手順" in joined
        # 旧様式の見出しが残っていないこと
        assert "申請研究の概要" not in joined
        # 章番号 3-1 形式が含まれる
        assert any("3-1" in t for t in titles)


def test_outline_questionnaire_branch() -> None:
    for builder in (ipg.build_implementation_plan_outline, ldg.build_implementation_plan_outline):
        titles = _outline_titles(builder(is_questionnaire=True))
        joined = "\n".join(titles)
        assert "3.アンケートの実施方法" in joined
        assert "3-1.アンケートの目的" in joined
        assert "3-2.研究対象者" in joined
        assert "3-3.実施内容" in joined
        # アンケート分岐では「健常者」「被験者」を使わず研究対象者
        for term in FORBIDDEN_TERMS:
            assert term not in joined


def test_implementation_plan_docx_uses_new_headings(tmp_path: Path) -> None:
    """テンプレ版 generate_implementation_plan_docx が新様式見出しで描画されること。"""
    from docx import Document

    form_data = {
        "research_title": "字幕の研究",
        "overview": "本研究では字幕の見やすさを明らかにする。",
        "experiment_objective": "字幕条件ごとの理解度を測定する。",
        "participant_info": "参加者は18歳以上の成人とする。",
        "equipment_description": "パソコンとヘッドホンを用いる。",
        "procedures": ["説明と同意取得", "映像視聴と回答"],
    }
    out = ipg.generate_implementation_plan_docx(form_data, tmp_path, lab_defaults={})
    text = "\n".join(p.text for p in Document(out).paragraphs)
    assert "2.研究の概要" in text
    assert "3.実験方法" in text
    assert "3-1.実験の目的" in text
    assert "3-4.実験手順" in text
    for term in FORBIDDEN_TERMS:
        assert term not in text


# ---------------------------------------------------------------------------
# (c) form_context_builder の safety.* 追加と既存キー保持
# ---------------------------------------------------------------------------

def _build_context(form_data: dict[str, Any]) -> dict[str, Any]:
    settings = load_user_settings(app_config)
    presets = load_preset_bundle(app_config)
    return build_generation_context(form_data, settings, presets)


@pytest.fixture
def base_form_data() -> dict[str, Any]:
    # tests/test_official_renderers.py の generation_context フィクスチャに準拠
    return {
        "title": "Official Render Test",
        "purpose": "Purpose",
        "methodology": "Task and questionnaire",
        "targetDescription": "Adult participants",
        "inclusionCriteria": ["Adults"],
        "exclusionCriteria": ["None"],
        "expectedParticipants": 10,
        "participantsJustification": "Needed for validation",
        "procedures": ["Task and questionnaire"],
        "risks": ["Minor fatigue"],
        "riskCountermeasures": ["Rest"],
        "duration": 60,
        "rewardAmount": 1000,
        "app_config": {
            "applicationType": "new",
            "researchPeriodEndText": "2027年3月31日",
            "invasiveness": False,
        },
    }


def test_context_has_safety_section(base_form_data: dict[str, Any]) -> None:
    context = _build_context(base_form_data)
    assert "safety" in context
    safety = context["safety"]
    assert "measures" in safety
    assert "compensation_text" in safety
    # リスク対策（Rest）が安全性記述に取り込まれること
    assert safety["measures"]
    assert "Rest" in safety["measures"]
    # 既定で国大協保険ありの補償文
    assert "国大協保険" in safety["compensation_text"]


def test_context_safety_no_compensation(base_form_data: dict[str, Any]) -> None:
    base_form_data["app_config"]["hasCompensation"] = "無"
    base_form_data["app_config"]["noCompensationReason"] = "侵襲を伴わないため"
    context = _build_context(base_form_data)
    assert "侵襲を伴わないため" in context["safety"]["compensation_text"]


def test_context_safety_terminology(base_form_data: dict[str, Any]) -> None:
    context = _build_context(base_form_data)
    measures = context["safety"]["measures"]
    for term in FORBIDDEN_TERMS:
        assert term not in measures


def test_context_preserves_existing_keys(base_form_data: dict[str, Any]) -> None:
    """safety 追加で既存の必須セクションが消えていないこと。"""
    context = _build_context(base_form_data)
    expected_keys = {
        "meta", "application", "research", "submission", "principal_investigator",
        "conductors", "domain_head", "facility", "funding", "reward", "participants",
        "participant_list", "procedures", "risks", "risk_countermeasures", "recording",
        "ethics", "data", "consent", "publication", "attachments", "safety",
    }
    missing = expected_keys - set(context.keys())
    assert not missing, f"context から消えたキー: {missing}"
    # 代表的な既存値が維持されること
    assert context["research"]["title"] == "Official Render Test"
    assert context["reward"]["amount"] == 1000
    assert context["participants"]["count"] == 10
