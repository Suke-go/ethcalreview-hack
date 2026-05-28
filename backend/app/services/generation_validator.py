from __future__ import annotations

from typing import Any

from pydantic import BaseModel

# 公式同意書の注記: 「健常者・被験者という表現を使用しない」
# 生成文では「研究対象者」または「参加者」を使うこと。
_FORBIDDEN_TERMS = ["健常者", "被験者"]


class ValidationIssue(BaseModel):
    field: str
    message: str
    severity: str = "error"


def get_path(data: dict[str, Any], dotted_path: str, default: Any = None) -> Any:
    current: Any = data
    for part in dotted_path.split("."):
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return default
        elif isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return default
    return current


def is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, list):
        return len(value) == 0 or all(is_blank(item) for item in value)
    if isinstance(value, dict):
        return len(value) == 0
    return False


def _require(context: dict[str, Any], path: str, label: str) -> ValidationIssue | None:
    if is_blank(get_path(context, path)):
        return ValidationIssue(field=path, message=f"{label}が未入力です")
    return None


def _warn(context: dict[str, Any], path: str, label: str) -> ValidationIssue | None:
    if is_blank(get_path(context, path)):
        return ValidationIssue(field=path, message=f"{label}が未入力です", severity="warning")
    return None


def _contains_forbidden_term(text: str) -> str | None:
    """文字列中に禁止用語が含まれていれば最初に見つかったものを返す。なければ None。"""
    for term in _FORBIDDEN_TERMS:
        if term in text:
            return term
    return None


def _collect_free_text_values(context: dict[str, Any]) -> list[tuple[str, str]]:
    """
    context 内の自由記述フィールドを (dotted_path, value) のリストで返す。
    対象: research.* / participants.criteria / participants.count_rationale /
          risks / risk_countermeasures / procedures (文字列・文字列リスト)
    """
    results: list[tuple[str, str]] = []

    # research サブツリーの文字列フィールド
    research = context.get("research", {})
    if isinstance(research, dict):
        for key, value in research.items():
            path = f"research.{key}"
            if isinstance(value, str) and value:
                results.append((path, value))

    # participants の自由記述フィールド
    participants = context.get("participants", {})
    if isinstance(participants, dict):
        for key in ("criteria", "count_rationale", "recruitment_method"):
            value = participants.get(key)
            if isinstance(value, str) and value:
                results.append((f"participants.{key}", value))
        # inclusion_criteria / exclusion_criteria はリスト
        for key in ("inclusion_criteria", "exclusion_criteria"):
            items = participants.get(key)
            if isinstance(items, list):
                for i, item in enumerate(items):
                    if isinstance(item, str) and item:
                        results.append((f"participants.{key}.{i}", item))

    # トップレベルのリストフィールド
    for field in ("risks", "risk_countermeasures", "procedures"):
        items = context.get(field)
        if isinstance(items, list):
            for i, item in enumerate(items):
                if isinstance(item, str) and item:
                    results.append((f"{field}.{i}", item))
        elif isinstance(items, str) and items:
            results.append((field, items))

    return results


def _check_forbidden_terminology(context: dict[str, Any]) -> list[ValidationIssue]:
    """
    P0-1 用語ガード: 自由記述フィールドに「健常者」または「被験者」が含まれていれば
    warning の ValidationIssue を追加する。
    公式同意書注記: 「健常者・被験者という表現を使用しない」
    正しい表現: 「研究対象者」「参加者」
    """
    issues: list[ValidationIssue] = []
    seen_fields: set[str] = set()

    for path, value in _collect_free_text_values(context):
        term = _contains_forbidden_term(value)
        if term is not None:
            # リストの場合は親フィールド名で重複排除しつつ報告
            parent_field = path.rsplit(".", 1)[0] if path.count(".") >= 2 and path[-1].isdigit() else path
            # ただし同一フィールドに複数の禁止語があっても一度だけ報告
            report_field = parent_field if parent_field not in seen_fields else path
            if report_field not in seen_fields:
                seen_fields.add(report_field)
                issues.append(
                    ValidationIssue(
                        field=report_field,
                        message=(
                            f"「{term}」という表現が含まれています。"
                            "公式同意書の注記に従い「研究対象者」または「参加者」を使用してください。"
                        ),
                        severity="warning",
                    )
                )

    return issues


