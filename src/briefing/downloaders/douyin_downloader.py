"""
Douyin (抖音) fetch/download via the `f2` library.

Why this module exists: yt-dlp's Douyin extractor breaks on the `a_bogus`
signature requirement. `f2` implements that signature, so it can both list a
user's homepage posts and resolve no-watermark video URLs.

Public surface (used by downloader.py):
    is_douyin(url) -> bool
    fetch_homepage_entries(source_url, limit) -> list[dict]   # normalized entries
    download_to(webpage_url, out_path_no_ext) -> Path | None  # saves a video file

Self-test (run inside the `briefing` conda env):
    python douyin_downloader.py <homepage_url>          # list posts
    python douyin_downloader.py video <video_url>       # resolve + show direct url
    python douyin_downloader.py download <video_url>    # actually download one
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime
from http.cookiejar import MozillaCookieJar
from pathlib import Path

import requests

from briefing.config import COOKIES_TXT, AUDIO_DIR, DATA_DIR

import logging

def _quiet_f2() -> None:
    logging.getLogger("f2").setLevel(logging.CRITICAL)  # silence F2's verbose logging

_quiet_f2()

# On-disk cache of fresh direct URLs captured during homepage listing, so the
# later download phase can reuse them instead of calling the Douyin API again.
_URL_CACHE = DATA_DIR / ".douyin_urls.json"

# f2 imports are deferred into functions so importing this module never hard-fails
# if f2 isn't installed in a given environment (e.g. the YouTube-only path).

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def is_douyin(url: str) -> bool:
    return bool(url) and "douyin.com" in url


def _make_video_id(webpage_url: str) -> str:
    # keep identical to downloader.make_video_id so the rest of the pipeline agrees
    return hashlib.sha1(webpage_url.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# direct-url cache  (video_id -> {"url": ..., "exp": epoch_seconds})
# --------------------------------------------------------------------------- #
def _url_exp(direct_url: str) -> int:
    """Read the URL's own expiry (Douyin signs links with x-expires=<epoch>).
    Falls back to now+1h when absent."""
    try:
        from urllib.parse import urlparse, parse_qs
        q = parse_qs(urlparse(direct_url).query)
        for k in ("x-expires", "X-Expires", "expires"):
            if k in q and q[k] and str(q[k][0]).isdigit():
                return int(q[k][0])
    except Exception:
        pass
    return int(datetime.now().timestamp()) + 3600


def _cache_load() -> dict:
    try:
        return json.loads(_URL_CACHE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _cache_save(d: dict) -> None:
    try:
        _URL_CACHE.parent.mkdir(parents=True, exist_ok=True)
        _URL_CACHE.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def cache_put(video_id: str, direct_url: str) -> None:
    if not video_id or not direct_url:
        return
    d = _cache_load()
    now = int(datetime.now().timestamp())
    # garbage-collect expired entries on every write so the file stays bounded
    d = {k: v for k, v in d.items() if v.get("exp", 0) > now}
    d[video_id] = {"url": direct_url, "exp": _url_exp(direct_url)}  # overwrite = dedup
    _cache_save(d)


def cache_get(video_id: str) -> str | None:
    """Return a still-valid cached URL, or None. Prunes expired entries."""
    d = _cache_load()
    rec = d.get(video_id)
    now = int(datetime.now().timestamp())
    if rec and rec.get("exp", 0) > now + 60:  # 60s safety margin
        return rec.get("url")
    if rec:                                    # expired -> drop it
        d.pop(video_id, None)
        _cache_save(d)
    return None


def _load_cookie() -> str:
    """Build a 'k=v; k=v' Cookie header from cookies.txt (Mozilla format,
    filtered to douyin.com). Returns "" if none found."""
    cookies_txt = COOKIES_TXT
    if cookies_txt.exists():
        try:
            jar = MozillaCookieJar()
            jar.load(str(cookies_txt), ignore_discard=True, ignore_expires=True)
            douyin = [c for c in jar if "douyin.com" in (c.domain or "")]
            auth = [c for c in douyin if c.name in ("sessionid", "sessionid_ss", "sid_guard")]
            if not auth or all(c.is_expired() for c in auth):
                print("[douyin] WARNING: login cookies missing/expired")
            parts = [f"{c.name}={c.value}" for c in douyin]
            if parts:
                return "; ".join(parts)
        except Exception:
            pass
    return ""


def _build_kwargs() -> dict:
    cookie = _load_cookie()
    if not cookie:
        print("[douyin] WARNING: no Douyin cookie found in cookies.txt. "
              "Homepage listing may fail.")
    return {
        "headers": {"User-Agent": _UA, "Referer": "https://www.douyin.com/"},
        "cookie": cookie,
        "proxies": {"http://": None, "https://": None},
        "timeout": 20,
        "max_retries": 3,
        "max_connections": 5,
        "max_tasks": 5,
        # download-side keys f2's DouyinDownloader expects to exist; we don't use
        # f2's downloader, but the handler constructs one at init.
        "mode": "post",
        "path": str(AUDIO_DIR),
        "naming": "{create}_{desc}",
        "folderize": False,
        "page_counts": 20,
        "max_counts": 0,
        "interval": "all",
        "cover": False,
        "music": False,
        "download": False,
    }


def _handler():
    from f2.apps.douyin.handler import DouyinHandler
    _quiet_f2()  # re-apply: F2 resets its logger level on init
    return DouyinHandler(_build_kwargs())


def _run(coro):
    # F2 prints page headers via a rich console (stdout); send all its output to the void.
    import os, contextlib
    with open(os.devnull, "w") as _null, contextlib.redirect_stdout(_null), contextlib.redirect_stderr(_null):
        return asyncio.run(coro)


def _find_play_url(obj) -> str | None:
    """Recursively dig a playable http(s) video URL out of an f2 result dict.

    Prefers values living under keys that mention 'play'/'addr'/'url_list',
    skips obvious image/cover URLs. Robust to f2 field-name drift across versions.
    """
    best: str | None = None

    def visit(node, key_hint=""):
        nonlocal best
        if best:
            return
        if isinstance(node, str):
            s = node
            if s.startswith("http") and any(
                t in key_hint.lower() for t in ("play", "addr", "url", "video")
            ):
                low = s.lower()
                if not any(b in low for b in (".jpg", ".jpeg", ".png", ".webp", "cover", "music")):
                    best = s
            return
        if isinstance(node, dict):
            # try the most specific keys first
            for k in ("video_play_addr", "play_addr", "play_url", "url_list", "main_url"):
                if k in node:
                    visit(node[k], k)
                    if best:
                        return
            for k, v in node.items():
                visit(v, k)
        elif isinstance(node, (list, tuple)):
            for v in node:
                visit(v, key_hint)

    visit(obj)
    return best


def _to_dict(filter_obj) -> dict:
    for attr in ("_to_dict", "to_dict"):
        fn = getattr(filter_obj, attr, None)
        if callable(fn):
            try:
                d = fn()
                if isinstance(d, dict):
                    return d
            except Exception:
                pass
    return {}


def _to_list(filter_obj) -> list:
    for attr in ("_to_list", "to_list"):
        fn = getattr(filter_obj, attr, None)
        if callable(fn):
            try:
                lst = fn()
                if isinstance(lst, list):
                    return lst
            except Exception:
                pass
    return []


def _fmt_upload_date(raw) -> str | None:
    """Normalize f2's create_time into 'YYYYMMDD'.

    f2 0.0.1.7 returns a string like '2026-03-29 02-28-24' (note: time also uses
    '-'), so we take the date portion before the space and strip separators.
    Also tolerates epoch seconds.
    """
    if raw is None or raw == "":
        return None
    try:
        if isinstance(raw, (int, float)) or (isinstance(raw, str) and raw.isdigit()):
            return datetime.fromtimestamp(int(raw)).strftime("%Y%m%d")
        date_part = str(raw).strip().split(" ")[0]               # '2026-03-29'
        digits = date_part.replace("-", "").replace("/", "").replace(".", "")
        return digits[:8] if len(digits) >= 8 else None
    except Exception:
        return None


def _ms_to_sec(raw) -> int | None:
    """f2's video_duration is in milliseconds; convert to whole seconds."""
    try:
        return round(int(raw) / 1000)
    except Exception:
        return None


