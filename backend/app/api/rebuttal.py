"""
Rebuttal（修正対応）APIエンドポイント

委員会からの審査コメントに対する point-by-point の回答書と、
申請書類の具体的な修正案を LLM で生成する。

旧実装からの主な改善点（ブラッシュアップ）:
- GeminiClient 直接利用 → LLMClient 抽象に切替（OpenAI / Gemini 両対応）
- X-API-Key を required → optional に変更（settings.json をフォールバック）
- プロンプトに現在の申請書記載内容・研究責任者・過去ラウンド履歴を投入
- 委員会指摘テキストを最小単位の項目に自動分解して指摘番号付きで処理
- 日本の倫理審査委員会対応の慣例的書式（point-by-point の敬体回答書）を厳格化
- LLM 応答 JSON の頑健なフォールバックパース
"""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from pathlib import Path
import json
import re

from app.models.session import Session, StepStatus, SessionStatus, RebuttalRound
from app.services.llm_client import LLMClient, create_llm_client
from app.services.llm_dependency import get_llm_client
from app.services.lab_defaults_manager import load_lab_defaults
from app.config import app_config
from app.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()

# セッション保存ディレクトリは ETHICS_DATA_DIR/sessions に統一
SESSIONS_DIR = app_config.sessions_dir


# ============================================================
# Pydantic スキーマ（フロントエンド互換のため形は維持）
# ============================================================

class CreateRebuttalRequest(BaseModel):
    """Rebuttal作成リクエスト"""
    feedback_text: str = Field(..., alias="feedbackText", description="委員会からの指摘事項テキスト")

    model_config = {"populate_by_name": True}


class RebuttalSuggestion(BaseModel):
    """AI修正提案"""
    field: str
    original_value: str = Field(alias="originalValue")
    suggested_value: str = Field(alias="suggestedValue")
    reason: str

    model_config = {"populate_by_name": True}


class RebuttalResponse(BaseModel):
    """Rebuttalレスポンス"""
    round_number: int = Field(alias="roundNumber")
    feedback_text: str = Field(alias="feedbackText")
    suggestions: List[RebuttalSuggestion]
    response_draft: str = Field(alias="responseDraft")
    status: StepStatus

    model_config = {"populate_by_name": True}


# ============================================================
# システムプロンプト
# ============================================================

REBUTTAL_SYSTEM_INSTRUCTION = """あなたは日本の大学における研究倫理審査委員会への対応文書作成を支援する、経験豊富な研究者です。

# あなたのタスク
1. 委員会からの指摘事項を最小単位に正確に解釈する。
2. それぞれの指摘について、申請書類のどの項目をどう修正すべきか具体案を提示する。
3. 委員会に提出する正式な回答書（point-by-point response）を作成する。

# 出力フォーマット（必須）
回答は必ず以下の JSON 形式 1 つのみで返してください。前置き・後置き・マークダウンのコードブロックは禁止。
{
  "suggestions": [
    {
      "field": "申請書上の項目名（research_purpose / risks / safety_measures / anonymization_method など、form_data のキー）",
      "original_value": "現在の記載（提供された form_data から抜粋。該当が無い場合は『（記載なし）』）",
      "suggested_value": "修正後の完全な記載文",
      "reason": "委員会指摘との対応関係を 1〜2 文で"
    }
  ],
  "response_draft": "委員会宛の正式な回答書"
}

# 修正提案（suggestions）の品質ルール
- 委員会指摘の最小単位ごとに 1 エントリを作る。1 つの指摘から複数の項目修正が必要な場合は複数エントリに分ける。
- field は form_data に存在するキー（スネークケース英語）を優先して使う。
- suggested_value は「である調」の自然な学術文章で、本人が記述したかのような文体にする。
- 段落は 2〜4 文程度。長すぎる場合は要点を絞る。
- AI らしい不自然な表現は禁止: 「素晴らしい」「重要です」「ご活躍をお祈りします」「以上のように」「〜と言えるでしょう」など。
- マークダウン記号（**、##、--、・）は使わない。文章は段落形式で記述する。
- コロン（:）や波線（〜〜）の濫用、記号的箇条書きは避ける。

# 回答書（response_draft）の体裁（厳格に従う）
- 敬体（です・ます調）で統一。
- 冒頭の挨拶、point-by-point の回答、末尾の結語、署名の 4 部構成。
- 各指摘は「【ご指摘 No.N】」「【ご回答】」の見出しを使って番号付きで明示。
- 「ご指摘の通り」「ご指摘を踏まえ」「申請書の『〇〇』欄を以下のとおり修正いたしました」等、
  日本の学術委員会対応で慣例的に使われる表現を中心に用いる。
- 反論する場合は「ご指摘の点につきましては、〇〇の理由により本申請書の記載のとおりとさせていただきたく存じます」と
  丁寧かつ毅然と主張する。
- 「指摘事項に対する具体的な修正提案を生成しました」のようなメタ的・AI 的な文は絶対に出力しない。
- 過度な迎合表現（「大変勉強になりました」「おっしゃる通りでございます」の濫用）は避ける。

# 回答書テンプレート（このフォーマットを厳守）
─────────────────────────────────
研究倫理審査委員会 御中

この度は、本研究計画書のご審査を賜り、誠にありがとうございます。
いただきましたご指摘事項につきまして、以下のとおりご回答申し上げます。

【ご指摘 No.1】
（委員会指摘の要約を 1〜2 文で再掲する。原文の引用が長すぎる場合は要点を絞る）

【ご回答】
ご指摘のとおり、〜について記載が不十分でございました。
申請書の「〇〇」欄を以下のとおり修正いたしました。
〔修正後の記載抜粋〕

【ご指摘 No.2】
…
【ご回答】
…

以上、ご審査のほどよろしくお願い申し上げます。

{PI_AFFILIATION} {PI_NAME}
─────────────────────────────────

# 重要
- 指摘番号は提供される No.1〜No.N に必ず一致させる。順序を入れ替えない。
- form_data に存在しない情報を捏造しない。不明な箇所は「現状の記載に基づき」「研究計画に従い」と
  ぼかして表現する。
"""


