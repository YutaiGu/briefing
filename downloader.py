from yt_dlp import YoutubeDL
from datetime import datetime
import hashlib

from .config import AUDIO_DIR, ENTRIES_LIMIT, SOURCE_URLS, UPDATE_LIMIT
from .db import Video, update_entries, init_entries, get_undownloaded, get_entries_by_ids, save_entries

def downloader(session) -> None:
    for source_url in SOURCE_URLS:
        entries = fetch_all_entries(source_url)
        n = init_entries(session, entries)
        print(f"Inited {n} entries.")
        videos = get_undownloaded(session, source_url, UPDATE_LIMIT)

        ok = 0
        fail = 0
        for v in videos:
            entry = download_entry(v)
            if entry.downloaded == 0:
                fail += 1
            else:
                ok += 1
            update_entries(session, [entry])
        print(f"Download finished: {ok} succeeded, {fail} failed.")

def make_local_audio_id(filename: str) -> str:
    # 24-char id for external audio files
    return hashlib.sha1(filename.encode("utf-8")).hexdigest()[:24]

def make_video_id(webpage_url: str) -> str:
    # 16-char id for webpage url
    return hashlib.sha1(webpage_url.encode("utf-8")).hexdigest()[:16]

def fetch_all_entries(source_url: str) -> list:
    '''
    Fetch and normalize video entries from a source URL.

    entry: 
        source            Guaranteed  <-
        extractor         Nullable    <-
        upload_date       Nullable    <-
        duration          Nullable    <-
        language          Nullable    <-
        title             Nullable    <-
        webpage_url       Guaranteed  <-
        inserted_at       Not set here
        downloaded        Not set here
        downloaded_at     Not set here
        file_path         Not set here
        download_error    Not set here
        transcribed       Not set here
        summarized        Not set here
        pushed            Not set here
        video_id          Guaranteed  <-
    '''
    ydl_opts = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "playlist_items": ENTRIES_LIMIT,
    }

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(source_url, download=False)
    if not info:
        return []
   
    raw_entries = info.get("entries")
    if raw_entries is None:
        raw_entries = [info]  # Single video
    
    entries = []
    for e in raw_entries:
        if not isinstance(e, dict):
            continue
        
        # check entry is a single downloadable item (video)
        if "entries" in e:
            print(f"{source_url} is not a video page.")
            return []
        
        webpage_url = e.get("webpage_url") or e.get("original_url") or e.get("url")
        if not webpage_url:
            continue

        entry = {
            "source": source_url,
            "extractor": e.get("extractor") or e.get("extractor_key"),
            "upload_date": e.get("upload_date"),
            "duration": e.get("duration"),
            "language": e.get("language"),
            "title": e.get("title"),
            "webpage_url": webpage_url,
            "video_id": make_video_id(webpage_url),
        }

        entries.append(entry)

    print(f"Fetched {len(entries)} entries from {source_url}")
    return entries

def download_entry(entry: Video) -> bool:
    '''
    Download one entry
    
    entry: 
        source            Exist
        extractor         Nullable
        upload_date       Nullable
        duration          Nullable
        language          Nullable
        title             Nullable
        webpage_url       Exist
        inserted_at       Exist
        downloaded        Exist     <-
        downloaded_at     Nullable  <-
        file_path         Nullable  <-
        download_error    Nullable  <-
        transcribed       Exist
        summarized        Exist
        pushed            Exist
        video_id          Exist
    '''
    outtmpl = str(AUDIO_DIR / f"{entry.video_id}.%(ext)s")
    out_path = AUDIO_DIR / f"{entry.video_id}.mp3"

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "format": "bestaudio/best",
        "noplaylist": True,
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0.0.0 Safari/537.36"
        ),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "outtmpl": outtmpl,
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(entry.webpage_url, download=True)

        if out_path.exists():
            entry.downloaded = 1
            entry.downloaded_at = datetime.now().isoformat(timespec="seconds")
            entry.file_path = str(out_path)
            entry.download_error = None
            return entry

        # ffmpeg did not create MP3
        entry.downloaded = 0
        entry.download_error = "mp3 not created"
        print(f"{entry.webpage_url} download failed: mp3 not created.")
        return entry
    except Exception as ex:
        entry.downloaded = 0
        entry.download_error = f"{type(ex).__name__}: {ex}"
        print(f"{entry.webpage_url} download failed. {ex}")
        return entry

def import_external_entries(session):
    # Scan AUDIO_DIR for audio files not in DB and insert them for transcription.
    now = datetime.now()
    inserted_at = now.strftime("%Y%m%d")

    for p in AUDIO_DIR.iterdir():
        try:
            if not p.is_file():
                continue
            
            # skip if downloading
            PARTIAL_SUFFIXES = {".part", ".tmp", ".download"}
            Video_SUFFIXES = {
                ".mp3", ".wav", ".m4a", ".aac", ".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv"
            }
            suf = p.suffix.lower()
            if suf in PARTIAL_SUFFIXES:
                continue
            if suf not in Video_SUFFIXES:
                continue
            stem = p.stem
            downloading = any((AUDIO_DIR / f"{stem}{ps}").exists() for ps in PARTIAL_SUFFIXES)
            if downloading:
                continue

            # skip very recent files (still being written)
            if (now.timestamp() - p.stat().st_mtime) < 60:
                continue

            filename = p.stem
            exists = get_entries_by_ids(session, [filename])
            if exists:
                continue
            local_id = make_local_audio_id(filename)
            new_path = p.with_name(f"{local_id}{p.suffix.lower()}")
            entry = Video(
                source="local",
                extractor="local",
                upload_date=None,
                duration=None,
                language=None,
                title=filename,
                webpage_url=f"local:{local_id}",
                inserted_at=inserted_at,
                downloaded=1, 
                downloaded_at=now.isoformat(timespec="seconds"),
                file_path=str(new_path),
                download_error=None,
                transcribed=0,
                summarized=0,
                pushed=0,
                video_id=local_id,
            )
            p.rename(new_path)
            save_entries(session, [entry])
            print(f"[Inserted] {local_id}")

        except Exception:
            session.rollback()
            pass

    return 