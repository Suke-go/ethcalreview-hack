"""生成ドラフトのレビュー指摘サマリ（人間が「しばく」ための一覧）。

検証結果（過不足・整合性・用語）と、LLMが入力から自動推定した項目（assumptions）・
要確認項目（missing_items）を1つに統合し、レビュー用の構造化データと Markdown を作る。
中断せずドラフトを出す方針のため、足りない所はここに集約して可視化する。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.generation_validator import issue_payload, validate_generation_context


def build_review_notes(context: dict[str, Any]) -> dict[str, Any]:
    """context からレビュー指摘サマリ（構造化）を作る。"""
    issues = issue_payload(validate_generation_context(context))
    errors = [issue for issue in issues if issue.get("severity") == "error"]
    warnings = [issue for issue in issues if issue.get("severity") != "error"]

    meta = context.get("meta", {}) if isinstance(context, dict) else {}
    assumptions = meta.get("llm_assumptions", []) or []
    missing_items = meta.get("llm_missing_items", []) or []

    return {
        "errors": errors,            # 提出前に埋めるべき不足（提案で仮埋め済みでも要確認）
        "warnings": warnings,        # 任意・整合性・用語などの注意
        "assumptions": assumptions,  # 入力から自動推定して補完した項目（要確認）
        "missing_items": missing_items,  # LLMが「確認が必要」と判断した項目
        "counts": {
            "errors": len(errors),
            "warnings": len(warnings),
            "assumptions": len(assumptions),
            "missing_items": len(missing_items),
        },
    }


def _format_issue(issue: dict[str, Any]) -> str:
    field = issue.get("field", "")
    message = issue.get("message", "")
    return f"- [ ] **{field}**：{message}"


def _format_assumption(item: dict[str, Any]) -> str:
    if not isinstance(item, dict):
        return f"- [ ] {item}"
    field = item.get("field", "")
    value = item.get("value", "")
    reason = item.get("reason", "")
    tail = f"（根拠：{reason}）" if reason else ""
    return f"- [ ] **{field}** → 推定値「{value}」{tail}"


def _format_missing(item: dict[str, Any]) -> str:
    if not isinstance(item, dict):
        return f"- [ ] {item}"
    field = item.get("field", "")
    question = item.get("question", "")
    blocking = "（要回答）" if item.get("blocking") else ""
    return f"- [ ] **{field}**{blocking}：{question}"


def render_review_notes_markdown(notes: dict[str, Any], title: str = "") -> str:
    counts = notes.get("counts", {})
    lines: list[str] = []
    lines.append("# レビュー指摘リスト（AIドラフト・要確認）")
    if title:
        lines.append(f"\n対象：{title}")
    lines.append(
        "\n> 本書類はAIが入力から自動生成したドラフトです。提出前に必ず内容を確認・修正してください。"
        "\n> 不足項目は提案値で仮に補完している場合があります。チェックを付けながら確認してください。"
    )
    lines.append(
        f"\n要確認サマリ：不足 {counts.get('errors', 0)} 件 / 注意 {counts.get('warnings', 0)} 件 / "
        f"自動推定 {counts.get('assumptions', 0)} 件 / 確認質問 {counts.get('missing_items', 0)} 件\n"
    )

    errors = notes.get("errors", [])
    lines.append("## 1. 不足している項目（提案で仮埋め。要確認）")
    lines.extend(_format_issue(i) for i in errors) if errors else lines.append("- 不足項目はありません。")

    assumptions = notes.get("assumptions", [])
    lines.append("\n## 2. 入力から自動推定して補完した項目")
    lines.extend(_format_assumption(a) for a in assumptions) if assumptions else lines.append("- 自動推定した項目はありません。")

    missing_items = notes.get("missing_items", [])
    lines.append("\n## 3. 確認が必要な項目（AIからの質問）")
    lines.extend(_format_missing(m) for m in missing_items) if missing_items else lines.append("- 追加の確認事項はありません。")

    warnings = notes.get("warnings", [])
    lines.append("\n## 4. 注意・整合性・用語")
    lines.extend(_format_issue(w) for w in warnings) if warnings else lines.append("- 注意事項はありません。")

    return "\n".join(lines) + "\n"


def write_review_notes_file(context: dict[str, Any], output_dir: Path) -> Path:
    """レビュー指摘リストを Markdown ファイルとして出力ディレクトリに書き出す。"""
    notes = build_review_notes(context)
    title = ""
    research = context.get("research", {}) if isinstance(context, dict) else {}
    if isinstance(research, dict):
        title = str(research.get("title", "") or "")
    markdown = render_review_notes_markdown(notes, title)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "_レビュー指摘リスト.md"
    output_path.write_text(markdown, encoding="utf-8")
    return output_path
