import subprocess
import sys
import signal
import os
from pathlib import Path
from typing import Optional

# Frozen-aware: logs and pid live in backend/data/ alongside the exe.
if getattr(sys, 'frozen', False):
    DATA_DIR = Path(sys.executable).resolve().parent / "backend" / "data"
else:
    DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LOG_PATH = DATA_DIR / "run.log"
PID_PATH = DATA_DIR / "run.pid"


class Runner:
    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        LOG_PATH.touch(exist_ok=True)
        self.process: Optional[subprocess.Popen] = None
        self._restore_if_running()

    def _restore_if_running(self):
        if PID_PATH.exists():
            try:
                int(PID_PATH.read_text().strip())
            except ValueError:
                PID_PATH.unlink(missing_ok=True)

    def is_running(self) -> bool:
        if self.process and self.process.poll() is None:
            return True
        if PID_PATH.exists():
            try:
                pid = int(PID_PATH.read_text().strip())
                if sys.platform != "win32":
                    os.kill(pid, 0)
                return True
            except Exception:
                PID_PATH.unlink(missing_ok=True)
        return False

    def start(self, main_script: Path) -> Optional[int]:
        if self.is_running():
            return None
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        log_file = LOG_PATH.open("a", buffering=1, encoding="utf-8")
        if getattr(sys, 'frozen', False):
            # Re-invoke the frozen exe in worker mode; main.py doesn't exist separately.
            cmd      = [sys.executable, "--worker"]
            work_dir = Path(sys.executable).resolve().parent
        else:
            cmd      = [sys.executable, "-u", str(main_script)]
            work_dir = main_script.parent
        proc = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            cwd=str(work_dir),
        )
        PID_PATH.write_text(str(proc.pid))
        self.process = proc
        return proc.pid

    def stop(self) -> bool:
        if not self.is_running():
            PID_PATH.unlink(missing_ok=True)
            return False
        try:
            if self.process and self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
            elif PID_PATH.exists():
                pid = int(PID_PATH.read_text().strip())
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/PID", str(pid), "/F"], check=False)
                else:
                    os.kill(pid, signal.SIGTERM)
        finally:
            PID_PATH.unlink(missing_ok=True)
            self.process = None
        return True

    def tail_log(self, limit: int = 2000) -> str:
        LOG_PATH.touch(exist_ok=True)
        data = LOG_PATH.read_bytes()
        return data[-limit:].decode("utf-8", errors="replace")

    def clear_log(self):
        LOG_PATH.write_text("", encoding="utf-8")

    def status(self):
        pid = None
        if self.process and self.process.poll() is None:
            pid = self.process.pid
        elif PID_PATH.exists():
            try:
                pid = int(PID_PATH.read_text())
            except Exception:
                pid = None
        return {"running": self.is_running(), "pid": pid}


runner = Runner()