def _create_ts(item) -> int:
    """Epoch seconds for sorting newest-first. Handles f2's epoch ints and its
    '2026-03-29 02-28-24' string (time also uses '-'). Unknown -> 0 (sorts last)."""
    raw = item.get("create_time") or item.get("createTime")
    if raw in (None, ""):
        return 0
    try:
        if isinstance(raw, (int, float)) or str(raw).isdigit():
            return int(raw)
        date_part, _, time_part = str(raw).strip().partition(" ")
        y, m, d = (date_part.split("-") + ["1", "1", "1"])[:3]
        hh, mm, ss = (time_part.split("-") + ["0", "0", "0"])[:3]
        return int(datetime(int(y), int(m), int(d), int(hh), int(mm), int(ss)).timestamp())
    except Exception:
        return 0


# --------------------------------------------------------------------------- #
# public: list a homepage's recent posts
# --------------------------------------------------------------------------- #
async def _afetch_homepage_entries(source_url: str, limit: int) -> list[dict]:
    from f2.apps.douyin.utils import SecUserIdFetcher

    sec_uid = await SecUserIdFetcher.get_sec_user_id(source_url)
    handler = _handler()

    # Pinned (is_top, cap 3) posts come first and can be old; pull limit+3 in one
    # request (break after page 1), then sort by create_time and keep newest `limit`.
    fetch_n = limit + 3
    raw_items: list = []
    async for page in handler.fetch_user_post_videos(
        sec_uid, page_counts=fetch_n, max_counts=fetch_n
    ):
        raw_items = _to_list(page)
        break

    entries: list[dict] = []
    for item in raw_items:
        aweme_id = (
            item.get("aweme_id")
            or item.get("awemeId")
            or item.get("aweme_id_str")
        )
        if not aweme_id:
            continue
        webpage_url = f"https://www.douyin.com/video/{aweme_id}"
        entries.append({
            "source": source_url,
            "extractor": "douyin",
            "upload_date": _fmt_upload_date(item.get("create_time") or item.get("createTime")),
            "duration": _ms_to_sec(item.get("video_duration")),
            "language": None,
            "title": item.get("desc_raw") or item.get("desc") or item.get("title") or aweme_id,
            "webpage_url": webpage_url,
            "video_id": _make_video_id(webpage_url),
            "_ts": _create_ts(item),
            "_play": _find_play_url(item),
        })

    entries.sort(key=lambda e: e["_ts"], reverse=True)
    entries = entries[:limit]
    for e in entries:
        cache_put(e["video_id"], e.pop("_play"))
        e.pop("_ts", None)

    return entries


