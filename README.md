# EthicalReviewHacker

> 筑波大学の研究倫理審査申請書類を自動生成するAI駆動システム

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Node.js 18+](https://img.shields.io/badge/Node.js-18+-green.svg)](https://nodejs.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 🚀 クイックスタート

### Windows
```
start.bat をダブルクリック
```

### macOS / Linux
```bash
chmod +x start.sh
./start.sh
```

> 初回起動時は依存関係のインストールに数分かかります。  
> 起動後、ブラウザが自動で開きます。**設定画面からAPIキーを入力してください。**

---

## 概要

**EthicalReviewHacker** は、筑波大学の研究倫理審査プロセスを効率化するための高精度自動化システムです。React 19フロントエンドとFastAPIバックエンドを組み合わせ、永続化されたPydanticセッションモデル、AI駆動の反論提案、リアルタイムSSE追跡を特徴としています。

### 主な機能

- 📝 **書類自動生成**: docxtplによる公式テンプレート完全準拠のdocx生成
- 🤖 **AI支援**: Google Gemini/OpenAIによる記述内容の自動生成・改善提案
- 💾 **セッション永続化**: Pydantic Settingsによる作業状態の保存・復元
- 🔄 **リアルタイム更新**: Server-Sent Events (SSE) による生成進捗の可視化
- 📋 **複数書類対応**: 申請書・同意書・実施計画書・募集案内など7種類
- ⚙️ **フロントエンド設定**: ブラウザ上で研究室情報・APIキーを設定可能

### 対応書類

1. **研究倫理審査申請書** (`01-1_申請書_template.docx`)
2. **実施計画書** (`01-2_実施計画書_template.docx`)
3. **同意書** (`03_同意書_template.docx`)
4. **同意撤回書** (`04_同意撤回書_template.docx`)
5. **募集案内文** (`募集案内文_template.docx`)
6. **アンケート用紙** (新規生成)
7. **実験説明台本** (新規生成)

## 技術スタック

### Frontend
- **Framework**: React 19.2 + TypeScript
- **Build Tool**: Vite 7.2
- **Form Management**: React Hook Form + Zod
- **HTTP Client**: Axios
- **UI Feedback**: React-Toastify

### Backend
- **Framework**: FastAPI (>=0.110.0)
- **Server**: Uvicorn with async/await support
- **AI Models**: Google Gemini AI + OpenAI
- **Document Generation**: docxtpl (>=0.18.0) + python-docx (>=1.1.0)
- **Validation**: Pydantic 2.0
- **Resilience**: Tenacity (retry logic)

## セットアップ（手動）

### 前提条件

- **Node.js**: 18.x 以上
- **Python**: 3.10 以上
- **API Key**: Google Gemini API または OpenAI API

### 1. リポジトリのクローン

```bash
git clone https://github.com/your-org/EthicalReviewHacker.git
cd EthicalReviewHacker
```


### 2. バックエンドのセットアップ

```bash
cd backend

# 仮想環境の作成と有効化 (推奨)
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux

# 依存関係のインストール
pip install -r requirements.txt
```

**settings.jsonの設定**:

```json
{
  "llm_provider": "gemini",
  "gemini_api_key": "YOUR_GEMINI_API_KEY",
  "openai_api_key": "YOUR_OPENAI_API_KEY",
  "model_name": "gemini-2.0-flash-exp",
  "max_retries": 3,
  "retry_delay": 2.0
}
```

### 3. フロントエンドのセットアップ

```bash
cd ../frontend

# 依存関係のインストール
npm install
```

### 4. 起動

**バックエンド**:
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

**フロントエンド**:
```bash
cd frontend
npm run dev
```

フロントエンドは `http://localhost:5173` で起動します。

## プロジェクト構造

```
EthicalReviewHacker/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPIアプリケーションエントリーポイント
│   │   ├── config.py            # 設定管理 (Pydantic Settings)
│   │   ├── logger.py            # ロギング設定
│   │   ├── routes/              # APIエンドポイント
│   │   ├── services/            # ビジネスロジック (LLM, 書類生成)
│   │   └── models/              # Pydanticモデル
│   ├── templates/               # docxtplテンプレート (.docx)
│   ├── schemas/                 # JSON Schema
│   ├── sessions/                # セッション永続化
│   ├── output/                  # 生成されたdocxファイル
│   ├── requirements.txt
│   └── settings.json            # 環境設定 (API Key等)
│
├── frontend/
│   ├── src/
│   │   ├── components/          # React コンポーネント
│   │   ├── hooks/               # カスタムフック
│   │   ├── services/            # API通信
│   │   ├── types/               # TypeScript型定義
│   │   └── App.tsx              # ルートコンポーネント
│   ├── public/
│   ├── package.json
│   └── vite.config.ts
│
├── docs/
│   └── docx_generation_design.md  # docx生成方式設計書
│
├── sample/                      # サンプル書類・テンプレート
├── scripts/                     # ユーティリティスクリプト
└── README.md
```

## 使い方

### 基本フロー

1. **研究情報の入力**: Webフォームから研究課題名、研究者情報、実験概要等を入力
2. **AI生成**: 自動的に各書類の記述内容をAIが生成・提案
3. **内容確認・編集**: 生成された内容をレビュー・修正
4. **書類ダウンロード**: docxファイル一括ダウンロード

### docx生成の仕組み

#### docxtpl方式

公式テンプレートに **Jinja2プレースホルダー** を挿入し、データを埋め込む方式を採用。これにより大学指定のフォーマットを完全に保持できます。

**テンプレート例**:
```
研究代表者: {{ pi_name }}
所属: {{ pi_affiliation }}

{{ is_new_application | checkbox }}新規申請
{{ is_resubmission | checkbox }}再申請
```

**コード例**:
```python
from docxtpl import DocxTemplate

doc = DocxTemplate("templates/03_同意書_template.docx")
context = {
    "research_title": "視線追跡による認知負荷測定",
    "pi_name": "山田 太郎",
    "pi_tel": "029-853-XXXX",
    "duration_minutes": 60,
    "reward_amount": "2000円分のQUOカード"
}
doc.render(context)
doc.save("output/consent_form.docx")
```

詳細は [`docs/docx_generation_design.md`](docs/docx_generation_design.md) を参照。

## API仕様

### 主要エンドポイント

#### `POST /api/generate`
研究情報から書類を一括生成

**Request**:
```json
{
  "research_title": "視線追跡による認知負荷測定実験",
  "pi_name": "山田 太郎",
  "experiment_type": "行動実験",
  "participant_count": 30,
  "duration_minutes": 60,
  ...
}
```

**Response**: Server-Sent Events (SSE)
```
event: progress
data: {"status": "generating_consent_form", "progress": 30}

event: complete
data: {"files": ["consent.docx", "application.docx", ...]}
```

#### `GET /api/session/{session_id}`
保存されたセッション情報を取得

#### `POST /api/rebuttal`
査読コメントへの反論文を自動生成

## 開発ガイド

### テンプレート作成方法

1. `sample/` から公式テンプレートをコピー
2. 記入済み箇所を Jinja2 プレースホルダーに置換
3. `backend/templates/` に保存

**チェックボックス処理例**:
```python
# カスタムフィルター登録
doc = DocxTemplate("template.docx")
doc.jinja_env.filters["checkbox"] = lambda v: "■" if v else "□"

# テンプレート内
{{ is_new | checkbox }}新規  {{ is_resubmission | checkbox }}再申請
```

**表の行ループ**:
```
{% tr for member in team_members %}
{{ member.affiliation }} | {{ member.position }} | {{ member.name }}
{% tr endfor %}
```

### テスト

```bash
# バックエンド単体テスト
cd backend
pytest

# フロントエンドテスト用クライアント
python test_client.py
```

## トラブルシューティング

### Windows OSError 22 (SSE接続エラー)

**症状**: SSEストリーミング中に `OSError: [Errno 22] Invalid argument`

**解決策**:
1. Uvicornの起動時に `--log-config` を指定し、stderrへのロギングを優先
2. FastAPIのSSEハンドラーで明示的な `await asyncio.sleep(0)` を追加
3. `StreamingResponse` の `media_type` を `text/event-stream; charset=utf-8` に設定

詳細は Knowledge Item `Ethical Review Hacker (University of Tsukuba)` を参照。

### LLM認証エラー

**症状**: `401 Unauthorized` または API Key エラー

**確認事項**:
- `backend/settings.json` のAPI Keyが正しいか
- API Keyに課金設定がされているか（無料枠の制限）
- `llm_provider` の値が `"gemini"` または `"openai"` か

## ライセンス

MIT License

## 貢献

Issues / Pull Requests歓迎します。

## 関連ドキュメント

- [docx生成方式設計書](docs/docx_generation_design.md)
- [Frontend README](frontend/README.md)

## 連絡先

- Email: your.email@example.com
- GitHub Issues: [Issues Page](https://github.com/yourusername/EthicalReviewHacker/issues)