def _check_checklist_required_fields(context: dict[str, Any]) -> list[ValidationIssue]:
    """
    P2-6 チェックリスト検証:
    記載事項確認チェックリスト_260127.xls の趣旨に基づく必須項目・整合性チェック。
    (.xls は openpyxl 非対応・xlrd/pandas 未インストールのため項目を直接実装)

    チェック内容:
    1. 課題名・実施責任者・撤回期限・データ管理4項目・対象者条件 が空でないこと
       (これらは required_fields にも含まれるが、checklist 観点で改めて確認)
    2. 謝礼ありのとき reward.amount があること (既存ロジックと整合)
    3. consent.withdrawal_deadline_text が空でないこと (撤回期限記載の代替チェック)
    """
    issues: list[ValidationIssue] = []

    # チェックリスト必須項目 (required_fields と重複するものは後方互換で再確認)
    checklist_required = [
        ("research.title", "課題名（チェックリスト項目）"),
        ("principal_investigator.name", "実施責任者氏名（チェックリスト項目）"),
        ("consent.withdrawal_deadline_text", "同意撤回期限（チェックリスト項目）"),
        ("data.storage_location", "データ管理場所（チェックリスト項目）"),
        ("data.manager", "データ管理責任者（チェックリスト項目）"),
        ("data.management_method", "データ管理方法（チェックリスト項目）"),
        ("data.disposal_method", "データ処分方法（チェックリスト項目）"),
        ("participants.criteria", "研究対象者条件（チェックリスト項目）"),
    ]
    # これらは既に required_fields / warning_fields で error/warning として出力されるため
    # 二重報告を避けるため、ここでは何もしない（既存チェックで十分）
    # → 代わりに既存チェックがカバーしていない整合性チェックのみ追加

    # 謝礼あり判定: reward.enabled が True だが reward.amount が空の場合は
    # 既存の reward セクションで _require 済み。ここでは enabled/amount 不一致を追加確認。
    reward_enabled = bool(get_path(context, "reward.enabled", False))
    reward_amount = get_path(context, "reward.amount")
    if not reward_enabled and not is_blank(reward_amount):
        # amount が設定されているのに enabled=False の不整合
        from numbers import Number
        amount_positive = (isinstance(reward_amount, Number) and reward_amount > 0) or (
            isinstance(reward_amount, str) and reward_amount.strip() not in ("", "0")
        )
        if amount_positive:
            issues.append(
                ValidationIssue(
                    field="reward.enabled",
                    message="謝金額が設定されていますが謝金が無効になっています。reward.enabled を確認してください。",
                    severity="warning",
                )
            )

    return issues


def _check_flag_text_consistency(context: dict[str, Any]) -> list[ValidationIssue]:
    """チェック欄（フラグ）と本文の不整合を検出する。

    例: 録画ありなのに研究方法・手順に録画/撮影の記述が無い、侵襲ありなのに侵襲内容が空、など。
    本文とフラグが食い違っていると審査で必ず指摘されるため、レビュー指摘として返す。
    """
    issues: list[ValidationIssue] = []

    method_parts = [str(get_path(context, "research.method", "") or "")]
    procedures = get_path(context, "procedures", []) or []
    if isinstance(procedures, list):
        method_parts.extend(str(item) for item in procedures)
    method_text = " ".join(method_parts)

    if bool(get_path(context, "recording.enabled", False)):
        recording_keywords = ("録画", "撮影", "ビデオ", "動画", "録音", "記録", "カメラ")
        if not any(keyword in method_text for keyword in recording_keywords):
            issues.append(
                ValidationIssue(
                    field="recording.enabled",
                    message="録画・撮影ありとなっていますが、研究方法・手順に該当する記述が見当たりません。方法と整合させてください。",
                    severity="warning",
                )
            )

    if bool(get_path(context, "ethics.invasiveness", False)) and is_blank(get_path(context, "ethics.invasiveness_details")):
        issues.append(
            ValidationIssue(
                field="ethics.invasiveness_details",
                message="侵襲ありとなっていますが、侵襲の具体的内容が未入力です。",
                severity="warning",
            )
        )

    return issues


