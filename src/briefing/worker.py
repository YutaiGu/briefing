import os

from briefing.config import FFMPEG_DIR, require_config

os.environ["PATH"] = str(FFMPEG_DIR) + os.pathsep + os.environ.get("PATH", "")

import time
from sqlalchemy.orm import Session

from briefing.config import DOWNLOAD_INTERVAL, PROCESS_INTERVAL, PUSHER_LIMIT, PUSHER_INTERVAL
from briefing.db import engine, clean_all, init_db, clean_entries
from briefing.downloaders.downloader import downloader, import_external_entries
from briefing.transcriber import transcriber, check_whisper_model
from briefing.summarizer_agent import summarizer
from briefing.pusher import pusher


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


def main():
    require_config()
    init_db()
    check_whisper_model()
    run()


if __name__ == "__main__":
    main()