# ============================================================
# ヘルパー
# ============================================================

# 指摘の区切りパターン: ・、-、•、●、1.、1)、1、、一.、No.1 など
_INDICATION_SPLIT_RE = re.compile(
    r"(?:^|\n)\s*(?:"
    r"[・\-•●◇◆□■]\s*"
    r"|\d+[\.\)、:：]\s*"
    r"|[①②③④⑤⑥⑦⑧⑨⑩]\s*"
    r"|[一二三四五六七八九十]+[\.\)、:：]\s*"
    r"|No\.?\s*\d+[\.\)、:：]?\s*"
    r")",
    re.MULTILINE,
)


def _split_indications(feedback_text: str) -> List[str]:
    """委員会指摘テキストを最小単位の項目に分解する。

    箇条書き記号や番号付きリストを検出して分割する。検出できない場合は段落単位で分割し、
    最終的に何も得られなければ全文をひとつの項目として返す。
    """
    text = (feedback_text or "").strip()
    if not text:
        return []

    # 区切り箇所にマーカーを差し込み、分割
    marked = _INDICATION_SPLIT_RE.sub("\n§§§\n", text)
    items = [s.strip() for s in marked.split("§§§") if s.strip()]

    # 箇条書きが検出されない場合は空行段落で分割
    if len(items) <= 1:
        items = [s.strip() for s in re.split(r"\n\s*\n", text) if s.strip()]

    return items if items else [text]


def _build_form_summary(session: Session) -> Dict[str, Any]:
    """現在の申請書記載内容を取得する（confirm の編集を analyze 結果に上書きマージ）"""
    analyzed = session.steps.analyze.result or {}
    edits = session.steps.confirm.user_edits or {}
    merged: Dict[str, Any] = {}
    if isinstance(analyzed, dict):
        merged.update(analyzed)
    if isinstance(edits, dict):
        merged.update(edits)
    return merged


def _truncate(text: Any, limit: int = 400) -> str:
    s = "" if text is None else str(text)
    if len(s) > limit:
        return s[: limit - 1] + "…"
    return s


def _compact_form_data(form_data: Dict[str, Any], per_field_limit: int = 400) -> Dict[str, Any]:
    """LLM に渡すために form_data を圧縮（空値除去・長すぎる値の切り詰め）"""
    out: Dict[str, Any] = {}
    for k, v in (form_data or {}).items():
        if v is None or v == "" or v == [] or v == {}:
            continue
        if isinstance(v, (str, int, float, bool)):
            out[k] = _truncate(v, per_field_limit) if isinstance(v, str) else v
        else:
            # list / dict は JSON 化して切り詰め
            try:
                out[k] = _truncate(json.dumps(v, ensure_ascii=False), per_field_limit)
            except (TypeError, ValueError):
                out[k] = _truncate(str(v), per_field_limit)
    return out


