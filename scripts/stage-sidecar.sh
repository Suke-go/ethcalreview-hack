#!/usr/bin/env bash
# scripts/stage-sidecar.sh
# PyInstaller (onefile) で backend を 1 バイナリ化し、Tauri sidecar として配置
#
# 使い方:
#   bash scripts/stage-sidecar.sh
#   (macOS / Linux 向け。Windows は scripts/stage-sidecar.ps1 を使用)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"
BIN_DIR="$ROOT/src-tauri/binaries"

# 1) venv の Python を準備
PYTHON="$BACKEND/venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
    echo "venv が無いので作成します..."
    python3 -m venv "$BACKEND/venv"
    "$PYTHON" -m pip install -q --upgrade pip
    "$PYTHON" -m pip install -q -r "$BACKEND/requirements.txt"
    "$PYTHON" -m pip install -q pyinstaller
fi

# 2) PyInstaller (onefile)
echo "PyInstaller で backend をビルド中 (1〜3 分)..."
(
    cd "$BACKEND"
    "$PYTHON" -m PyInstaller \
        --clean --noconfirm \
        --distpath dist-onefile \
        --workpath build-onefile \
        backend-onefile.spec
)

# 3) target triple を確定して sidecar 名にリネーム
TARGET_TRIPLE="$(rustc -Vv | awk '/^host:/ {print $2}')"
if [[ -z "$TARGET_TRIPLE" ]]; then
    echo "rustc が見つかりません。Rust を入れてから再実行してください。" >&2
    exit 1
fi

mkdir -p "$BIN_DIR"

SRC="$BACKEND/dist-onefile/backend"
DST="$BIN_DIR/backend-${TARGET_TRIPLE}"
case "$TARGET_TRIPLE" in
    *-windows-*) SRC="$SRC.exe"; DST="$DST.exe" ;;
esac

[[ -f "$SRC" ]] || { echo "ビルド成果物が見つかりません: $SRC" >&2; exit 1; }
cp -f "$SRC" "$DST"
chmod +x "$DST"

echo
echo "✓ sidecar 配置完了"
echo "  $DST"
echo "  size: $(du -h "$DST" | cut -f1)"
echo
echo "次は: npm --prefix frontend exec tauri build"
