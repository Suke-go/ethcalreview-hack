#!/bin/bash
# ========================================
#   EthicalReviewHacker 起動スクリプト
# ========================================

set -e
cd "$(dirname "$0")"

echo "========================================"
echo "  EthicalReviewHacker 起動スクリプト"
echo "========================================"
echo ""

# バックエンド準備
echo "[1/4] バックエンド環境を準備中..."
cd backend
if [ ! -d "venv" ]; then
    echo "  仮想環境を作成中..."
    python3 -m venv venv
fi
source venv/bin/activate
pip install -r requirements.txt -q
echo "  バックエンド準備完了"

# バックエンド起動（バックグラウンド）
echo "[2/4] バックエンドサーバーを起動中..."
uvicorn app.main:app --port 8000 &
BACKEND_PID=$!

# フロントエンド準備
echo "[3/4] フロントエンドを準備中..."
cd ../frontend
if [ ! -d "node_modules" ]; then
    echo "  npm install を実行中..."
    npm install --silent
fi

# フロントエンド起動（バックグラウンド）
echo "[4/4] フロントエンドサーバーを起動中..."
npm run dev &
FRONTEND_PID=$!

echo ""
echo "========================================"
echo "  サーバー起動完了！"
echo "  5秒後にブラウザを開きます..."
echo "========================================"
sleep 5

# ブラウザを開く
if command -v open &> /dev/null; then
    open http://localhost:5173
elif command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:5173
else
    echo "  ブラウザで http://localhost:5173 を開いてください"
fi

echo ""
echo "Ctrl+C で停止します..."

# 終了時にサーバーを停止
cleanup() {
    echo ""
    echo "サーバーを停止中..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM

wait
