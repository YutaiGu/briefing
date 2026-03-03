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


def _run_server(port: int) -> None:
    """Start uvicorn in the calling thread (blocking call)."""
    import uvicorn
    uvicorn.run(
        "backend.app.main:app",
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )


def _run_worker() -> None:
    """Run the background processing loop (download / transcribe / push)."""
    from main import main as worker_main
    worker_main()


def main() -> None:
    # Must be the first call in the __main__ guard on Windows.
    # freeze_support() intercepts the special arguments that multiprocessing.spawn
    # passes to child processes and prevents them from re-running the full launcher.
    multiprocessing.freeze_support()

    if "--worker" in sys.argv:
        _run_worker()
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
    window = webview.create_window(
        "Briefing",
        f"http://127.0.0.1:{port}",
        min_size=(800, 600),
    )
    # Blocks until the window is closed; daemon server thread exits with the process.
    webview.start()
    sys.exit(0)


if __name__ == "__main__":
    main()
