"""Canonical ``hve agent ask`` path.

Charter 13 requires "one Hermes agent interaction path." Issue #1 D4=A
makes ``hve agent ask`` that canonical path: a thin abstraction over the
local Hermes CLI that

* always loads the HVE Life OS skill,
* always writes an ``interactions`` row (success AND failure),
* never writes secrets, and
* exits 0 on success, non-zero on any failure so the caller (CLI,
  systemd, a shell script) can branch.

Audit policy (M1 repair, task item 2):

* interaction logging is part of the contract — a *successful* prompt
  that we fail to audit is a silent loss Hans asked us to stop.
* We therefore do NOT swallow logging errors. On a successful call,
  if the audit row cannot be written we raise
  :class:`AuditError` so the operator sees it (the HVE service writes a
  visible error instead of pretending the ask worked).
* On a failed call (non-zero exit / timeout) the audit row *best-effort*
  write is attempted once; a logging failure there is chained onto the
  primary :class:`AgentError` so the operator still sees the primary
  failure first.
* Responses are stored verbatim (no secrets expected in a local,
  loopback skill), but we strip a known set of secret-looking tokens
  before persisting.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import HveConfig
from ..db import open_db


class AgentError(RuntimeError):
    """Raised when the hermes CLI call does not succeed."""


class AuditError(RuntimeError):
    """Raised when a successful interaction could not be audited.

    Per the HVE audit policy, a successful prompt MUST have an
    interaction row. If the row could not be written, the caller
    should treat the ask as *unauditable* and surface this.
    """


_SECRET_RE = re.compile(
    r"(?i)(?:api[_-]?key|token|secret|password|passphrase|private[_-]?key|aws[_-]?secret)"
    r"\s*[=:]\s*\S{6,}"
    r"|\bAKIA[0-9A-Z]{16}\b"
)


def _strip_secrets(text: str) -> str:
    """Best-effort scrub of secret-looking substrings before persisting.

    Never returns a string that still contains a known key shape. If no
    match, the input is returned unchanged.
    """
    if not text:
        return text
    return _SECRET_RE.sub(lambda m: "<REDACTED>", text)


def _candidate_paths() -> list[Path]:
    """Portable, optional Hermes install locations.

    These are *fallbacks only* — a portability aid for developer and
    staging boxes — and are strictly less preferred than the
    ``HVE_HERMES_BIN`` env var or a ``hermes`` on PATH. They are
    checked in order; the first that exists AND is executable wins.

    We deliberately do NOT hardcode a single host-only absolute path.
    The correct, portable way to pin the binary on the Spark reference
    deployment is one of:

    * ``HVE_HERMES_BIN=/home/hans/.local/bin/hermes`` (explicit env), or
    * a ``hermes`` shim on the active runtime ``PATH``.

    (Hermes's local CLI typically lives at ``~/.local/bin/hermes``. The
    pre-m3 fix also probed ``~/.hermes/venv/bin/hermes`` — that was a
    mistaken assumption; it is kept ONLY as a last-resort fallback and is
    never trusted over the two preferred mechanisms.)
    """
    home = Path.home()
    return [
        home / ".local" / "bin" / "hermes",
        Path("/usr/local/bin/hermes"),
        Path("/usr/bin/hermes"),
        home / ".hermes" / "venv" / "bin" / "hermes",  # last resort
    ]


def _is_usable(p: Path | str | None) -> bool:
    """True if ``p`` is an existing, executable file (a real binary)."""
    if p is None:
        return False
    pp = Path(p)
    return pp.is_file() and os.access(pp, os.X_OK)


def _find_hermes() -> str | None:
    """Locate the ``hermes`` CLI.

    Resolution order (first usable wins):

    1. ``HVE_HERMES_BIN`` env var  (explicit operator pin — preferred)
    2. ``hermes`` on ``PATH``       (``shutil.which``)
    3. a small set of portable optional fallback locations

    Any of the first two that is present is authoritative. The env var
    is honored even if it points at a missing path — in that case we
    raise a clear error rather than silently falling through to a
    different binary (a pinned path that is absent is a config bug, not
    a fallback opportunity).
    """
    env = os.environ.get("HVE_HERMES_BIN")
    if env:
        p = Path(env).expanduser()
        if _is_usable(p):
            return str(p)
        # Operator pinned a path that is not usable. Surface it clearly
        # instead of guessing. (ask() turns this into an AgentError.)
        return "<UNRESOLVED:HVE_HERMES_BIN>:" + str(p)
    found = shutil.which("hermes")
    if found and _is_usable(found):
        return found
    for cand in _candidate_paths():
        if _is_usable(cand):
            return str(cand)
    return None


def _resolve_error(bin_hint: str) -> str:
    """Build a precise, actionable error message for a failed lookup."""
    base = (
        "hermes CLI not found. Resolve it in one of these ways:\n"
        "  1. Set HVE_HERMES_BIN=/abs/path/to/hermes (explicit pin; see "
        "docs/architecture-spark.md), or\n"
        "  2. Put `hermes` on the active runtime PATH, or\n"
        "  3. Install Hermes and verify `hermes --version` for the `hve` "
        "user.\n"
    )
    if bin_hint.startswith("<UNRESOLVED"):
        # Extract the offending path after the colon.
        offending = bin_hint.split(":", 2)[-1]
        base += f"  HVE_HERMES_BIN={offending} is set but not usable (missing or not executable).\n"
    return base


@dataclass(frozen=True)
class AgentResult:
    session_id: str
    prompt: str
    response: str
    latency_ms: int
    hermes_bin: str
    model: str


def ask(cfg: HveConfig, prompt: str, *,
        hermes_bin: str | None = None,
        session_id: str | None = None,
        timeout_s: int = 600,
        extra_args: list[str] | None = None,
        ) -> AgentResult:
    """Invoke the local Hermes CLI with the HVE Life OS skill.

    On success, an interaction row is written. If that write fails, an
    :class:`AuditError` is raised (task item 2: do not silently swallow
    audit failures).
    """
    hermes_bin = hermes_bin or _find_hermes()
    if hermes_bin is None or hermes_bin.startswith("<UNRESOLVED"):
        raise AgentError(_resolve_error(hermes_bin or ""))

    session_id = session_id or str(uuid.uuid4())
    started = time.monotonic()

    # Verified contract (task item 3, read-only inspection of
    # `hermes --help` and `hermes chat --help` on the reference runtime —
    # Hermes
    # Agent v0.20.5):
    #
    #   hermes chat -q "<prompt>" -s hve-life-os -Q
    #
    #   -q <QUERY>    single-query non-interactive mode
    #   -s <SKILLS>   preload one or more skills (repeat flag or
    #                 comma-separate)
    #   -Q/--quiet    programmatic: suppress banner, spinner, tool
    #                 previews; emit ONLY the final response
    #
    # Note: `hermes send` is the *messaging* command (deliver a text
    # message to a configured platform) — it does NOT run the agent,
    # does NOT accept --skill, and its --json flag shapes delivery
    # telemetry, not an LLM response. That is why `ask()` uses
    # `hermes chat -q` and not `hermes send`.
    cmd = [
        hermes_bin, "chat",
        "-q", prompt,
        "-s", "hve-life-os",
        "-Q",
    ]
    if extra_args:
        cmd.insert(1, *extra_args)

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        _record_fail(cfg, session_id, prompt, str(exc),
                     int((time.monotonic() - started) * 1000))
        raise AgentError(f"hermes send timed out after {timeout_s}s: {exc}") from exc
    except FileNotFoundError as exc:
        raise AgentError(f"hermes binary not executable: {hermes_bin}") from exc

    latency_ms = int((time.monotonic() - started) * 1000)
    if proc.returncode != 0:
        # Best-effort audit of the *failure*. A logging failure here is
        # chained onto the primary AgentError (task item 2: never masked).
        primary = AgentError(
            f"hermes send exited {proc.returncode}: {proc.stderr.strip()[:500]}"
        )
        try:
            _record_fail(cfg, session_id, prompt, proc.stderr.strip(), latency_ms)
        except Exception as log_exc:  # noqa: BLE001
            primary.__cause__ = log_exc
            raise primary from log_exc
        raise primary

    response = _parse_response(proc.stdout)

    # Successful call: audit is mandatory. Raise AuditError if it
    # fails, rather than swallowing it silently.
    try:
        _record_success(cfg, session_id, prompt, response, latency_ms,
                        hermes_bin=hermes_bin, model=f"custom@{cfg.model_endpoint}")
    except Exception as log_exc:  # noqa: BLE001
        raise AuditError(
            f"hermes send succeeded but the interaction could not be "
            f"audited: {log_exc}"
        ) from log_exc

    return AgentResult(
        session_id=session_id,
        prompt=prompt,
        response=response,
        latency_ms=latency_ms,
        hermes_bin=hermes_bin,
        model=f"custom@{cfg.model_endpoint}",
    )


def _parse_response(out: str) -> str:
    """The HVE skill contract: stdout is a single UTF-8 string."""
    return out.strip()


def _insert(cfg: HveConfig, session_id: str, prompt: str, response: str,
            latency_ms: int, model: str) -> None:
    prompt = _strip_secrets(prompt or "")
    response = _strip_secrets(response or "")
    with open_db(cfg) as conn:
        conn.execute(
            "INSERT INTO interactions "
            "(session_id, prompt, response, latency_ms, model) "
            "VALUES (?,?,?,?,?)",
            (session_id, prompt, response, latency_ms, model),
        )
        conn.commit()


def _record_success(cfg: HveConfig, session_id: str, prompt: str,
                    response: str, latency_ms: int, *, hermes_bin: str,
                    model: str) -> None:
    """Mandatory audit for a successful call.

    Any exception propagates to the caller (ask() wraps it in
    AuditError) — never silently swallowed.
    """
    _insert(cfg, session_id, prompt, response, latency_ms, model)


def _record_fail(cfg: HveConfig, session_id: str, prompt: str,
                 error: str, latency_ms: int) -> None:
    """Best-effort audit for a failed call.

    Logging failures on this path are chained onto the *primary* error
    in ask() so the operator still sees why the call actually failed
    first.
    """
    _insert(cfg, session_id, prompt, f"ERROR: {error[:800]}", latency_ms,
            "custom@unknown")


def recent(cfg: HveConfig, n: int = 5) -> list[dict[str, Any]]:
    with open_db(cfg) as conn:
        rows = conn.execute(
            "SELECT session_id, prompt, response, latency_ms, created_at "
            "FROM interactions ORDER BY created_at DESC LIMIT ?",
            (n,),
        ).fetchall()
    return [dict(r) for r in rows]
