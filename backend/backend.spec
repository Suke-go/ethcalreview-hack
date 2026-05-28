# -*- mode: python ; coding: utf-8 -*-
"""
EthicalReviewHacker Backend - PyInstaller spec file
FastAPIバックエンドをスタンドアロンexeにビルド
"""

import os
from pathlib import Path

block_cipher = None

# プロジェクトのルートディレクトリ
ROOT_DIR = Path(SPECPATH)

# 隠れたインポート（動的にインポートされるモジュール）
hidden_imports = [
    # FastAPI / Uvicorn
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'uvicorn.lifespan.off',
    
    # FastAPI / Starlette
    'starlette.responses',
    'starlette.routing',
    'starlette.middleware',
    'starlette.middleware.cors',
    'fastapi.middleware.cors',
    'fastapi.responses',
    'fastapi.templating',
    
    # Pydantic
    'pydantic',
    'pydantic_core',
    'pydantic_settings',
    
    # LLM Clients
    'openai',
    'google.genai',
    'google.generativeai',
    
    # Document generation
    'docxtpl',
    'docx',
    'openpyxl',
    'lxml',
    'lxml.etree',
    
    # HTTP
    'httpx',
    'httpcore',
    
    # Async
    'anyio',
    'anyio._backends._asyncio',
    'sniffio',
    
    # その他
    'dotenv',
    'tenacity',
    'email_validator',
    
    # Appモジュール
    'app',
    'app.main',
    'app.config',
    'app.logger',
    'app.api',
    'app.api.settings',
    'app.api.analyze',
    'app.api.analyze_stream',
    'app.api.generate',
    'app.api.generate_stream',
    'app.api.review',
    'app.api.review_stream',
    'app.api.session',
    'app.api.rebuttal',
    'app.api.detect',
    'app.api.documents',
    'app.services',
    'app.models',
    'app.schemas',
    'app.utils',
]

# データファイル（テンプレート、スキーマなど）
datas = [
    # テンプレートファイル
    (str(ROOT_DIR / 'templates'), 'templates'),
    # スキーマファイル  
    (str(ROOT_DIR / 'schemas'), 'schemas'),
    # .env.example（.envは含めない）
    (str(ROOT_DIR / '.env.example'), '.'),
]

# 追加の .env があれば含める（オプション）
# if (ROOT_DIR / '.env').exists():
#     datas.append((str(ROOT_DIR / '.env'), '.'))

a = Analysis(
    ['run_server.py'],
    pathex=[str(ROOT_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 不要なモジュールを除外
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'cv2',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # コンソール出力を有効化（デバッグ用）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # アイコンが必要な場合は指定
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='backend',
)
