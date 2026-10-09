"""書類間で共有する撤回・補償の説明文。"""
from __future__ import annotations


def withdrawal_policy(days: int | None) -> tuple[str, str]:
    """期限設定と、参加中止・データ提供同意の撤回を分けた説明を返す。"""
    if days is None:
        deadline = "研究成果の公表前まで"
        data_withdrawal = f"データ提供の同意は{deadline}撤回できます"
    else:
        deadline = f"同意書署名日から{days}日以内"
        data_withdrawal = f"データ提供の同意は{deadline}であれば撤回できます"

    notice = (
        "研究への参加は任意です。実験への参加はいつでも中止でき、中止しても不利益はありません。"
        f"{data_withdrawal}。撤回の申し出があった場合、削除可能な当該研究データを削除します。"
        "ただし、既に仮名加工したうえで集計・公表したデータは、個別に特定して削除できません。"
    )
    return deadline, notice


def compensation_policy(has_compensation: bool, reason: str = "") -> str:
    if has_compensation:
        return (
            "本研究への参加に起因して健康被害が生じた場合は、"
            "国立大学法人総合損害保険（国大協保険）により対応します。"
        )
    reason = str(reason or "").strip()
    if reason:
        return f"本研究では健康被害に対する補償は行いません（理由：{reason}）。"
    return "本研究では健康被害に対する補償は行いません。"
