from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
import json
import os
import sqlite3
import sys
import threading
import time
import webbrowser
from .config_store import load_config, save_config, get_schema
from .runner import runner

app = FastAPI(title="Local Runner")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from briefing.config import STATIC_DIR, DB_PATH, OUTPUT_DIR, PROGRESS_DIR
from sqlalchemy.orm import Session
from briefing.db import engine, save_feedback, get_feedback_map, Feedback

BROWSER_URL = os.environ.get("RUNNER_URL", "http://localhost:8000/")
AUTO_OPEN   = os.environ.get("AUTO_OPEN_BROWSER", "1") != "0"

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def root_page():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "UI not found. Ensure briefing/web/static/index.html exists."}


@app.on_event("startup")
def _open_browser():
    if not AUTO_OPEN:
        return
    # Open asynchronously after server binds.
    def _launch():
        time.sleep(0.6)
        try:
            webbrowser.open(BROWSER_URL)
        except Exception:
            pass
    threading.Thread(target=_launch, daemon=True).start()


@app.get("/api/config")
def get_config():
    return load_config()


@app.put("/api/config")
def put_config(cfg: dict):
    saved = save_config(cfg)
    return saved


@app.get("/api/schema")
def get_config_schema():
    from briefing.llm import price_label
    fields = []
    for f in get_schema():
        if f.get("type") == "model":
            f = {**f, "prices": {opt: price_label(opt) for opt in (f.get("options") or [])}}
        fields.append(f)
    return {"fields": fields}


@app.post("/api/run")
def start_run():
    pid = runner.start()
    if pid is None:
        raise HTTPException(status_code=409, detail="already running")
    return {"pid": pid}


@app.post("/api/stop")
def stop_run():
    stopped = runner.stop()
    if not stopped:
        raise HTTPException(status_code=409, detail="not running")
    return {"stopped": True}


@app.get("/api/status")
def status():
    return runner.status()


@app.get("/api/migration/export")
def migration_export():
    if runner.is_running():
        raise HTTPException(status_code=409, detail="Stop the worker before exporting.")
    from briefing.migration import export_to_file
    p = export_to_file()
    return {"path": str(p), "name": p.name}


