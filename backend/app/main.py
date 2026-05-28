"""
FastAPI メインアプリケーション
"""
import sys
import asyncio
import os
from pathlib import Path

# .env ファイルから環境変数を読み込み
from dotenv import load_dotenv

# backend/.env を優先的に読み込み
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"[MAIN] Loaded .env from {env_path}", flush=True)
else:
    # フォールバック: カレントディレクトリの.env
    load_dotenv()

# 読み込み確認
if os.environ.get("OPENAI_API_KEY"):
    print("[MAIN] OPENAI_API_KEY: SET", flush=True)
if os.environ.get("GEMINI_API_KEY"):
    print("[MAIN] GEMINI_API_KEY: SET", flush=True)

# Windows環境でのイベントループポリシー設定（アプリ起動前に設定）
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    print("[MAIN] Windows: Set WindowsSelectorEventLoopPolicy", flush=True)

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError

from app.api import settings, analyze, generate, review
from app.api import analyze_stream, review_stream, generate_stream
from app.api import session, rebuttal, detect, documents, ingest

app = FastAPI(
    title="EthicalReviewHacker API",
    description="Ethical Review Document Support System",
    version="0.1.0"
)


def add_cors_headers(response: JSONResponse, origin: str) -> JSONResponse:
    """レスポンスにCORSヘッダーを追加"""
    response.headers["Access-Control-Allow-Origin"] = origin if origin else "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response


# HTTPException用ハンドラー（最も重要）
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    print(f"[HTTP ERROR {exc.status_code}] {exc.detail}", flush=True)
    origin = request.headers.get("origin", "*")
    response = JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )
    return add_cors_headers(response, origin)


# バリデーションエラー用ハンドラー
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print(f"[VALIDATION ERROR] {exc.errors()}", flush=True)
    origin = request.headers.get("origin", "*")
    response = JSONResponse(
        status_code=422,
        content={"detail": exc.errors()}
    )
    return add_cors_headers(response, origin)


# その他すべての例外用ハンドラー
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"[UNHANDLED ERROR] {type(exc).__name__}: {str(exc)}", flush=True)
    origin = request.headers.get("origin", "*")
    response = JSONResponse(
        status_code=500,
        content={"detail": f"{type(exc).__name__}: {str(exc)}"}
    )
    return add_cors_headers(response, origin)


# CORS設定（開発環境：すべてのオリジンを許可）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ルーター登録
app.include_router(settings.router, prefix="/api/settings", tags=["Settings"])
app.include_router(analyze.router, prefix="/api/analyze", tags=["Analyze"])
app.include_router(analyze_stream.router, prefix="/api/analyze", tags=["Analyze Stream"])
app.include_router(generate.router, prefix="/api/generate", tags=["Generate"])
app.include_router(generate_stream.router, prefix="/api/generate", tags=["Generate Stream"])
app.include_router(review.router, prefix="/api/review", tags=["Review"])
app.include_router(review_stream.router, prefix="/api/review", tags=["Review Stream"])
app.include_router(session.router, prefix="/api/sessions", tags=["Session"])
app.include_router(rebuttal.router, prefix="/api/rebuttal", tags=["Rebuttal"])
app.include_router(detect.router, prefix="/api/detect", tags=["Detection"])
app.include_router(documents.router, prefix="/api/documents", tags=["Document Generation"])
app.include_router(ingest.router, prefix="/api/ingest", tags=["Document Ingestion"])


@app.get("/health")
async def health():
    return {"status": "healthy"}


# ============================================================
# フロントエンドの静的配信 (SPA)
# - ERH_FRONTEND_DIST 環境変数で明示指定可
# - 既定では <project_root>/frontend/dist を探す (Web ホスティング / Tauri 双方で利用)
# - dist が無ければ API のみのモードで起動 (開発時 / Vite dev server と併用)
# ============================================================

def _resolve_frontend_dist() -> Path | None:
    """フロントエンドのビルド成果物ディレクトリを解決する。"""
    explicit = os.environ.get("ERH_FRONTEND_DIST")
    if explicit:
        p = Path(explicit)
        return p if p.exists() else None

    project_root = Path(__file__).parent.parent.parent
    candidates = [
        project_root / "frontend" / "dist",   # 通常のリポジトリ構成
        Path(__file__).parent.parent / "dist",  # PyInstaller bundle が backend/dist にコピーされた場合
        Path(getattr(sys, "_MEIPASS", "")) / "frontend" / "dist" if hasattr(sys, "_MEIPASS") else None,
    ]
    for c in candidates:
        if c and c.exists() and (c / "index.html").exists():
            return c
    return None


_FRONTEND_DIST = _resolve_frontend_dist()

if _FRONTEND_DIST is not None:
    print(f"[MAIN] Serving frontend SPA from {_FRONTEND_DIST}", flush=True)

    # /api/* は include_router で先に登録済みなので、こちらが先に match される。
    # ここでの mount は残った GET にだけ index.html / 静的ファイルを返す。
    app.mount(
        "/",
        StaticFiles(directory=_FRONTEND_DIST, html=True),
        name="spa",
    )
else:
    print("[MAIN] frontend/dist not found; running in API-only mode", flush=True)

    @app.get("/", include_in_schema=False)
    async def root():
        return {"message": "EthicalReviewHacker API", "version": "0.1.0"}
