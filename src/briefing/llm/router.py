"""Minimal LiteLLM-compatible completion over any OpenAI-compatible endpoint.

Call site matches litellm, so switching later is just an import swap:
    from briefing.llm import completion, completion_cost
    resp = completion(model="gpt-4o", messages=[{"role": "user", "content": q}])
    text = resp["choices"][0]["message"]["content"]   # dict OR attr access
    usd  = completion_cost(resp)

Model families differ in which sampling params they accept (reasoning models
reject temperature / presence_penalty / max_tokens). Instead of per-model rules,
a param the endpoint rejects with HTTP 400 is dropped and the call retried; the
rejection is remembered for that model for the rest of the process.
Prices come from the litellm dataset (see pricing.py).
"""
import requests

from briefing.config import api_info
from briefing.llm.pricing import price

_CHAT_PATH = "/chat/completions"
_OPTIONAL = ("temperature", "presence_penalty", "max_tokens", "max_completion_tokens")
_rejected: dict[tuple[str, str], set[str]] = {}   # (url, model) -> params the endpoint refused


class _Dot(dict):
    """dict with attribute access too, like litellm's ModelResponse."""
    __getattr__ = dict.get


def _wrap(obj):
    if isinstance(obj, dict):
        return _Dot({k: _wrap(v) for k, v in obj.items()})
    if isinstance(obj, list):
        return [_wrap(x) for x in obj]
    return obj


def _cost(model: str, usage: dict) -> float:
    p = price(model)
    return p["input"] * (usage.get("prompt_tokens") or 0) + p["output"] * (usage.get("completion_tokens") or 0)


def chat_url(base: str) -> str:
    """Accept either a base URL (.../v1) or the full .../chat/completions URL."""
    base = (base or "").strip().rstrip("/")
    return base if base.endswith(_CHAT_PATH) else base + _CHAT_PATH


def _rejected_param(status: int, data, payload: dict) -> str | None:
    """The optional param a 400 response complains about, if any."""
    if status != 400:
        return None
    err = data[0].get("error") if isinstance(data, list) and data and isinstance(data[0], dict) else \
        data.get("error") if isinstance(data, dict) else None
    if not isinstance(err, dict):
        return None
    sent = [p for p in _OPTIONAL if p in payload]
    if err.get("param") in sent:
        return err["param"]
    message = str(err.get("message") or "")
    return next((p for p in sent if p in message), None)


def completion(model, messages, api_key=None, api_base=None,
               temperature=None, presence_penalty=None, max_tokens=None,
               timeout=(20, 120), **kwargs):
    url = chat_url(api_base or api_info["url_redirect"])
    # OpenAI accepts max_completion_tokens on every chat model; reasoning models only that one.
    max_key = "max_completion_tokens" if "api.openai.com" in url else "max_tokens"
    payload = {"model": model, "messages": messages, **kwargs}
    for key, value in (("temperature", temperature), ("presence_penalty", presence_penalty), (max_key, max_tokens)):
        if value is not None:
            payload[key] = value

    headers = {
        "Authorization": f"Bearer {api_key or api_info['api_key']}",
        "Content-Type": "application/json",
    }
    rejected = _rejected.setdefault((url, model), set())
    for _ in range(len(_OPTIONAL) + 1):
        for p in rejected:
            payload.pop(p, None)
        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
        raw = resp.json()
        bad = _rejected_param(resp.status_code, raw, payload)
        if bad is None:
            break
        print(f"[llm] {model} rejected '{bad}', retrying without it")
        rejected.add(bad)

    data = _wrap(raw if isinstance(raw, dict) else {"error": raw})
    data["_hidden_params"] = {"response_cost": _cost(model, data.get("usage") or {})}
    return data


def completion_cost(completion_response) -> float:
    try:
        return float(completion_response["_hidden_params"]["response_cost"])
    except Exception:
        return 0.0