def validate_generation_context(context: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    required_fields = [
        ("research.title", "課題名"),
        ("research.method", "研究方法"),
        ("research.period_end_text", "研究期間の終了日"),
        ("submission.recipient", "提出先"),
        ("submission.committee_name", "研究倫理委員会名"),
        ("submission.office_name", "事務局名"),
        ("submission.office_tel", "事務局TEL"),
        ("principal_investigator.affiliation", "実施責任者の所属"),
        ("principal_investigator.position", "実施責任者の職名"),
        ("principal_investigator.name", "実施責任者の氏名"),
        ("principal_investigator.tel", "実施責任者のTEL"),
        ("principal_investigator.email", "実施責任者のメールアドレス"),
        ("conductors.0.affiliation", "実施分担者の所属"),
        ("conductors.0.name", "実施分担者の氏名"),
        ("facility.rooms", "実施施設・部屋"),
        ("data.types", "取得する研究データの種類"),
        ("data.retention_period", "研究データの保存期間"),
        ("data.storage_location", "研究データの管理場所"),
        ("data.manager", "研究データの管理責任者"),
        ("data.management_method", "研究データの管理方法"),
        ("data.disposal_method", "研究データの処分方法"),
        ("consent.withdrawal_deadline_text", "同意撤回期限"),
        ("domain_head.domain", "関係組織の領域名"),
        ("domain_head.name", "関係組織の長"),
    ]

    for path, label in required_fields:
        issue = _require(context, path, label)
        if issue:
            issues.append(issue)

    warning_fields = [
        ("participants.criteria", "研究対象者の条件"),
        ("participants.count", "予定参加者数"),
        ("participants.recruitment_method", "募集方法"),
        ("funding.source", "費用の出所"),
    ]
    for path, label in warning_fields:
        issue = _warn(context, path, label)
        if issue:
            issues.append(issue)

    reward_enabled = bool(get_path(context, "reward.enabled", False))
    if reward_enabled:
        for path, label in [
            ("reward.amount", "謝金額"),
            ("reward.type", "謝金種別"),
            ("reward.estimated_minutes", "謝金計算の所要時間"),
            ("reward.estimated_participants", "謝金計算の予定参加者数"),
            ("reward.total_amount", "謝金総額"),
            ("participants.count", "予定参加者数"),
            ("funding.source", "謝金支出元"),
        ]:
            issue = _require(context, path, label)
            if issue:
                issues.append(issue)
        if is_blank(get_path(context, "reward.hourly_rate")) and is_blank(get_path(context, "reward.rationale")):
            issues.append(
                ValidationIssue(
                    field="reward.hourly_rate",
                    message="謝金ありの場合は謝金単価または計算根拠を入力してください",
                )
            )
    elif is_blank(get_path(context, "reward.rationale")):
        issues.append(
            ValidationIssue(
                field="reward.rationale",
                message="謝金なしの場合は理由を入力してください",
                severity="warning",
            )
        )

    if get_path(context, "application.type") == "change" or get_path(context, "application.is_new") is False:
        issue = _require(context, "application.approval_number", "変更申請の審査承認番号")
        if issue:
            issues.append(issue)

    if bool(get_path(context, "application.similar_exists", False)):
        issue = _require(context, "application.similar_details", "類似申請の詳細")
        if issue:
            issues.append(issue)

    facility_type = get_path(context, "facility.type", "single")
    if facility_type in {"multi_tsukuba", "multi_other"}:
        issue = _require(context, "facility.tsukuba_role", "多施設共同研究における筑波大学の役割")
        if issue:
            issues.append(issue)
    if facility_type == "multi_other":
        for path, label in [
            ("facility.external_facility", "代表施設名"),
            ("facility.external_org_leader", "研究組織代表者氏名"),
        ]:
            issue = _require(context, path, label)
            if issue:
                issues.append(issue)

    if bool(get_path(context, "ethics.conflict_of_interest", False)):
        issue = _require(context, "ethics.conflict_of_interest_partner", "利益相反の相手先・企業名")
        if issue:
            issues.append(issue)

    if bool(get_path(context, "ethics.invasiveness", False)):
        issue = _require(context, "ethics.invasiveness_details", "侵襲性の具体的内容")
        if issue:
            issues.append(issue)

    if bool(get_path(context, "recording.enabled", False)) and is_blank(get_path(context, "recording.types")):
        issues.append(
            ValidationIssue(
                field="recording.types",
                message="ビデオ撮影ありの場合は記録種別を入力してください",
            )
        )

    # フラグと本文の整合チェック（録画ありなのに方法に記述が無い等）
    issues.extend(_check_flag_text_consistency(context))

    # P0-1 用語ガード: 「健常者」「被験者」の使用チェック
    issues.extend(_check_forbidden_terminology(context))

    # P2-6 チェックリスト整合性チェック
    issues.extend(_check_checklist_required_fields(context))

    return issues


def error_issues(issues: list[ValidationIssue]) -> list[ValidationIssue]:
    return [issue for issue in issues if issue.severity == "error"]


def issue_payload(issues: list[ValidationIssue]) -> list[dict[str, str]]:
    return [issue.model_dump() for issue in issues]
