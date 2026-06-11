"""Feedback-driven self-evolution of per-stage style preferences.

User signals are folded into a structured, weighted rule store (one JSON file per
stage); the top rules are injected into that stage's prompt at generation time.

Two signals, both keyed on (video_id, stage) in the Feedback table:
- a correction (non-empty opinion) -> LLM proposes incremental ops on the rules.
- a pass (empty opinion = user viewed the report and left it alone) -> the rules
  in effect are reinforced, since they produced an output worth keeping.

No time decay: a rule persists until contradicted or pushed out by the size cap.
"""
import json
import re

from briefing.config import PREFERENCES_DIR, load_prompt
from briefing.db import get_unapplied_feedback, mark_feedback_applied

SUBJECTIVE_STAGES = ("brief", "short")
MAX_RULES = 12
WEIGHT_CAP = 10.0
W_ADD = 1.0
W_REINFORCE = 1.0
W_UPDATE = 0.5
W_PASS = 0.25

_EVOLVE_PROMPT = load_prompt("evolve")


def _store_path(stage: str):
    return PREFERENCES_DIR / f"{stage}.json"


def _load_store(stage: str) -> dict:
    p = _store_path(stage)
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            data.setdefault("rules", [])
            return data
        except Exception:
            pass
    legacy = PREFERENCES_DIR / f"{stage}.txt"  # one-time migration from old free-text notes
    rules = []
    if legacy.exists():
        for i, line in enumerate(legacy.read_text(encoding="utf-8").splitlines()):
            t = line.strip().lstrip("-").strip()
            if t:
                rules.append({"id": f"r{i+1}", "text": t, "weight": W_ADD, "hits": 1})
    return {"rules": rules}


def _save_store(stage: str, store: dict) -> None:
    p = _store_path(stage)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")


def _next_id(rules: list) -> str:
    n = 0
    for r in rules:
        m = re.match(r"r(\d+)", str(r.get("id", "")))
        if m:
            n = max(n, int(m.group(1)))
    return f"r{n+1}"


def _clamp(w: float) -> float:
    return min(w, WEIGHT_CAP)


def load_notes(stage: str) -> str:
    """Top rules for injection, rendered as a '- ' list (highest weight first)."""
    rules = _load_store(stage)["rules"]
    top = sorted(rules, key=lambda r: r.get("weight", 0), reverse=True)[:MAX_RULES]
    return "\n".join(f"- {r['text']}" for r in top if r.get("text"))


def _active_ids(rules: list) -> list:
    top = sorted(rules, key=lambda r: r.get("weight", 0), reverse=True)[:MAX_RULES]
    return [r["id"] for r in top]


def _apply_ops(rules: list, ops: list) -> None:
    by_id = {r["id"]: r for r in rules}
    remove = set()
    for op in ops:
        if not isinstance(op, dict):
            continue
        kind = op.get("op")
        rule = by_id.get(op.get("id"))
        if kind == "reinforce" and rule:
            rule["weight"] = _clamp(rule.get("weight", 0) + W_REINFORCE)
            rule["hits"] = rule.get("hits", 1) + 1
        elif kind == "update" and rule and op.get("text"):
            rule["text"] = str(op["text"]).strip()
            rule["weight"] = _clamp(rule.get("weight", 0) + W_UPDATE)
            rule["hits"] = rule.get("hits", 1) + 1
        elif kind == "contradict" and rule:
            remove.add(rule["id"])  # newer feedback wins — drop it outright
        elif kind == "add" and op.get("text"):
            new = {"id": _next_id(rules), "text": str(op["text"]).strip(), "weight": W_ADD, "hits": 1}
            rules.append(new)
            by_id[new["id"]] = new

    rules[:] = [r for r in rules if r["id"] not in remove and r.get("weight", 0) > 0]
    rules.sort(key=lambda r: r.get("weight", 0), reverse=True)
    del rules[MAX_RULES:]


def _reinforce(rules: list, passes: int) -> None:
    active = set(_active_ids(rules))
    for r in rules:
        if r["id"] in active:
            r["weight"] = _clamp(r.get("weight", 0) + W_PASS * passes)


def _parse_ops(raw: str) -> list:
    s = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        ops = json.loads(s)
        return ops if isinstance(ops, list) else []
    except Exception:
        return []


def evolve(session, model: str) -> None:
    """Fold unapplied corrections and passes into each stage's rule store."""
    from briefing.summarizer_agent.pipeline import request_gpt  # lazy: avoid import cycle

    feedback = get_unapplied_feedback(session)
    if not feedback:
        return

    # headline is produced by the brief prompt, so its feedback evolves brief's rules
    def _stage_of(fb):
        return "brief" if fb.stage == "headline" else fb.stage

    corrections: dict[str, list] = {}
    passes: dict[str, int] = {}
    for fb in feedback:
        stage = _stage_of(fb)
        if (fb.opinion or "").strip():
            corrections.setdefault(stage, []).append(fb)
        else:
            passes[stage] = passes.get(stage, 0) + 1

    for stage in set(corrections) | set(passes):
        items = corrections.get(stage, [])
        store = _load_store(stage)
        rules = store["rules"]
        try:
            if items:
                rules_block = "\n".join(f'{r["id"]}: {r["text"]}' for r in rules) or "(none yet)"
                block = "\n\n".join(
                    f"{i+1}. OUTPUT SHOWN:\n{fb.output}\n   OPINION:\n{fb.opinion}"
                    for i, fb in enumerate(items)
                )
                system = _EVOLVE_PROMPT.format(stage=stage, rules=rules_block, corrections=block)
                resp = request_gpt("Produce the operations.", system, model)
                _apply_ops(rules, _parse_ops(resp["choices"][0]["message"]["content"]))
            if passes.get(stage):
                _reinforce(rules, passes[stage])
            _save_store(stage, store)

            keys = [(fb.video_id, fb.stage) for fb in items]
            keys += [(fb.video_id, fb.stage) for fb in feedback
                     if _stage_of(fb) == stage and not (fb.opinion or "").strip()]
            mark_feedback_applied(session, keys)
            print(f"[evolve] {stage}: {len(items)} corrections, {passes.get(stage, 0)} passes, {len(rules)} rules")
        except Exception as e:
            print(f"[evolve skipped {stage}: {e}]")
