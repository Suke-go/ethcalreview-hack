"""
PyInstaller用エントリポイント
Uvicornを使ってFastAPIアプリを起動
"""
import sys
import os

# PyInstaller環境の場合、実行ファイルのディレクトリを設定
if getattr(sys, 'frozen', False):
    # PyInstallerでビルドされた実行ファイルの場合
    base_path = sys._MEIPASS
    os.chdir(os.path.dirname(sys.executable))
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

# パスを追加
sys.path.insert(0, base_path)

import uvicorn
from app.main import app

if __name__ == "__main__":
    # 環境変数からポートを取得（デフォルト8000）
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "127.0.0.1")
    
    print(f"[Backend] Starting server on {host}:{port}", flush=True)
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True,
    )