def _build_history_block(session: Session) -> str:
    """過去ラウンドの要約ブロックを構築（現在のラウンドは含めない）"""
    prior = session.rebuttal.rounds[:-1]
    if not prior:
        return ""

    lines = ["# 過去のラウンド履歴（参考）"]
    for r in prior:
        sug = r.ai_suggestions or {}
        draft = sug.get("response_draft", "") if isinstance(sug, dict) else ""
        lines.append(
            f"- ラウンド{r.round_number}\n"
            f"  指摘: {_truncate(r.feedback_text, 200)}\n"
            f"  当時の回答骨子: {_truncate(draft, 200)}"
        )
    return "\n".join(lines) + "\n"


def _build_user_prompt(
    session: Session,
    feedback_text: str,
    indications: List[str],
    lab_defaults: Dict[str, Any],
) -> str:
    """LLM に渡すユーザープロンプトを構築"""
    form_data = _build_form_summary(session)
    compact = _compact_form_data(form_data)

    lab_info = (lab_defaults or {}).get("lab_info", {}) or {}
    pi_name = lab_info.get("pi_name", "")
    pi_affiliation = lab_info.get("pi_affiliation", "")

    numbered = "\n".join(f"No.{i + 1}: {item}" for i, item in enumerate(indications))
    history_block = _build_history_block(session)

    title = session.title or session.research_plan.raw_input[:120] or "（タイトル未設定）"
    raw_input_excerpt = _truncate(session.research_plan.raw_input, 1200)

    return f"""# 研究課題
{title}

# 研究計画（生入力からの抜粋）
{raw_input_excerpt}

# 現在の申請書記載内容（form_data）
```json
{json.dumps(compact, ensure_ascii=False, indent=2)}
```

# 研究責任者
所属: {pi_affiliation}
氏名: {pi_name}

（システム指示の回答書テンプレート末尾の署名には、上記の所属と氏名を {{PI_AFFILIATION}} / {{PI_NAME}} に当てはめてください）

# 委員会からの指摘事項（自動分解済み・指摘番号付き）
{numbered}

# 元の指摘事項テキスト（参考。番号付けに従うこと）
{feedback_text}

{history_block}
上記の指摘事項 No.1 〜 No.{len(indications)} のそれぞれについて、
- 申請書類の修正案（suggestions、指摘番号と対応させる）
- 委員会への正式回答書（response_draft、point-by-point 形式）
をシステム指示の JSON 形式で生成してください。
"""


def _safe_parse_json(text: str) -> Dict[str, Any]:
    """LLM 応答テキストから JSON を頑健に抽出してパース。失敗時はフォールバック構造を返す。"""
    t = (text or "").strip()

    # 先頭/末尾のコードフェンス除去
    if t.startswith("```json"):
        t = t[7:]
    elif t.startswith("```"):
        t = t[3:]
    if t.endswith("```"):
        t = t[:-3]
    t = t.strip()

    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass

    # 最外殻の { ... } を抽出して再試行
    match = re.search(r"\{[\s\S]*\}", t)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # 最終フォールバック: テキスト全文を response_draft に詰める
    logger.warning("rebuttal: JSON parse failed; falling back to raw text as response_draft")
    return {"suggestions": [], "response_draft": text}


def _resolve_llm_client(
    x_api_key: Optional[str],
    x_llm_provider: Optional[str],
) -> LLMClient:
    """LLM クライアントを解決する。

    ヘッダで明示指定があればそれを使い、無ければ settings.json から取得する。
    既存挙動との互換性: X-API-Key のみ指定された場合は gemini を仮定する。
    """
    if x_api_key:
        provider = (x_llm_provider or "gemini").lower()
        return create_llm_client(provider=provider, api_key=x_api_key)
    return get_llm_client()


# ============================================================
# エンドポイント
# ============================================================

