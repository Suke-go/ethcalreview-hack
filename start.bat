@echo off
chcp 65001 > nul
echo ========================================
echo   EthicalReviewHacker 起動スクリプト
echo ========================================
echo.

cd /d %~dp0

REM Python仮想環境確認・作成
echo [1/4] バックエンド環境を準備中...
cd backend
if not exist venv (
    echo   仮想環境を作成中...
    python -m venv venv
)
call venv\Scripts\activate
pip install -r requirements.txt -q
echo   バックエンド準備完了

REM バックエンド起動（新しいウィンドウ）
echo [2/4] バックエンドサーバーを起動中...
start "EthicalReviewHacker Backend" cmd /k "cd /d %~dp0backend && venv\Scripts\activate && uvicorn app.main:app --port 8000"

REM フロントエンド準備
echo [3/4] フロントエンドを準備中...
cd /d %~dp0frontend
if not exist node_modules (
    echo   npm install を実行中...
    call npm install
)

REM フロントエンド起動（新しいウィンドウ）
echo [4/4] フロントエンドサーバーを起動中...
start "EthicalReviewHacker Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo ========================================
echo   サーバー起動完了！
echo   5秒後にブラウザを開きます...
echo ========================================
timeout /t 5 /nobreak > nul
start http://localhost:5173

echo.
echo 終了するにはこのウィンドウを閉じ、
echo BackendとFrontendのウィンドウも閉じてください。
pause
