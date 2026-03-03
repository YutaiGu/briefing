# Runtime hook: redirect tiktoken's model cache to a writable directory
# when running as a frozen PyInstaller executable.
# Without this, tiktoken tries to write to the read-only _MEIPASS temp dir.
import os
import sys
from pathlib import Path

if getattr(sys, 'frozen', False):
    cache = Path(sys.executable).parent / "data" / ".tiktoken_cache"
    cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("TIKTOKEN_CACHE_DIR", str(cache))
