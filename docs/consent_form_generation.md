# 同意書生成機能

## 概要

フォームデータから研究計画概要を含む同意書をdocx形式で生成します。
テンプレート化ではなく、python-docxを使用して動的に生成します。

## 生成される同意書の構成

### 表面（基本情報）
- タイトル: 「同意書」
- 研究課題名
- 研究責任者情報（研究室デフォルトから取得）
- 同意文
- 署名欄

### 裏面（研究の概要）

以下のセクションが含まれます：

1. **研究対象者条件**
   - 参加可能な条件
   - 除外基準

2. **目的**
   - 研究の目的

3. **意義**
   - 研究の意義・期待される効果

4. **方法**
   - 研究方法の概要

5. **実験内容（手順）**
   - 実験の具体的な手順（番号付きリスト）

6. **所要時間**
   - 実験にかかる時間

7. **考えられるリスク**
   - 想定されるリスクとその対処方法

8. **謝礼**
   - 謝礼の金額と支払い方法

9. **研究対象者の必要性、リスクと安全性、危険回避の方法**
   - 安全対策の詳細

10. **個人情報の保護**
    - データの匿名化方法
    - データの管理方法
    - 研究参加の任意性

## API仕様

### エンドポイント

```
POST /api/consent/consent-form
```

### リクエスト

```json
{
  "form_data": {
    "research_title": "視線追跡による認知負荷測定実験",
    "participant_criteria": "本研究では...",
    "research_purpose": "本研究は...",
    "research_significance": "本研究の意義は...",
    "research_method": "研究対象者には...",
    "experiment_procedures": [
      "研究の説明と同意取得を行います",
      "実験装置を装着します",
      "実験タスクを実施します"
    ],
    "duration_minutes": 60,
    "risks": "本実験で想定される肉体的・精神的苦痛は...",
    "reward_amount": 1500,
    "reward_type": "Amazonギフトカード（Eメールタイプ）",
    "safety_measures": "万一健康被害が見られる場合は...",
    "anonymization_method": "連結可能匿名化による...",
    "consent_withdrawal_deadline": "同意書署名の日から90日後"
  }
}
```

### レスポンス

docxファイルがダウンロードされます。

**ファイル名**: `同意書.docx`

## 使用例

### cURLでテスト

```bash
curl -X POST http://localhost:8000/api/consent/consent-form \
  -H "Content-Type: application/json" \
  -d @consent_request.json \
  --output consent.docx
```

### Pythonで使用

```python
import requests

data = {
    "form_data": {
        "research_title": "テスト研究",
        "research_purpose": "これはテストです",
        # ... その他のフィールド
    }
}

response = requests.post(
    "http://localhost:8000/api/consent/consent-form",
    json=data
)

with open("同意書.docx", "wb") as f:
    f.write(response.content)
```

### フロントエンドで使用

```typescript
const generateConsentForm = async (formData: any) => {
  const response = await fetch('/api/consent/consent-form', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ form_data: formData }),
  });

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = '同意書.docx';
  a.click();
};
```

## フィールド詳細

### 必須フィールド

- `research_title`: 研究課題名
- `research_purpose`: 研究目的
- `research_method`: 研究方法

### 推奨フィールド

- `participant_criteria`: 研究対象者条件
- `research_significance`: 研究の意義
- `experiment_procedures`: 実験手順（配列）
- `duration_minutes`: 所要時間（分）
- `risks`: 考えられるリスク
- `reward_amount`: 謝礼額
- `safety_measures`: 安全対策

### オプションフィールド

- `reward_type`: 謝礼の種類（デフォルト: Amazonギフトカード）
- `anonymization_method`: 匿名化方法
- `consent_withdrawal_deadline`: 同意撤回期限

## 研究室デフォルトとの統合

以下の情報は `lab_defaults.json` から自動取得されます：

- 研究責任者名
- 所属
- 連絡先
- データ管理場所
- データ管理方法
- データ処分方法

## 同意撤回書

同意撤回書は別途サンプルファイルとして提供されます。
基本的にフォーマットが固定されているため、サンプルをそのままダウンロードして使用できます。

## 注意事項

1. **個人情報の取り扱い**
   - 生成された同意書には個人情報は含まれません
   - 署名欄は空白で生成されます

2. **カスタマイズ**
   - 生成後、Wordで開いて微調整が可能です
   - フォーマットは基本的なものなので、必要に応じて調整してください

3. **バージョン管理**
   - 同意書の内容を変更した場合は、バージョン番号を記録することを推奨します
