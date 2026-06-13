"""
Reset already-finished entries back to "needs summarize", skipping download
and whisper. Sets summarized=0 / pushed=0 and deletes the summarize/push
outputs while keeping whisper.txt. Does NOT run anything — the worker picks
the entries up on its next pass.

Run (in the conda env):
    python -m briefing.test.replay --list          # show finished entries
    python -m briefing.test.replay <video_id> ...  # reset specific entries
    python -m briefing.test.replay --all           # reset every transcribed entry
"""

import sys

from sqlalchemy.orm import Session

from briefing.config import OUTPUT_DIR, require_config
from briefing.db import engine, init_db, Video, update_entries

# stage outputs to drop so they regenerate; whisper.txt is kept on purpose
STAGE_FILES = ["outline.txt", "brief.txt", "headline.txt", "short.txt", "recommend.txt", "report.json"]


def _finished(session):
    return (
        session.query(Video)
        .filter(Video.downloaded == 1, Video.transcribed == 1)
        .order_by(Video.inserted_at.asc())
        .all()
    )


def list_entries(session) -> None:
    rows = _finished(session)
    if not rows:
        print("No transcribed entries.")
        return
    for v in rows:
        print(f"{v.video_id}    {(v.title or '')[:60]}")


def reset_entry(session, v: Video) -> bool:
    vid_dir = OUTPUT_DIR / str(v.video_id)
    if not (vid_dir / "whisper.txt").exists():
        print(f"[skip] {v.video_id}: no whisper.txt (cannot skip transcribe)")
        return False

    for name in STAGE_FILES:
        p = vid_dir / name
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass

    v.summarized = 0
    v.pushed = 0
    v.tokens = 0
    v.cost = 0.0
    v.domain = None
    update_entries(session, [v])
    print(f"[reset] {v.video_id}  {(v.title or '')[:50]}")
    return True


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return

    require_config()
    init_db()

    with Session(engine, future=True) as session:
        if args[0] == "--list":
            list_entries(session)
            return

        if args[0] == "--all":
            targets = _finished(session)
        else:
            targets = session.query(Video).filter(Video.video_id.in_(args)).all()
            for m in set(args) - {v.video_id for v in targets}:
                print(f"[skip] {m}: not in DB")

        reset = [v for v in targets if reset_entry(session, v)]
        if not reset:
            print("Nothing reset.")
            return
        print(f"\n[done] reset {len(reset)} entr{'y' if len(reset) == 1 else 'ies'}; worker will re-summarize on its next pass.")


if __name__ == "__main__":
    main()
