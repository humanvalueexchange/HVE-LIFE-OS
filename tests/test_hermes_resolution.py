"""Focused tests for Hermes binary resolution (loop item 1).

Covers the full resolution ladder in ``hve/agent/ask.py`` without
depending on the real reference runtime:

* explicit ``HVE_HERMES_BIN`` pin is authoritative (preferred)
* a *pinned* path that is missing/not-executable raises a clear error
  and is NOT silently substituted by another binary
* ``hermes`` on PATH is the second preference
* portable optional fallback locations are only used as a last resort
* total failure produces a clear, actionable message
* the removed hard-coded ``/home/hermes/...`` path is no longer special-cased

Every stub is created in ``tmp_path`` and made executable, so these
tests are deterministic and safe to run on any machine.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hve.agent import ask as agent_ask


def _make_stub(tmp_path: Path, name: str = "hermes", body: str = "echo pong\n") -> Path:
    p = tmp_path / name
    p.write_text("#!/usr/bin/env bash\n" + body + "\nexit 0\n")
    p.chmod(0o755)
    return p


def test_env_pin_is_preferred(tmp_path, monkeypatch, cfg):
    """HVE_HERMES_BIN wins over PATH and fallbacks (preferred mechanism)."""
    stub = _make_stub(tmp_path, "hermes-pinned")
    onpath = _make_stub(tmp_path, "hermes-path")
    # Put a decoy 'hermes' first on PATH to prove the pin still wins.
    decoy_dir = tmp_path / "decoy-bin"
    decoy_dir.mkdir()
    decoy = _make_stub(decoy_dir, "hermes", body="echo DECOY\n")
    assert decoy.exists()

    monkeypatch.setenv("HVE_HERMES_BIN", str(stub))
    monkeypatch.setenv("PATH", f"{decoy_dir}:{onpath.parent}:")

    resolved = agent_ask._find_hermes()
    assert resolved == str(stub)


def test_env_pin_missing_raises_clear_error(tmp_path, monkeypatch, cfg):
    """A pinned path that is absent is a config bug: raise, don't fall through.

    This is the key behavioral change in loop item 1: the previous code
    silently returned None and the operator never saw *why*. Now the error
    names the offending path and the three ways to fix it.
    """
    # Deliberately point at a real dir that does NOT contain an executable
    # hermes — proves we don't fall through to PATH/fallbacks either.
    missing = tmp_path / "does-not-exist" / "hermes"
    assert not missing.exists()
    monkeypatch.setenv("HVE_HERMES_BIN", str(missing))
    # Ensure PATH has no hermes so a fall-through would be detectable.
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    monkeypatch.setattr(agent_ask.shutil, "which", lambda _x: None)

    with pytest.raises(agent_ask.AgentError) as exc:
        agent_ask.ask(cfg, "ping")
    msg = str(exc.value)
    assert "HVE_HERMES_BIN" in msg
    assert str(missing) in msg                      # offending path named
    assert "not usable" in msg                       # reason
    assert "docs/runbook-spark.md" in msg            # actionable pointer (Spark)



def test_env_pin_not_executable_treated_as_missing(tmp_path, monkeypatch, cfg):
    """Existing but non-executable file is NOT a usable binary."""
    not_exec = tmp_path / "hermes"
    not_exec.write_text("# not a real shell script")
    not_exec.chmod(0o644)                            # not executable
    monkeypatch.setenv("HVE_HERMES_BIN", str(not_exec))

    # _is_usable must reject it.
    assert agent_ask._is_usable(not_exec) is False
    # And resolution must not return it.
    resolved = agent_ask._find_hermes()
    assert resolved != str(not_exec)


def test_path_discovery_second_preference(tmp_path, monkeypatch, cfg):
    """With no env pin, `hermes` on PATH is used (second preference)."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = _make_stub(bin_dir, "hermes")
    monkeypatch.delenv("HVE_HERMES_BIN", raising=False)
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.setattr(agent_ask.shutil, "which", lambda _x: str(stub))

    resolved = agent_ask._find_hermes()
    assert resolved == str(stub)


def test_fallback_locations_are_last_resort(tmp_path, monkeypatch, cfg):
    """With no env pin and no PATH hermes, a portable fallback may supply.

    We do NOT assert a specific absolute path (portability): we assert
    only that when the two preferred mechanisms are absent and the
    fallbacks are also empty, resolution fails cleanly.
    """
    monkeypatch.delenv("HVE_HERMES_BIN", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    monkeypatch.setattr(agent_ask.shutil, "which", lambda _x: None)
    monkeypatch.setattr(agent_ask, "_candidate_paths", lambda: [])

    assert agent_ask._find_hermes() is None
    with pytest.raises(agent_ask.AgentError) as exc:
        agent_ask.ask(cfg, "ping")
    assert "HVE_HERMES_BIN" in str(exc.value)


def test_no_hardcoded_herms_user_path(tmp_path, monkeypatch, cfg):
    """The old host-only /home/hermes hardcode is gone.

    We point the resolver at an EMPTY candidate list and a PATH with no
    hermes, and assert that resolution does NOT magically return a
    /home/hermes path — it must fail cleanly. This pins the portability
    fix: resolution is env/PATH/fallbacks, never a baked-in account path.
    """
    monkeypatch.delenv("HVE_HERMES_BIN", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    monkeypatch.setattr(agent_ask.shutil, "which", lambda _x: None)
    monkeypatch.setattr(agent_ask, "_candidate_paths", lambda: [])

    resolved = agent_ask._find_hermes()
    if resolved is None:
        return  # expected: clean failure
    assert "/home/hermes" not in resolved, (
        "resolver still returned a hard-coded /home/hermes path "
        f"({resolved}); that host-only absolute path must not be "
        "special-cased (portability)"
    )


def test_usable_check_requires_exec_bit(tmp_path):
    present_not_exec = tmp_path / "ne"
    present_not_exec.write_text("x")
    present_not_exec.chmod(0o644)
    present_exec = tmp_path / "pe"
    present_exec.write_text("x")
    present_exec.chmod(0o755)
    missing = tmp_path / "nope"

    assert agent_ask._is_usable(present_exec) is True
    assert agent_ask._is_usable(present_not_exec) is False
    assert agent_ask._is_usable(missing) is False
    assert agent_ask._is_usable(None) is False
