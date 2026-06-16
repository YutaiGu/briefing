"""
Entry point for briefing.exe (PyInstaller build) and direct execution.

Two modes:
  briefing.exe           -- server mode: starts FastAPI + opens a pywebview window.
                            Closing the window exits the process.
  briefing.exe --worker  -- worker mode: runs the background processing loop.
                            Called by runner.py; not meant to be invoked manually.
"""

import multiprocessing
import os
import socket
import sys
import threading
import time

# In dev (not frozen), make the src-layout package importable without install.
if not getattr(sys, "frozen", False):
    _SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
    if _SRC not in sys.path:
        sys.path.insert(0, _SRC)


def _find_free_port() -> int:
    """Ask the OS for an available port by binding to port 0."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_server(port: int, timeout: float = 30.0) -> bool:
    """Poll until the local uvicorn server accepts connections."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def _run_server(port: int, host: str = "127.0.0.1") -> None:
    """Start uvicorn in the calling thread (blocking call)."""
    import uvicorn
    uvicorn.run(
        "briefing.web.app.main:app",
        host=host,
        port=port,
        log_level="warning",
    )


def _run_worker() -> None:
    """Run the background processing loop (download / transcribe / push)."""
    import os
    import socket
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(line_buffering=True)
        except Exception:
            pass
    try:
        with socket.create_connection(("huggingface.co", 443), timeout=6):
            pass
    except OSError:
        os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    from briefing.worker import main as worker_main
    worker_main()


def main() -> None:
    # Must be the first call in the __main__ guard on Windows.
    # freeze_support() intercepts the special arguments that multiprocessing.spawn
    # passes to child processes and prevents them from re-running the full launcher.
    multiprocessing.freeze_support()

    if "--worker" in sys.argv:
        _run_worker()
        return

    if "--server" in sys.argv:
        os.environ["AUTO_OPEN_BROWSER"] = "0"
        _run_server(8000, host="0.0.0.0")
        return

    # --- server mode ---
    port = _find_free_port()

    # Disable FastAPI's built-in browser-open; pywebview creates the window instead.
    os.environ["AUTO_OPEN_BROWSER"] = "0"

    server_thread = threading.Thread(target=_run_server, args=(port,), daemon=True)
    server_thread.start()

    if not _wait_for_server(port):
        print("ERROR: server did not start within 30 seconds.", file=sys.stderr)
        sys.exit(1)

    import webview

    class _JsApi:
        def export_backup(self):
            try:
                from briefing.web.app.runner import runner
                if runner.is_running():
                    return {"error": "Stop the worker before exporting."}
            except Exception:
                pass
            from datetime import datetime
            from pathlib import Path
            from briefing.migration import export_bytes
            window = webview.active_window()
            save_mode = getattr(getattr(webview, "FileDialog", None), "SAVE", None) or webview.SAVE_DIALOG
            result = window.create_file_dialog(
                save_mode,
                save_filename=f"briefing-backup-{datetime.now():%Y%m%d-%H%M%S}.zip",
                file_types=("Zip archive (*.zip)",),
            )
            if not result:
                return {"cancelled": True}
            path = result if isinstance(result, str) else result[0]
            Path(path).write_bytes(export_bytes())
            return {"path": path}

    api = _JsApi()
    webview.create_window(
        "Briefing",
        f"http://127.0.0.1:{port}",
        width=1440,
        height=960,
        min_size=(900, 600),
        js_api=api,
    )
    # Blocks until the window is closed; daemon server thread exits with the process.
    # EdgeChromium is Windows-only; on macOS/Linux let pywebview pick the native backend.
    if sys.platform == "win32":
        webview.start(gui="edgechromium")
    else:
        webview.start()
    sys.exit(0)


if __name__ == "__main__":
    main()
