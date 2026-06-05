# -*- coding: utf-8 -*-
"""フルLLM E2E 検証スクリプト：議論ログ → analyze → generate → reformat を本番APIで通す。

フロントエンド（App.tsx handleGenerate）と同じリクエストを組み立てて、起動済みの
バックエンド API に投げる。レンダラ直叩きではなく HTTP 経由なので本番経路そのもの。

前提:
  1. リポジトリ直下の .env.local に GEMINI_API_KEY=... または OPENAI_API_KEY=... を記載
  2. バックエンドを起動しておく:
       cd backend && ../.venv/Scripts/python.exe -m uvicorn app.main:app --port 8123

使い方:
    .venv/Scripts/python.exe scripts/run_full_llm_e2e.py                  # 既定: 旧セッションの議論ログを再利用
    .venv/Scripts/python.exe scripts/run_full_llm_e2e.py --input my.txt   # 任意の議論ログで
    .venv/Scripts/python.exe scripts/run_full_llm_e2e.py --port 8123
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SESSION = ROOT / "backend" / "sessions" / "c9ec2606-4b7d-4d54-9677-a45ccfffdf88.json"
LOG = ROOT / "output" / "_e2e_llm" / "e2e_log.txt"

_log_lines: list[str] = []


def log(msg: str) -> None:
    _log_lines.append(msg)
    try:
        print(msg)
    except UnicodeEncodeError:  # Windows コンソールの cp932 対策
        print(msg.encode("cp932", "replace").decode("cp932"))


def load_api_key() -> tuple[str, str]:
    """(.env.local から) APIキーとプロバイダーを読む。"""
    env_file = ROOT / ".env.local"
    if not env_file.exists():
        raise SystemExit("ERROR: .env.local がありません。GEMINI_API_KEY=... か OPENAI_API_KEY=... を記載してください。")
    key = ""
    provider = ""
    for line in env_file.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name, value = name.strip(), value.strip().strip('"').strip("'")
        if name in ("GEMINI_API_KEY", "GOOGLE_API_KEY") and value:
            key, provider = value, "gemini"
        elif name == "OPENAI_API_KEY" and value:
            key, provider = value, "openai"
    if not key:
        raise SystemExit("ERROR: .env.local に GEMINI_API_KEY / OPENAI_API_KEY が見つかりません。")
    return key, provider


def main() -> int:
    parser = argparse.ArgumentParser(description="議論ログ→analyze→generate→reformat のフルLLM E2E")
    parser.add_argument("--input", type=str, default=None, help="議論ログのテキストファイル")
    parser.add_argument("--port", type=int, default=8123)
    args = parser.parse_args()

    base = f"http://127.0.0.1:{args.port}"
    api_key, provider = load_api_key()
    log(f"プロバイダー: {provider}（キー先頭 {api_key[:4]}***）")

    # ---- 入力（議論ログ） ----
    if args.input:
        raw_input_text = Path(args.input).read_text(encoding="utf-8")
    else:
        session_json = json.loads(DEFAULT_SESSION.read_text(encoding="utf-8"))
        raw_input_text = session_json["research_plan"]["raw_input"]
    log(f"議論ログ: {len(raw_input_text)} 文字")

    headers = {"X-API-Key": api_key, "X-LLM-Provider": provider}

    # ---- ヘルスチェック ----
    r = requests.get(f"{base}/health", timeout=10)
    r.raise_for_status()
    log("バックエンド: healthy")

    # ---- 設定取得（フロントと同じく謝礼単価を設定から計算） ----
    try:
        settings = requests.get(f"{base}/api/settings", timeout=10).json()
    except Exception:
        settings = {}
    hourly_rate = (settings.get("budget") or {}).get("hourly_rate") or 1000

    # ---- Step 1: analyze（議論ログ → 構造化） ----
    log("\n=== Step 1: /api/analyze（議論ログの構造化） ===")
    t0 = time.time()
    r = requests.post(
        f"{base}/api/analyze",
        json={"researchPlan": raw_input_text},
        headers=headers,
        timeout=300,
    )
    if r.status_code != 200:
        log(f"NG analyze: {r.status_code} {r.text[:500]}")
        return 1
    analysis = r.json()
    log(f"OK analyze（{time.time() - t0:.1f}秒）")
    log(f"  課題名: {analysis['research_title']}")
    log(f"  対象者: {analysis['target_participants']}")
    log(f"  人数: {analysis['participant_count']}（{analysis['participant_count_reason'][:60]}）")
    log(f"  所要時間: {analysis['duration_minutes']}分 / 機器: {', '.join(analysis['devices'])}")
    log(f"  リスク: {len(analysis['risks'])}件 / 対策: {len(analysis['risk_countermeasures'])}件")
    if analysis.get("clarification_needed"):
        for q in analysis.get("clarification_questions", []):
            log(f"  [聞き返し] {q}")

    # ---- Step 2: generate（App.tsx handleGenerate と同じ form_data 構築） ----
    duration = analysis["duration_minutes"]
    reward_amount = round(hourly_rate * duration / 60)
    pi = settings.get("principal_investigator") or {
        "name": "善甫 啓一",
        "affiliation": "筑波大学 システム情報系",
        "position": "准教授",
        "email": "zempo@iit.tsukuba.ac.jp",
        "phone": "029-853-5338",
    }
    form_data = {
        "research_plan": raw_input_text,
        "followupAnswers": {},
        "title": analysis["research_title"],
        "principalInvestigator": pi,
        "subInvestigators": settings.get("subInvestigators") or [],
        "purpose": analysis["research_purpose"],
        "background": "",
        "methodology": analysis["research_method"],
        "targetDescription": analysis["target_participants"],
        "inclusionCriteria": [analysis["selection_criteria"]],
        "exclusionCriteria": [analysis["exclusion_criteria"]],
        "expectedParticipants": analysis["participant_count"],
        "participantsJustification": analysis["participant_count_reason"],
        "recruitmentMethod": "",
        "procedures": [analysis["research_method"]],
        "duration": duration,
        "location": "",
        "devices": analysis["devices"],
        "risks": analysis["risks"],
        "riskCountermeasures": analysis["risk_countermeasures"],
        "dataProtection": "",
        "emergencyProcedures": "",
        "rewardAmount": reward_amount,
        "rewardRationale": f"所要時間{duration}分に基づく計算",
        "consentWithdrawalProcedure": "",
        "dataHandlingOnWithdrawal": "",
    }
    # App.tsx defaultAppConfig 相当（UI 既定値のまま＝人手の追記なしを再現）
    app_config = {
        "applicationType": "new",
        "domainName": "システム情報系",
        "domainHeadName": "矢野 博明",
        "researchPeriodStartText": "研究倫理委員会承認後",
        "researchPeriodEndText": "",
        "rewardUnit": "回",
        "similarApplicationExists": False,
        "subInvestigators": [],
        "facilityType": "a",
        "facilityName": "3M211",
        "fundingSource": "(教研)教研-重点-人材養成機能強化経費",
        "fundingPI": "善甫 啓一",
        "fundingProjectName": "",
        "genomeRelated": False,
        "conflictOfInterest": False,
        "videoRecording": False,
        "recordingPublicRelease": False,
        "invasiveness": False,
        "dataTypes": "",
        "retentionPeriod": "10years",
        "hasAnonymization": True,
        "hasCorrespondenceTable": True,
        "storageLocation": "研究室(3M211)にて管理されたノートパソコン",
        "dataManager": "善甫 啓一",
        "managementMethod": "ノートパソコンの使用を関係者のみとし、結果の解析はネットに接続されない状態で行う。また、暗号化およびパスワード保護を用いることによりデータを保護する。同意書等の紙媒体については研究室(3M211)の鍵付き棚に保管し、鍵は管理責任者が管理する。",
        "disposalMethod": "研究対象者からの実験に関するデータの破棄が申請された場合は直ちに研究対象者のデータを破棄する。また、研究成果発表から10年が経過した場合、データの保存しているSSDを初期化し、データの復元をできないようにして処分する。同意書等の紙媒体についてはシュレッダーにかけた上で破棄し、復元できないように処分する",
    }

    log("\n=== Step 2: /api/generate（書類一式のフルLLM生成） ===")
    t0 = time.time()
    r = requests.post(
        f"{base}/api/generate",
        json={"form_data": form_data, "app_config": app_config},
        headers=headers,
        timeout=1800,
    )
    if r.status_code != 200:
        log(f"NG generate: {r.status_code} {r.text[:1000]}")
        return 1
    result = r.json()
    session_id = result["session_id"]
    log(f"OK generate（{time.time() - t0:.1f}秒） status={result['status']}")
    log(f"  セッション: {session_id}")
    for name in result["documents_generated"]:
        log(f"  生成: {name}")
    for err in result.get("errors", []):
        log(f"  エラー: {err}")
    counts = (result.get("review_notes") or {}).get("counts", {})
    log(
        f"  レビュー指摘: 不足 {counts.get('errors', '?')} / 注意 {counts.get('warnings', '?')} / "
        f"自動推定 {counts.get('assumptions', '?')} / 確認質問 {counts.get('missing_items', '?')}"
    )

    # ---- Step 3: reformat（再フォーマットボタンの経路） ----
    log("\n=== Step 3: /api/generate/reformat（公式様式へ再適用） ===")
    t0 = time.time()
    r = requests.post(f"{base}/api/generate/reformat/{session_id}", timeout=300)
    if r.status_code != 200:
        log(f"NG reformat: {r.status_code} {r.text[:500]}")
        return 1
    ref = r.json()
    log(f"OK reformat（{time.time() - t0:.1f}秒） status={ref['status']} 再生成 {len(ref['regenerated'])} 件")
    for e in ref.get("errors", []):
        log(f"  エラー: {e}")

    log(f"\n出力先: backend/output/{session_id}")
    log("完了。docx をダンプして内容を確認してください。")
    return 0


if __name__ == "__main__":
    code = 1
    try:
        code = main()
    finally:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        LOG.write_text("\n".join(_log_lines), encoding="utf-8")
    raise SystemExit(code)
