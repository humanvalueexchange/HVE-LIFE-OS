# B1 — Alpha profile pinning (hve-alpha, Qwen3.8-2B-Distill, 127.0.0.1:8089)
#
# The fixture alpha_profile_env pins HERMES_HOME to a fresh temp dir
# profiles/hve-alpha and HVE_HERMES_PROFILE=hve-alpha. The stub hermes
# binary reports its child environment so we can verify the pin landed
# and that any caller-supplied HERMES_PROFILE was stripped before exec.

import textwrap
from pathlib import Path

import pytest

from hve.agent import ask as agent_ask

STUB_REPORT_ENV = textwrap.dedent(
    """#!/usr/bin/env bash
    echo "child-HERMES_HOME=${HERMES_HOME-}"
    echo "child-HERMES_PROFILE=${HERMES_PROFILE-}"
    echo "pong"
    exit 0
    """
).strip() + "\n"

STUB_LEAK_PROBE = textwrap.dedent(
    """#!/usr/bin/env bash
    echo "FALLBACK-LEAK"
    exit 0
    """
).strip() + "\n"


def _get_line(text: str, prefix: str) -> str:
    for line in text.splitlines():
        if line.startswith(prefix):
            return line
    raise AssertionError(f"line with prefix {prefix!r} not found in {text!r}")


def test_b1_alpha_profile_pinned_in_subprocess_env(
    cfg, seeded, tmp_path, monkeypatch, alpha_profile_env
):
    """The hermes subprocess MUST see HERMES_HOME=<alpha profile dir> and
    an empty HERMES_PROFILE so it routes to Qwen3.8-2B-Distill @
    127.0.0.1:8089, never to the caller's ambient profile.
    """
    # Simulate a hostile caller environment. ask() must strip it and
    # pin its own value.
    monkeypatch.setenv("HERMES_PROFILE", "attacker-profile")

    stub = tmp_path / "hermes-stub-b1"
    stub.write_text(STUB_REPORT_ENV)
    stub.chmod(0o755)
    monkeypatch.setenv("HVE_HERMES_BIN", str(stub))

    res = agent_ask.ask(seeded, "b1-ping")
    assert "pong" in res.response

    hermes_home_line = _get_line(res.response, "child-HERMES_HOME=")
    child_home = hermes_home_line.split("=", 1)[1].strip()
    assert child_home.endswith("/profiles/hve-alpha"), child_home

    # Caller HERMES_PROFILE must be stripped (empty in the child).
    hermes_profile_line = _get_line(res.response, "child-HERMES_PROFILE=")
    assert hermes_profile_line == "child-HERMES_PROFILE=", (
        f"caller HERMES_PROFILE leaked into the child env: {hermes_profile_line!r}"
    )


def test_b1_fails_loud_when_no_profile_resolves(
    cfg, seeded, tmp_path, monkeypatch
):
    """With no Alpha profile resolvable, ask() must raise AgentError and
    not silently invoke the ambient caller's Hermes profile.
    """
    # Point both resolution paths at a location that does not exist.
    monkeypatch.setenv("HERMES_HOME", str(cfg.home / "no-such-profile"))
    monkeypatch.setenv("HVE_HERMES_PROFILE", "no-such-profile")
    monkeypatch.setenv("HERMES_ROOT", str(cfg.home))

    # A stub that would flag any silent fallback.
    stub = tmp_path / "hermes-must-not-run"
    stub.write_text(STUB_LEAK_PROBE)
    stub.chmod(0o755)
    monkeypatch.setenv("HVE_HERMES_BIN", str(stub))

    with pytest.raises(agent_ask.AgentError, match="Alpha profile not resolved"):
        agent_ask.ask(seeded, "b1-must-fail")


def test_b1_profile_resolution_prefers_hermes_home_env(
    cfg, seeded, monkeypatch
):
    """When HERMES_HOME already points at a valid profiles/<name> dir,
    the resolver must honour it as-is.
    """
    pinned = cfg.home / "profiles" / "pinned-profile"
    pinned.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HERMES_HOME", str(pinned))

    resolved = agent_ask._resolve_profile_home()
    assert resolved is not None
    assert str(resolved) == str(pinned)


def test_b1_profile_resolution_by_name(cfg, seeded, monkeypatch):
    """When HERMES_HOME is unset and HVE_HERMES_PROFILE is set, the
    resolver must resolve <HERMES_ROOT|~/.hermes>/profiles/<name>.
    """
    monkeypatch.delenv("HERMES_HOME", raising=False)
    profile_dir = cfg.home / "profiles" / "byname-profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HERMES_ROOT", str(cfg.home))
    monkeypatch.setenv("HVE_HERMES_PROFILE", "byname-profile")

    resolved = agent_ask._resolve_profile_home()
    assert resolved is not None
    assert str(resolved) == str(profile_dir)


