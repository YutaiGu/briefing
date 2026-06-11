# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for briefing.exe

import os, sys, glob
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# F2 (Douyin downloader) loads apps.douyin.* via dynamic string imports and
# ships its own config/data files. Static analysis misses both, so collect the
# whole package (submodules + data + binaries) explicitly.
_f2_datas, _f2_binaries, _f2_hiddenimports = collect_all("f2")

# venv fix: the base Python's DLLs aren't in the venv dir, so PyInstaller misses
# them. Bundle the ones C-extensions (e.g. pyexpat) need: pythonXY.dll + python3.dll.
_dll_names = [
    f"python{sys.version_info.major}{sys.version_info.minor}.dll",
    "python3.dll",
]
_dll_dirs = [sys.base_prefix, os.path.join(sys.base_prefix, "DLLs")]
_extra_binaries = []
for _name in _dll_names:
    for _d in _dll_dirs:
        _p = os.path.join(_d, _name)
        if os.path.exists(_p):
            _extra_binaries.append((_p, "."))
            break

datas = [
    (p, "briefing/summarizer_agent/prompts")
    for p in glob.glob("src/briefing/summarizer_agent/prompts/*.txt")
] + [
    ("assets/ffmpeg/ffmpeg.exe",            "assets/ffmpeg"),
    ("src/briefing/web/static/index.html",  "briefing/web/static"),
] + _f2_datas

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
    # briefing package — web app loaded via uvicorn string "briefing.web.app.main:app"
    "briefing",
    "briefing.config",
    "briefing.llm",
    "briefing.llm.router",
    "briefing.llm.pricing",
    "briefing.db",
    "briefing.cookies",
    "briefing.transcriber",
    "briefing.pusher",
    "briefing.worker",
    "briefing.downloaders",
    "briefing.downloaders.downloader",
    "briefing.downloaders.douyin_downloader",
    "briefing.summarizer_agent",
    "briefing.summarizer_agent.pipeline",
    "briefing.web",
    "briefing.web.app",
    "briefing.web.app.main",
    "briefing.web.app.config_store",
    "briefing.web.app.config_schema",
    "briefing.web.app.runner",
] + _f2_hiddenimports

a = Analysis(
    ["launcher.py"],
    pathex=["src", "."],
    binaries=_extra_binaries + _f2_binaries,
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
