"""Tests for DATA-05: Daemon PID file management + localhost-only uvicorn bind.

Tests:
  - check_pid_file: missing / stale / ok states
  - ensure_pid_file: write current PID, raise on live PID, overwrite stale
  - remove_pid_file: idempotent removal
  - run.ps1 and Makefile contain --host 127.0.0.1
  - CLI script exit codes
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# check_pid_file
# ---------------------------------------------------------------------------


class TestCheckPidFile:
    def test_check_pid_file_missing(self, tmp_path):
        """File does not exist -> ('missing', None)."""
        from scripts.ensure_pid import check_pid_file
        pid_file = tmp_path / "daemon.pid"
        state, pid = check_pid_file(pid_file)
        assert state == "missing"
        assert pid is None

    def test_check_pid_file_stale_dead_pid(self, tmp_path):
        """File contains a guaranteed-dead PID -> ('stale', <pid>)."""
        from scripts.ensure_pid import check_pid_file
        pid_file = tmp_path / "daemon.pid"
        # PID 9999999 is virtually guaranteed not to exist on any system
        pid_file.write_text("9999999")
        state, pid = check_pid_file(pid_file)
        assert state == "stale"
        assert pid == 9_999_999

    def test_check_pid_file_ok_current_process(self, tmp_path):
        """File contains our own PID -> ('ok', <pid>)."""
        from scripts.ensure_pid import check_pid_file
        pid_file = tmp_path / "daemon.pid"
        pid_file.write_text(str(os.getpid()))
        state, pid = check_pid_file(pid_file)
        assert state == "ok"
        assert pid == os.getpid()


# ---------------------------------------------------------------------------
# ensure_pid_file
# ---------------------------------------------------------------------------


class TestEnsurePidFile:
    def test_ensure_pid_file_raises_when_live(self, tmp_path):
        """File with live PID -> RuntimeError('Daemon already running')."""
        from scripts.ensure_pid import ensure_pid_file
        pid_file = tmp_path / "daemon.pid"
        # Current process is definitely live
        pid_file.write_text(str(os.getpid()))
        with pytest.raises(RuntimeError, match="Daemon already running"):
            ensure_pid_file(pid_file)

    def test_ensure_pid_file_overwrites_stale(self, tmp_path):
        """File with dead PID -> overwritten with our PID, returns our PID."""
        from scripts.ensure_pid import ensure_pid_file
        pid_file = tmp_path / "daemon.pid"
        pid_file.write_text("9999999")
        result = ensure_pid_file(pid_file)
        assert result == os.getpid()
        assert pid_file.read_text().strip() == str(os.getpid())

    def test_ensure_pid_file_creates_missing(self, tmp_path):
        """No file -> creates it with our PID."""
        from scripts.ensure_pid import ensure_pid_file
        pid_file = tmp_path / "daemon.pid"
        result = ensure_pid_file(pid_file)
        assert result == os.getpid()
        assert pid_file.exists()
        assert pid_file.read_text().strip() == str(os.getpid())


# ---------------------------------------------------------------------------
# remove_pid_file
# ---------------------------------------------------------------------------


class TestRemovePidFile:
    def test_remove_pid_file_missing_ok(self, tmp_path):
        """File absent -> returns False without raising."""
        from scripts.ensure_pid import remove_pid_file
        pid_file = tmp_path / "daemon.pid"
        result = remove_pid_file(pid_file)
        assert result is False

    def test_remove_pid_file_present(self, tmp_path):
        """File present -> removes it, returns True."""
        from scripts.ensure_pid import remove_pid_file
        pid_file = tmp_path / "daemon.pid"
        pid_file.write_text("12345")
        result = remove_pid_file(pid_file)
        assert result is True
        assert not pid_file.exists()


# ---------------------------------------------------------------------------
# localhost bind verification (grep run.ps1 + Makefile)
# ---------------------------------------------------------------------------


class TestLocalhostBind:
    def test_run_ps1_has_localhost_bind(self):
        """run.ps1 must contain --host 127.0.0.1 on uvicorn invocation lines."""
        content = Path("run.ps1").read_text(encoding="utf-8")
        occurrences = content.count("--host 127.0.0.1")
        assert occurrences >= 2, (
            f"Expected >= 2 occurrences of '--host 127.0.0.1' in run.ps1, "
            f"found {occurrences}"
        )

    def test_makefile_run_backend_has_localhost_bind(self):
        """Makefile run-backend target must contain --host 127.0.0.1."""
        content = Path("Makefile").read_text(encoding="utf-8")
        assert "--host 127.0.0.1" in content, (
            "Makefile run-backend target missing '--host 127.0.0.1'"
        )


# ---------------------------------------------------------------------------
# CLI script
# ---------------------------------------------------------------------------


class TestEnsurePidCli:
    def test_ensure_pid_script_cli_check(self, tmp_path):
        """python scripts/ensure_pid.py --check exits 0."""
        result = subprocess.run(
            [sys.executable, "scripts/ensure_pid.py", "--check"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_ensure_pid_script_cli_remove_stale(self, tmp_path):
        """--remove-stale removes a stale PID file and exits 0."""
        # Write stale PID file to a temp path; use --path to target it
        pid_file = tmp_path / "daemon.pid"
        pid_file.write_text("9999999")
        result = subprocess.run(
            [
                sys.executable,
                "scripts/ensure_pid.py",
                "--check",
                "--remove-stale",
                "--path",
                str(pid_file),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert not pid_file.exists(), "Stale PID file should have been removed"
