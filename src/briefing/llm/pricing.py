"""Model prices & limits from the litellm dataset, self-maintained.

pricing.py owns one file (data/model_prices.json): loads it, and on startup the
main process refreshes it in the background (weekly TTL, offline-safe). Pool
workers never fetch — they read the file the main process wrote. Unknown models
cost 0.0 and fall back to safe limits.
"""
import json
import threading
import time
import multiprocessing as mp

from briefing.config import DATA_DIR

_URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
_FILE = DATA_DIR / "model_prices.json"
_TTL = 7 * 24 * 3600   # refresh at most weekly


def _load() -> dict:
    try:
        return json.loads(_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


_PRICES = _load()


def refresh(force: bool = False) -> None:
    """Fetch the latest table into data/model_prices.json. Best-effort, never raises."""
    global _PRICES
    try:
        if not force and _FILE.exists() and (time.time() - _FILE.stat().st_mtime) < _TTL:
            return
        import requests
        data = requests.get(_URL, timeout=10).json()
        if isinstance(data, dict) and data:
            _FILE.parent.mkdir(parents=True, exist_ok=True)
            _FILE.write_text(json.dumps(data), encoding="utf-8")
            _PRICES = data
    except Exception:
        pass  # keep whatever we loaded; offline is fine


def price(model: str) -> dict:
    """USD per token: {'input', 'output'}."""
    row = _PRICES.get(model) or {}
    return {
        "input": row.get("input_cost_per_token") or 0.0,
        "output": row.get("output_cost_per_token") or 0.0,
    }


def model_limits(model: str) -> dict:
    """Chunk/output budgets: input = 90% of context, output = model max."""
    row = _PRICES.get(model) or {}
    ctx = row.get("max_input_tokens") or row.get("max_tokens") or 8192
    out = row.get("max_output_tokens") or row.get("max_tokens") or 4096
    return {"max_input": int(ctx * 0.9), "max_output": int(out)}


if mp.current_process().name == "MainProcess":
    threading.Thread(target=refresh, daemon=True).start()
