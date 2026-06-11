from __future__ import annotations

import json
import sys
from pathlib import Path

# Paths — frozen-aware, no side effects (safe to import before config.json exists).
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
    PKG_DIR = Path(sys._MEIPASS) / "briefing"
    ASSETS_DIR = Path(sys._MEIPASS) / "assets"
else:
    PKG_DIR = Path(__file__).resolve().parent             # src/briefing
    BASE_DIR = PKG_DIR.parents[1]                         # repo root
    ASSETS_DIR = BASE_DIR / "assets"

# writable runtime data
DATA_DIR = BASE_DIR / "data"
AUDIO_DIR = DATA_DIR / "audio"
OUTPUT_DIR = DATA_DIR / "output"
TEMPORARY_DIR = DATA_DIR / "temporary"
REPORT_DIR = DATA_DIR / "reports"
PENDING_FILE = DATA_DIR / ".pending.json"
COOKIES_TXT = DATA_DIR / "cookies.txt"
CONFIG_JSON = DATA_DIR / "config.json"
DB_PATH = DATA_DIR / "db.sqlite3"
DB_URL = f"sqlite:///{DB_PATH.as_posix()}"

# read-only bundled assets
PROMPT_DIR = PKG_DIR / "summarizer_agent" / "prompts"
FFMPEG_DIR = ASSETS_DIR / "ffmpeg"
STATIC_DIR = PKG_DIR / "web" / "static"

# writable: evolving per-domain/per-stage style preferences
PREFERENCES_DIR = DATA_DIR / "preferences"

# writable: one tiny file per in-flight video holding transcription percent (0-100)
PROGRESS_DIR = DATA_DIR / "progress"

def load_prompt(name: str) -> str:
    path = PROMPT_DIR / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text(encoding="utf-8")


model_para = {
    "system_content": {
        "outline": load_prompt("outline"),
        "brief": load_prompt("brief"),
        "short": load_prompt("short"),
        "additional": "",
    },
    "temperature": 0.1,
    "presence_penalty": -0.2,
}

# Config values from config.json. Missing file is non-fatal at import;
# worker startup calls require_config() to fail with a clear message.
CONFIG_LOADED = False
READ_LANGUAGE = None
UPDATE_LIMIT = None
TRANSCRIBER_LIMIT = None
SUMMARIZER_LIMIT = None
PUSHER_LIMIT = None
PUSH_TO = "ntfy"
DOWNLOAD_INTERVAL = None
PROCESS_INTERVAL = None
PUSHER_INTERVAL = None
POOL_NUM = None
COMPRESS_LEVEl = None
ENTRIES_LIMIT = None
SOURCE_URLS = []
NTFY_SERVER = None
api_info = {"api_key": "", "url_redirect": ""}
api_model = None
PROVIDERS = []

if CONFIG_JSON.exists():
    try:
        _raw = json.loads(CONFIG_JSON.read_text(encoding="utf-8"))
    except Exception as e:
        raise RuntimeError(f"Failed to read config.json: {CONFIG_JSON}") from e

    from briefing.web.app.config_schema import merge_lenient
    _cfg = merge_lenient(_raw)

    READ_LANGUAGE = _cfg["READ_LANGUAGE"]
    UPDATE_LIMIT = int(_cfg["UPDATE_LIMIT"])
    TRANSCRIBER_LIMIT = _cfg["TRANSCRIBER_LIMIT"]
    SUMMARIZER_LIMIT = _cfg["SUMMARIZER_LIMIT"]
    PUSHER_LIMIT = int(_cfg["PUSHER_LIMIT"])
    PUSH_TO = str(_cfg.get("PUSH_TO", "ntfy"))
    DOWNLOAD_INTERVAL = int(_cfg["DOWNLOAD_INTERVAL"])
    PROCESS_INTERVAL = int(_cfg["PROCESS_INTERVAL"])
    PUSHER_INTERVAL = int(_cfg["PUSHER_INTERVAL"])
    POOL_NUM = int(_cfg["POOL_NUM"])
    COMPRESS_LEVEl = int(_cfg["COMPRESS_LEVEl"])
    ENTRIES_LIMIT = f"1-{int(_cfg['ENTRIES_LIMIT'])}"  # "1-x"
    SOURCE_URLS = [str(x).strip() for x in _cfg.get("SOURCE_URLS", []) if str(x).strip()]
    NTFY_SERVER = _cfg.get("NTFY_SERVER") or None
    api_model = {
        "whisper_model": _cfg["whisper_model"],
        "outline_model": _cfg["outline_model"],
        "brief_model": _cfg["brief_model"],
        "evolve_model": _cfg["evolve_model"],
        "translate_model": _cfg["translate_model"],
    }
    PROVIDERS = _cfg.get("PROVIDERS") or []
    CONFIG_LOADED = True


def resolve_model(model_str):
    """'<provider>/<model>' -> (model_name, api_key, base_url).

    The prefix before the first '/' picks a PROVIDERS row for its key + URL; the
    rest is the model name sent to that endpoint. Keys live only in providers.
    """
    s = (model_str or "").strip()
    provider, sep, name = s.partition("/")
    if not sep:
        provider, name = None, s
    row = next((p for p in PROVIDERS if p.get("id") == provider), None) if provider else None
    row = row or {}
    return name, row.get("api_key", ""), row.get("base_url", "")


def require_config() -> None:
    if not CONFIG_LOADED:
        raise FileNotFoundError(
            "Missing configuration. Please save the configuration once in the panel first."
        )


def check_config() -> tuple[bool, list[str], list[str]]:
    for d in [DATA_DIR, AUDIO_DIR, OUTPUT_DIR, TEMPORARY_DIR, REPORT_DIR, PROGRESS_DIR]:
        d.mkdir(parents=True, exist_ok=True)
    if not PENDING_FILE.exists():
        PENDING_FILE.write_text("{}", encoding="utf-8")
    return True, [], []
