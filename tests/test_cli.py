"""Tests for the CLI entry point (argparse wiring + a few calls)."""

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent


def _run(args: list[str], **env) -> subprocess.CompletedProcess:
    import os
    env_full = os.environ.copy()
    if env:
        env_full.update(env)
    return subprocess.run(
        [sys.executable, "-m", "hve", *args],
        capture_output=True,
        text=True,
        timeout=30,
        env=env_full,
        cwd=REPO,
    )


def test_version():
    p = _run(["--version"])
    assert p.returncode == 0
    assert "hve" in p.stdout


def test_help_lists_commands():
    p = _run(["--help"])
    assert p.returncode == 0
    for word in ("init", "status", "report", "health", "agent", "db"):
        assert word in p.stdout


def test_init_and_status(tmp_path):
    env = {
        "HVE_HOME": str(tmp_path / "hve-home"),
        "HVE_DB_PATH": str(tmp_path / "hve-home" / "data" / "hve.db"),
        "HVE_KNOWLEDGE_DIR": str(tmp_path / "hve-home" / "knowledge"),
        "HVE_REPORTS_DIR": str(tmp_path / "hve-home" / "reports"),
        "HVE_BACKUPS_DIR": str(tmp_path / "hve-home" / "backups"),
    }
    p = _run(["init"], **env)
    assert p.returncode == 0
    p = _run(["status"], **env)
    assert p.returncode == 0
    p = _run(["status", "--json"], **env)
    assert p.returncode in (0, 2)  # health may warn if the model endpoint is absent
