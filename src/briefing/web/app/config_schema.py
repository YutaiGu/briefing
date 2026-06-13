"""
Single source of truth for configurable fields.
"""

from __future__ import annotations
from typing import Any, Dict, List

# Curated "<provider>/<model>" options for the model dropdowns. The provider
# prefix (before the first "/") selects which PROVIDERS row supplies key + URL;
# the rest is the model name sent to that endpoint. Users may also type custom.
MODEL_OPTIONS: List[str] = [
    "openai/gpt-4o", "openai/gpt-4o-mini",
    "openai/gpt-4.1", "openai/gpt-4.1-mini", "openai/gpt-4.1-nano", "openai/o3-mini",
    "deepseek/deepseek-chat", "deepseek/deepseek-reasoner",
    "gemini/gemini-2.5-flash", "gemini/gemini-2.5-pro", "gemini/gemini-2.0-flash",
    "openrouter/anthropic/claude-3.5-sonnet",
    "openrouter/meta-llama/llama-3.3-70b-instruct",
]

# Pre-seeded OpenAI-compatible endpoints; user just fills the api_key it needs.
PROVIDER_SEED: List[Dict[str, str]] = [
    {"id": "openai",     "base_url": "https://api.openai.com/v1/chat/completions",                       "api_key": ""},
    {"id": "deepseek",   "base_url": "https://api.deepseek.com/chat/completions",                        "api_key": ""},
    {"id": "gemini",     "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", "api_key": ""},
    {"id": "openrouter", "base_url": "https://openrouter.ai/api/v1/chat/completions",                    "api_key": ""},
]

SCHEMA: List[Dict[str, Any]] = [
    {
        "name": "Reading Language",
        "key": "READ_LANGUAGE",
        "type": "select",
        "default": "english",
        "choices": ["chinese", "english"],
        "desc": "Your reading language",
        "cn": "你的阅读语言",
    },
    {
        "name": "Update Limit", 
        "key": "UPDATE_LIMIT", 
        "type": "int", "default": 3, "min": 1, "max": 20, 
        "desc": "Max process number per source", 
        "cn": "每源最大处理条数"
    },
    {
        "name": "Pool Num", 
        "key": "POOL_NUM", 
        "type": "int", "default": 2, "min": 1, "max": 16, 
        "desc": "Worker processes", 
        "cn": "工作进程数"
    },
    {
        "name": "Transcribe Limit", 
        "key": "TRANSCRIBER_LIMIT", 
        "type": "int_optional", 
        "default": None, "min": 1, "max": 20, 
        "desc": "Max transcribe number per run", 
        "cn": "最大转写条数/次"
    },
    {
        "name": "Summarize Limit", 
        "key": "SUMMARIZER_LIMIT", 
        "type": "int_optional", "default": None, "min": 1, "max": 20, 
        "desc": "Max summarize number per run", 
        "cn": "最大总结条数/次"
    },
    {
        "name": "Push Limit",
        "key": "PUSHER_LIMIT",
        "type": "int_optional", "default": None, "min": 1, "max": 20,
        "desc": "Max push number per run",
        "cn": "最大推送条数/次"
    },
    {
        "name": "Push To",
        "key": "PUSH_TO",
        "type": "select",
        "default": "LocalFile",
        "choices": ["ntfy", "LocalFile"],
        "desc": "Push to where",
        "cn": "推送到哪里",
    },
    {
        "name": "Download Interval", 
        "key": "DOWNLOAD_INTERVAL", 
        "type": "int", "default": 6 * 60 * 60, "min": 0, "max": 24 * 60 * 60, 
        "desc": "Seconds between downloads", 
        "cn": "下载间隔 秒"
    },
    {
        "name": "Process Interval", 
        "key": "PROCESS_INTERVAL", 
        "type": "int", "default": 10 * 60, "min": 0, "max": 24 * 60 * 60, 
        "desc": "Seconds between processes", 
        "cn": "处理间隔 秒"
    },
    {
        "name": "Push Interval", 
        "key": "PUSHER_INTERVAL", 
        "type": "int", "default": 10 * 60, "min": 0, "max": 24 * 60 * 60, 
        "desc": "Seconds between pushes", 
        "cn": "推送间隔 秒"
    },
    {
        "name": "Entries Limit", 
        "key": "ENTRIES_LIMIT", 
        "type": "int", "default": 3, "min": 1, "max": 20, 
        "desc": "Newest entries to fetch", 
        "cn": "每源最大下载条数"
    },
    {
        "name": "Source Urls", 
        "key": "SOURCE_URLS", 
        "type": "list_str", "default": [], 
        "desc": "Channels", 
        "cn": "主页链接"
    },
    {
        "name": "Whisper Model",
        "key": "whisper_model",
        "type": "select",
        "default": "small",
        "choices": ["tiny", "small", "medium", "large"],
        "desc": "Speech recognition model",
        "cn": "语音识别模型",
    },
    {
        "name": "Outline Model",
        "key": "outline_model",
        "type": "model",
        "default": "openai/gpt-4.1-nano",
        "options": MODEL_OPTIONS,
        "desc": "Model for the outline stage (provider/model)",
        "cn": "大纲模型（服务商/模型）",
    },
    {
        "name": "Brief Model",
        "key": "brief_model",
        "type": "model",
        "default": "openai/gpt-4.1-nano",
        "options": MODEL_OPTIONS,
        "desc": "Model for the brief + short stages (provider/model)",
        "cn": "简报/短摘要模型（服务商/模型）",
    },
    {
        "name": "Evolve Model",
        "key": "evolve_model",
        "type": "model",
        "default": "openai/gpt-4.1-nano",
        "options": MODEL_OPTIONS,
        "desc": "Model for folding feedback into preferences (provider/model)",
        "cn": "反馈进化模型（服务商/模型）",
    },
    {
        "name": "Translate Model",
        "key": "translate_model",
        "type": "model",
        "default": "openai/gpt-4o-mini",
        "options": MODEL_OPTIONS,
        "desc": "Model for translation / compression (provider/model)",
        "cn": "翻译/压缩模型（服务商/模型）",
    },
    {
        "name": "COMPRESS_LEVEl",
        "key": "COMPRESS_LEVEl",
        "type": "select",
        "default": "100",
        "choices": ["100", "75", "50", "25"],
        "desc": "Summary Text Volume Reduction % (Recommended: 100%)",
        "cn": "总结文本量压缩% (推荐100%)",
    },
    # --- Secrets ---
    {
        "name": "Providers",
        "key": "PROVIDERS",
        "type": "providers",
        "default": PROVIDER_SEED,
        "desc": "Per-provider endpoint + API key; the model prefix picks the provider",
        "cn": "各服务商的接口地址与密钥；模型前缀决定用哪个服务商",
        "group": "secrets",
    },
    {
        "name": "NTFY Server",
        "key": "NTFY_SERVER",
        "type": "str",
        "default": "",
        "desc": "NTFY server ID",
        "cn": "NTFY 服务器 ID",
        "group": "secrets",
    },
]