@router.post("/{session_id}", response_model=RebuttalResponse)
async def create_rebuttal(
    session_id: str,
    request: CreateRebuttalRequest,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_llm_provider: Optional[str] = Header(None, alias="X-LLM-Provider"),
):
    """新しい Rebuttal ラウンドを作成し、AI 修正提案と回答書を生成する。"""
    try:
        session = Session.load(SESSIONS_DIR, session_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")

    # Rebuttal 有効化 + 新ラウンド追加
    session.rebuttal.enabled = True
    session.status = SessionStatus.REBUTTAL
    round_number = len(session.rebuttal.rounds) + 1
    rebuttal_round = RebuttalRound(
        round_number=round_number,
        feedback_text=request.feedback_text,
        status=StepStatus.RUNNING,
    )
    session.rebuttal.rounds.append(rebuttal_round)
    session.save(SESSIONS_DIR)

    try:
        # LLM クライアント解決
        try:
            llm = _resolve_llm_client(x_api_key, x_llm_provider)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=(
                    "LLM クライアントを初期化できませんでした。設定画面で API キーを保存するか、"
                    f"X-API-Key ヘッダを指定してください: {e}"
                ),
            )

        # 委員会指摘の自動分解
        indications = _split_indications(request.feedback_text)
        if not indications:
            raise HTTPException(status_code=400, detail="指摘事項が空です")

        # ラボデフォルト（取得失敗しても続行）
        try:
            lab_defaults = load_lab_defaults().model_dump()
        except Exception as e:
            logger.warning(f"lab_defaults load failed (continuing without it): {e}")
            lab_defaults = {}

        # プロンプト構築
        prompt = _build_user_prompt(session, request.feedback_text, indications, lab_defaults)

        # Chain of Thought 保存
        session.add_chain_of_thought(step="rebuttal", prompt=prompt)
        session.save(SESSIONS_DIR)

        # LLM 呼び出し
        raw_response = await llm.generate_content_async(
            prompt=prompt,
            system_instruction=REBUTTAL_SYSTEM_INSTRUCTION,
        )

        session.add_chain_of_thought(step="rebuttal", response=raw_response)

        # 結果パース（フォールバック付き）
        result = _safe_parse_json(raw_response)

        # 結果を保存
        rebuttal_round.ai_suggestions = result
        rebuttal_round.status = StepStatus.COMPLETED
        session.rebuttal.rounds[-1] = rebuttal_round
        session.save(SESSIONS_DIR)

        # フロントエンド互換のレスポンス形に整形
        suggestions = [
            RebuttalSuggestion(
                field=str(s.get("field", "") or ""),
                originalValue=str(s.get("original_value", "") or ""),
                suggestedValue=str(s.get("suggested_value", "") or ""),
                reason=str(s.get("reason", "") or ""),
            )
            for s in (result.get("suggestions") or [])
            if isinstance(s, dict)
        ]

        return RebuttalResponse(
            roundNumber=round_number,
            feedbackText=request.feedback_text,
            suggestions=suggestions,
            responseDraft=(result.get("response_draft") or "").strip(),
            status=StepStatus.COMPLETED,
        )

    except HTTPException:
        # HTTPException はエラー保存して再送出
        rebuttal_round.status = StepStatus.ERROR
        session.rebuttal.rounds[-1] = rebuttal_round
        session.save(SESSIONS_DIR)
        raise
    except Exception as e:
        logger.error(f"rebuttal generation error: {type(e).__name__}: {e}")
        session.add_chain_of_thought(step="rebuttal", error=str(e))
        rebuttal_round.status = StepStatus.ERROR
        session.rebuttal.rounds[-1] = rebuttal_round
        session.save(SESSIONS_DIR)
        raise HTTPException(status_code=500, detail=f"修正提案の生成に失敗しました: {e}")


@router.get("/{session_id}/rounds", response_model=List[dict])
async def get_rebuttal_rounds(session_id: str):
    """Rebuttalラウンド一覧を取得"""
    try:
        session = Session.load(SESSIONS_DIR, session_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")

    return [
        {
            "roundNumber": r.round_number,
            "feedbackText": r.feedback_text,
            "status": r.status,
            "createdAt": r.created_at,
            "hasSuggestions": r.ai_suggestions is not None,
        }
        for r in session.rebuttal.rounds
    ]


class ApplyRebuttalRequest(BaseModel):
    """Rebuttal適用リクエスト"""
    user_response: str = Field(..., alias="userResponse", description="ユーザーが編集した回答")
    accepted_suggestions: List[int] = Field(default_factory=list, alias="acceptedSuggestions")

    model_config = {"populate_by_name": True}


@router.post("/{session_id}/rounds/{round_number}/apply")
async def apply_rebuttal(
    session_id: str,
    round_number: int,
    request: ApplyRebuttalRequest,
):
    """Rebuttal修正を適用"""
    try:
        session = Session.load(SESSIONS_DIR, session_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")

    target_round = None
    for r in session.rebuttal.rounds:
        if r.round_number == round_number:
            target_round = r
            break

    if not target_round:
        raise HTTPException(status_code=404, detail="Rebuttal round not found")

    target_round.user_response = request.user_response
    session.save(SESSIONS_DIR)

    return {
        "message": "Rebuttal applied",
        "roundNumber": round_number,
        "acceptedCount": len(request.accepted_suggestions),
    }
