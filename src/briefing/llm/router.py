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

Responses are streamed and assembled into a normal completion dict: long
reasoning answers take minutes, and a silent non-streamed connection gets cut
by the network in between. Dropped connections are retried.
Prices come from the litellm dataset (see pricing.py).
"""
import json
import time

import requests

from briefing.config import api_info
from briefing.llm.pricing import price

_CHAT_PATH = "/chat/completions"
_OPTIONAL = ("temperature", "presence_penalty", "max_tokens", "max_completion_tokens", "stream_options")
_NETWORK_ERRORS = (requests.exceptions.ChunkedEncodingError, requests.exceptions.ConnectionError,
                   requests.exceptions.Timeout)
_RETRY_DELAYS = (5, 15)
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


def _stream(url: str, payload: dict, headers: dict, timeout) -> tuple[int, object]:
    """One streamed call -> (status, body). body is the assembled completion on
    success, else the endpoint's error JSON."""
    with requests.post(url, json={**payload, "stream": True}, headers=headers,
                       timeout=timeout, stream=True) as resp:
        if resp.status_code != 200:
            try:
                return resp.status_code, resp.json()
            except ValueError:
                return resp.status_code, {"error": {"message": resp.text[:500]}}
        resp.encoding = "utf-8"
        content, usage, finish = [], {}, None
        for line in resp.iter_lines(decode_unicode=True):
            if not line.startswith("data:"):
                continue                      # keep-alive blank lines / SSE comments
            data = line[5:].strip()
            if data == "[DONE]":
                break
            chunk = json.loads(data)
            if chunk.get("error"):
                return 502, chunk
            usage = chunk.get("usage") or usage
            for choice in chunk.get("choices") or []:
                content.append((choice.get("delta") or {}).get("content") or "")
                finish = choice.get("finish_reason") or finish
    if finish is None:  # closed without a final chunk: the answer is truncated
        raise requests.exceptions.ChunkedEncodingError("stream ended before finish_reason")
    message ={"role": "assistant", "content": "".join(content)}
    return 200, {"choices": [{"index": 0, "message": message, "finish_reason": finish}], "usage": usage}


def _send(url: str, payload: dict, headers: dict, timeout) -> tuple[int, object]:
    for delay in (*_RETRY_DELAYS, None):
        try:
            return _stream(url, payload, headers, timeout)
        except _NETWORK_ERRORS as e:
            if delay is None:
                raise
            print(f"[llm] {payload['model']} {type(e).__name__}, retrying in {delay}s")
            time.sleep(delay)


def completion(model, messages, api_key=None, api_base=None,
               temperature=None, presence_penalty=None, max_tokens=None,
               timeout=(20, 600), **kwargs):
    url = chat_url(api_base or api_info["url_redirect"])
    # OpenAI accepts max_completion_tokens on every chat model; reasoning models only that one.
    max_key = "max_completion_tokens" if "api.openai.com" in url else "max_tokens"
    payload = {"model": model, "messages": messages, "stream_options": {"include_usage": True}, **kwargs}
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
        status, raw = _send(url, payload, headers, timeout)
        bad = _rejected_param(status, raw, payload)
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
