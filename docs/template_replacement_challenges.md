# テンプレート化の課題と改善案

## 現状

### 実行結果
- 同意書: **0個** のプレースホルダー挿入
- 同意撤回書: **1個** のプレースホルダー挿入 (`conductor_tel`)

### 問題の原因

1. **テキストの不一致**: サンプルファイル内の実際のテキストが置換マッピングと完全一致していない
   - 全角スペース vs 半角スペース
   - 改行文字の有無
   - フォーマット分割（例: "善甫" と "啓一" が別のRunに分かれている）

2. **python-docxの制限**: `paragraph.text` でまとめて取得できても、`run.text` 単位で置換しないとフォーマットが崩れる問題

## 推奨する解決策

### Option A: 手動でWordファイルを編集 ✅ 最も確実

**手順**:
1. `backend/templates/03_同意書_template.docx` をWordで開く
2. Ctrl+H （検索と置換）を使用
3. 以下を順番に置換:

```
検索: 善甫 啓一
置換: {{ pi_name }}

検索: 029-853-5338
置換: {{ pi_tel }}

検索: 清水 啓斗
置換: {{ conductor_name }}

検索: 029-853-6185
置換: {{ conductor_tel }}

検索: 筑波大学 システム情報系
置換: {{ pi_affiliation }}

検索: システム情報系 研究倫理委員会事務局
置換: {{ ethics_committee }}

検索: 029-853-4989
置換: {{ ethics_tel }}
```

4. 保存

**メリット**: 
- 確実にフォーマットを保持
- 目視で確認しながら作業できる
- 表内のテキストもまとめて置換可能

**デメリット**: 
- 手作業が必要（10分程度）

---

### Option B: python-docx-templateを利用した段階的置換

**コンセプト**: 
サンプルファイルを直接テンプレートとして使用し、プログラムから動的に埋める部分のみプレースホルダー化

**実装例**:
```python
# 既存のサンプルファイルをテンプレートとしてそのまま使用
template = DocxTemplate('sample/03_同意書（shimizu）_v3.docx')

# コンテキストで上書き
context = {
    'pi_name': '山田 太郎',  # デフォルト: 善甫 啓一
    # ... サンプルファイルにない変数のみ定義
}
```

**課題**: サンプルファイルの値をプレースホルダーに変えないと、常に「善甫 啓一」のまま

---

### Option C: より高度な置換スクリプト

**アプローチ**:
1. Runレベルでテキストを結合
2. 置換後、元のRunに戻す

```python
def replace_text_in_runs(paragraph, old, new):
    """Run単位でテキストを結合してから置換"""
    full_text = ''.join(run.text for run in paragraph.runs)
    if old in full_text:
        # 全Runのテキストをクリア
        for run in paragraph.runs:
            run.text = ''
        # 最初のRunに置換後のテキストを設定
        paragraph.runs[0].text = full_text.replace(old, new)
        return True
    return False
```

**デメリット**: フォーマット（太字、色など）が失われる可能性

---

## 推奨手順

### 短期的解決策（今すぐ動作確認）

**1. 手動でテンプレート化** (10分)
   - `backend/templates/03_同意書_template.docx` をWordで編集
   - 主要フィールドのみプレースホルダー化:
     - `{{ pi_name }}`
     - `{{ pi_tel }}`
     - `{{ conductor_name }}`
     - `{{ conductor_tel }}`

**2. テスト実行**
```python
from docxtpl import DocxTemplate

doc = DocxTemplate('backend/templates/03_同意書_template.docx')
context = {
    'pi_name': '山田 太郎',
    'pi_tel': '029-853-XXXX',
    'conductor_name': '佐藤 花子',
    'conductor_tel': '029-853-YYYY',
}
doc.render(context)
doc.save('test_output.docx')
```

**3. 確認**
   - `test_output.docx` をWordで開いて確認

---

### 長期的解決策（完全自動化）

**AI生成セクション**を活用:

```
【研究目的】
{{ research_purpose }}

【研究方法】
{{ research_method }}

【実験手順】
{{ experiment_procedure }}
```

これらはサンプルファイルごとに内容が大きく異なるため、固定値ではなくAI生成が適切。

---

## 次のアクション

### ユーザーに確認が必要な点

1. **手動編集で進めるか？** (推奨: Option A)
2. **どのフィールドをプレースホルダー化するか？**
   - 最小構成: 名前・電話番号のみ
   - 完全構成: 研究内容もすべてプレースホルダー化

### 実装支援

Option Aを選択する場合:
- 具体的な置換リストを提供
- テスト用コードを提供
- 検証スクリプトを提供
