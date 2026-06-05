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


def _as_int_list(value: Any) -> list[int]:
    """整数（分）のリストへ正規化する。数値化できない要素は 0 とする。"""
    if not isinstance(value, list):
        return []
    result: list[int] = []
    for item in value:
        try:
            result.append(int(round(float(str(item).replace(",", "").strip()))))
        except (TypeError, ValueError):
            result.append(0)
    return result


# 公式同意書の用語制約：「被験者」「健常者」は使わない（研究対象者／参加者へ統一）。
# LLM は「被験者内計画」等の統計用語を好み、プロンプト指示だけでは残ることがあるため、
# 生成テキストに対して決定的に置換して提出書類から確実に除く。語の長い順に処理する。
_TERMINOLOGY_REPLACEMENTS: list[tuple[str, str]] = [
    ("被験者間", "参加者間"),   # between-subjects（統計用語）
    ("被験者内", "参加者内"),   # within-subjects（統計用語）
    ("被験者", "研究対象者"),
    ("健常者", "研究対象者"),
]


def normalize_research_terminology(text: Any) -> Any:
    """文字列中の禁止用語（被験者・健常者）を許容語に置換する。文字列以外はそのまま返す。"""
    if not isinstance(text, str) or not text:
        return text
    for forbidden, allowed in _TERMINOLOGY_REPLACEMENTS:
        if forbidden in text:
            text = text.replace(forbidden, allowed)
    return text


def normalize_context_terminology(context: dict[str, Any]) -> dict[str, Any]:
    """context 内の本文用テキスト（文字列）を再帰的に正規化する。

    meta は生入力（source_text 等）の保管領域なので対象外とし、提出書類に流れる
    本文フィールドのみ用語統一する。リスト・ネスト辞書も再帰的にたどる。
    """
    def _walk(value: Any) -> Any:
        if isinstance(value, str):
            return normalize_research_terminology(value)
        if isinstance(value, list):
            return [_walk(item) for item in value]
        if isinstance(value, dict):
            return {key: _walk(item) for key, item in value.items()}
        return value

    for key, value in context.items():
        if key == "meta":
            continue  # 生入力（source_text・followup 等）は書き換えない
        context[key] = _walk(value)
    return context


def _clip_text(value: Any, limit: int = 60_000) -> str:
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

本文生成の方針:
- **入力された研究計画（source_text / followup_answers / 各フィールド）に書かれている内容だけ**を根拠に具体化してください。特定の研究テーマ（字幕・音声・特定の手法名など）を勝手に想定しないでください。
- **入力が議論ログ・打合せメモ等の未整理テキスト（口語・複数発言・脱線・未決・矛盾を含む）の場合**：会話から「決定事項」を抽出して本文化し、脱線・雑談は無視してください。矛盾する記述がある場合は**より新しい/結論側の発言を優先**し、未確定事項は本文に混ぜず missing_items に分けてください。
- 実験デザイン（条件比較・反復測定・カウンターバランス等）、課題、評価指標が入力に含まれる場合は、その範囲で「何を比較するか（独立変数/条件）」「参加者が何をするか（課題）」「何を測るか（従属変数/評価指標）」を明示してください。入力に無いデザインは創作しないでください。
- 実験手順（procedures）には、各手順の所要時間の目安を procedure_minutes に「分（正の整数）」で対応づけてください。procedures と同じ順序・同じ要素数にし、合計が全体の想定所要時間（reward.estimated_minutes）に一致するように配分してください。各手順の文には所要時間を書かず（時間は procedure_minutes だけに入れる）、説明と同意取得・準備・本試行・終了処理などに無理なく割り振ってください。
- アンケート用紙や実験刺激の生成に使えるよう、入力に基づく測定ブロック（conditions と measures）を具体化してください。
- 不明点は本文に曖昧に混ぜず、missing_items に分けてください。
- 入力から妥当に推定した項目は assumptions に「項目・推定値・推定理由」を必ず記録してください（後で利用者が確認できるようにするため）。
- followup_answers に回答がある場合は、それを最優先してください。
- すべての本文は研究倫理審査書類にそのまま入る公式な文体にしてください。入力に含まれる打合せメモ・TODO・予算メモ（例「700円×64人=42,000円」）・「研究メモ」「資料」等の出所表現や金額計算を本文に引用・転記しないでください（人数の根拠は検出力・先行研究・実施可能性などの観点で述べる）。
- 用語は公式同意書の制約に従い「研究対象者」または「参加者」を用いてください。「被験者」「健常者」は使わないでください（実験計画の用語も「参加者内計画／参加者内要因」のように言い換える）。

入力:
{_brief_context(context)}

