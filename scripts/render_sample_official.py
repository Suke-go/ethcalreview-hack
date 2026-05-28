"""公式書類一式を APIキー不要・決定的にレンダリングする検証用スクリプト。

レンダラやテンプレートを変更したあと、生成される docx/xlsx を Word/Excel で開いて
フォーマット崩れ・差し込み内容・過不足を目視確認するための簡易ツール。LLM は呼ばない。

使い方（リポジトリ直下または backend/ から）:
    .venv/Scripts/python.exe scripts/render_sample_official.py            # サンプルで全公式書類を出力
    .venv/Scripts/python.exe scripts/render_sample_official.py --open     # 出力後フォルダを開く(Windows)
    .venv/Scripts/python.exe scripts/render_sample_official.py --no-recording  # ビデオ承諾書を除外
    .venv/Scripts/python.exe scripts/render_sample_official.py --form my_form.json  # 実データJSONで
    .venv/Scripts/python.exe scripts/render_sample_official.py --out C:\\tmp\\check  # 出力先指定

既定の出力先: <repo>/output/_sample/
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.config import app_config, load_user_settings  # noqa: E402
from app.services.preset_manager import load_preset_bundle  # noqa: E402
from app.services.form_context_builder import build_generation_context  # noqa: E402
from app.services.official_document_service import (  # noqa: E402
    default_official_document_types,
    render_official_document,
)
from app.services.generation_validator import issue_payload, validate_generation_context  # noqa: E402
from app.services.review_summary import build_review_notes, write_review_notes_file  # noqa: E402


# 公式様式の体裁確認用サンプル（用語は「研究対象者/参加者」で統一。旧サンプル値は使わない）
SAMPLE_FORM: dict = {
    "title": "韻律可視化字幕による英語聴解支援の検証",
    "purpose": "音声の韻律的特徴を字幕表示に反映することで、英語を第二言語とする参加者の聴解理解が向上するかを検証する。",
    "significance": "音声情報を受け取りにくい状況での情報提示や語学学習支援の改善につながる可能性がある。",
    "methodology": "短い英語映像を複数回視聴し、内容理解・話者意図・負担感に関する選択式回答を取得する。",
    "targetDescription": "英語を第二言語として学習・使用している18歳以上の成人",
    "inclusionCriteria": ["18歳以上65歳以下", "矯正視力を含め字幕を読み取れること"],
    "exclusionCriteria": ["重篤な眼疾患のある者"],
    "expectedParticipants": 64,
    "participantsJustification": "統計的検出力の確保に必要な人数として算出した。",
    "procedures": ["研究説明と同意取得", "視線・音声機器の準備", "英語映像の視聴と回答", "終了後アンケート"],
    "risks": ["長時間の画面視聴による眼精疲労", "聞き取りにくい音声による軽度の心理的負担"],
    "riskCountermeasures": ["適宜休憩を挟む", "音量を事前に無理のない範囲へ調整する"],
    "duration": 45,
    "rewardAmount": 750,
    "app_config": {
        "applicationType": "new",
        "researchPeriodEndText": "2027年3月31日",
        "domainName": "知能機能工学域",
        "domainHeadName": "矢野 博明",
        "subInvestigators": [
            {
                "affiliation": "筑波大学情報学群情報メディア創成学類",
                "position": "学群生",
                "name": "清水 紘輔",
                "tel": "029-853-6185",
            }
        ],
        "facilityName": "3M211",
        "fundingSource": "科学研究費助成事業 基盤研究(B)",
        "fundingProjectName": "音声非言語情報に関する研究",
        "fundingProjectCode": "00X00000",
        "dataTypes": "回答内容、回答時間、提示条件",
        "storageLocation": "3G214の鍵のかかる保管庫",
        "dataManager": "善甫 啓一",
        "managementMethod": "暗号化したノートPCに保存し、関係者のみが扱う。",
        "disposalMethod": "成果公表後10年で復元不能な形で物理破棄する。",
        "videoRecording": True,
        "recordingPublicRelease": True,
        "invasiveness": False,
        "conflictOfInterest": False,
    },
}


def main() -> int:
    parser = argparse.ArgumentParser(description="公式書類を決定的にレンダリングして目視確認する")
    parser.add_argument("--form", type=str, default=None, help="フォームデータ JSON のパス")
    parser.add_argument("--no-recording", action="store_true", help="録画公開なし（ビデオ承諾書を除外）")
    parser.add_argument("--out", type=str, default=None, help="出力先ディレクトリ（既定: output/_sample）")
    parser.add_argument("--open", action="store_true", help="出力後にフォルダを開く（Windows）")
    args = parser.parse_args()

    if args.form:
        form = json.loads(Path(args.form).read_text(encoding="utf-8"))
    else:
        form = json.loads(json.dumps(SAMPLE_FORM))  # deep copy
    if args.no_recording:
        form.setdefault("app_config", {})
        form["app_config"]["videoRecording"] = False
        form["app_config"]["recordingPublicRelease"] = False

    settings = load_user_settings(app_config)
    presets = load_preset_bundle(app_config)
    context = build_generation_context(form, settings, presets)

    default_sample = ROOT / "output" / "_sample"
    out_dir = Path(args.out) if args.out else default_sample
    out_dir.mkdir(parents=True, exist_ok=True)
    # 既定のサンプル用フォルダのときだけ前回分を掃除（--out 指定時は消さない）
    if out_dir.resolve() == default_sample.resolve():
        for old in [
            *out_dir.glob("*.docx"),
            *out_dir.glob("*.doc"),
            *out_dir.glob("*.xlsx"),
            *out_dir.glob("*.xlsm"),
        ]:
            old.unlink()

    print(f"出力先: {out_dir.resolve()}")
    print(f"録画公開: {'あり（ビデオ承諾書を含む）' if not args.no_recording else 'なし'}\n")

    rendered: list[str] = []
    errors: list[str] = []
    for doc_type in default_official_document_types(context):
        try:
            path = render_official_document(doc_type, context, out_dir)
            rendered.append(path.name)
            print(f"  OK  {doc_type:22s} -> {path.name}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{doc_type}: {exc}")
            print(f"  NG  {doc_type:22s} : {type(exc).__name__}: {exc}")

    issues = issue_payload(validate_generation_context(context))
    print(f"\n生成 {len(rendered)} 件 / エラー {len(errors)} 件 / 過不足(要確認) {len(issues)} 件")
    for issue in issues:
        print(f"  - 過不足: {issue}")

    # レビュー指摘リスト（_レビュー指摘リスト.md）も出力一式に同梱
    notes = build_review_notes(context)
    review_path = write_review_notes_file(context, out_dir)
    counts = notes["counts"]
    print(
        f"レビュー指摘: {review_path.name}（不足 {counts['errors']} / 注意 {counts['warnings']} / "
        f"自動推定 {counts['assumptions']} / 確認質問 {counts['missing_items']}）"
    )

    if args.open and sys.platform.startswith("win"):
        import os

        os.startfile(str(out_dir.resolve()))  # type: ignore[attr-defined]  # noqa: S606

    print("\nWord / Excel で開いてフォーマットと差し込み内容を確認してください。")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
