"""Per-stage validators for LLM output. Each returns (ok, error)."""
import json
import re

_EVOLVE_OPS = {"add", "reinforce", "update", "contradict"}


def _check_markdown(text):
    idxs = [m.start() for m in re.finditer(r"\*\*", text)]
    if len(idxs) % 2 != 0:
        return False, "unbalanced '**': every bold must be opened and closed"
    for i in range(0, len(idxs), 2):
        inner = text[idxs[i] + 2: idxs[i + 1]]
        if not inner.strip():
            return False, "empty '**' bold; remove it or put real text inside"
        if inner[0].isspace() or inner[-1].isspace():
            return False, "no space just inside '**': write '**word**', never '** word **'"
        if not re.search(r"[^\W_]", inner):
            return False, "don't bold a lone symbol; bold real words only"
    return True, ""


def check_short(text, src=""):
    if not text.strip():
        return False, "empty output"
    return _check_markdown(text)


def check_translate(text, src=""):
    if not text.strip():
        return False, "empty output"
    return _check_markdown(text)


def check_brief(text):
    from briefing.summarizer_agent.pipeline import _split_headline
    headline, body = _split_headline(text)
    if not headline:
        return False, "missing a headline line"
    if len(headline) > 120:
        return False, "headline/body boundary is wrong: output one short 'HEADLINE:' line, then a '---' line, then the body — nothing else"
    if not body:
        return False, "the brief body after the headline is empty"
    return _check_markdown(text)


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