def fetch_homepage_entries(source_url: str, limit: int) -> list[dict]:
    """Return up to `limit` normalized entries from a Douyin user homepage."""
    try:
        entries = _run(_afetch_homepage_entries(source_url, limit))
        print(f"[douyin] fetched {len(entries)} entries from {source_url}")
        return entries
    except Exception as e:
        print(f"[douyin] fetch_homepage_entries failed: {type(e).__name__}")
        return []


# --------------------------------------------------------------------------- #
# public: resolve + download a single video
# --------------------------------------------------------------------------- #
async def _aresolve_direct_url(webpage_url: str) -> str | None:
    from f2.apps.douyin.utils import AwemeIdFetcher

    aweme_id = await AwemeIdFetcher.get_aweme_id(webpage_url)
    handler = _handler()
    detail = await handler.fetch_one_video(aweme_id)
    return _find_play_url(_to_dict(detail))


def resolve_direct_url(webpage_url: str) -> str | None:
    try:
        return _run(_aresolve_direct_url(webpage_url))
    except Exception as e:
        print(f"[douyin] resolve failed for {webpage_url}: {type(e).__name__}")
        return None


def _pick_ext(direct_url: str, content_type: str) -> str:
    """Choose a file extension from the resolved URL / Content-Type.

    Preference per project rule: if the source is already audio (mp3), keep it;
    otherwise save the original container (mp4). No transcoding.
    """
    ct = (content_type or "").lower()
    low = direct_url.lower()
    if "mpeg" in ct or "mp3" in ct or ".mp3" in low:
        return ".mp3"
    if "audio" in ct or ".m4a" in low:
        return ".m4a"
    return ".mp4"