def _set_path(target: Dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    cur = target
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = value


def make_default_config() -> Dict[str, Any]:
    cfg: Dict[str, Any] = {}
    for f in SCHEMA:
        path = f.get("key") or f["name"]
        _set_path(cfg, path, _coerce(f, f.get("default")))
    return cfg


def _coerce(field: Dict[str, Any], value: Any) -> Any:
    ftype = field["type"]
    minv = field.get("min")
    maxv = field.get("max")
    if ftype == "int":
        if isinstance(value, str) and "-" in value:
            try:
                value = value.split("-")[-1]
            except Exception:
                pass
        v = int(value)
        if minv is not None and v < minv:
            raise ValueError(f"{field['name']} must be >= {minv}")
        if maxv is not None and v > maxv:
            raise ValueError(f"{field['name']} must be <= {maxv}")
        return v
    if ftype == "int_optional":
        if value in (None, "", "null"):
            return None
        v = int(value)
        if minv is not None and v < minv:
            raise ValueError(f"{field['name']} must be >= {minv}")
        if maxv is not None and v > maxv:
            raise ValueError(f"{field['name']} must be <= {maxv}")
        return v
    if ftype == "list_str":
        if value is None:
            return []
        if isinstance(value, str):
            # split by newline or comma
            parts = []
            for line in value.replace("\r", "").split("\n"):
                for seg in line.split(","):
                    seg = seg.strip()
                    if seg:
                        parts.append(seg)
            return parts
        if isinstance(value, list):
            return [str(x).strip() for x in value if str(x).strip()]
        raise ValueError(f"{field['name']} must be list or string")
    if ftype == "select":
        if value not in field["choices"]:
            raise ValueError(f"{field['name']} must be one of {field['choices']}")
        return value
    if ftype == "str" or ftype == "model":
        return "" if value is None else str(value).strip()
    if ftype == "providers":
        if not isinstance(value, list):
            return []
        rows = []
        for r in value:
            if not isinstance(r, dict):
                continue
            pid = str(r.get("id") or "").strip()
            if not pid:
                continue
            rows.append({
                "id": pid,
                "base_url": str(r.get("base_url") or "").strip(),
                "api_key": str(r.get("api_key") or "").strip(),
            })
        return rows
    return value


def _merge(data: Dict[str, Any], lenient: bool) -> Dict[str, Any]:
    result = make_default_config()
    for f in SCHEMA:
        name = f.get("key") or f["name"]
        parts = name.split(".")
        incoming = data
        for p in parts:
            if isinstance(incoming, dict) and p in incoming:
                incoming = incoming[p]
            else:
                incoming = None
                break
        if incoming is None:
            coerced = f.get("default")
        elif lenient:
            try:
                coerced = _coerce(f, incoming)
            except Exception:
                coerced = f.get("default")  # one bad field -> just its own default
        else:
            coerced = _coerce(f, incoming)
        _set_path(result, name, coerced)
    return result


def validate_and_merge(data: Dict[str, Any]) -> Dict[str, Any]:
    # Strict: any invalid field raises. Used when saving user input.
    return _merge(data, lenient=False)


def merge_lenient(data: Dict[str, Any]) -> Dict[str, Any]:
    # Tolerant: an invalid field falls back to its own default. Used when loading.
    return _merge(data, lenient=True)
