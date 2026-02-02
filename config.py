from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
AUDIO_DIR = DATA_DIR / "audio"
PROMPT_DIR = DATA_DIR / "prompts"
OUTPUT_DIR = DATA_DIR / "output"
TEMPORARY_DIR = DATA_DIR / "temporary"
SOURCE_FILE = DATA_DIR / "channels.txt"
CONFIG_FILE = DATA_DIR / "config.txt"
DB_URL = f"sqlite:///{(DATA_DIR / 'db.sqlite3').as_posix()}"

def load_config(path: Path) -> dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    data = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip()
    return data

_cfg = load_config(CONFIG_FILE)

SERVER3_KEY = _cfg.get("SERVER3_KEY", None)

api_info = {
    "1": {
        "api_key": _cfg.get("API_KEY", None),
        "url_redirect": _cfg.get("API_URL", None),
    }
}

ENTRIES_LIMIT = "1-3"
UPDATE_LIMIT = 3
TRANSCRIBER_LIMIT = None
SUMMARIZER_LIMIT = None
PUSHER_LIMIT = 5
DOWNLOAD_INTERVAL = 6 * 60 * 60
PROCESS_INTERVAL = 1 * 10 * 60
PUSHER_INTERVAL = 1 * 10 * 60
READ_LANGUAGE = "chinese"

def load_source_urls(path: Path) -> list[str]:
    if not path.exists():
        return []

    urls = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        urls.append(line)

    return urls

SOURCE_URLS = load_source_urls(SOURCE_FILE)

model_info = {
    "gpt-4o-mini": {
        "model": "gpt-4o-mini",
        "max_input": 2048,
        "max_output": 4096,
        "input_price": 0,
        "output_price": 0,
    },

    "gpt-3.5-turbo": {
        "model": "gpt-3.5-turbo-0125",
        "max_input": 16385,
        "max_output": 4096,
        "input_price": 0.0035,
        "output_price": 0.0035,
    },

    "gpt-4o": {
        "model": "gpt-4o-2024-08-06",
        "max_input": 10000,
        "max_output": 16384,
        "input_price": 0.0175,
        "output_price": 0.0175,
    },

    "gpt-4.1-nano": {
        "model": "gpt-4.1-nano-2025-04-14",
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
        "deep": load_prompt("deep"),
        "additional": "",
    },
    "temperature": 0.1,  # 0~2，生成内容的随机性
    "presence_penalty": -0.2,  # -2~2，新主题的可能性
}

api_model = {
    "whisper_model": "small",  # base small medium

    "summarize_api": "1",  # free 1
    "summarize_model": "gpt-4.1-nano",  # gpt-4o-mini gpt-4o gpt-4.1-nano

    "translate_api": "1",  # free 1
    "translate_model": "gpt-4o-mini",  # gpt-4o-mini gpt-4o gpt-4.1-nano
}


