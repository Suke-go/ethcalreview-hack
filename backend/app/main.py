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
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.api import settings, analyze, generate, review
from app.api import analyze_stream, review_stream, generate_stream
from app.api import session, rebuttal, detect, consent, documents

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
app.include_router(consent.router, prefix="/api/consent", tags=["Consent Forms"])
app.include_router(documents.router, prefix="/api/documents", tags=["Document Generation"])


@app.get("/")
async def root():
    return {"message": "EthicalReviewHacker API", "version": "0.1.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
