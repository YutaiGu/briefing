from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
import os
import sqlite3
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

BACKEND_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = BACKEND_ROOT / "static"
MAIN_SCRIPT = BACKEND_ROOT.parent / "main.py"
DB_PATH = BACKEND_ROOT.parent / "data" / "db.sqlite3"
OUTPUT_DIR = BACKEND_ROOT.parent / "data" / "output"
BROWSER_URL = os.environ.get("RUNNER_URL", "http://localhost:8000/")
AUTO_OPEN = os.environ.get("AUTO_OPEN_BROWSER", "1") != "0"

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def root_page():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "UI not found. Ensure backend/static/index.html exists."}


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
    return {"fields": get_schema()}


@app.post("/api/run")
def start_run():
    pid = runner.start(MAIN_SCRIPT)
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
            SELECT id, video_id, title, source, downloaded_at, pushed, downloaded, webpage_url
            FROM videos
            WHERE downloaded = 1
            ORDER BY downloaded_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        )
        for r in cur.fetchall():
            video_id = (r["video_id"] or "").strip()
            report_path = OUTPUT_DIR / video_id / "report.txt"
            rows.append({
                "id": r["id"],
                "video_id": video_id,
                "title": r["title"] or "",
                "source": r["source"] or "",
                "webpage_url": r["webpage_url"] or "",
                "downloaded_at": r["downloaded_at"] or "",
                "pushed": int(r["pushed"] or 0),
                "report_exists": bool(video_id and report_path.exists()),
            })
    finally:
        conn.close()

    return {"items": rows}


@app.get("/api/report/{video_id}")
def get_report_detail(video_id: str):
    v = (video_id or "").strip()
    if not v:
        raise HTTPException(status_code=400, detail="invalid video_id")
    report_path = OUTPUT_DIR / v / "report.txt"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="report.txt not found")
    return {
        "video_id": v,
        "content": report_path.read_text(encoding="utf-8"),
    }
