# 配布ガイド (Web ホスティング & Tauri デスクトップ)

EthicalReviewHacker は **同一コードベースから 2 通りの配布**ができます。

| 配布形態 | 用途 | 必要ツール |
|---|---|---|
| **Web 配信** | 研究室内に常時稼働の URL を 1 つ持つ | Docker + Fly.io (無料枠あり) |
| **Tauri デスクトップ** | 各端末にインストールしてオフライン利用 | Rust + Node + Python + (mac の場合) Apple Developer 証明書 |

---

## 共通の事前準備

### フロントエンドのビルド

両方の配布形態で、ビルド済みの React (`frontend/dist/`) を使います。

```bash
cd frontend
npm install
npm run build
# → frontend/dist/ が生成される
```

FastAPI は `frontend/dist/` が存在すれば自動で `/` から SPA を配信します(`app/main.py` の `_resolve_frontend_dist()`)。

### API ベース URL の自動判定

`frontend/src/api/client.ts` は実行環境に応じて自動で URL を切り替えます:

| 実行環境 | API ベース URL |
|---|---|
| Tauri ランタイム内 | `http://127.0.0.1:17500` (sidecar の固定ポート) |
| `VITE_API_URL` 環境変数指定時 | その値 |
| それ以外 | 同一オリジン (`""`) |

開発時は `frontend/.env.development` で `VITE_API_URL=http://localhost:8000` が指定されています。

---

## Phase A: Web 配信 (Fly.io)

### 1. ローカルで Docker 動作確認

```bash
docker build -t ethical-review-hacker .
docker run --rm -p 8000:8000 \
  -v ethics_data:/data \
  ethical-review-hacker

# 別ターミナルで
curl http://localhost:8000/health
# → {"status":"healthy"}
# ブラウザで http://localhost:8000 → SPA が表示
```

### 2. Fly.io にデプロイ

```bash
# 初回のみ
flyctl auth signup           # or `flyctl auth login`
flyctl launch --no-deploy    # fly.toml の app 名を一意に書き換える
flyctl volumes create ethics_data --region nrt --size 1

# 環境変数 (任意。フロント側で API キー設定するなら不要)
flyctl secrets set GEMINI_API_KEY="..." OPENAI_API_KEY="..."

# デプロイ
flyctl deploy

# 確認
flyctl open
```

### 3. (推奨) 簡易アクセス制御を入れる

`settings.json` に自分の API キーが入った状態でインターネットに公開すると、第三者が叩けて従量課金が走る。**最低でも以下のいずれかは必須:**

- **Cloudflare Access** (推奨。Fly.io の前段に置く)
- **Fly.io の `[deploy] strategy = "bluegreen"` + reverse-proxy で Basic 認証**
- 上記のいずれも面倒なら、API キーをサーバに保存せずフロントの設定画面から毎回入れる運用にする

### 4. 料金の目安

- Fly.io 共有 1×CPU / 512MB / 1GB volume / nrt: **約 0〜3 USD/月** (auto-stop で実質ほぼ無料)
- 帯域はほぼ無視できる量

---

## Phase B: Tauri デスクトップ

### 0. 前提ツール

- **Rust** (`rustup` 経由): https://www.rust-lang.org/tools/install
- **Node.js 18+**
- **Python 3.10+** (PyInstaller でバックエンドを sidecar 化する)
- macOS ビルドを Windows 上で作ることはできないので、**macOS 版は Mac で or GitHub Actions の `macos-latest` で**ビルドする

### 1〜2. バックエンドを sidecar として配置 (一発スクリプト)

**onefile 版 spec** (`backend/backend-onefile.spec`) を使うと 1 ファイルの `backend.exe` (約 37MB) が生成され、Tauri sidecar にそのまま渡せます。

PowerShell 一撃で:
```powershell
pwsh scripts/stage-sidecar.ps1
# → src-tauri/binaries/backend-x86_64-pc-windows-msvc.exe が配置される
```

