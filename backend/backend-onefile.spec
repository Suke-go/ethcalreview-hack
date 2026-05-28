# -*- mode: python ; coding: utf-8 -*-
"""
EthicalReviewHacker Backend - PyInstaller spec (onefile mode for Tauri sidecar)

backend.spec (onedir) との違い: EXE() に a.binaries / a.zipfiles / a.datas を直接渡し、
COLLECT() を行わない。結果として 1 つの実行ファイルにすべてが詰まる。

利点: Tauri の bundle.externalBin にそのまま渡せる
欠点: 起動時に %TEMP% へ展開する分、初回起動が 1〜2 秒遅い
"""

import os
from pathlib import Path

block_cipher = None

ROOT_DIR = Path(SPECPATH)

# 既存の onedir spec と同じ内容
hidden_imports = [
    'uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto',
    'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets', 'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan', 'uvicorn.lifespan.on', 'uvicorn.lifespan.off',
    'starlette.responses', 'starlette.routing', 'starlette.middleware',
    'starlette.middleware.cors',
    'fastapi.middleware.cors', 'fastapi.responses', 'fastapi.templating',
    'pydantic', 'pydantic_core', 'pydantic_settings',
    'openai', 'google.genai', 'google.generativeai',
    'docxtpl', 'docx', 'openpyxl', 'lxml', 'lxml.etree',
    'httpx', 'httpcore',
    'anyio', 'anyio._backends._asyncio', 'sniffio',
    'dotenv', 'tenacity', 'email_validator',
    'app', 'app.main', 'app.config', 'app.logger',
    'app.api', 'app.api.settings', 'app.api.analyze', 'app.api.analyze_stream',
    'app.api.generate', 'app.api.generate_stream', 'app.api.review',
    'app.api.review_stream', 'app.api.session', 'app.api.rebuttal',
    'app.api.detect', 'app.api.documents',
    'app.services', 'app.models', 'app.schemas', 'app.utils',
]

datas = [
    (str(ROOT_DIR / 'templates'), 'templates'),
    (str(ROOT_DIR / 'schemas'), 'schemas'),
    (str(ROOT_DIR / '.env.example'), '.'),
]

a = Analysis(
    ['run_server.py'],
    pathex=[str(ROOT_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas', 'scipy', 'PIL', 'cv2'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ===== onefile: binaries / zipfiles / datas を EXE に直接埋め込む =====
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