def _fresh_cfg(hve_home):
    """An HveConfig rooted at hve_home WITHOUT the alpha_profile_env
    fixture (which would pin HERMES_HOME to a temp dir and shadow the
    HVE_HOME fallback)."""
    from hve.config import HveConfig
    return HveConfig(home=hve_home)


def test_b1_hve_home_only_fallback_uses_alpha_default(
    hve_home, monkeypatch
):
    """Step 4 (option a): with only HVE_HOME set — no HVE_HERMES_HOME,
    no HERMES_HOME, no HVE_HERMES_PROFILE — the resolver MUST return the
    standard registry Alpha profile ``~/.hermes/profiles/hve-alpha``.

    This isolates step 4 by using an hve_home-based config (no
    alpha_profile_env fixture), so none of steps 1-3 fire.
    """
    _fresh_cfg(hve_home)  # create the directory tree the resolver checks
    monkeypatch.delenv("HVE_HERMES_HOME", raising=False)
    monkeypatch.delenv("HERMES_HOME", raising=False)
    monkeypatch.delenv("HVE_HERMES_PROFILE", raising=False)
    monkeypatch.delenv("HERMES_ROOT", raising=False)
    monkeypatch.setenv("HVE_HOME", str(hve_home))

    resolved = agent_ask._resolve_profile_home()
    expected = Path.home() / ".hermes" / "profiles" / "hve-alpha"
    assert resolved == expected, resolved


def test_b1_hve_home_only_with_explicit_profile_name(
    hve_home, monkeypatch, tmp_path
):
    """Step 4: HVE_HOME alone + HVE_HERMES_PROFILE name — the name
    takes precedence over the default ``hve-alpha`` and resolves
    through the standard registry (HERMES_ROOT)."""
    _fresh_cfg(hve_home)
    monkeypatch.delenv("HVE_HERMES_HOME", raising=False)
    monkeypatch.delenv("HERMES_HOME", raising=False)
    monkeypatch.setenv("HERMES_ROOT", str(tmp_path))
    monkeypatch.setenv("HVE_HOME", str(hve_home))
    monkeypatch.setenv("HVE_HERMES_PROFILE", "custom-profile")
    target = tmp_path / "profiles" / "custom-profile"
    target.mkdir(parents=True, exist_ok=True)
    resolved = agent_ask._resolve_profile_home()
    assert resolved == target, resolved


def test_b1_hve_home_only_fails_loudly_when_no_profile(
    hve_home, monkeypatch, tmp_path
):
    """Step 4: HVE_HOME set, but the standard registry (HERMES_ROOT) has
    no Alpha profile and no other path resolves — must return None
    (loud), NOT a non-standard ``<HVE_HOME>/hermes-profiles/`` path."""
    _fresh_cfg(hve_home)
    monkeypatch.delenv("HVE_HERMES_HOME", raising=False)
    monkeypatch.delenv("HERMES_HOME", raising=False)
    monkeypatch.delenv("HVE_HERMES_PROFILE", raising=False)
    monkeypatch.setenv("HERMES_ROOT", str(tmp_path))
    monkeypatch.setenv("HVE_HOME", str(hve_home))
    # Ensure no profiles/hve-alpha in tmp_path (the standard registry).
    assert not (tmp_path / "profiles" / "hve-alpha").exists()
    resolved = agent_ask._resolve_profile_home()
    # Must be None (loud failure), not a <HVE_HOME>/hermes-profiles path.
    nonstandard = hve_home.parent / "hermes-profiles" / "hve-alpha"
    assert resolved != nonstandard, f"returned non-standard path: {resolved}"
    assert resolved is None, f"should have failed loud, got: {resolved}"


def test_b1_no_silent_fallback_on_profile_missing(
    cfg, seeded, tmp_path, monkeypatch
):
    """End-to-end: with the Alpha profile directory absent, the stub
    hermes binary must NOT be invoked (no silent ambient-profile
    fallback). The AgentError is raised before subprocess.run.
    """
    monkeypatch.setenv("HERMES_HOME", str(cfg.home / "absent-profile"))
    monkeypatch.setenv("HVE_HERMES_PROFILE", "absent-profile")
    monkeypatch.setenv("HERMES_ROOT", str(cfg.home))

    stub = tmp_path / "hermes-must-not-run"
    stub.write_text(STUB_LEAK_PROBE)
    stub.chmod(0o755)
    monkeypatch.setenv("HVE_HERMES_BIN", str(stub))

    with pytest.raises(agent_ask.AgentError, match="Alpha profile not resolved"):
        agent_ask.ask(seeded, "no-fallback")

    # No audit row should have been written for a call that never reached
    # the hermes binary (the profile guard precedes the subprocess).
    records = agent_ask.recent(seeded, n=5)
    assert not any(r.get("prompt") == "no-fallback" for r in records), (
        "fallback call leaked an audit row"
    )