def _stream_to(direct_url: str, out_path_no_ext: Path) -> Path | None:
    """Stream a known direct URL (CDN, not the Douyin API) to disk.

    No Douyin API call here — this is the cheap, ban-safe step. Extension
    follows the source: a direct mp3 stays mp3, otherwise mp4. No transcoding.
    Returns the saved Path, else None.
    """
    headers = {"User-Agent": _UA, "Referer": "https://www.douyin.com/"}
    cookie = _load_cookie()
    if cookie:
        headers["Cookie"] = cookie

    out_path: Path | None = None
    try:
        with requests.get(direct_url, headers=headers, stream=True, timeout=60) as r:
            r.raise_for_status()
            ext = _pick_ext(direct_url, r.headers.get("Content-Type", ""))
            out_path = Path(str(out_path_no_ext) + ext)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    if chunk:
                        f.write(chunk)
    except Exception as e:
        print(f"[douyin] download failed: {type(e).__name__}")
        if out_path and out_path.exists():
            try:
                out_path.unlink()
            except Exception:
                pass
        return None

    if out_path and out_path.exists() and out_path.stat().st_size > 100 * 1024:
        return out_path

    print("[douyin] file too small / missing")
    return None


def download_to(webpage_url: str, out_path_no_ext: Path,
                video_id: str | None = None) -> Path | None:
    """Download a Douyin video to <out_path_no_ext>.<ext>.

    Request budget: tries the cached direct URL first (captured during homepage
    listing -> 0 API calls). Only if the cache misses or the cached URL has
    expired do we fall back to one fetch_one_video API call to re-resolve.
    """
    video_id = video_id or _make_video_id(webpage_url)

    cached = cache_get(video_id)
    if cached:
        saved = _stream_to(cached, out_path_no_ext)
        if saved:
            return saved
        print("[douyin] cached url failed/expired -> re-resolving via API")

    direct = resolve_direct_url(webpage_url)
    if not direct:
        print(f"[douyin] no direct url for {webpage_url}")
        return None
    cache_put(video_id, direct)
    return _stream_to(direct, out_path_no_ext)


# --------------------------------------------------------------------------- #
# self-test
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd == "keys" and len(sys.argv) >= 3:
        n = int(sys.argv[3]) if len(sys.argv) >= 4 else 3
        async def _dump(url):
            from f2.apps.douyin.utils import SecUserIdFetcher
            sec_uid = await SecUserIdFetcher.get_sec_user_id(url)
            handler = _handler()
            async for page in handler.fetch_user_post_videos(
                sec_uid, page_counts=n, max_counts=n
            ):
                return _to_list(page)
            return []
        items = _run(_dump(sys.argv[2]))
        for i, it in enumerate(items):
            ct = it.get("create_time") or it.get("createTime")
            print(f"[{i}] ts={_create_ts(it)} create_time={ct!r} | {(it.get('desc') or '')[:32]}")
        print(f"-- {len(items)} posts --")
    elif cmd == "video" and len(sys.argv) >= 3:
        url = sys.argv[2]
        d = _run(_aresolve_direct_url(url))
        print("direct url:", d)
    elif cmd == "download" and len(sys.argv) >= 3:
        url = sys.argv[2]
        vid = _make_video_id(url)
        p = download_to(url, AUDIO_DIR / vid)
        print("saved:", p)
    else:
        # treat arg as a homepage url; optional 2nd arg = how many (default 3)
        url = cmd
        n = int(sys.argv[2]) if len(sys.argv) >= 3 else 3
        for e in fetch_homepage_entries(url, n):
            print(json.dumps(e, ensure_ascii=False))
