"""Export browser cookies to cookies.txt (Mozilla format).

Douyin homepage listing needs a logged-in cookie. Log into douyin.com in any
installed browser, then run:

    python cookies.py                  # try all known browsers, merge what works
    python cookies.py chrome firefox   # restrict to specific browsers

Cookies from every readable browser are merged into cookies.txt next to the
project; douyin_downloader filters the douyin.com entries from it at runtime.
"""
import sys
from http.cookiejar import MozillaCookieJar

from yt_dlp import YoutubeDL

from config import COOKIES_TXT

# Ordered by how common they are; unknown/uninstalled ones are skipped.
ALL_BROWSERS = ["safari", "edge", "firefox", "chrome"]

class _SilentLogger:
    """Swallow yt-dlp's stderr noise for browsers that aren't installed."""
    def debug(self, msg): pass
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass


def create_cookies_txt(browsers: list[str] | None = None) -> None:
    browsers = browsers or ALL_BROWSERS
    merged = MozillaCookieJar(str(COOKIES_TXT))

    report = []
    for b in browsers:
        try:
            with YoutubeDL({
                "cookiesfrombrowser": (b,),
                "quiet": True,
                "no_warnings": True,
                "logger": _SilentLogger(),
            }) as ydl:
                jar = ydl.cookiejar  # lazily extracts on access
                total = 0
                douyin = 0
                for c in jar:
                    merged.set_cookie(c)
                    total += 1
                    if "douyin.com" in (c.domain or ""):
                        douyin += 1
            report.append(f"  {b:9s} ok   total={total:<5d} douyin={douyin}")
        except Exception as e:
            report.append(f"  {b:9s} skip {type(e).__name__}: {e}")

    merged.save(ignore_discard=True, ignore_expires=True)

    douyin_total = sum(1 for c in merged if "douyin.com" in (c.domain or ""))
    print("\n".join(report))
    print(f"\nSaved cookies to {COOKIES_TXT}")
    print(f"Douyin cookies in file: {douyin_total}")
    if douyin_total == 0:
        print("WARNING: no douyin.com cookies found — log into douyin.com in a "
              "browser first, then re-run.")


if __name__ == "__main__":
    args = sys.argv[1:]
    create_cookies_txt(args or None)
