"""
Single source of truth for configurable fields.
"""

from __future__ import annotations
from typing import Any, Dict, List

SCHEMA: List[Dict[str, Any]] = [
    {
        "name": "Reading Language",
        "key": "READ_LANGUAGE",
        "type": "select",
        "default": "chinese",
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
        "type": "int", "default": 5, "min": 1, "max": 20, 
        "desc": "Push jobs per run", 
        "cn": "最大推送条数/次"
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
        "default": "medium",
        "choices": ["tiny", "small", "medium", "large"],
        "desc": "Speech recognition model",
        "cn": "语音识别模型",
    },
    {
        "name": "Summarize Model",
        "key": "summarize_model",
        "type": "select",
        "default": "gpt-4.1-nano",
        "choices": ["gpt-4.1-nano"],
        "desc": "Summarize model (Unique)",
        "cn": "总结模型 (唯一)",
    },
    {
        "name": "Translate Model",
        "key": "translate_model",
        "type": "select",
        "default": "gpt-4o-mini",
        "choices": ["gpt-4o-mini", "gpt-4o"],
        "desc": "Translate Model",
        "cn": "翻译模型",
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
    if ftype == "str":
        return "" if value is None else str(value)
    return value


def validate_and_merge(data: Dict[str, Any]) -> Dict[str, Any]:
    # Merge incoming data with defaults, coerce types according to SCHEMA.
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
        else:
            coerced = _coerce(f, incoming)
        _set_path(result, name, coerced)
    return result
