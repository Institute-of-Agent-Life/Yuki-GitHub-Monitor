"""Standalone doctor configuration and read-only diagnostics."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from github_monitor.doctor import inspect_database


def _doctor(*arguments: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run(
        [sys.executable, "doctor.py", *arguments],
        cwd=Path(__file__).parents[1],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_help_and_runtime_import_do_not_load_private_host():
    result = _doctor("--help")
    assert result.returncode == 0
    assert "--database-url" in result.stdout
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import github_monitor.doctor; "
            "assert not any(n == 'yuki' or n.startswith('yuki.') for n in sys.modules)",
        ],
        cwd=Path(__file__).parents[1],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_explicit_missing_database_does_not_create_file(tmp_path):
    path = tmp_path / "does-not-exist.db"
    result = _doctor("--database-url", f"sqlite+aiosqlite:///{path.as_posix()}")
    assert result.returncode == 1
    assert json.loads(result.stdout) == {"ok": False, "error_category": "ValueError"}
    assert not path.exists()


def test_report_checks_explicit_database_without_writing(tmp_path):
    path = tmp_path / "stopped-host.db"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE plugin_state (
                plugin_id TEXT, namespace TEXT, key TEXT, value_json TEXT, expires_at TEXT
            );
            CREATE TABLE plugin_notification_outbox (
                plugin_id TEXT, last_error_category TEXT, status TEXT
            );
            CREATE TABLE plugin_background_turn_jobs (
                plugin_id TEXT, last_error_category TEXT, status TEXT
            );
            """
        )
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    url = f"sqlite+aiosqlite:///{path.as_posix()}"
    report = inspect_database(url)
    assert report.ok and report.mode == "check" and report.queue_count == 0
    result = _doctor("--database-url", url)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["ok"] is True
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
