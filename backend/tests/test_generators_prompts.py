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


class EmptyLLMClient:
    """常に空本文を返すモック（推論モデルの空応答を模擬）。"""

    async def generate_content_async(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        return ""

    async def generate_json(self, prompt: str, system_instruction: Optional[str] = None) -> dict[str, Any]:
        return {}


def _assert_terminology(text: str, label: str) -> None:
    assert REQUIRED_TERM in text, f"{label}: '{REQUIRED_TERM}' を含むこと"
    for term in FORBIDDEN_TERMS:
        assert term not in text, f"{label}: '{term}' を含まないこと"


def test_implementation_plan_sections_fallback_when_llm_empty() -> None:
    """LLMが空応答でも 3-1〜3-4・概要が空にならず、決定的フォールバックで埋まること。

    （以前は _call_llm が例外/空で "" を返し、3-1 実験の目的・3-2 実験参加者・
    3-3 実験装置が空欄のまま出力されていた。）
    """
    gen = LLMDocumentGenerator(EmptyLLMClient(), lab_defaults={})
    context = {
        "research_title": "字幕可視化の検証",
        "brief_description": "韻律を字幕に反映し理解を助けるか検証する",
        "methodology": "短い映像を4条件で視聴し認知負荷を測定する",
        "target_participants": "英語を第二言語とする18歳以上の成人",
        "duration": 60,
        "participant_count": 64,
        "devices": ["パソコン", "ヘッドホン"],
        "risks": ["眼精疲労"],
        "risk_countermeasures": ["適宜休憩"],
        "reward_amount": 1000,
    }
    sections = {
        "objective": asyncio.run(gen._generate_experiment_objective(context)),
        "participants": asyncio.run(gen._generate_participants(context)),
        "equipment": asyncio.run(gen._generate_equipment(context)),
        "procedures": asyncio.run(gen._generate_procedures(context)),
        "overview": asyncio.run(gen._generate_overview(context)),
    }
    for name, text in sections.items():
        assert text and text.strip(), f"{name} がフォールバックで埋まること"
        for term in FORBIDDEN_TERMS:
            assert term not in text, f"{name}: '{term}' を含まないこと"
    # 参加者フォールバックは予定人数を反映する
    assert "64名" in sections["participants"]


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


def test_normalize_research_terminology_rules() -> None:
    """用語の決定的正規化（被験者/健常者→研究対象者・参加者、研究者→実験実施者）。"""
    from app.services.context_text_enricher import normalize_research_terminology as norm

    assert norm("研究者は参加者に説明する。") == "実験実施者は参加者に説明する。"
    assert norm("被験者内計画で研究者が測定する。") == "参加者内計画で実験実施者が測定する。"
    assert norm("健常者を対象とする。") == "研究対象者を対象とする。"
    # 別概念・役職は保護される
    assert norm("共同研究者と連携する。") == "共同研究者と連携する。"
    assert norm("研究責任者は善甫である。") == "研究責任者は善甫である。"
    assert norm("研究対象者を募集する。") == "研究対象者を募集する。"
    assert norm("研究担当者へ申し出る。") == "研究担当者へ申し出る。"


def test_post_process_normalizes_researcher_term() -> None:
    """LLM生成物の後処理でも「研究者」が「実験実施者」に統一されること。"""
    gen = LLMDocumentGenerator(EmptyLLMClient(), lab_defaults={})
    out = gen._post_process("研究者は参加者へ説明する。")
    assert "研究者" not in out
    assert "実験実施者は参加者へ説明する。" in out


def test_explanation_contact_uses_principal_investigator() -> None:
    """参加者説明書の問い合わせ先が form_data の principalInvestigator から埋まること。

    （以前は lab_defaults.lab_info からのみ取得しており、設定由来の研究責任者が
    反映されず「■ 研究責任者」が空欄になっていた。）
    """
    generator = ExplanationGenerator(llm_client=None, lab_defaults={})
    form_data = {
        "title": "字幕に関する研究",
        "principalInvestigator": {
            "name": "善甫 啓一",
            "affiliation": "筑波大学 システム情報系",
            "position": "准教授",
            "email": "zempo@example.ac.jp",
            "phone": "029-000-0000",
        },
        "ethicsCommittee": "筑波大学 システム情報系 研究倫理委員会",
        "ethicsCommitteePhone": "029-111-1111",
    }
    context = generator._build_context(form_data)
    assert context["pi_name"] == "善甫 啓一"
    assert context["pi_affiliation"] == "筑波大学 システム情報系"
    assert context["pi_position"] == "准教授"
    assert context["pi_email"] == "zempo@example.ac.jp"
    assert context["pi_phone"] == "029-000-0000"
    assert context["ethics_committee"] == "筑波大学 システム情報系 研究倫理委員会"
    assert context["ethics_phone"] == "029-111-1111"


def test_explanation_contact_falls_back_to_lab_defaults() -> None:
    """principalInvestigator が無い場合は lab_defaults にフォールバックすること。"""
    generator = ExplanationGenerator(
        llm_client=None,
        lab_defaults={"lab_info": {"pi_name": "予備 太郎", "pi_affiliation": "予備所属"}},
    )
    context = generator._build_context({"title": "x"})
    assert context["pi_name"] == "予備 太郎"
    assert context["pi_affiliation"] == "予備所属"


def test_flatten_passes_resolved_contact() -> None:
    """flatten が context の解決済み研究責任者・倫理委員会を form_data へ渡すこと。"""
    from app.services.context_text_enricher import flatten_context_for_llm_form_data

    context = {
        "research": {"title": "t"},
        "principal_investigator": {
            "name": "善甫 啓一",
            "affiliation": "筑波大学 システム情報系",
            "position": "准教授",
            "email": "zempo@example.ac.jp",
            "tel": "029-000-0000",
        },
        "submission": {"committee_name": "倫理委員会", "office_tel": "029-111-1111"},
    }
    flat = flatten_context_for_llm_form_data({}, context)
    assert flat["principalInvestigator"]["name"] == "善甫 啓一"
    assert flat["principalInvestigator"]["phone"] == "029-000-0000"
    assert flat["ethicsCommittee"] == "倫理委員会"
    assert flat["ethicsCommitteePhone"] == "029-111-1111"


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
