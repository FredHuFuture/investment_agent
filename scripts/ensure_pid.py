"""Daemon PID file management (DATA-05).

Usage (standalone):
    python scripts/ensure_pid.py --check            # print status and exit 0
    python scripts/ensure_pid.py --remove-stale     # cleanup if daemon crashed
    python scripts/ensure_pid.py --path data/daemon.pid --check

Used by daemon/scheduler.py on startup to detect and handle stale PIDs.

Stale-PID detection uses ``os.kill(pid, 0)`` -- cross-platform on Python 3.11+:
  - POSIX: raises ProcessLookupError (errno ESRCH) if process not found.
  - Windows: raises OSError with winerror 87 (ERROR_INVALID_PARAMETER) if PID gone.
"""
from __future__ import annotations

import argparse
import errno
import os
import sys
from pathlib import Path
from typing import Literal

DEFAULT_PID_PATH = Path("data/daemon.pid")


def _process_alive(pid: int) -> bool:
    """Return True if a process with ``pid`` is currently running.

    Uses ``os.kill(pid, 0)`` which is supported on Windows (Python 3.9+)
    and all POSIX platforms. Signal 0 does not actually send a signal;
    it only checks whether the process exists and we have permission.
    """
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError as exc:
        # ESRCH = no such process (POSIX + Windows)
        if exc.errno == errno.ESRCH:
            return False
        # Windows: ERROR_INVALID_PARAMETER (winerror 87) means PID does not exist
        if sys.platform == "win32" and getattr(exc, "winerror", None) == 87:
            return False
        # PermissionError / EPERM: process exists, we just can't signal it
        return True
    return True


def check_pid_file(
    path: Path = DEFAULT_PID_PATH,
) -> tuple[Literal["ok", "stale", "missing"], int | None]:
    """Inspect a PID file and classify its state.

    Returns:
        ("missing", None)   -- file does not exist
        ("stale",   pid)    -- file exists but PID is not a live process
        ("ok",      pid)    -- file exists and PID maps to a running process
    """
    if not path.exists():
        return ("missing", None)
    try:
        pid = int(path.read_text().strip())
    except (ValueError, OSError):
        return ("stale", None)
    if _process_alive(pid):
        return ("ok", pid)
    return ("stale", pid)


def ensure_pid_file(path: Path = DEFAULT_PID_PATH) -> int:
    """Write the current process PID to ``path``.

    - If ``path`` refers to a live process: raises ``RuntimeError``.
    - If ``path`` contains a stale PID: overwrites it.
    - If ``path`` is missing: creates it (including parent directories).

    Returns:
        The PID written (``os.getpid()``).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    state, existing_pid = check_pid_file(path)
    if state == "ok":
        raise RuntimeError(
            f"Daemon already running (pid={existing_pid}, file={path})"
        )
    my_pid = os.getpid()
    path.write_text(str(my_pid))
    return my_pid


def remove_pid_file(path: Path = DEFAULT_PID_PATH) -> bool:
    """Remove the PID file if it exists.

    Returns:
        True if removed, False if file was already absent or removal failed.
    """
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def _main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect or clean up the daemon PID file."
    )
    parser.add_argument(
        "--path",
        default=str(DEFAULT_PID_PATH),
        help="Path to the PID file (default: data/daemon.pid)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Print PID file state and exit 0.",
    )
    parser.add_argument(
        "--remove-stale",
        action="store_true",
        help="Remove the PID file if it contains a stale PID.",
    )
    args = parser.parse_args()
    p = Path(args.path)
    state, pid = check_pid_file(p)
    print(f"pid_file={p} state={state} pid={pid}")
    if args.remove_stale and state == "stale":
        removed = remove_pid_file(p)
        if removed:
            print("removed stale pid file")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
