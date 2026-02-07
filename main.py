from pathlib import Path
import json
import os

CONFIG_PATH = Path(__file__).parent / "backend" / "data" / "config.json"
FFMPEG_DIR = Path(__file__).parent / "data" / "ffmpeg"
os.environ["PATH"] = str(FFMPEG_DIR) + os.pathsep + os.environ.get("PATH", "")

import time
from sqlalchemy.orm import Session

from config import DOWNLOAD_INTERVAL, PROCESS_INTERVAL, PUSHER_LIMIT, PUSHER_INTERVAL
from db import engine, clean_all, init_db, clean_entries
from downloader import downloader, import_external_entries
from transcriber import transcriber, check_whisper_model
from summarizer import summarizer
from pusher import pusher

def run() -> None:
    download_timer = 0
    process_timer = 0
    pusher_timer = 0
    print("START")
    
    while True:
        now = time.time()

        with Session(engine, future=True) as session:
            # ---- downloader ----
            if now - download_timer >= DOWNLOAD_INTERVAL:
                downloader(session)
                download_timer = now
                time.sleep(10)

            # ---- process ----
            if now - process_timer >= PROCESS_INTERVAL:
                import_external_entries(session)
                transcriber(session)
                summarizer(session)
                clean_all(session)
                process_timer = now
                time.sleep(10)
            
            # ---- pusher ----
            if now - pusher_timer >= PUSHER_INTERVAL:
                pusher(session, PUSHER_LIMIT)
                clean_entries(session)
                pusher_timer = now
                time.sleep(10)

def load_config():
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Config not found at {CONFIG_PATH}. Start the API once to generate defaults."
        )
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)

def main():
    load_config()
    init_db()
    check_whisper_model()
    run()

if __name__ == "__main__":
    main()
