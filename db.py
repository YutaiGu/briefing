from sqlalchemy import create_engine, Column, Integer, String, UniqueConstraint, select
from sqlalchemy.orm import declarative_base
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from pathlib import Path
import hashlib
import shutil

from config import DB_URL, DATA_DIR, AUDIO_DIR, OUTPUT_DIR, PROMPT_DIR, TEMPORARY_DIR, check_config


engine = create_engine(DB_URL, future=True)
Base = declarative_base()

AUDIO_SUFFIXES = {
    ".aac", ".aiff", ".alac", ".flac", ".m4a", ".mp3", ".ogg",
    ".opus", ".wav", ".wma", ".webm",
}
PARTIAL_SUFFIXES = {
    ".part", ".partial", ".tmp", ".crdownload", ".download", ".ytdl",
}

class Video(Base):
    __tablename__ = "videos"
    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String, nullable=False)                     # source url
    extractor = Column(String)                                  # youtube
    upload_date = Column(String)                                # 20251223
    duration = Column(Integer)                                  # 366s
    language = Column(String)                                   # en-US /
    title = Column(String)
    webpage_url = Column(String, nullable=False)
    inserted_at = Column(String, nullable=False)                # 20251225
    downloaded = Column(Integer, nullable=False, default=0)     # 0/1
    downloaded_at = Column(String)                              # download time 20251225
    file_path = Column(String)                                  # video path
    download_error = Column(String)                             # file name
    transcribed = Column(Integer, nullable=False, default=0)    # 0/1
    summarized = Column(Integer, nullable=False, default=0)     # 0/1
    pushed = Column(Integer, nullable=False, default=0)         # 0/1
    video_id = Column(String)                                   # video filename
    __table_args__ = (UniqueConstraint("webpage_url", name="uq_webpage_url"),)

def init_db() -> None:
    # Ensure DB file & tables exist.
    Base.metadata.create_all(bind=engine)

    ok, missing, errors = check_config()
    if ok:
        return
    print("[CONFIG ERROR]")
    if missing:
        print("Missing:")
        for x in missing:
            print(" -", x)
    if errors:
        print("Invalid:")
        for x in errors:
            print(" -", x)

def clean_all(session) -> None:
    try:
        valid_ids = {
            v.video_id
            for v in session.query(Video.video_id).all()
            if v.video_id
        }

        # AUDIO_DIR cleanup
        for p in AUDIO_DIR.iterdir():
            try:
                if not p.is_file() or p.stem not in valid_ids:
                    if p.is_file():
                        p.unlink()
                    else:
                        shutil.rmtree(p)
            except Exception:
                pass

        # OUTPUT_DIR cleanup
        for d in OUTPUT_DIR.iterdir():
            if d.name not in valid_ids:
                try:
                    shutil.rmtree(d)  # delete directory recursively
                except Exception:
                    pass
        
        # TEMPORARY_DIR cleanup
        for d in TEMPORARY_DIR.iterdir():
            if d.name not in valid_ids:
                try:
                    shutil.rmtree(d)  # delete directory recursively
                except Exception:
                    pass
    except Exception:
        pass

def check_is_entry(entry: dict) -> bool:
    if not isinstance(entry, dict):
        return False

    if not entry.get("webpage_url"):
        return False

    return True

def init_entries(session, entries) -> int:
    '''
    Fetch and normalize video entries from a source URL.
    
    entry: 
        source            Exist
        extractor         Nullable
        upload_date       Nullable
        duration          Nullable
        language          Nullable
        title             Nullable
        webpage_url       Exist
        inserted_at       Guaranteed  <-
        downloaded        Guaranteed  <-
        downloaded_at     Not set here
        file_path         Not set here
        download_error    Not set here
        transcribed       Guaranteed  <-
        summarized        Guaranteed  <-
        pushed            Guaranteed  <-
        video_id          Exist
    '''
    inserted_at = datetime.now().strftime("%Y%m%d")
    inserted = 0

    for e in entries:
        if not check_is_entry(e):
            continue

        row = Video(
            source=e["source"],
            extractor=e.get("extractor"),
            upload_date=e.get("upload_date"),
            duration=e.get("duration"),
            language=e.get("language"),
            title=e.get("title"),
            webpage_url=e["webpage_url"],
            inserted_at=inserted_at,
            downloaded=0,
            transcribed=0,
            video_id=e["video_id"]
        )

        session.add(row)
        try:
            session.commit()  # UNIQUE(webpage_url)
            inserted += 1
        except IntegrityError:
            session.rollback()  # duplicate -> ignore
        except Exception as ex:
            print(f"Save error on {row.webpage_url}: {type(ex).__name__}: {ex}")

    return inserted

def save_entries(session, entries: list[Video]) -> int:
    inserted = 0
    for v in entries:
        session.add(v)
        try:
            session.commit()  # UNIQUE(webpage_url)
            inserted += 1
        except IntegrityError:
            session.rollback()  # duplicate -> ignore
        except Exception as ex:
            print(f"Save error on {v.webpage_url}: {type(ex).__name__}: {ex}")
    return inserted

def update_entries(session, entries: list[Video]) -> int:
    updated = 0
    for v in entries:
        try:
            session.merge(v)
            session.commit()
            updated += 1
        except Exception as ex:
            session.rollback()
            print(f"Update error on {v.webpage_url}: {type(ex).__name__}: {ex}")
    return updated

def get_undownloaded(session, source_url: str, limit: int) -> list:
    q = (
        session.query(Video)
        .filter(Video.downloaded == 0, Video.source == source_url)
        .order_by(Video.id.asc())  # Oldest first
    )
    if limit:
        q = q.limit(limit)
    return q.all()

def get_untranscribed(session, limit: int):
    q = (
        session.query(Video)
        .filter(Video.downloaded == 1, Video.transcribed == 0)
        .order_by(Video.id.asc())  # Oldest first
    )
    if limit:
        q = q.limit(limit)
    return q.all()

def get_unsummarized(session, limit: int):
    q = (
        session.query(Video)
        .filter(Video.downloaded == 1, Video.transcribed == 1, Video.summarized == 0)
        .order_by(Video.id.asc())  # Oldest first
    )
    if limit:
        q = q.limit(limit)
    return q.all()

def get_unpushed(session, limit: int):
    q = (
        session.query(Video)
        .filter(Video.downloaded == 1, 
                Video.transcribed == 1, 
                Video.summarized == 1, 
                Video.pushed == 0)
        .order_by(Video.id.asc())  # Oldest first
    )
    if limit:
        q = q.limit(limit)
    return q.all()

def get_entries_by_ids(session, video_ids: list[str]):
    if not video_ids:
        return []
    stmt = select(Video).where(Video.video_id.in_(video_ids))
    return session.execute(stmt).scalars().all()
