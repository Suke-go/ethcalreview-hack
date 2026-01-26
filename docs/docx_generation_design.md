# docx生成方式設計書

## 概要

倫理審査書類のdocx生成には **docxtpl（python-docx-template）** を使用する。
これにより、既存の公式テンプレートのフォーマットを完全に保持しながら、プレースホルダーに値を埋め込むことができる。

## 生成方式の比較

| 方式 | メリット | デメリット | 採用 |
|------|---------|-----------|------|
| **docxtpl** | 公式フォーマット完全保持、Jinja2構文 | テンプレート準備が必要 | ✅ |
| python-docx | 完全な制御が可能 | ゼロから構築が必要、フォーマット再現困難 | ❌ |
| テキスト→docx変換 | 実装が簡単 | 書式が保持されない | ❌ |

## テンプレート準備方法

### Step 1: 公式テンプレートのコピー
既存のsampleファイルをコピーしてテンプレート化

### Step 2: プレースホルダー挿入
記入済み部分をJinja2プレースホルダーに置換

```
# 変数置換
善甫 啓一 → {{ pi_name }}

# チェックボックス
■新規申請 → {% if application_type == "new" %}■{% else %}□{% endif %}新規申請

# 条件付き段落
{%p if has_device %}デバイス説明文...{%p endif %}

# 表の行ループ
{% tr for member in team_members %}
{{ member.affiliation }} | {{ member.position }} | {{ member.name }}
{% tr endfor %}
```

## 各書類の生成方式

### 1. 研究倫理審査申請書
- **テンプレート**: `01-1_申請書_template.docx`
- **方式**: docxtpl
- **特記**: チェックボックス（■/□）の動的切替が多い

### 2. 同意書
- **テンプレート**: `03_同意書_template.docx`
- **方式**: docxtpl
- **特記**: 研究概要セクションはAI生成テキストを挿入

### 3. 同意撤回書
- **テンプレート**: `04_同意撤回書_template.docx`
- **方式**: docxtpl
- **特記**: ほぼ固定テキスト、研究課題名と署名欄のみ置換

### 4. 実施計画書
- **テンプレート**: `01-2_実施計画書_template.docx`
- **方式**: docxtpl
- **特記**: 自由記述が多い、AI生成比率高

### 5. 募集案内文
- **テンプレート**: `募集案内文_template.docx`
- **方式**: docxtpl
- **特記**: 簡潔な形式、研究概要・条件・連絡先

### 6. アンケート用紙（新規生成）
- **テンプレート**: なし（python-docxで新規生成）
- **方式**: python-docx
- **特記**: ユーザー入力の質問項目から自動生成

### 7. 実験説明台本（新規生成）
- **テンプレート**: なし（python-docxで新規生成）
- **方式**: python-docx
- **特記**: 実験手順からAIが台本形式で生成

## docxtplコード例

```python
from docxtpl import DocxTemplate

def generate_consent_form(data: dict, output_path: str):
    """同意書を生成"""
    doc = DocxTemplate("templates/03_同意書_template.docx")
    
    context = {
        "research_title": data["research_title"],
        "pi_name": data["pi_name"],
        "pi_tel": data["pi_tel"],
        "conductor_name": data["conductor_name"],
        "conductor_tel": data["conductor_tel"],
        "ethics_committee": data["ethics_committee"],
        "ethics_tel": data["ethics_tel"],
        "participant_criteria": data["participant_criteria"],
        "research_purpose": data["research_purpose"],
        "research_method": data["research_method"],
        "experiment_procedure": data["experiment_procedure"],
        "duration_minutes": data["duration_minutes"],
        "risks": data["risks"],
        "reward_amount": data["reward_amount"],
        "reward_type": data["reward_type"],
        "data_protection": data["data_protection"],
    }
    
    doc.render(context)
    doc.save(output_path)
```

## チェックボックス処理

Wordのチェックボックスは文字（■/□）として表現されているため、以下のJinja2フィルターで処理：

```python
# カスタムフィルター
def checkbox(value, checked_char="■", unchecked_char="□"):
    return checked_char if value else unchecked_char

# テンプレート登録
doc = DocxTemplate("template.docx")
doc.jinja_env.filters["checkbox"] = checkbox

# テンプレート内
{{ is_new_application | checkbox }}新規申請
```

## テンプレート作成タスク

1. [ ] `01-1_申請書_template.docx` - プレースホルダー挿入
2. [ ] `03_同意書_template.docx` - プレースホルダー挿入
3. [ ] `04_同意撤回書_template.docx` - プレースホルダー挿入
4. [ ] `01-2_実施計画書_template.docx` - プレースホルダー挿入
5. [ ] `募集案内文_template.docx` - プレースホルダー挿入
