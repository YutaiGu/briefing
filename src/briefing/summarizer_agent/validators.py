"""Per-stage validators for LLM output. Each returns (ok, error)."""
import json
import re

_EVOLVE_OPS = {"add", "reinforce", "update", "contradict"}


def check_short(text, src=""):
    if not text.strip():
        return False, "empty output"
    return True, ""


def check_translate(text, src=""):
    if not text.strip():
        return False, "empty output"
    return True, ""


def check_brief(text):
    from briefing.summarizer_agent.pipeline import _split_headline
    headline, body = _split_headline(text)
    if not headline:
        return False, "missing a headline line"
    if len(headline) > 120:
        return False, "headline/body boundary is wrong: output one short 'HEADLINE:' line, then a '---' line, then the body — nothing else"
    if not body:
        return False, "the brief body after the headline is empty"
    return True, ""


def check_evolve(text):
    s = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        data = json.loads(s)
    except Exception:
        return False, "not valid JSON"
    if not isinstance(data, list):
        return False, "top level must be a JSON array"
    for op in data:
        if not isinstance(op, dict) or op.get("op") not in _EVOLVE_OPS:
            return False, "each item needs a valid 'op'"
        if op["op"] in ("add", "update") and not op.get("text"):
            return False, f"'{op['op']}' requires a 'text' field"
        if op["op"] in ("reinforce", "update", "contradict") and not op.get("id"):
            return False, f"'{op['op']}' requires an 'id' field"
    return True, ""
