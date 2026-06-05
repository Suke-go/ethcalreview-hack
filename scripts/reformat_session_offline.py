# -*- coding: utf-8 -*-
"""保存済みセッションの context_snapshot から公式様式だけを再レンダリングする（APIキー不要・決定的）。

E2E で LLM が生成した実データ（文末「。」付きの対策文や文形式の対象者条件など）に対して、
レンダラ修正（句読点スティッチングの是正）が効いているかを検証するために使う。

使い方:
    .venv/Scripts/python.exe scripts/reformat_session_offline.py <session_id> [--out DIR]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.services.official_document_service import (  # noqa: E402
    default_official_document_types,
    render_official_document,
)
from app.services.review_summary import write_review_notes_file  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("session_id")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    sessions_dir = ROOT / "backend" / "sessions"
    session_file = sessions_dir / f"{args.session_id}.json"
    if not session_file.exists():
        print(f"NG: セッションが見つかりません: {session_file}")
        return 1
    session = json.loads(session_file.read_text(encoding="utf-8"))
    context = session.get("steps", {}).get("generate", {}).get("context_snapshot")
    if not context:
        print("NG: context_snapshot がありません")
        return 1

    out_dir = Path(args.out) if args.out else (ROOT / "backend" / "output" / args.session_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"出力先: {out_dir}")

    errors = []
    for doc_type in default_official_document_types(context):
        try:
            path = render_official_document(doc_type, context, out_dir)
            print(f"  OK  {doc_type:26s} -> {path.name}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{doc_type}: {exc}")
            print(f"  NG  {doc_type:26s} : {type(exc).__name__}: {exc}")
    write_review_notes_file(context, out_dir)
    print(f"\n再生成完了 / エラー {len(errors)} 件")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
