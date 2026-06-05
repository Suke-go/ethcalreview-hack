"""生成済みセッションの「対話的編集」を支える、編集可能フィールドの定義と適用ロジック。

設計の要点（様式を崩さない＝崩れない設計）:
- 編集は docx ではなく構造化データ（context_snapshot）に対して行う。
- 保存後の見た目は、既存のアンカーベースの公式様式レンダラ（official_docx_renderer）で
  再描画する。テンプレートの段組み・チェック欄・項番は一切触らないため、編集しても崩れない。
- ここでは「UIに出す編集可能フィールド」と context 内パスの対応のみを定義する。
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


# 編集可能フィールド定義。
#   key   : フロントとやり取りする識別子
#   path  : context 内のドット区切りパス
#   label : 画面表示名
#   type  : "text"（1行）/ "textarea"（複数行）/ "number" / "list"（改行区切り）
#   group : 画面上のセクション分け
FIELD_DEFS: list[dict[str, str]] = [
    # 研究の基本
    {"key": "title", "path": "research.title", "label": "課題名", "type": "text", "group": "研究の基本"},
    {"key": "purpose", "path": "research.purpose", "label": "目的", "type": "textarea", "group": "研究の基本"},
    {"key": "significance", "path": "research.significance", "label": "意義", "type": "textarea", "group": "研究の基本"},
    {"key": "method", "path": "research.method", "label": "方法", "type": "textarea", "group": "研究の基本"},
    {"key": "period_end_text", "path": "research.period_end_text", "label": "研究期間（終了）", "type": "text", "group": "研究の基本"},
    # 参加者
    {"key": "participants_criteria", "path": "participants.criteria", "label": "対象者条件", "type": "textarea", "group": "参加者"},
    {"key": "participants_count", "path": "participants.count", "label": "予定人数", "type": "number", "group": "参加者"},
    {"key": "count_rationale", "path": "participants.count_rationale", "label": "人数の根拠", "type": "textarea", "group": "参加者"},
    {"key": "inclusion_criteria", "path": "participants.inclusion_criteria", "label": "選択基準（改行区切り）", "type": "list", "group": "参加者"},
    {"key": "exclusion_criteria", "path": "participants.exclusion_criteria", "label": "除外基準（改行区切り）", "type": "list", "group": "参加者"},
    {"key": "recruitment_method", "path": "participants.recruitment_method", "label": "募集方法", "type": "textarea", "group": "参加者"},
    {"key": "gender", "path": "participants.gender", "label": "性別", "type": "text", "group": "参加者"},
    # 手順・リスク
    {"key": "procedures", "path": "procedures", "label": "実験手順（改行区切り）", "type": "list", "group": "手順・リスク"},
    {"key": "procedure_minutes", "path": "procedure_minutes", "label": "各手順の所要時間（分・改行区切り）", "type": "list", "group": "手順・リスク"},
    {"key": "risks", "path": "risks", "label": "想定リスク（改行区切り）", "type": "list", "group": "手順・リスク"},
    {"key": "risk_countermeasures", "path": "risk_countermeasures", "label": "リスク対策（改行区切り）", "type": "list", "group": "手順・リスク"},
    {"key": "safety_measures", "path": "safety.measures", "label": "安全配慮・危険回避", "type": "textarea", "group": "手順・リスク"},
    # 謝礼
    {"key": "reward_amount", "path": "reward.amount", "label": "謝礼（1人あたり・円）", "type": "number", "group": "謝礼"},
    {"key": "reward_type", "path": "reward.type", "label": "謝礼の形式", "type": "text", "group": "謝礼"},
    {"key": "estimated_minutes", "path": "reward.estimated_minutes", "label": "所要時間（分）", "type": "number", "group": "謝礼"},
    # データ管理
    {"key": "data_types", "path": "data.types", "label": "取得データ種別（改行区切り）", "type": "list", "group": "データ管理"},
    {"key": "storage_location", "path": "data.storage_location", "label": "保管場所", "type": "text", "group": "データ管理"},
    {"key": "data_manager", "path": "data.manager", "label": "管理責任者", "type": "text", "group": "データ管理"},
    {"key": "withdrawal_deadline_text", "path": "consent.withdrawal_deadline_text", "label": "撤回期限", "type": "text", "group": "データ管理"},
]

_FIELD_BY_KEY = {f["key"]: f for f in FIELD_DEFS}


def _get_path(context: dict[str, Any], dotted: str) -> Any:
    current: Any = context
    for part in dotted.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _set_path(context: dict[str, Any], dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    current = context
    for part in parts[:-1]:
        nxt = current.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            current[part] = nxt
        current = nxt
    current[parts[-1]] = value


def _to_number(value: Any) -> int | None:
    if value in (None, "", [], {}):
        return None
    try:
        return int(round(float(str(value).replace(",", "").strip())))
    except (TypeError, ValueError):
        return None


def _coerce(field: dict[str, str], value: Any) -> Any:
    """フィールド型に合わせて値を正規化する。"""
    ftype = field["type"]
    if ftype == "list":
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        text = str(value or "")
        return [line.strip() for line in text.splitlines() if line.strip()]
    if ftype == "number":
        return _to_number(value)
    return str(value or "").strip()


def extract_editable_fields(context: dict[str, Any]) -> list[dict[str, Any]]:
    """context から編集可能フィールドの現在値を UI 向けに取り出す。"""
    result: list[dict[str, Any]] = []
    for field in FIELD_DEFS:
        raw = _get_path(context, field["path"])
        if field["type"] == "list":
            value = raw if isinstance(raw, list) else ([] if raw in (None, "") else [str(raw)])
            display = "\n".join(str(v) for v in value)
        elif field["type"] == "number":
            num = _to_number(raw)
            display = "" if num is None else str(num)
            value = num
        else:
            value = "" if raw is None else str(raw)
            display = value
        result.append(
            {
                "key": field["key"],
                "label": field["label"],
                "type": field["type"],
                "group": field["group"],
                "value": value,
                "text": display,
            }
        )
    return result


def apply_editable_fields(context: dict[str, Any], edits: dict[str, Any]) -> dict[str, Any]:
    """編集値を context に反映した新しい context を返す（元の context は変更しない）。

    - 未知のキーは無視する（安全側）。
    - reward.enabled / reward.total_amount / participant_list は、謝礼・人数の変更に
      追従して再計算する（書類間の整合を保つ）。
    """
    updated = deepcopy(context)
    for key, value in (edits or {}).items():
        field = _FIELD_BY_KEY.get(key)
        if not field:
            continue
        _set_path(updated, field["path"], _coerce(field, value))

    # --- 整合性の再計算 ---
    reward = updated.setdefault("reward", {})
    participants = updated.setdefault("participants", {})

    amount = _to_number(reward.get("amount"))
    count = _to_number(participants.get("count"))
    reward["enabled"] = bool(amount and amount > 0)
    if amount and amount > 0 and count and count > 0:
        reward["total_amount"] = amount * count
    else:
        # 謝礼0/未入力 または 人数未確定 → 総額は未定（書類側は「(未定)」表示になる）
        reward["total_amount"] = None

    # 参加者リストの集計用フィールドも追従
    participant_list = updated.setdefault("participant_list", {})
    participant_list["planned_count"] = participants.get("count")
    participant_list["reward_per_person"] = reward.get("amount")
    participant_list["total_reward"] = reward.get("total_amount")

    # 手順の所要時間は、手順数と一致しないと表示崩れになるため不一致なら破棄
    procs = updated.get("procedures") or []
    minutes = updated.get("procedure_minutes") or []
    minutes = [m for m in (_to_number(x) for x in minutes) if m is not None]
    if minutes and len(minutes) == len(procs):
        updated["procedure_minutes"] = minutes
    elif "procedure_minutes" in updated:
        # 不一致 or 空 → 併記しない（フィールド自体を削除）
        updated.pop("procedure_minutes", None)

    return updated
