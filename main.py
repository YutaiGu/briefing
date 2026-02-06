import time
from sqlalchemy.orm import Session
import os
from pathlib import Path
from config import DOWNLOAD_INTERVAL, PROCESS_INTERVAL, PUSHER_LIMIT, PUSHER_INTERVAL, DATA_DIR

FFMPEG_DIR = DATA_DIR / "ffmpeg"
os.environ["PATH"] = str(FFMPEG_DIR) + os.pathsep + os.environ.get("PATH", "")

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

if __name__ == "__main__":
    init_db()
    check_whisper_model()
    run()