手動でやりたい場合:
```bash
cd backend
python -m venv venv && venv\Scripts\activate   # Windows
# source venv/bin/activate                      # macOS / Linux
pip install -r requirements.txt pyinstaller
python -m PyInstaller --clean --noconfirm \
    --distpath dist-onefile --workpath build-onefile \
    backend-onefile.spec
# → backend/dist-onefile/backend.exe (single file, ~37MB)

# sidecar として配置 (target triple サフィックスを付ける)
mkdir -p ../src-tauri/binaries
cp dist-onefile/backend.exe ../src-tauri/binaries/backend-x86_64-pc-windows-msvc.exe
# macOS Apple Silicon の場合:
# cp dist-onefile/backend ../src-tauri/binaries/backend-aarch64-apple-darwin
```

> **検証済み**: Windows 上で `backend-onefile.spec` の onefile ビルドは 37MB、起動 ~2 秒。
> 起動時に `%TEMP%\_MEI*\` へ展開されるため初回だけ遅い (2 回目以降はキャッシュされる)。

### 3. Tauri CLI を入れる (済 — frontend の devDependencies に追加済み)

```bash
npm --prefix frontend install   # @tauri-apps/cli と @tauri-apps/api が入る
```

### 4. 開発モードで起動

```bash
# プロジェクトルート (ethcalreview-hack/) から実行
npm --prefix frontend exec tauri dev
# Vite dev server + Tauri ウィンドウ + sidecar (backend) が一括で起動
```

### 5. 本番ビルド

```bash
# プロジェクトルートから
npm --prefix frontend exec tauri build
# Windows: src-tauri/target/release/bundle/msi/*.msi
#          src-tauri/target/release/bundle/nsis/*.exe
# macOS:   src-tauri/target/release/bundle/dmg/*.dmg
```

> 初回ビルドは cargo の依存コンパイルで 15〜25 分かかります。2 回目以降はキャッシュが効いて 1〜2 分。

### 6. 署名 / 公証

| OS | 署名なし | 推奨 |
|---|---|---|
| Windows | SmartScreen 警告が出るが起動可 | Code Signing 証明書 (年 1〜5 万円) |
| macOS | **Gatekeeper で起動拒否** | Apple Developer Program 加入 + `notarytool` で公証 (年 99 USD) |

研究室内配布なら署名無しでも、配布相手に「右クリック → 開く」または `xattr -dr com.apple.quarantine /Applications/EthicalReviewHacker.app` をやってもらえば動きます。

### 7. (推奨) GitHub Actions で 3 OS 同時ビルド

`.github/workflows/tauri-release.yml` の例:

```yaml
name: Tauri Release
on:
  push:
    tags: ['v*']
jobs:
  build:
    strategy:
      matrix:
        platform: [windows-latest, macos-latest]
    runs-on: ${{ matrix.platform }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20 }
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - uses: dtolnay/rust-toolchain@stable
      - name: Build backend sidecar (PyInstaller)
        run: |
          cd backend
          pip install -r requirements.txt pyinstaller
          pyinstaller --clean --noconfirm backend.spec
        shell: bash
      - name: Stage sidecar binary
        run: bash scripts/stage-sidecar.sh
      - run: npm --prefix frontend ci
      - uses: tauri-apps/tauri-action@v0
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        with:
          tagName: ${{ github.ref_name }}
          releaseName: 'EthicalReviewHacker ${{ github.ref_name }}'
```

---

## 動作確認チェックリスト

### Web (ローカル)
- [ ] `npm --prefix frontend run build` 成功
- [ ] `docker build -t ethical-review-hacker .` 成功
- [ ] `docker run -p 8000:8000 ethical-review-hacker` で http://localhost:8000 が SPA を表示
- [ ] http://localhost:8000/health が 200
- [ ] http://localhost:8000/docs (FastAPI) が表示
- [ ] 設定画面で API キー保存 → 解析実行 → ファイル生成まで通る

### Tauri (ローカル)
- [ ] `cd backend && pyinstaller backend.spec` で `dist/backend/backend.exe` 生成
- [ ] `src-tauri/binaries/backend-x86_64-pc-windows-msvc.exe` が存在
- [ ] `npx tauri dev` でウィンドウが開いて SPA 表示
- [ ] ウィンドウ内から `/api/health` が叩ける (DevTools の Network で確認)
- [ ] `npx tauri build` で `.msi` 生成
