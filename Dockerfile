# syntax=docker/dockerfile:1.6
# ============================================================
# EthicalReviewHacker — single-tenant Web 配信用イメージ
# ------------------------------------------------------------
# 構成: Vite で React をビルド → Python 3.11 ランタイムに同梱
#       FastAPI が /api/* と /(static SPA) を同一ポートで配信
# 永続データ: ETHICS_DATA_DIR=/data (volume にマウント)
# ============================================================

# ---- Stage 1: Frontend build ----
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

# 依存だけ先に入れてキャッシュを効かせる
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

# ソース投入してビルド
COPY frontend/ ./
RUN npm run build


# ---- Stage 2: Python runtime ----
FROM python:3.11-slim AS runtime

# docx 生成系の C ライブラリ依存
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libxml2 \
        libxslt1.1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python 依存
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# バックエンド本体
COPY backend/ ./backend/

# フロントの static 成果物
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# 永続データディレクトリ (settings.json, sessions/, output/, lab_defaults.json)
RUN mkdir -p /data

# 設定
ENV PORT=8000 \
    HOST=0.0.0.0 \
    ETHICS_DATA_DIR=/data \
    ERH_FRONTEND_DIST=/app/frontend/dist \
    PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://127.0.0.1:${PORT}/health || exit 1

WORKDIR /app/backend
CMD ["python", "run_server.py"]
