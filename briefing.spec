# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for briefing.exe

import os, sys, glob

block_cipher = None

# venv fix: python3xx.dll lives in the base Python install, not in the venv.
# PyInstaller only searches sys.executable's directory, so it misses it.
_py_dll = os.path.join(
    sys.base_prefix,
    f"python{sys.version_info.major}{sys.version_info.minor}.dll",
)
_extra_binaries = [(_py_dll, ".")] if os.path.exists(_py_dll) else []

datas = [
    # Prompt templates (read-only, loaded from _MEIPASS via config.py)
    ("data/prompts/brief.txt",          "data/prompts"),
    ("data/prompts/inspect.txt",        "data/prompts"),
    ("data/prompts/outline_trace.txt",  "data/prompts"),
    ("data/prompts/summarize.txt",      "data/prompts"),
    # ffmpeg binary (read-only, added to PATH at startup via main.py)
    ("data/ffmpeg/ffmpeg.exe",          "data/ffmpeg"),
    # Web UI single-page app
    ("backend/static/index.html",       "backend/static"),
]

hiddenimports = [
    # uvicorn — uses string-based dynamic imports that PyInstaller misses
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    # fastapi / starlette
    "fastapi",
    "fastapi.staticfiles",
    "fastapi.responses",
    "fastapi.middleware.cors",
    "starlette.routing",
    "starlette.staticfiles",
    "starlette.responses",
    "starlette.middleware.cors",
    "anyio",
    "anyio.abc",
    # sqlalchemy
    "sqlalchemy",
    "sqlalchemy.dialects.sqlite",
    "sqlalchemy.orm",
    "sqlalchemy.ext.declarative",
    # faster-whisper / ctranslate2
    "faster_whisper",
    "ctranslate2",
    # yt-dlp (has 1000+ site extractors loaded dynamically)
    "yt_dlp",
    "yt_dlp.extractor",
    "yt_dlp.postprocessor",
    # tiktoken
    "tiktoken",
    "tiktoken.core",
    "tiktoken_ext",
    "tiktoken_ext.openai_public",
    # pywebview (Windows uses EdgeChromium backend)
    "webview",
    "webview.platforms.edgechromium",
    "webview.platforms.winforms",
    # stdlib / other
    "multiprocessing",
    "requests",
    # backend app — loaded dynamically via uvicorn string "backend.app.main:app"
    "backend",
    "backend.app",
    "backend.app.main",
    "backend.app.config_store",
    "backend.app.config_schema",
    "backend.app.runner",
]

a = Analysis(
    ["launcher.py"],
    pathex=["."],
    binaries=_extra_binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["hooks/rthook_tiktoken.py"],
    excludes=["pytest", "ipython", "jupyter", "matplotlib", "tkinter"],
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
    name="briefing",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,   # keep terminal visible for error diagnostics
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="briefing",
)
