"""Export / import all briefing state as one portable zip, for moving between
machines (mac/windows) and across app versions.

Bundled: config.json, cookies.txt, db.sqlite3, output/, reports/, preferences/.
Excluded: audio/ and model_prices.json (large, regenerable) and transient files.

Forward compatibility: zip paths use forward slashes; config.json is re-merged
leniently on import and the DB schema is auto-synced, so an archive from an
older version still imports cleanly.
"""
import io
import json
import shutil
import zipfile
from pathlib import Path

from briefing.config import DATA_DIR, BASE_DIR

FORMAT = "briefing-migration"
FORMAT_VERSION = 1

# members relative to DATA_DIR; directories are included recursively
MEMBERS = ["config.json", "cookies.txt", "db.sqlite3", "output", "reports", "preferences"]


def _app_version() -> str:
    try:
        import importlib.metadata as m
        return m.version("briefing")
    except Exception:
        return "unknown"


def _files(rel: str):
    p = DATA_DIR / rel
    if p.is_dir():
        yield from (f for f in p.rglob("*") if f.is_file())
    elif p.is_file():
        yield p


def export_bytes() -> bytes:
    members = []
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in MEMBERS:
            for f in _files(rel):
                arc = f.relative_to(DATA_DIR).as_posix()
                z.write(f, arc)
                members.append(arc)
        z.writestr("manifest.json", json.dumps({
            "format": FORMAT,
            "format_version": FORMAT_VERSION,
            "app_version": _app_version(),
            "files": members,
        }, ensure_ascii=False, indent=2))
    return buf.getvalue()


def export_to_file() -> Path:
    """Write the backup zip to disk (pywebview can't trigger browser downloads)."""
    from datetime import datetime
    dest = BASE_DIR / f"briefing-backup-{datetime.now():%Y%m%d-%H%M%S}.zip"
    dest.write_bytes(export_bytes())
    return dest


def _unsafe(name: str) -> bool:
    p = Path(name)
    return p.is_absolute() or ".." in p.parts


def import_bytes(data: bytes) -> dict:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data), "r")
    except zipfile.BadZipFile:
        raise ValueError("not a valid backup file")
    with zf as z:
        try:
            manifest = json.loads(z.read("manifest.json"))
        except KeyError:
            raise ValueError("not a briefing backup (missing manifest.json)")
        if manifest.get("format") != FORMAT:
            raise ValueError("not a briefing backup")

        restored = 0
        for name in z.namelist():
            if name == "manifest.json" or name.endswith("/") or _unsafe(name):
                continue
            target = DATA_DIR / name
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.name == "config.json":
                from briefing.web.app.config_schema import merge_lenient
                merged = merge_lenient(json.loads(z.read(name)))
                target.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
            else:
                with z.open(name) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
            restored += 1

    try:
        from briefing.db import init_db  # forward-migrate the imported DB's schema
        init_db()
    except Exception:
        pass

    return {"app_version": manifest.get("app_version"), "restored": restored}
