"""
研究計画解析サービス
"""
import time
from typing import Dict, Any, List
from app.services.llm_client import LLMClient
from app.logger import get_logger

logger = get_logger(__name__)


class PlanAnalyzer:
    """研究計画を解析してフォームフィールドを自動抽出"""
    
    SYSTEM_INSTRUCTION = """あなたは筑波大学の研究倫理審査書類作成を支援するアシスタントです。
あなたの役割は、論文、実装メモ、既存資料、ユーザー入力から、倫理審査に必要な研究計画情報を構造化することです。

重要な制約:
- ユーザー入力や資料本文をそのまま長文コピーしないでください。
- 入力にない日付、金額、責任者名、所属長名、予算名、承認番号は作らないでください。
- 実験条件、課題、評価指標、リスク、アンケートで測る内容は、資料から合理的に推論して構いません。
- 推論した内容は断定しすぎず、確認が必要な場合は clarification_questions に入れてください。
- 「必要に応じて」「など」「可」「適宜」のような曖昧語に逃げず、実施内容を具体化してください。
- 行政的・責任所在に関わる不足情報は必ず確認質問にしてください。
- 用語の制約：研究に協力する人は必ず「研究対象者」または「参加者」と表記してください。それ以外の旧来の呼称（健康状態を含意する語や、実験の語を含む対象側の旧来の呼称など）は使用しないでください。
- 出力は必ず指定されたJSON形式にしてください。"""

    def __init__(self, client: LLMClient):
        self.client = client
    
    async def analyze(self, research_plan: str) -> Dict[str, Any]:
        """研究計画を解析"""
        logger.info(f"研究計画解析 開始 (入力: {len(research_plan)} 文字)")
        start_time = time.time()
        
        prompt = f"""以下の研究資料を解析し、倫理審査申請書に必要な情報を抽出してください。
入力には、論文、実装メモ、既存様式のテキスト、ユーザーの短い指示が混在する場合があります。

# 入力資料
{research_plan}

# 解析方針
- 研究目的、研究意義、実験デザイン、参加者条件、手続き、測定項目、リスク、所要時間を整理してください。
- 入力が不完全な場合でも、研究内容から妥当な実験計画案を作ってください。
- ただし、研究期間終了日、関係組織の長、責任者、謝金財源、最終参加者数は、入力にない場合は勝手に確定しないでください。
- 参加者数が入力に数値で書かれている場合（募集見込み・実施可能性として『○人を達成できそう』『○人を予定』等の表現を含む）は、その数を participant_count に採用してください。数値の出所が打合せメモ・予算メモであっても、数自体は入力に書かれた情報として採用してよいです（ただし participant_count_reason の文章にメモ・金額計算をそのまま引用しないこと）。
- アンケート生成に使えるよう、研究方法には実験条件（独立変数）、課題、測定内容（従属変数・評価指標）を、入力に書かれている範囲で具体的に含めてください。
- 特定の研究テーマ（字幕・音声など）を勝手に想定しないでください。入力に実験デザイン（条件比較・反復測定・カウンターバランス等）が書かれている場合のみ、その範囲で具体化してください。
- すべての出力は研究倫理審査申請書にそのまま転記できる公式な文体にしてください。入力に含まれる打合せメモ・TODO・予算メモ（例「700円×64人=42,000円」）・「研究メモ」「資料」等の出所表現や金額計算を、根拠説明の文中に引用・転記しないでください（人数の根拠は検出力・先行研究・実施可能性など方法論的な観点で述べる）。

# clarification_questions に必ず含めるべき場合
- 実施形態がオンライン、ラボ、ハイブリッドのどれか不明な場合
- 参加者数が資料から読み取れない場合
- 研究期間終了日が不明な場合
- 保存するデータ種別が不明な場合
- 謝金額または財源が不明な場合
- 音声・映像・画面録画など個人情報性が高いデータ取得の有無が不明な場合

# 出力形式（JSON）
{{
    "research_title": "研究課題名",
    "research_purpose": "研究目的（2-4文で具体的に）",
    "research_method": "研究方法。条件、刺激、課題、測定項目、実施形態、条件順序の扱いを含める。",
    "target_participants": "実験参加者の条件",
    "participant_count": 0,
    "participant_count_reason": "人数設定の根拠。統計的検出力・先行研究の標本規模・実施可能性など方法論的な観点で、公式申請書の文体で述べる。打合せメモや予算計算（例『700円×64人』）は引用しない。根拠が全く不明なら空文字。",
    "age_range": "18歳以上の成人",
    "selection_criteria": "選択基準",
    "exclusion_criteria": "除外基準",
    "risks": ["リスク1", "リスク2"],
    "risk_countermeasures": ["対策1", "対策2"],
    "duration_minutes": 0,
    "devices": ["使用するデバイス"],
    "clarification_needed": true,
    "clarification_questions": [
        "ユーザーに確認すべき具体的な質問"
    ]
}}

注意:
- participant_count と duration_minutes は、入力から合理的に推定できない場合は 0 にしてください。
- clarification_needed は、clarification_questions が1つでもある場合 true にしてください。
- リスクと対策は同じ順序で対応させてください。
- 研究倫理申請にそのまま移せる、落ち着いた文体にしてください。"""

        try:
            result = await self.client.generate_json(prompt, self.SYSTEM_INSTRUCTION)
            elapsed = time.time() - start_time
            logger.info(f"研究計画解析 完了 (所要時間: {elapsed:.2f}秒)")
            logger.info(f"  研究課題名: {result.get('research_title', 'N/A')}")
            logger.info(f"  抽出リスク数: {len(result.get('risks', []))}")
            logger.info(f"  要確認: {result.get('clarification_needed', False)}")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"研究計画解析 失敗 ({elapsed:.2f}秒): {type(e).__name__}: {e}")
            raise

