"""Minimal LiteLLM-compatible completion (single self-contained call path).

Call site matches litellm, so switching later is just an import swap:
    from briefing.llm import completion, completion_cost
    resp = completion(model="gpt-4o", messages=[{"role": "user", "content": q}])
    text = resp["choices"][0]["message"]["content"]   # dict OR attr access
    usd  = completion_cost(resp)

Uses the single endpoint/key from config (api_info). api_key/api_base can be
overridden per call, so per-provider routing can be added later without touching
call sites. Prices come from the bundled litellm dataset (see pricing.py).
"""
import requests

from briefing.config import api_info
from briefing.llm.pricing import price


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


def completion(model, messages, api_key=None, api_base=None,
               temperature=None, presence_penalty=None, max_tokens=None,
               timeout=(20, 120), **kwargs):
    payload = {"model": model, "messages": messages, **kwargs}
    if temperature is not None:
        payload["temperature"] = temperature
    if presence_penalty is not None:
        payload["presence_penalty"] = presence_penalty
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    headers = {
        "Authorization": f"Bearer {api_key or api_info['api_key']}",
        "Content-Type": "application/json",
    }
    resp = requests.post(api_base or api_info["url_redirect"],
                         json=payload, headers=headers, timeout=timeout)
    data = _wrap(resp.json())
    data["_hidden_params"] = {"response_cost": _cost(model, data.get("usage") or {})}
    return data


def completion_cost(completion_response) -> float:
    try:
        return float(completion_response["_hidden_params"]["response_cost"])
    except Exception:
        return 0.0
