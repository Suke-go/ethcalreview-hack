from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.services.llm_client import LLMClient


ENRICHMENT_SYSTEM_INSTRUCTION = """
あなたは筑波大学の研究倫理審査書類の本文作成補助者です。
公式様式のレイアウト、項番、チェック欄は変更しません。あなたの役割は、入力された研究計画から本文欄に入れる具体的な日本語文だけを作ることです。

制約:
- ユーザー入力をそのまま貼り付けない。
- 入力にない事実、日付、人数、固有名詞を創作しない。
- 「可能」「想定」だけで済ませず、研究計画書として実施内容を断定調で具体化する。
- 在宅オンライン実施が基本の場合、「必要に応じてラボ実施も可」のような曖昧な表現は避ける。
- 実施形態が不明な場合は本文に混ぜず、missing_items に確認事項として出す。
- 研究期間、責任者、関係組織の長、謝金財源などの行政的項目を創作しない。
- 研究内容の本文と、要確認事項を混ぜない。
- 返答は JSON のみ。
"""


def _set_if_present(target: dict[str, Any], key: str, value: Any) -> None:
    if value not in (None, "", [], {}):
        target[key] = value


def _as_list(value: Any) -> list[str]:
    if value in (None, "", [], {}):
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()]


def _clip_text(value: Any, limit: int = 18_000) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[truncated]"


def _brief_context(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_text": _clip_text(context.get("meta", {}).get("source_text", "")),
        "followup_answers": context.get("meta", {}).get("followup_answers", {}),
        "research": context.get("research", {}),
        "participants": context.get("participants", {}),
        "procedures": context.get("procedures", []),
        "risks": context.get("risks", []),
        "risk_countermeasures": context.get("risk_countermeasures", []),
        "reward": context.get("reward", {}),
        "data": context.get("data", {}),
        "facility": context.get("facility", {}),
        "funding": context.get("funding", {}),
    }


async def enrich_generation_context_with_llm(
    context: dict[str, Any],
    llm_client: LLMClient,
) -> dict[str, Any]:
    enriched = deepcopy(context)
    prompt = f"""
以下の研究計画コンテキストを、研究倫理審査書類に入る具体的な本文へ再構成してください。

特に次を必ず具体化してください。
- 参加者条件
- 目的
- 意義
- 方法
- 所要時間
- 考えられるリスク
- 謝礼
- 取得する研究データ
- データ管理方法

この研究では、複数条件（無字幕・通常字幕・Dynamik・提案手法）による反復測定デザイン、短い講演クリップ、理解確認、韻律に基づく強調語同定、話者の態度・意図推定、主観的認知負荷評価、追加ブロックとして音声劣化条件における通常字幕と韻律ベース字幕の比較、条件順序のカウンターバランスを含む場合があります。入力に含まれる範囲でこれらを自然な研究計画本文にしてください。

本文生成の方針:
- 「何を比較するか」「参加者が何をするか」「何を測るか」を明示してください。
- アンケート用紙や実験刺激の生成に使えるよう、測定ブロックを具体化してください。
- 不明点は本文に曖昧に混ぜず、missing_items に分けてください。
- followup_answers に回答がある場合は、それを優先してください。

入力:
{_brief_context(context)}

JSON schema:
{{
  "purpose": "研究目的。2から4文。",
  "significance": "研究意義。2から4文。",
  "method": "研究方法。オンライン実施、条件、課題、評価指標、カウンターバランスを含める。4から8文。",
  "participant_conditions": "対象者条件。1から3文。",
  "count_rationale": "予定人数の根拠。人数が不明なら空文字。",
  "recruitment_method": "募集方法。1から3文。",
  "procedures": ["手順を時系列の文で列挙"],
  "risks": ["考えられるリスクを列挙"],
  "risk_countermeasures": ["risks と同じ順序で対策を列挙"],
  "data_types": ["取得する研究データを具体的に列挙"],
  "reward_rationale": "謝礼の説明。単価と所要時間に矛盾が出ないように説明。",
  "data_management_method": "データ管理方法。1から3文。",
  "data_disposal_method": "データ処分方法。1から3文。",
  "assumptions": [
    {{"field": "推定した項目", "value": "推定値", "reason": "推定理由"}}
  ],
  "missing_items": [
    {{"field": "確認が必要な項目", "question": "ユーザーに確認すべき質問", "blocking": true}}
  ]
}}
"""
    generated = await llm_client.generate_json(prompt, ENRICHMENT_SYSTEM_INSTRUCTION)

    research = enriched.setdefault("research", {})
    participants = enriched.setdefault("participants", {})
    data = enriched.setdefault("data", {})
    reward = enriched.setdefault("reward", {})

    _set_if_present(research, "purpose", generated.get("purpose"))
    _set_if_present(research, "significance", generated.get("significance"))
    _set_if_present(research, "method", generated.get("method"))
    _set_if_present(participants, "criteria", generated.get("participant_conditions"))
    _set_if_present(participants, "count_rationale", generated.get("count_rationale"))
    _set_if_present(participants, "recruitment_method", generated.get("recruitment_method"))
    _set_if_present(reward, "rationale", generated.get("reward_rationale"))
    _set_if_present(data, "management_method", generated.get("data_management_method"))
    _set_if_present(data, "disposal_method", generated.get("data_disposal_method"))

    procedures = _as_list(generated.get("procedures"))
    if procedures:
        enriched["procedures"] = procedures
    risks = _as_list(generated.get("risks"))
    if risks:
        enriched["risks"] = risks
    risk_countermeasures = _as_list(generated.get("risk_countermeasures"))
    if risk_countermeasures:
        enriched["risk_countermeasures"] = risk_countermeasures
    data_types = _as_list(generated.get("data_types"))
    if data_types:
        data["types"] = data_types
    assumptions = generated.get("assumptions")
    if isinstance(assumptions, list):
        enriched.setdefault("meta", {})["llm_assumptions"] = assumptions
    missing_items = generated.get("missing_items")
    if isinstance(missing_items, list):
        enriched.setdefault("meta", {})["llm_missing_items"] = missing_items

    return enriched


def flatten_context_for_llm_form_data(form_data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    research = context.get("research", {})
    participants = context.get("participants", {})
    reward = context.get("reward", {})
    data = context.get("data", {})
    flattened = dict(form_data)
    flattened.update(
        {
            "research_title": research.get("title", ""),
            "title": research.get("title", ""),
            "research_purpose": research.get("purpose", ""),
            "purpose": research.get("purpose", ""),
            "research_significance": research.get("significance", ""),
            "significance": research.get("significance", ""),
            "research_method": research.get("method", ""),
            "methodology": research.get("method", ""),
            "target_participants": participants.get("criteria", ""),
            "targetDescription": participants.get("criteria", ""),
            "participant_count_reason": participants.get("count_rationale", ""),
            "participantsJustification": participants.get("count_rationale", ""),
            "recruitmentMethod": participants.get("recruitment_method", ""),
            "procedures": context.get("procedures", []),
            "risks": context.get("risks", []),
            "riskCountermeasures": context.get("risk_countermeasures", []),
            "rewardRationale": reward.get("rationale", ""),
            "dataTypes": data.get("types", []),
            "managementMethod": data.get("management_method", ""),
            "disposalMethod": data.get("disposal_method", ""),
        }
    )
    return flattened