@app.post("/api/migration/import")
async def migration_import(request: Request):
    if runner.is_running():
        raise HTTPException(status_code=409, detail="Stop the worker before importing.")
    from briefing.migration import import_bytes
    body = await request.body()
    try:
        return import_bytes(body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/progress")
def get_progress(limit: int = 300):
    """In-flight videos (not yet pushed) with per-stage status and LLM usage."""
    items = []
    limit = max(1, min(limit, 2000))
    if not DB_PATH.exists():
        return {"items": items}

    def stage(done, error=False):
        return "error" if error else ("done" if done else "pending")

    conn = sqlite3.connect(DB_PATH.as_posix())
    conn.row_factory = sqlite3.Row
    try:
        # SELECT * so a DB not yet migrated to tokens/cost still works.
        cur = conn.execute(
            "SELECT * FROM videos WHERE pushed = 0 ORDER BY inserted_at DESC, id DESC LIMIT ?",
            (limit,),
        )
        for r in cur.fetchall():
            d = dict(r)
            vid = (d.get("video_id") or "").strip()
            downloaded = d.get("downloaded") or 0
            dl_err = d.get("download_error") or ""

            tprog = 0
            pf = PROGRESS_DIR / vid
            if vid and pf.exists():
                try:
                    tprog = int((pf.read_text(encoding="utf-8").strip() or "0"))
                except Exception:
                    tprog = 0

            items.append({
                "video_id": vid,
                "title": d.get("title") or "",
                "source": d.get("source") or "",
                "download": stage(downloaded, bool(dl_err) and not downloaded),
                "transcribe": stage(d.get("transcribed") or 0),
                "transcribe_progress": tprog,
                "summarize": stage(d.get("summarized") or 0),
                "push": stage(d.get("pushed") or 0),
                "tokens": int(d.get("tokens") or 0),
                "cost": float(d.get("cost") or 0.0),
                "error": dl_err,
            })
    finally:
        conn.close()

    return {"items": items}


@app.get("/api/log")
def get_log(tail: int = 2000):
    tail = max(0, min(tail, 50000))
    return {"log": runner.tail_log(tail)}


@app.post("/api/log/clear")
def clear_log():
    runner.clear_log()
    return {"cleared": True}


@app.get("/api/reports")
def get_reports(limit: int = 200):
    rows = []
    limit = max(1, min(limit, 1000))
    if not DB_PATH.exists():
        return {"items": rows}

    conn = sqlite3.connect(DB_PATH.as_posix())
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            """
            SELECT id, video_id, title, source, downloaded_at, inserted_at, upload_date, pushed, downloaded, webpage_url
            FROM videos
            WHERE downloaded = 1
            ORDER BY REPLACE(REPLACE(REPLACE(REPLACE(
                COALESCE(NULLIF(upload_date, ''), inserted_at),
                '-', ''), ':', ''), 'T', ''), ' ', '') DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        )
        for r in cur.fetchall():
            video_id = (r["video_id"] or "").strip()
            report_path = OUTPUT_DIR / video_id / "report.json"
            report_data = json.loads(report_path.read_text(encoding="utf-8")) if video_id and report_path.exists() else {}
            rows.append({
                "id": r["id"],
                "video_id": video_id,
                "title": r["title"] or "",
                "source": r["source"] or "",
                "webpage_url": r["webpage_url"] or "",
                "downloaded_at": r["downloaded_at"] or "",
                "upload_date": r["upload_date"] or "",
                "inserted_at": r["inserted_at"] or "",
                "pushed": int(r["pushed"] or 0),
                "report_exists": bool(report_data),
                "headline": report_data.get("headline", ""),
            })
    finally:
        conn.close()

    return {"items": rows}


@app.get("/api/report/{video_id}")
def get_report_detail(video_id: str):
    v = (video_id or "").strip()
    if not v:
        raise HTTPException(status_code=400, detail="invalid video_id")
    report_path = OUTPUT_DIR / v / "report.json"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="report.json not found")
    data = json.loads(report_path.read_text(encoding="utf-8"))
    with Session(engine, future=True) as session:
        feedback = get_feedback_map(session, v)
    return {
        "video_id": v,
        "content": data.get("content", ""),
        "headline": data.get("headline", ""),
        "short": data.get("short", ""),
        "feedback": feedback,
    }


@app.post("/api/feedback")
def post_feedback(body: dict):
    video_id = (body.get("video_id") or "").strip()
    stage = (body.get("stage") or "").strip()
    opinion = (body.get("opinion") or "").strip()
    if not video_id or not opinion or stage not in ("headline", "brief", "short"):
        raise HTTPException(status_code=400, detail="video_id, valid stage, and non-empty opinion required")
    # store the English generated text (internal flow is English), not the translated display
    src = OUTPUT_DIR / video_id / f"{stage}.txt"
    output = src.read_text(encoding="utf-8").strip() if src.exists() else ""
    with Session(engine, future=True) as session:
        save_feedback(session, video_id, stage, output, opinion)
    return {"ok": True}


@app.post("/api/review")
def post_review(body: dict):
    # User closed the report (viewed it). Stages left without a correction count as
    # a "pass" (empty opinion) and reinforce the rules that produced them.
    video_id = (body.get("video_id") or "").strip()
    stages = [s for s in (body.get("stages") or []) if s in ("headline", "brief", "short")]
    if not video_id or not stages:
        return {"ok": True}
    with Session(engine, future=True) as session:
        for stage in stages:
            if session.get(Feedback, (video_id, stage)):
                continue  # already has a correction or pass — don't overwrite
            src = OUTPUT_DIR / video_id / f"{stage}.txt"
            output = src.read_text(encoding="utf-8").strip() if src.exists() else ""
            save_feedback(session, video_id, stage, output, "")  # empty opinion = pass
    return {"ok": True}
