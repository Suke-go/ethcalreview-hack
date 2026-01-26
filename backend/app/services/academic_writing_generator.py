"""
研究計画書文章生成サービス（アカデミックライティング対応）

LLMを使用して自然な学術文章を生成します。
AIライクな表現を避け、アカデミックライティングの基準に準拠した文章を生成します。
"""

from typing import Dict, Any
from app.services.llm_client import LLMClient
from app.logger import get_logger

logger = get_logger(__name__)


# アカデミックライティング用プロンプト
ACADEMIC_WRITING_PROMPT = """
あなたは日本の大学における研究倫理審査申請書を作成する研究者です。
以下の情報を基に、アカデミックな文章で研究計画の各セクションを記述してください。

【重要な執筆ルール】
1. 自然な日本語の学術文章として記述する
2. 以下の表現は避ける:
   - コロン（:）や波線（~~）などの記号的表現
   - 「素晴らしい」「重要です」などの断定的・強調的表現
   - 「実施します」ではなく「実施する」「実施される」のような客観的表現
   - 箇条書き記号（・や-）の乱用
   - 見出し風の太字表現
3. 使用すべき表現:
   - 「〜を目的とする」「〜が期待される」「〜を明らかにする」
   - 「〜と考えられる」「〜が示唆される」「〜を検証する」
   - 「実施される」「測定される」「収集される」のような受動態
4. 文体は「である調」で統一する
5. 造語や不自然な日本語は使用しない
6. 一般的な学術用語のみを使用する

【入力情報】
研究タイトル: {research_title}
簡単な説明: {brief_description}
研究分野: {research_field}

【出力形式】
以下の各セクションを生成してください。各セクションは段落形式で記述し、見出しは含めないでください。

1. 研究対象者条件
2. 研究目的
3. 研究の意義
4. 研究方法
5. 考えられるリスクと対処方法

各セクションは2-4文程度の自然な段落として記述してください。
JSONではなく、プレーンテキストで各セクションを区切り線（---）で分けて出力してください。
"""


async def generate_research_plan_sections(
    research_title: str,
    brief_description: str,
    research_field: str,
    llm_client: LLMClient
) -> Dict[str, str]:
    """
    研究計画の各セクションをアカデミックな文章で生成
    
    Args:
        research_title: 研究タイトル
        brief_description: 簡単な説明
        research_field: 研究分野
        llm_client: LLMクライアント
    
    Returns:
        各セクションのテキストを含む辞書
    """
    logger.info("=" * 60)
    logger.info("研究計画文章生成開始")
    
    try:
        prompt = ACADEMIC_WRITING_PROMPT.format(
            research_title=research_title,
            brief_description=brief_description,
            research_field=research_field
        )
        
        response = await llm_client.generate_content_async(
            prompt=prompt,
            system_instruction=(
                "あなたは日本の大学で研究倫理審査申請書を作成する経験豊富な研究者です。"
                "自然で読みやすい学術文章を生成してください。"
                "AIが生成したと分かるような不自然な表現は避けてください。"
            )
        )
        
        # レスポンスをセクションごとに分割
        sections_text = response.split('---')
        
        sections = {}
        expected_sections = [
            'participant_criteria',
            'research_purpose',
            'research_significance',
            'research_method',
            'risks'
        ]
        
        for i, section_name in enumerate(expected_sections):
            if i < len(sections_text):
                sections[section_name] = sections_text[i].strip()
        
        logger.info(f"生成完了: {len(sections)} セクション")
        logger.info("=" * 60)
        
        return sections
        
    except Exception as e:
        logger.error(f"文章生成エラー: {type(e).__name__}: {e}")
        return {}


# より詳細なプロンプト（セクション別）
def create_section_prompt(section_type: str, context: Dict[str, Any]) -> str:
    """
    セクション別の詳細プロンプトを生成
    """
    
    base_instructions = """
【文体ルール】
- である調で統一
- 受動態を適切に使用（「実施される」「測定される」など）
- 断定的表現を避ける（「〜と考えられる」「〜が期待される」など）
- 記号的表現（:、~~、！など）は使用しない
- 箇条書きではなく段落形式で記述
- 自然な接続詞を使用（「また」「さらに」「したがって」など）
"""
    
    prompts = {
        "participant_criteria": f"""
{base_instructions}

【タスク】
以下の研究の参加者条件を記述してください。

研究タイトル: {context.get('research_title', '')}
研究概要: {context.get('brief_description', '')}

【記述すべき内容】
1. 対象となる参加者の条件（年齢、健康状態など）
2. 除外基準
3. 参加の任意性と不利益がないこと

2-3段落で自然な文章として記述してください。
""",
        
        "research_purpose": f"""
{base_instructions}

【タスク】
以下の研究の目的を記述してください。

研究タイトル: {context.get('research_title', '')}
研究概要: {context.get('brief_description', '')}

【記述すべき内容】
1. 何を明らかにするのか
2. 何を検証するのか
3. 何を目的とするのか

「〜を目的とする」「〜を明らかにする」のような表現を使用し、
1-2段落で簡潔に記述してください。
""",
        
        "research_significance": f"""
{base_instructions}

【タスク】
以下の研究の意義を記述してください。

研究タイトル: {context.get('research_title', '')}
研究分野: {context.get('research_field', '')}

【記述すべき内容】
1. 研究の学術的意義
2. 応用可能性（VR、医療、工学など）
3. 期待される貢献

「〜が期待される」「〜への応用が考えられる」のような表現を使用し、
1-2段落で記述してください。
"""
    }
    
    return prompts.get(section_type, "")
