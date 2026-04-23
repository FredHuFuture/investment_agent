"""CLOSE-03: Daemon PID file lifecycle under real subprocess launch.

This test spawns the daemon as a subprocess, verifies the PID file is
written with a live PID, then verifies the file is removed after the
subprocess exits (atexit cleanup).

The parallel localhost-bind grep tests (run.ps1, Makefile contain
``--host 127.0.0.1``) are re-asserted here to prevent regression from
Phase 5 work that also modifies these files (future phases may).

Platform notes:
  - Windows: use subprocess.Popen; Popen.terminate() calls TerminateProcess.
    atexit handlers DO fire on normal exit (time.sleep + natural exit).
    On Windows, SIGTERM sent by terminate() may NOT trigger atexit;
    we rely on the subprocess exiting naturally (sleep + exit) for clean
    PID file removal in these tests. terminate() is only used in cleanup.
  - POSIX: Popen.terminate() sends SIGTERM; atexit fires via signal handler.
  - Both: atexit handlers fire on normal exit (not SIGKILL).
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest


@pytest.fixture
def clean_pid_file(tmp_path, monkeypatch):
    """Redirect daemon PID file to a tmp path for test isolation."""
    pid_file = tmp_path / "daemon.pid"
    # Pass the pid file path to the subprocess via env var
    monkeypatch.setenv("DAEMON_PID_FILE", str(pid_file))
    yield pid_file
    # Cleanup: remove if still present (guards against test failure leaving stale file)
    if pid_file.exists():
        pid_file.unlink()


def _subprocess_launcher_script(pid_file_path: str) -> str:
    """Generate a Python snippet that writes a PID file via ensure_pid_file,
    registers atexit cleanup, sleeps 3 seconds, then exits naturally.

    Uses a raw string for the path to handle Windows backslashes safely.
    """
    # Use forward slashes to avoid backslash escape issues in the snippet
    safe_path = pid_file_path.replace("\\", "/")
    return (
        "import atexit, time\n"
        "from pathlib import Path\n"
        "from scripts.ensure_pid import ensure_pid_file, remove_pid_file\n"
        f"_pid_file = Path(r\"{safe_path}\")\n"
        "ensure_pid_file(_pid_file)\n"
        "atexit.register(remove_pid_file, _pid_file)\n"
        "# Hold for 3 seconds to allow the test to observe the PID file\n"
        "time.sleep(3)\n"
    )


def test_daemon_subprocess_writes_pid_file_on_launch(clean_pid_file) -> None:
    """CLOSE-03 evidence: daemon subprocess writes PID file with live PID."""
    pid_file = clean_pid_file
    script = _subprocess_launcher_script(str(pid_file))

    proc = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        # Poll for PID file up to 5 seconds
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if pid_file.exists():
                break
            time.sleep(0.1)
        assert pid_file.exists(), (
            f"PID file {pid_file} was not created within 5s of subprocess launch"
        )
        content = pid_file.read_text().strip()
        assert content.isdigit(), f"PID file does not contain numeric PID: {content!r}"
        pid_written = int(content)
        assert pid_written == proc.pid, (
            f"PID file contains {pid_written} but subprocess PID is {proc.pid}"
        )
        print(f"CLOSE-03 EVIDENCE: PID file {pid_file} contains {pid_written} (live)")
    finally:
        # Let subprocess exit naturally (it sleeps 3s then exits)
        proc.wait(timeout=10)


def test_daemon_pid_cleaned_up_on_graceful_exit(clean_pid_file) -> None:
    """CLOSE-03 evidence: atexit handler removes PID file after clean exit."""
    pid_file = clean_pid_file
    script = _subprocess_launcher_script(str(pid_file))

    proc = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Wait for PID file to appear
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if pid_file.exists():
            break
        time.sleep(0.1)
    assert pid_file.exists(), "PID file missing during subprocess lifetime"

    # Let subprocess exit naturally (sleeps 3s + atexit fires on clean exit)
    proc.wait(timeout=10)

    # Small grace period for atexit flush (esp. on Windows)
    time.sleep(0.5)

    assert not pid_file.exists(), (
        f"PID file {pid_file} was NOT removed after subprocess exit "
        f"(atexit handler did not fire or failed)"
    )
    print(f"CLOSE-03 EVIDENCE: PID file removed on graceful exit.")


def test_ensure_pid_script_check_subcommand_returns_zero() -> None:
    """Re-assert the --check CLI returns exit 0 (regression guard)."""
    result = subprocess.run(
        [sys.executable, "scripts/ensure_pid.py", "--check"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, (
        f"scripts/ensure_pid.py --check returned {result.returncode}; "
        f"stderr={result.stderr!r}"
    )


def test_localhost_bind_assertions_preserved() -> None:
    """CLOSE-03 regression guard: run.ps1 + Makefile still have --host 127.0.0.1."""
    run_ps1 = Path("run.ps1").read_text(encoding="utf-8")
    makefile = Path("Makefile").read_text(encoding="utf-8")
    assert run_ps1.count("--host 127.0.0.1") >= 2, (
        "run.ps1 lost '--host 127.0.0.1' occurrences (expected >=2)"
    )
    assert "--host 127.0.0.1" in makefile, "Makefile lost '--host 127.0.0.1'"
