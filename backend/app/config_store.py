from pathlib import Path
import json
from .config_schema import SCHEMA, validate_and_merge

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CONFIG_PATH = DATA_DIR / "config.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    file_data = {}
    if CONFIG_PATH.exists():
        try:
            file_data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            file_data = {}
    try:
        merged = validate_and_merge(file_data)
    except Exception:
        merged = validate_and_merge({})
    save_config(merged)  # keep file in sync with defaults
    return merged


def save_config(cfg: dict) -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    clean = validate_and_merge(cfg)
    CONFIG_PATH.write_text(json.dumps(clean, indent=2), encoding="utf-8")
    return clean


def get_schema() -> list:
    return SCHEMA
