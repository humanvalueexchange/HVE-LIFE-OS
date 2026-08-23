"""Tests for the `hve agent ask` path (D4=A).

The HVE app does not depend on the Hermes SDK: it shells out to the
``hermes`` binary and captures stdout. These tests cover:

* binary-not-found raises :class:`hve.agent.ask.AgentError`
* a *stub* hermes binary on PATH is invoked with the right argv
* the interaction is logged
* a failing exit code is surfaced
"""

import json
import os
import stat
import subprocess
import textwrap
import time
from pathlib import Path

import pytest

from hve.agent import ask as agent_ask
from hve.db import ensure_schema


def test_missing_binary_raises(cfg, monkeypatch):
    monkeypatch.setenv("HVE_HERMES_BIN", "/nonexistent/hermes")
    with pytest.raises(agent_ask.AgentError, match="not found"):
        agent_ask.ask(cfg, "ping")


def test_successful_invocation_logs_interaction(cfg, seeded, tmp_path, monkeypatch):
    # Build a stub hermes executable that prints a fixed response.
    stub = tmp_path / "hermes-stub"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        "echo 'pong'\n"
        "exit 0\n"
    )
    stub.chmod(0o755)
    monkeypatch.setenv("HVE_HERMES_BIN", str(stub))

    res = agent_ask.ask(seeded, "ping")
    assert res.response == "pong"
    assert "Hermes" not in res.response
    # The interaction was logged.
    records = agent_ask.recent(seeded, n=5)
    assert any(r["prompt"] == "ping" for r in records)


def test_failing_exit_raises(cfg, seeded, tmp_path, monkeypatch):
    stub = tmp_path / "hermes-stub-fail"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        "echo 'boom' >&2\n"
        "exit 3\n"
    )
    stub.chmod(0o755)
    monkeypatch.setenv("HVE_HERMES_BIN", str(stub))
    with pytest.raises(agent_ask.AgentError, match="exited 3"):
        agent_ask.ask(seeded, "ping")


def test_timeout_raises(cfg, seeded, tmp_path, monkeypatch):
    stub = tmp_path / "hermes-stub-sleep"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        "sleep 30\n"
    )
    stub.chmod(0o755)
    monkeypatch.setenv("HVE_HERMES_BIN", str(stub))
    with pytest.raises(agent_ask.AgentError, match="timed out"):
        agent_ask.ask(seeded, "ping", timeout_s=1)


def test_argv_matches_verified_contract(seeded, monkeypatch, capsys, tmp_path):
    """Task item 3: pin the EXACT argv the module passes to subprocess.

    The Mercury CLI (Hermes v0.20.5, read-only inspection) exposes:
        hermes chat -q "<prompt>" -s hve-life-os -Q
    `hermes send` is the messaging command and is NOT the right tool
    for running a prompted agent.

    We mock subprocess.run to capture argv without executing anything,
    so this test is deterministic and does not depend on a live Hermes.
    """
    fake_bin = tmp_path / "fake-hermes"
    fake_bin.write_text("#!/bin/sh\nexit 0\n")
    fake_bin.chmod(0o755)

    called = {}

    class FakeProc:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_run(cmd, **kwargs):
        called["argv"] = list(cmd)
        return FakeProc()

    monkeypatch.setattr(agent_ask.subprocess, "run", fake_run)
    monkeypatch.setenv("HVE_HERMES_BIN", str(fake_bin))

    res = agent_ask.ask(seeded, "how are you?", timeout_s=5)
    assert called, "subprocess.run was not called"
    argv = called["argv"]

    # argv[0] is the fake binary; argv[1] must be "chat" (NOT "send").
    assert argv[1] == "chat"
    # Prompt is the value after -q.
    assert "-q" in argv and "how are you?" in argv
    # hve-life-os skill is preloaded.
    assert "-s" in argv and "hve-life-os" in argv
    # -Q (quiet) must appear so output is a single response.
    assert "-Q" in argv

    # The call succeeded and the audit row was written (task item 2).
    assert res.response == "ok"
    rows = agent_ask.recent(seeded, n=5)
    assert any(r["prompt"] == "how are you?" for r in rows)


def test_audit_row_written_on_success(seeded, monkeypatch, tmp_path):
    """Task item 2: successful calls MUST write an interactions row."""
    fake_bin = tmp_path / "fake-hermes"
    fake_bin.write_text("#!/bin/sh\nexit 0\n")
    fake_bin.chmod(0o755)

    class FakeProc:
        returncode = 0
        stdout = "pong"
        stderr = ""
    monkeypatch.setattr(agent_ask.subprocess, "run", lambda *a, **kw: FakeProc())
    monkeypatch.setenv("HVE_HERMES_BIN", str(fake_bin))
    agent_ask.ask(seeded, "hello", timeout_s=5)
    rows = agent_ask.recent(seeded, n=5)
    assert any(r["prompt"] == "hello" and r["response"] == "pong" for r in rows)


def test_audit_failure_surfaces_not_swallowed(seeded, monkeypatch, tmp_path):
    """Task item 2: a failure to write the audit row on a SUCCESSFUL
    call MUST surface, not be swallowed.
    """
    fake_bin = tmp_path / "fake-hermes"
    fake_bin.write_text("#!/bin/sh\nexit 0\n")
    fake_bin.chmod(0o755)

    class FakeProc:
        returncode = 0
        stdout = "pong"
        stderr = ""
    monkeypatch.setattr(agent_ask.subprocess, "run", lambda *a, **kw: FakeProc())
    monkeypatch.setenv("HVE_HERMES_BIN", str(fake_bin))

    # Force the audit write to fail by making open_db raise.
    def boom(cfg):
        raise RuntimeError("simulated db outage")
    monkeypatch.setattr(agent_ask, "open_db", boom)

    with pytest.raises(agent_ask.AuditError, match="could not be audited"):
        agent_ask.ask(seeded, "hello", timeout_s=5)
