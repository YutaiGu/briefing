import time
from sqlalchemy.orm import Session

from .config import DOWNLOAD_INTERVAL, PROCESS_INTERVAL, PUSHER_LIMIT, PUSHER_INTERVAL
from .db import engine, clean_all, init_db
from .downloader import downloader, import_external_entries
from .transcriber import transcriber
from .summarizer import summarizer
from .pusher import pusher

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
                pusher_timer = now
                time.sleep(10)

if __name__ == "__main__":
    init_db()
    run()