JSON schema:
{{
  "purpose": "研究目的。2から4文。",
  "significance": "研究意義。2から4文。",
  "method": "研究方法。オンライン実施、条件、課題、評価指標、カウンターバランスを含める。4から8文。",
  "participant_conditions": "対象者条件。1から3文。",
  "count_rationale": "予定人数の根拠。統計的検出力・先行研究の標本規模・実施可能性などの観点で公式申請書の文体で述べる。打合せメモや予算計算（例『700円×64人』）は引用しない。人数が不明なら空文字。",
  "recruitment_method": "募集方法。1から3文。",
  "procedures": ["手順を時系列の文で列挙（各文に所要時間は書かない）"],
  "procedure_minutes": [10, 5, 40, 5],
  "conditions": ["実験条件（独立変数の水準）を列挙。条件比較が無ければ空配列"],
  "measures": ["測定項目（従属変数・評価指標・尺度）を列挙"],
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
        # 各手順の所要時間（分）。procedures と要素数が一致する場合のみ採用し、
        # 同意書裏面の【実験手順】で「（約N分）」として表示する。
        procedure_minutes = _as_int_list(generated.get("procedure_minutes"))
        if procedure_minutes and len(procedure_minutes) == len(procedures):
            enriched["procedure_minutes"] = procedure_minutes
    risks = _as_list(generated.get("risks"))
    if risks:
        enriched["risks"] = risks
    risk_countermeasures = _as_list(generated.get("risk_countermeasures"))
    if risk_countermeasures:
        enriched["risk_countermeasures"] = risk_countermeasures
    data_types = _as_list(generated.get("data_types"))
    if data_types:
        data["types"] = data_types
    # 測定設計（条件・評価指標）をアンケート生成へ橋渡しするため context に保持
    conditions = _as_list(generated.get("conditions"))
    if conditions:
        enriched["conditions"] = conditions
    measures = _as_list(generated.get("measures"))
    if measures:
        enriched["measures"] = measures
    assumptions = generated.get("assumptions")
    if isinstance(assumptions, list):
        # context構築時に提案補完した assumption（meta.llm_assumptions）を消さずに追記する
        existing_assumptions = enriched.setdefault("meta", {}).get("llm_assumptions", []) or []
        enriched["meta"]["llm_assumptions"] = [*existing_assumptions, *assumptions]
    missing_items = generated.get("missing_items")
    if isinstance(missing_items, list):
        existing_missing = enriched.setdefault("meta", {}).get("llm_missing_items", []) or []
        enriched["meta"]["llm_missing_items"] = [*existing_missing, *missing_items]

    # 提出書類に流れる本文の用語を統一（被験者・健常者 → 研究対象者／参加者内 等）
    normalize_context_terminology(enriched)
    return enriched


def flatten_context_for_llm_form_data(form_data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    research = context.get("research", {})
    participants = context.get("participants", {})
    reward = context.get("reward", {})
    data = context.get("data", {})
    pi = context.get("principal_investigator", {}) or {}
    submission = context.get("submission", {}) or {}
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
            "conditions": context.get("conditions", []),
            "measures": context.get("measures", []),
            "risks": context.get("risks", []),
            "riskCountermeasures": context.get("risk_countermeasures", []),
            "rewardRationale": reward.get("rationale", ""),
            "dataTypes": data.get("types", []),
            "managementMethod": data.get("management_method", ""),
            "disposalMethod": data.get("disposal_method", ""),
        }
    )
    # 所要時間・謝礼は context 構築時に提案補完される場合があるため、補完後の値を LLM 生成物にも反映する
    # （元の form_data に 0/空欄 が残っていても、計画書・説明書・アンケートが補完値を参照できるようにする）
    estimated_minutes = reward.get("estimated_minutes")
    if estimated_minutes not in (None, "", 0):
        flattened["duration"] = estimated_minutes
        flattened["duration_minutes"] = estimated_minutes
    reward_amount = reward.get("amount")
    if reward_amount not in (None, "", 0):
        flattened["rewardAmount"] = reward_amount
        flattened["reward_amount"] = reward_amount
    # 問い合わせ先（研究責任者・倫理委員会）は context 側に解決済み。
    # 説明書などの LLM 生成物がプリセット/設定由来の正しい値を参照できるよう、解決済みの値を渡す。
    flattened["principalInvestigator"] = {
        "name": pi.get("name", ""),
        "affiliation": pi.get("affiliation", ""),
        "position": pi.get("position", ""),
        "email": pi.get("email", ""),
        "phone": pi.get("tel", pi.get("phone", "")),
    }
    flattened["ethicsCommittee"] = submission.get("committee_name", "")
    flattened["ethicsCommitteePhone"] = submission.get("office_tel", "")
    return flattened
