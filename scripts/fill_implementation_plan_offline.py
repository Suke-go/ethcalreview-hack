# -*- coding: utf-8 -*-
"""既存セッションの実施計画書を、空セクション（3-1〜3-3）だけフォールバックで埋めて再構築する。

LLM 不調で空になった 3-1.実験の目的 / 3-2.実験参加者 / 3-3.実験装置・実験タスク を、
決定的フォールバック（context 由来の本文）で補完する。良い本文（概要・手順）は保持する。
APIキー不要。

使い方:
    .venv/Scripts/python.exe scripts/fill_implementation_plan_offline.py <session_id>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.services.llm_document_generator import (  # noqa: E402
    LLMDocumentGenerator,
    build_implementation_plan_outline,
)
from app.services.context_text_enricher import normalize_research_terminology  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: fill_implementation_plan_offline.py <session_id>")
        return 1
    sid = sys.argv[1]
    session_dir = ROOT / "backend" / "output" / sid
    snap = json.loads((ROOT / "backend" / "sessions" / f"{sid}.json").read_text(encoding="utf-8"))
    context_snap = snap["steps"]["generate"]["context_snapshot"]

    research = context_snap.get("research", {})
    participants = context_snap.get("participants", {})
    reward = context_snap.get("reward", {})

    # 実施計画書生成器が使う内部 context（generate_implementation_plan と同じ形）を復元
    impl_context = {
        "research_title": research.get("title", ""),
        "brief_description": research.get("purpose", ""),
        "methodology": research.get("method", ""),
        "target_participants": participants.get("criteria", ""),
        "duration": reward.get("estimated_minutes", 60) or 60,
        "participant_count": participants.get("count", "") or "",
        "devices": context_snap.get("devices", []) or [],
        "risks": context_snap.get("risks", []) or [],
        "risk_countermeasures": context_snap.get("risk_countermeasures", []) or [],
        "reward_amount": reward.get("amount", "") or "",
    }

    # 既存の中間結果（良い本文）を読み、空セクションだけフォールバックで埋める
    intermediate = session_dir / "_intermediate_plan.json"
    sections = {}
    if intermediate.exists():
        sections = json.loads(intermediate.read_text(encoding="utf-8")).get("sections", {})

    gen = LLMDocumentGenerator(llm_client=None, lab_defaults={})
    fallbacks = {
        "overview": gen._fallback_overview,
        "experiment_objective": gen._fallback_experiment_objective,
        "participants": gen._fallback_participants,
        "equipment": gen._fallback_equipment,
        "procedures": gen._fallback_procedures,
    }
    filled = []
    for key, fb in fallbacks.items():
        if not str(sections.get(key, "")).strip():
            sections[key] = fb(impl_context)
            filled.append(key)

    # 既存本文の用語も統一（研究者→実験実施者、被験者→研究対象者 等）
    for key in list(sections.keys()):
        sections[key] = normalize_research_terminology(sections[key])

    outline = build_implementation_plan_outline(is_questionnaire=False)
    out = gen._build_implementation_plan_docx(
        sections=sections, context=impl_context, outline=outline, output_dir=session_dir
    )
    print(f"再構築: {out}")
    print(f"フォールバックで補完したセクション: {filled or '（なし＝すべて既存本文あり）'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
