"""Feedback-driven self-evolution of per-domain, per-stage style preferences.

Only subjective stages evolve. Each piece of user feedback (the generated output
+ the user's opinion) is folded into a reusable list of style rules, which is then
injected into that stage's prompt at generation time.
"""
from briefing.config import PREFERENCES_DIR, load_prompt
from briefing.db import get_unapplied_feedback, mark_feedback_applied

SUBJECTIVE_STAGES = ("brief", "recommend")
MAX_RULES = 12

_EVOLVE_PROMPT = load_prompt("evolve")


def _notes_path(domain: str, stage: str):
    return PREFERENCES_DIR / (domain or "other") / f"{stage}.txt"


def load_notes(domain: str, stage: str) -> str:
    p = _notes_path(domain, stage)
    return p.read_text(encoding="utf-8").strip() if p.exists() else ""


def save_notes(domain: str, stage: str, text: str) -> None:
    p = _notes_path(domain, stage)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text.strip() + "\n", encoding="utf-8")


def evolve(session, model: str) -> None:
    """Fold all unapplied feedback into the per-(domain, stage) preference notes."""
    from briefing.summarizer_agent.pipeline import request_gpt  # lazy: avoid import cycle

    feedback = get_unapplied_feedback(session)
    if not feedback:
        return

    groups: dict[tuple[str, str], list] = {}
    for fb in feedback:
        # the headline is produced by the brief prompt, so its feedback evolves brief's notes
        notes_stage = "brief" if fb.stage == "headline" else fb.stage
        groups.setdefault((fb.domain or "other", notes_stage), []).append(fb)

    for (domain, stage), items in groups.items():
        current = load_notes(domain, stage) or "(none yet)"
        fb_block = "\n\n".join(
            f"{i + 1}. OUTPUT SHOWN:\n{fb.output}\n   YOUR OPINION:\n{fb.opinion}"
            for i, fb in enumerate(items)
        )
        system = _EVOLVE_PROMPT.format(stage=stage, domain=domain, n=MAX_RULES)
        user = f"CURRENT PREFERENCES:\n{current}\n\nNEW FEEDBACK:\n{fb_block}"
        try:
            resp = request_gpt(user, system, model)
            new_notes = resp["choices"][0]["message"]["content"].strip()
            if new_notes:
                save_notes(domain, stage, new_notes)
                mark_feedback_applied(session, [(fb.video_id, fb.stage) for fb in items])
                print(f"[evolve] updated {domain}/{stage} from {len(items)} feedback")
        except Exception as e:
            print(f"[evolve skipped {domain}/{stage}: {e}]")
