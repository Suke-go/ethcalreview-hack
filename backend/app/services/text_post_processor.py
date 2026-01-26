"""
テキスト後処理サービス

LLM生成テキストの校正・用語統一・繰り返し削減を行います。
"""

import re
from typing import Dict, List


def post_process_academic_text(text: str) -> str:
    """
    学術文章の後処理
    
    - 用語統一
    - 繰り返し削減
    - 不要な記号除去
    - 冗長表現の簡略化
    
    Args:
        text: 処理対象テキスト
    
    Returns:
        処理後テキスト
    """
    if not text:
        return text
    
    # 1. 用語統一
    text = unify_terminology(text)
    
    # 2. 不要な記号除去
    text = remove_ai_like_symbols(text)
    
    # 3. 冗長表現の簡略化
    text = simplify_expressions(text)
    
    # 4. 繰り返し削減（警告のみ）
    check_repetition(text)
    
    return text


def unify_terminology(text: str) -> str:
    """
    用語を統一
    
    実験実施者 / 研究者 → 実施分担者
    """
    replacements = {
        '実験実施者': '実施分担者',
        '研究者が': '実施分担者が',
        '研究者は': '実施分担者は',
        '研究者': '実施分担者',  # 最後に適用
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    return text


def remove_ai_like_symbols(text: str) -> str:
    """
    AIライクな記号を除去
    """
    # コロンを句点に
    text = re.sub(r'：\s*', '。', text)
    text = re.sub(r':\s*(?=[^0-9])', '。', text)  # 時刻以外のコロン
    
    # 波線除去
    text = text.replace('~~', '')
    text = text.replace('〜〜', '')
    
    # 感嘆符を句点に
    text = text.replace('!', '。')
    text = text.replace('！', '。')
    
    # 連続句点の除去
    text = re.sub(r'。+', '。', text)
    
    return text


def simplify_expressions(text: str) -> str:
    """
    冗長な表現を簡略化
    """
    replacements = {
        '者とする。': '者である。',
        'ものとする。': 'ものである。',
        'ことができます': 'ことが可能である',
        'することができる': 'できる',
        '行うことができる': '行える',
        '非常に重要': '重要',
        '非常に': '',
        '素晴らしい': '',
        '画期的な': '',
        '確実に': '',
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    return text


def check_repetition(text: str, max_count: int = 3) -> List[str]:
    """
    過度な繰り返しをチェック
    
    Returns:
        警告メッセージのリスト
    """
    warnings = []
    
    phrases_to_check = [
        '自由意思',
        '自由意志',
        '参加者',
        '実験参加者',
        '研究対象者',
        '実施分担者',
    ]
    
    for phrase in phrases_to_check:
        count = text.count(phrase)
        if count > max_count:
            warnings.append(
                f"'{phrase}' が {count} 回出現しています（推奨: {max_count} 回以下）"
            )
    
    return warnings


def reduce_repetition(text: str, phrase: str, max_count: int = 2) -> str:
    """
    特定フレーズの繰り返しを削減
    
    Args:
        text: 対象テキスト
        phrase: 削減対象フレーズ
        max_count: 許容回数
    
    Returns:
        処理後テキスト
    """
    alternatives = {
        '自由意思': ['本人の意思', '自発的な意思', 'その意思'],
        '参加者': ['対象者', '本人', 'その者'],
        '実験参加者': ['参加者', '対象者', '本人'],
        '研究対象者': ['参加者', '対象者', '本人'],
        '実施分担者': ['担当者', '実施者'],
    }
    
    if phrase not in alternatives:
        return text
    
    count = text.count(phrase)
    if count <= max_count:
        return text
    
    # 代替表現に置換
    alt_list = alternatives[phrase]
    parts = text.split(phrase)
    result = []
    
    for i, part in enumerate(parts):
        result.append(part)
        if i < len(parts) - 1:
            if i < max_count:
                result.append(phrase)  # 最初の数回はそのまま
            else:
                # 代替表現を使用
                alt_index = (i - max_count) % len(alt_list)
                result.append(alt_list[alt_index])
    
    return ''.join(result)