def check_config() -> tuple[bool, list[str], list[str]]:
    missing: list[str] = []
    errors: list[str] = []

    # ---- required Path vars ----
    required_paths = {
        "BASE_DIR": BASE_DIR,
        "DATA_DIR": DATA_DIR,
        "AUDIO_DIR": AUDIO_DIR,
        "PROMPT_DIR": PROMPT_DIR,
        "OUTPUT_DIR": OUTPUT_DIR,
        "TEMPORARY_DIR": TEMPORARY_DIR,
        "SOURCE_FILE": SOURCE_FILE,
    }
    for k, p in required_paths.items():
        if not isinstance(p, Path):
            errors.append(f"{k} is not a Path")
            continue
        # BASE_DIR should exist; others may be created by init, but we still validate path is valid
        if k == "BASE_DIR" and not p.exists():
            errors.append(f"{k} does not exist: {p}")

    # ---- create dirs if missing (optional) ----
    # If you don't want config to create dirs, delete this block.
    for k in ("DATA_DIR", "AUDIO_DIR", "PROMPT_DIR", "OUTPUT_DIR"):
        p = required_paths[k]
        try:
            p.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            errors.append(f"cannot create {k}: {p} ({type(e).__name__}: {e})")

    # ---- source file ----
    if not SOURCE_FILE.exists():
        missing.append(f"SOURCE_FILE not found: {SOURCE_FILE}")
    else:
        try:
            urls = load_source_urls(SOURCE_FILE)
            if not urls:
                errors.append(f"SOURCE_URLS is empty (file: {SOURCE_FILE})")
        except Exception as e:
            errors.append(f"cannot read SOURCE_FILE: {SOURCE_FILE} ({type(e).__name__}: {e})")

    # ---- DB_URL sanity ----
    if not isinstance(DB_URL, str) or not DB_URL.startswith("sqlite:///"):
        errors.append(f"DB_URL invalid: {DB_URL}")

    # ---- numeric params sanity ----
    def _check_int(name: str, v, allow_none: bool = False):
        if allow_none and v is None:
            return
        if not isinstance(v, int):
            errors.append(f"{name} must be int (got {type(v).__name__})")
            return
        if v < 0:
            errors.append(f"{name} must be >= 0 (got {v})")

    _check_int("UPDATE_LIMIT", UPDATE_LIMIT)
    _check_int("PUSHER_LIMIT", PUSHER_LIMIT)
    _check_int("DOWNLOAD_INTERVAL", DOWNLOAD_INTERVAL)
    _check_int("PROCESS_INTERVAL", PROCESS_INTERVAL)
    _check_int("PUSHER_INTERVAL", PUSHER_INTERVAL)
    _check_int("TRANSCRIBER_LIMIT", TRANSCRIBER_LIMIT, allow_none=True)
    _check_int("SUMMARIZER_LIMIT", SUMMARIZER_LIMIT, allow_none=True)

    # ---- strings ----
    if not READ_LANGUAGE or not isinstance(READ_LANGUAGE, str):
        missing.append("READ_LANGUAGE is missing/invalid")
    if not SERVER3_KEY or not isinstance(SERVER3_KEY, str):
        missing.append("SERVER3_KEY is missing/invalid")

    # ---- api_info ----
    if not isinstance(api_info, dict) or not api_info:
        missing.append("api_info is missing/empty")
    else:
        for slot, cfg in api_info.items():
            if not isinstance(cfg, dict):
                errors.append(f"api_info['{slot}'] is not a dict")
                continue
            if not cfg.get("api_key"):
                missing.append(f"api_info['{slot}'].api_key missing")
            if not cfg.get("url_redirect"):
                missing.append(f"api_info['{slot}'].url_redirect missing")

    # ---- model_info ----
    if not isinstance(model_info, dict) or not model_info:
        missing.append("model_info is missing/empty")
    else:
        for name, cfg in model_info.items():
            if not isinstance(cfg, dict):
                errors.append(f"model_info['{name}'] is not a dict")
                continue
            for k in ("model", "max_input", "max_output", "input_price", "output_price"):
                if k not in cfg:
                    missing.append(f"model_info['{name}'].{k} missing")

    # ---- prompts (model_para.system_content) ----
    required_prompts = ("inspect", "summarize", "outline_trace", "brief", "deep", "additional")
    try:
        sc = model_para.get("system_content", {})
        for pn in required_prompts:
            if pn not in sc:
                missing.append(f"model_para.system_content['{pn}'] missing")
            else:
                # For file-backed prompts, content should be str (can be empty only for 'additional')
                val = sc[pn]
                if not isinstance(val, str):
                    errors.append(f"model_para.system_content['{pn}'] is not str")
                elif pn != "additional" and not val.strip():
                    errors.append(f"prompt '{pn}' is empty (check {PROMPT_DIR / (pn + '.txt')})")
    except Exception as e:
        errors.append(f"model_para invalid ({type(e).__name__}: {e})")

    # ---- api_model cross checks ----
    if not isinstance(api_model, dict) or not api_model:
        missing.append("api_model is missing/empty")
    else:
        # required keys
        for k in ("whisper_model", "summarize_api", "summarize_model", "translate_api", "translate_model"):
            if k not in api_model:
                missing.append(f"api_model['{k}'] missing")

        # slot/model existence
        sa = api_model.get("summarize_api")
        sm = api_model.get("summarize_model")
        ta = api_model.get("translate_api")
        tm = api_model.get("translate_model")

        if sa and sa not in api_info:
            errors.append(f"api_model.summarize_api '{sa}' not found in api_info")
        if ta and ta not in api_info:
            errors.append(f"api_model.translate_api '{ta}' not found in api_info")
        if sm and sm not in model_info:
            errors.append(f"api_model.summarize_model '{sm}' not found in model_info")
        if tm and tm not in model_info:
            errors.append(f"api_model.translate_model '{tm}' not found in model_info")

    ok = (len(missing) == 0 and len(errors) == 0)
    return ok, missing, errors