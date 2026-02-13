from __future__ import annotations

import json
from pathlib import Path

# Dir
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
AUDIO_DIR = DATA_DIR / "audio"
PROMPT_DIR = DATA_DIR / "prompts"
OUTPUT_DIR = DATA_DIR / "output"
TEMPORARY_DIR = DATA_DIR / "temporary"
REPORT_DIR = DATA_DIR / "reports"
PENDING_FILE = DATA_DIR / ".pending.json"
CONFIG_FILE = DATA_DIR / "config.txt"  # secret env
CONFIG_JSON = BASE_DIR / "backend" / "data" / "config.json"
DB_URL = f"sqlite:///{(DATA_DIR / 'db.sqlite3').as_posix()}"  # SQLite

# load configuration
if not CONFIG_JSON.exists():
    raise FileNotFoundError(f"Missing configuration. Please save the configuration once in the panel first.")

try:
    _cfg = json.loads(CONFIG_JSON.read_text(encoding="utf-8"))
except Exception as e:
    raise RuntimeError(f"Failed to read config.json: {CONFIG_JSON}") from e

READ_LANGUAGE = _cfg["READ_LANGUAGE"]
UPDATE_LIMIT = int(_cfg["UPDATE_LIMIT"])
TRANSCRIBER_LIMIT = _cfg["TRANSCRIBER_LIMIT"]
SUMMARIZER_LIMIT = _cfg["SUMMARIZER_LIMIT"]
PUSHER_LIMIT = int(_cfg["PUSHER_LIMIT"])
DOWNLOAD_INTERVAL = int(_cfg["DOWNLOAD_INTERVAL"])
PROCESS_INTERVAL = int(_cfg["PROCESS_INTERVAL"])
PUSHER_INTERVAL = int(_cfg["PUSHER_INTERVAL"])
POOL_NUM = int(_cfg["POOL_NUM"])
COMPRESS_LEVEl = int(_cfg["COMPRESS_LEVEl"])
ENTRIES_LIMIT = f"1-{int(_cfg['ENTRIES_LIMIT'])}"  # special: "1-x"
SOURCE_URLS = [str(x).strip() for x in _cfg.get("SOURCE_URLS", []) if str(x).strip()]

# load secret env
def load_config(path: Path) -> dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(f"Missing configuration: {path}")

    data = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip()
    return data

_secrets = load_config(CONFIG_FILE)

SERVER3_KEY = _secrets.get("SERVER3_KEY", None)
NTFY_SERVER = _secrets.get("NTFY_SERVER", None)

# configuration
try:
    api_info = {
        "api_key": _secrets["API_KEY"],
        "url_redirect": _secrets["API_URL"],
    }
except KeyError as e:
    raise RuntimeError(f"Failed to read API_KEY or API_URL: {e}")

api_model = {
    "whisper_model": _cfg["whisper_model"],
    "summarize_model": _cfg["summarize_model"],
    "translate_model": _cfg["translate_model"],
}

# regular information
model_info = {
    "gpt-4o-mini": {
        "model": "gpt-4o-mini",
        "max_input": 2048,
        "max_output": 4096,
        "input_price": 0,
        "output_price": 0,
    },
    "gpt-3.5-turbo": {
        "model": "gpt-3.5-turbo",
        "max_input": 16385,
        "max_output": 4096,
        "input_price": 0.0035,
        "output_price": 0.0035,
    },
    "gpt-4o": {
        "model": "gpt-4o",
        "max_input": 10000,
        "max_output": 16384,
        "input_price": 0.0175,
        "output_price": 0.0175,
    },
    "gpt-4.1-nano": {
        "model": "gpt-4.1-nano",
        "max_input": 1000000,
        "max_output": 32000,
        "input_price": 0.0028,
        "output_price": 0.0028,
    },
}

def load_prompt(name: str) -> str:
    path = PROMPT_DIR / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text(encoding="utf-8")

model_para = {
    "system_content": {
        "inspect": load_prompt("inspect"),
        "summarize": load_prompt("summarize"),
        "outline_trace": load_prompt("outline_trace"),
        "brief": load_prompt("brief"),
        "additional": "",
    },
    "temperature": 0.1,
    "presence_penalty": -0.2,
}


def check_config() -> tuple[bool, list[str], list[str]]:
    for d in [
        DATA_DIR,
        AUDIO_DIR,
        PROMPT_DIR,
        OUTPUT_DIR,
        TEMPORARY_DIR,
        REPORT_DIR,
    ]:
        d.mkdir(parents=True, exist_ok=True)
    return True, [], []