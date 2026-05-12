# sidecar binaries

ここに PyInstaller でビルドした backend バイナリを **Rust の target triple サフィックス付き** で配置します。
Tauri は `tauri.conf.json` の `bundle.externalBin: ["binaries/backend"]` から、ビルド対象に応じてサフィックス付きファイルを自動で拾います。

## 期待されるファイル名

| OS / Arch | 期待されるファイル名 |
|---|---|
| Windows x86_64 | `backend-x86_64-pc-windows-msvc.exe` |
| macOS Apple Silicon | `backend-aarch64-apple-darwin` |
| macOS Intel | `backend-x86_64-apple-darwin` |
| Linux x86_64 | `backend-x86_64-unknown-linux-gnu` |

## ビルド手順

### Windows
```powershell
cd backend
.\venv\Scripts\activate
python -m PyInstaller --clean --noconfirm backend.spec
# dist/backend/ に成果物が出る
# 1 つの onedir をそのまま sidecar には使えないので、`backend.exe` を _internal と一緒に
# binaries 配下にコピーし、ファイル名を target triple 付きにリネームする。
# (詳細は scripts/build-sidecar-windows.ps1 を参照)
```

### macOS
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt pyinstaller
pyinstaller --clean --noconfirm backend.spec
# Apple Silicon の場合
cp -R dist/backend ../src-tauri/binaries/backend-aarch64-apple-darwin-bundle
mv ../src-tauri/binaries/backend-aarch64-apple-darwin-bundle/backend \
   ../src-tauri/binaries/backend-aarch64-apple-darwin
```

## 注意

PyInstaller の **onedir** モードは `backend.exe + _internal/` のセットを必要とします。
sidecar 用には、Tauri が `_internal/` も同梱できるよう `tauri.conf.json` の `bundle.resources`
にディレクトリを追加するか、PyInstaller を **onefile** モード (`backend.spec` で
`EXE(...)` の `exclude_binaries=False`) に変更してください。

onefile は起動が 1〜2 秒遅いですが、単一バイナリで sidecar に乗せやすい利点があります。
