# 422 Unprocessable Entity エラー修正

## 問題の概要

`POST /api/generate` 呼び出し時に **422 Unprocessable Entity** エラーが発生していました。

## 原因

**フロントエンドとバックエンド間のフィールド名の不一致**

- **Frontend** (client.ts): `{ formData }` (camelCase) を送信
- **Backend** (generate.py): `{ form_data }` (snake_case) を期待

FastAPIのPydanticモデル検証により、期待されるフィールド名と異なるためリクエストが拒否されました。

## 修正内容

### 修正ファイル: `frontend/src/api/client.ts`

```diff
export const generateDocuments = async (
    formData: FormData
): Promise<GenerateResponse> => {
    const response = await defaultClient.post<GenerateResponse>('/api/generate', {
-        formData,
+        form_data: formData,  // snake_case に統一
    });
    return response.data;
};
```

## バックエンドのスキーマ定義

`backend/app/api/generate.py` の `GenerateRequest` モデル:

```python
class GenerateRequest(BaseModel):
    """書類生成リクエスト"""
    form_data: Dict[str, Any]  # ← snake_case
    documents: List[str] = [...]
```

## 再発防止策

### 1. 命名規則の統一

- **Python (Backend)**: snake_case
- **TypeScript (Frontend)**: camelCase
- **APIリクエスト/レスポンス**: snake_case に統一（Pydanticデフォルト）

### 2. 型定義の共有

TypeScriptの型定義にコメントでPythonフィールド名を記載:

```typescript
export interface GenerateRequest {
    form_data: FormData;  // Python: form_data
    documents?: string[];
}
```

### 3. Pydanticのエイリアス機能（オプション）

バックエンドでcamelCaseも受け付ける設定:

```python
from pydantic import BaseModel, Field

class GenerateRequest(BaseModel):
    form_data: Dict[str, Any] = Field(..., alias="formData")
    
    class Config:
        populate_by_name = True  # 両方の名前を許可
```

## 検証方法

1. フロントエンド再ビルド:
   ```bash
   cd frontend
   npm run dev
   ```

2. バックエンドで422エラーの詳細を確認:
   ```bash
   cd backend
   uvicorn app.main:app --reload
   # ログに [VALIDATION ERROR] と詳細が表示される
   ```

3. ブラウザの開発者ツールで確認:
   - Network タブ → `/api/generate` リクエスト
   - Payload に `form_data` フィールドが含まれているか確認

## 参考: 422エラーのデバッグ方法

FastAPIは親切にも、どのフィールドが問題かを `detail` に含めて返します:

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "form_data"],
      "msg": "Field required",
      "input": {"formData": {...}}
    }
  ]
}
```

ブラウザの開発者ツール (F12) → **Network** タブで確認できます。
