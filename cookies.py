import json
from http.cookiejar import MozillaCookieJar
from yt_dlp import YoutubeDL

from config import COOKIES_TXT, DD_COOKIES_JSON


def create_cookies_txt() -> None:
    with YoutubeDL({
        "cookiesfrombrowser": ("firefox",),
        "cookiefile": str(COOKIES_TXT),
        "quiet": True,
    }) as ydl:
        ydl.cookiejar


def export_cookies_json() -> None:
    jar = MozillaCookieJar()
    jar.load(str(COOKIES_TXT), ignore_discard=True, ignore_expires=True)
    cookies = {c.name: c.value for c in jar if "douyin.com" in (c.domain or "")}
    with open(DD_COOKIES_JSON, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "export-cookies":
        export_cookies_json()
        print("Exported cookies to douyin-downloader/.cookies.json")