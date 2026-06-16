from sqlalchemy import create_engine, Column, Integer, Float, String, UniqueConstraint, select
from sqlalchemy.orm import declarative_base
from sqlalchemy.exc import IntegrityError
from sqlalchemy.inspection import inspect
from datetime import datetime, timedelta
from pathlib import Path
import shutil
import os, stat, time

from briefing.config import DB_URL, AUDIO_DIR, OUTPUT_DIR, TEMPORARY_DIR, check_config, UPDATE_LIMIT, ENTRIES_LIMIT

# ENTRIES_LIMIT is the yt-dlp "1-x" string; the plain integer is the per-source keep count.
try:
    _ENTRIES_LIMIT_INT = int(str(ENTRIES_LIMIT).split("-")[-1])
except Exception:
    _ENTRIES_LIMIT_INT = 3

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
    domain = Column(String)                                     # finance / other (set by review stage)
    tokens = Column(Integer, nullable=False, default=0)         # LLM tokens used (summarize)
    cost = Column(Float, nullable=False, default=0.0)           # LLM cost in USD
    __table_args__ = (UniqueConstraint("webpage_url", name="uq_webpage_url"),)


class Feedback(Base):
    __tablename__ = "feedback"
    video_id = Column(String, primary_key=True)                 # the video this opinion is about
    stage = Column(String, primary_key=True)                    # headline / brief / short
    output = Column(String)                                     # the generated text the user critiqued
    opinion = Column(String)                                    # the user's improvement note
    applied = Column(Integer, nullable=False, default=0)        # 0/1 distilled into notes yet


def _sync_schema() -> None:
    """Add any model column missing from its existing table, for every table."""
    insp = inspect(engine)
    existing = set(insp.get_table_names())
    for table in Base.metadata.sorted_tables:
        if table.name not in existing:
            continue  # create_all already built new tables with the full schema
        have = {c["name"] for c in insp.get_columns(table.name)}
        with engine.begin() as conn:
            for col in table.columns:
                if col.name not in have:
                    coltype = col.type.compile(engine.dialect)
                    conn.exec_driver_sql(
                        f"ALTER TABLE {table.name} ADD COLUMN {col.name} {coltype}"
                    )

def init_db() -> None:
    # Ensure DB file & tables exist, and existing tables match the models.
    Base.metadata.create_all(bind=engine)
    _sync_schema()

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
        for p in AUDIO_DIR.rglob("*"):
            try:
                if p.is_dir():
                    if not any(p.iterdir()):
                        p.rmdir()
                elif p.is_file():
                    continue
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
    print("[CLEAN] Finished.\n")

ENTRY_TTL_DAYS = 7

def clean_entries(session) -> int:
    """Delete entries older than ENTRY_TTL_DAYS AND ranked outside their source's
    newest _ENTRIES_LIMIT_INT. Deleting a row still in the fetch window would just
    re-pull it (dedup is by webpage_url)."""
    cutoff = datetime.now() - timedelta(days=ENTRY_TTL_DAYS)
    deleted = 0
    try:
        rows = session.query(Video).all()
    except Exception as e:
        print(f"Error on clean_entries: {e}")
        return 0

    by_source: dict[str, list] = {}
    for v in rows:
        by_source.setdefault(v.source or "", []).append(v)

    for group in by_source.values():
        group.sort(key=lambda x: x.inserted_at or "", reverse=True)
        for rank, v in enumerate(group):
            if rank < _ENTRIES_LIMIT_INT:
                continue
            try:
                ts = datetime.fromisoformat(v.inserted_at)
            except Exception:
                continue
            if ts >= cutoff:
                continue
            delete_audio_by_path(v.file_path)
            try:
                session.query(Feedback).filter(Feedback.video_id == v.video_id).delete()
                session.delete(v)
                session.commit()
                deleted += 1
            except Exception:
                session.rollback()

    return deleted

def delete_audio_by_path(file_path: str) -> bool:
    try:
        p = Path(file_path)
        if p.exists() and p.is_file():
            os.chmod(p, stat.S_IWRITE)  # clear readonly bit first (required for deleting .m4a files on Windows)
            time.sleep(0.5)
            p.unlink()
            print(f"[DELETE] {p.name}")
            return True
        return False
    except Exception as e:
        print(f"Delete error on {file_path}: {e}")
        return False

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
    inserted = 0

    for e in entries:
        if not check_is_entry(e):
            continue
        
        inserted_at = datetime.now().isoformat(timespec="seconds")
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

def entry_to_payload(v: Video) -> dict:
    return {
        c.key: getattr(v, c.key)
        for c in inspect(Video).mapper.column_attrs
    }

def payload_to_entry(payload: dict) -> Video:
    v = Video()
    for k, val in payload.items():
        setattr(v, k, val)
    return v

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
        .order_by(Video.inserted_at.asc())  # Oldest first
    )
    if limit:
        q = q.limit(limit)
    return q.all()

def get_untranscribed(session, limit: int):
    q = (
        session.query(Video)
        .filter(Video.downloaded == 1, Video.transcribed == 0)
        .order_by(Video.inserted_at.asc())  # Oldest first
    )
    if limit:
        q = q.limit(limit)
    return q.all()

def get_unsummarized(session, limit: int):
    q = (
        session.query(Video)
        .filter(Video.downloaded == 1, Video.transcribed == 1, Video.summarized == 0)
        .order_by(Video.inserted_at.asc())  # Oldest first
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
        .order_by(Video.inserted_at.asc())  # Oldest first
    )
    if limit:
        q = q.limit(limit)
    return q.all()

def get_entries_by_ids(session, video_ids: list[str]):
    if not video_ids:
        return []
    stmt = select(Video).where(Video.video_id.in_(video_ids))
    return session.execute(stmt).scalars().all()

def save_feedback(session, video_id: str, stage: str, output: str, opinion: str) -> None:
    # one opinion per (video_id, stage): upsert, and reset applied so it re-evolves
    fb = session.get(Feedback, (video_id, stage))
    if fb:
        fb.output, fb.opinion, fb.applied = output, opinion, 0
    else:
        session.add(Feedback(video_id=video_id, stage=stage,
                             output=output, opinion=opinion, applied=0))
    session.commit()

def get_feedback_map(session, video_id: str) -> dict:
    rows = session.query(Feedback).filter(Feedback.video_id == video_id).all()
    return {r.stage: r.opinion for r in rows}

def get_unapplied_feedback(session):
    return session.query(Feedback).filter(Feedback.applied == 0).all()

def mark_feedback_applied(session, keys) -> None:
    # keys: iterable of (video_id, stage)
    for vid, stage in keys:
        fb = session.get(Feedback, (vid, stage))
        if fb:
            fb.applied = 1
    session.commit()
