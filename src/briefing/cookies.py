"""Export browser cookies, one file per browser, and pick one browser per site.

Content behind a login (Douyin / Bilibili homepages) needs the cookies of a
logged-in browser. Log into the site in any installed browser, then run:

    python cookies.py                  # try all known browsers
    python cookies.py chrome firefox   # restrict to specific browsers

Each readable browser is saved to data/cookies/<browser>.txt. Cookies are never
mixed across browsers: a site is served from a single browser, and requests
carry that browser's User-Agent, so the cookies and the headers tell the same
story (Douyin rejects Firefox cookies sent with a Chrome UA).
"""
import sys
from dataclasses import dataclass
from http.cookiejar import Cookie, MozillaCookieJar
from urllib.parse import urlparse

from yt_dlp import YoutubeDL

from briefing.config import COOKIES_DIR, DATA_DIR

# Ordered by how common they are; unknown/uninstalled ones are skipped.
# Also the tie-break when several browsers are logged into the same site.
ALL_BROWSERS = ["safari", "edge", "firefox", "chrome"]

# A browser holding one of these (unexpired) is considered logged in to the site.
LOGIN_COOKIES = {
    "douyin.com": {"sessionid", "sessionid_ss", "sid_guard"},
    "bilibili.com": {"SESSDATA"},
    "youtube.com": {"SID", "__Secure-3PSID"},
}
SITE_ALIASES = {"b23.tv": "bilibili.com", "youtu.be": "youtube.com"}

_LEGACY_TXT = DATA_DIR / "cookies.txt"   # merged file from older versions


class _SilentLogger:
    """Swallow yt-dlp's stderr noise for browsers that aren't installed."""
    def debug(self, msg): pass
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass


# --------------------------------------------------------------------------- #
# browser profiles: UA + the fields Douyin's web API reports about the browser
# --------------------------------------------------------------------------- #
_VERSIONS = {"chrome": "140.0.0.0", "edge": "140.0.0.0", "firefox": "143.0", "safari": "18.5"}
_OS = {  # sys.platform prefix -> (UA token, os_name, os_version, navigator.platform)
    "win": ("Windows NT 10.0; Win64; x64", "Windows", "10", "Win32"),
    "darwin": ("Macintosh; Intel Mac OS X 10_15_7", "Mac OS", "10.15.7", "MacIntel"),
    "linux": ("X11; Linux x86_64", "Linux", "", "Linux x86_64"),
}


def browser_profile(browser: str) -> dict:
    os_key = next((k for k in _OS if sys.platform.startswith(k)), "linux")
    token, os_name, os_version, platform = _OS[os_key]
    version = _VERSIONS[browser]
    if browser == "firefox":
        token = token.replace("10_15_7", "10.15")
        ua = f"Mozilla/5.0 ({token}; rv:{version}) Gecko/20100101 Firefox/{version}"
        name, engine, engine_version = "Firefox", "Gecko", version
    elif browser == "safari":
        ua = (f"Mozilla/5.0 ({token}) AppleWebKit/605.1.15 (KHTML, like Gecko) "
              f"Version/{version} Safari/605.1.15")
        name, engine, engine_version = "Safari", "WebKit", "605.1.15"
    else:
        ua = f"Mozilla/5.0 ({token}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{version} Safari/537.36"
        if browser == "edge":
            ua += f" Edg/{version}"
        name, engine, engine_version = browser.capitalize(), "Blink", version
    return {
        "user_agent": ua,
        "browser_name": name,
        "browser_version": version,
        "browser_platform": platform,
        "engine_name": engine,
        "engine_version": engine_version,
        "os_name": os_name,
        "os_version": os_version,
    }


# --------------------------------------------------------------------------- #
# export
# --------------------------------------------------------------------------- #
def create_cookies_txt(browsers: list[str] | None = None) -> None:
    browsers = browsers or ALL_BROWSERS
    COOKIES_DIR.mkdir(parents=True, exist_ok=True)
    _LEGACY_TXT.unlink(missing_ok=True)

    report = []
    for b in browsers:
        path = COOKIES_DIR / f"{b}.txt"
        try:
            with YoutubeDL({
                "cookiesfrombrowser": (b,),
                "quiet": True,
                "no_warnings": True,
                "logger": _SilentLogger(),
            }) as ydl:
                jar = MozillaCookieJar(str(path))
                for c in ydl.cookiejar:  # lazily extracts on access
                    jar.set_cookie(c)
            jar.save(ignore_discard=True, ignore_expires=True)
            logged = [site for site in LOGIN_COOKIES if _logged_in(_site_cookies(jar, site), site)]
            report.append(f"  {b:9s} ok   total={len(jar):<5d} logged_in={','.join(logged) or '-'}")
        except Exception as e:
            path.unlink(missing_ok=True)  # uninstalled / unreadable now: drop stale cookies
            report.append(f"  {b:9s} skip {type(e).__name__}: {e}")

    print("[cookies]")
    print("\n".join(report))
    print(f"Saved cookies to {COOKIES_DIR}\n")


# --------------------------------------------------------------------------- #
# per-site session
# --------------------------------------------------------------------------- #
@dataclass
class Session:
    site: str
    browser: str
    cookies: list[Cookie]
    profile: dict

    @property
    def user_agent(self) -> str:
        return self.profile["user_agent"]

    @property
    def cookie_header(self) -> str:
        return "; ".join(f"{c.name}={c.value}" for c in self.cookies)

    @property
    def logged_in(self) -> bool:
        return _logged_in(self.cookies, self.site)


def site_of(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    host = SITE_ALIASES.get(host, host)
    return ".".join(host.split(".")[-2:])


def _site_cookies(jar, site: str) -> list[Cookie]:
    return [c for c in jar if (c.domain or "").lstrip(".") == site
            or (c.domain or "").endswith("." + site)]


def _logged_in(cookies: list[Cookie], site: str) -> bool:
    names = LOGIN_COOKIES.get(site, set())
    return any(c.name in names and not c.is_expired() for c in cookies)


def session_for(url: str) -> Session | None:
    """Cookies of a single browser for the url's site, preferring a logged-in one.
    None when no exported browser has any cookie for the site."""
    site = site_of(url)
    best = None
    for rank, b in enumerate(ALL_BROWSERS):
        path = COOKIES_DIR / f"{b}.txt"
        if not path.exists():
            continue
        jar = MozillaCookieJar()
        try:
            jar.load(str(path), ignore_discard=True, ignore_expires=True)
        except Exception:
            continue
        cookies = _site_cookies(jar, site)
        if not cookies:
            continue
        key = (not _logged_in(cookies, site), rank)
        if best is None or key < best[0]:
            best = (key, b, cookies)
    if best is None:
        return None
    _, b, cookies = best
    return Session(site=site, browser=b, cookies=cookies, profile=browser_profile(b))


if __name__ == "__main__":
    args = sys.argv[1:]
    create_cookies_txt(args or None)
