# Runtime hook: redirect tiktoken's model cache to a writable directory
# when running as a frozen PyInstaller executable.
# Without this, tiktoken tries to write to the read-only _MEIPASS temp dir.
# Must match config.BASE_DIR: on macOS the cache must NOT go inside the .app
# bundle, or writing to it breaks the code signature ("damaged" on launch).
import os
import sys
from pathlib import Path

if getattr(sys, 'frozen', False):
    if sys.platform == 'darwin':
        base = Path.home() / "Library" / "Application Support" / "Briefing"
    else:
        base = Path(sys.executable).parent
    cache = base / "data" / ".tiktoken_cache"
    cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("TIKTOKEN_CACHE_DIR", str(cache))
