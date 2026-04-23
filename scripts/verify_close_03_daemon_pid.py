"""CLOSE-03 operator CLI: launch daemon + API, capture PID + netstat evidence.

Usage (POSIX):
    python scripts/verify_close_03_daemon_pid.py

Usage (Windows):
    python scripts\\verify_close_03_daemon_pid.py

This script:
  1. Spawns uvicorn api.app:app --host 127.0.0.1 --port 8000 as a subprocess
  2. Spawns the daemon as a subprocess (which writes data/daemon.pid)
  3. Captures ``netstat -an`` output filtered for port 8000
  4. Prints the evidence block: PID file path+content, netstat output, dates
  5. Terminates both subprocesses

Operator must run this manually -- spinning up ports is a real side effect.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def _capture_netstat_port_8000() -> str:
    """Return netstat output filtered for port 8000 (cross-platform)."""
    if not shutil.which("netstat"):
        return "netstat not on PATH -- install or use psutil fallback"
    try:
        result = subprocess.run(
            ["netstat", "-an"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        lines = [ln for ln in result.stdout.splitlines() if ":8000" in ln]
        return "\n".join(lines) or "(no :8000 lines in netstat output)"
    except Exception as exc:
        return f"netstat error: {exc}"


def main() -> int:
    pid_file = Path("data/daemon.pid")
    ts = datetime.now(timezone.utc).isoformat()

    # 1. Launch uvicorn
    uvicorn_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api.app:app",
         "--host", "127.0.0.1", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Give uvicorn 3 seconds to bind
    time.sleep(3)

    # 2. Launch daemon (long-running; write PID and hold)
    daemon_proc = subprocess.Popen(
        [sys.executable, "-m", "daemon.scheduler"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Give daemon 3 seconds to write PID file
    time.sleep(3)

    try:
        # 3. Capture evidence
        pid_content = pid_file.read_text().strip() if pid_file.exists() else "(missing)"
        netstat_out = _capture_netstat_port_8000()

        print("=" * 70)
        print(f"CLOSE-03 EVIDENCE  ({ts})")
        print(f"  platform:         {platform.platform()}")
        print(f"  data/daemon.pid:  {pid_content}")
        print(f"  daemon subprocess.pid: {daemon_proc.pid}")
        print(f"  pid_file_matches_proc: {pid_content == str(daemon_proc.pid)}")
        print(f"  netstat :8000 lines:")
        for ln in netstat_out.splitlines():
            print(f"    {ln}")
        print("=" * 70)
    finally:
        # 4. Terminate both subprocesses
        try:
            daemon_proc.terminate()
            daemon_proc.wait(timeout=5)
        except Exception:
            daemon_proc.kill()
        try:
            uvicorn_proc.terminate()
            uvicorn_proc.wait(timeout=5)
        except Exception:
            uvicorn_proc.kill()

    # 5. Verify cleanup (atexit may need a moment)
    time.sleep(1)
    pid_after = pid_file.read_text().strip() if pid_file.exists() else "(cleaned up)"
    print(f"After daemon stop -- data/daemon.pid: {pid_after}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
