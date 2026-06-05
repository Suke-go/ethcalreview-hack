"""対話的編集（崩れない設計）の中核 editable_context の検証。

- extract: context から型付きの編集フィールドを取り出す
- apply  : 編集値を context に反映し、謝礼・人数・手順時間の整合を再計算する
"""
from __future__ import annotations

from app.services.editable_context import (
    FIELD_DEFS,
    apply_editable_fields,
    extract_editable_fields,
)


def _sample_context() -> dict:
    return {
        "research": {"title": "字幕の研究", "purpose": "理解を助けるか検証", "method": "視聴と回答"},
        "participants": {"criteria": "成人", "count": 30, "inclusion_criteria": ["18歳以上"]},
        "procedures": ["説明と同意", "本試行", "終了"],
        "risks": ["眼精疲労"],
        "reward": {"enabled": True, "amount": 1000, "type": "Amazonギフトカード", "estimated_minutes": 60, "total_amount": 30000},
        "data": {"types": ["回答ログ"], "manager": "担当者"},
        "consent": {"withdrawal_deadline_text": "署名から90日後"},
    }


def test_extract_returns_typed_fields() -> None:
    fields = extract_editable_fields(_sample_context())
    by_key = {f["key"]: f for f in fields}
    # 主要フィールドが取り出せる
    assert by_key["title"]["value"] == "字幕の研究"
    assert by_key["participants_count"]["value"] == 30
    # list 型は改行区切りテキストで返る
    assert by_key["procedures"]["type"] == "list"
    assert by_key["procedures"]["text"] == "説明と同意\n本試行\n終了"
    # 全フィールド定義が出力に含まれる
    assert len(fields) == len(FIELD_DEFS)


def test_apply_updates_text_and_list() -> None:
    ctx = _sample_context()
    updated = apply_editable_fields(ctx, {
        "title": "新しい課題名",
        "procedures": "A\nB\nC\nD",
    })
    assert updated["research"]["title"] == "新しい課題名"
    assert updated["procedures"] == ["A", "B", "C", "D"]
    # 元の context は変更されない（イミュータブル）
    assert ctx["research"]["title"] == "字幕の研究"


def test_apply_recomputes_reward_total() -> None:
    ctx = _sample_context()
    updated = apply_editable_fields(ctx, {"reward_amount": 750, "participants_count": 64})
    assert updated["reward"]["amount"] == 750
    assert updated["participants"]["count"] == 64
    assert updated["reward"]["total_amount"] == 750 * 64
    assert updated["reward"]["enabled"] is True
    # 参加者リスト集計も追従
    assert updated["participant_list"]["total_reward"] == 48000


def test_apply_reward_zero_marks_undecided_total() -> None:
    ctx = _sample_context()
    updated = apply_editable_fields(ctx, {"reward_amount": 0})
    assert updated["reward"]["enabled"] is False
    assert updated["reward"]["total_amount"] is None


def test_apply_procedure_minutes_length_match() -> None:
    ctx = _sample_context()  # procedures has 3 items
    ok = apply_editable_fields(ctx, {"procedure_minutes": "10\n40\n10"})
    assert ok["procedure_minutes"] == [10, 40, 10]
    # 不一致なら併記しない（破棄）
    bad = apply_editable_fields(ctx, {"procedure_minutes": "10\n40"})
    assert "procedure_minutes" not in bad


def test_apply_ignores_unknown_keys() -> None:
    ctx = _sample_context()
    updated = apply_editable_fields(ctx, {"__nope__": "x", "title": "T"})
    assert updated["research"]["title"] == "T"
    assert "__nope__" not in updated
