"""HVE Life OS configuration.

All runtime paths are resolved from environment variables so the same code
runs on Mercury (dedicated ``hve`` user) and on developer machines
(``hermes`` user or a plain CLI session). No secrets are read here.

Defaults map to the Mercury runtime contract from Issue #1 (D5, D6):

* home directory   : ``~/.hve``                (dedicated ``hve`` service user)
* SQLite db path   : ``~/.hve/data/hve.db``
* knowledge dir    : ``~/.hve/knowledge``      (real Customer Zero data; never Git)
* report dir       : ``~/.hve/reports``
* backup dir       : ``~/.hve/backups``
* loopback listen  : ``127.0.0.1:8090``
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

#: Five Wealth domain vocabulary (charter 13, first alpha objective).
FIVE_WEALTH_DOMAINS: tuple[str, ...] = (
    "time_wealth",
    "physical_wealth",
    "mental_wealth",
    "social_wealth",
    "financial_wealth",
)

#: Default loopback health/report service port.
DEFAULT_HTTP_PORT = 8090
DEFAULT_LOOPBACK_HOST = "127.0.0.1"

DEFAULT_SCHEMA_VERSION = 1


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_path(name: str, default: Path | None, *, root: Path | None = None) -> Path:
    raw = os.environ.get(name)
    if raw:
        p = Path(raw).expanduser()
        return p if p.is_absolute() else (root or Path.cwd()) / p
    return default or (root or Path.home()) / ".hve"


@dataclass(frozen=True)
class HveConfig:
    """Immutable runtime configuration.

    Built with :func:`load` so it can be overridden per-process via env
    variables (the systemd EnvironmentFile pattern).
    """

    home: Path = field(
        default_factory=lambda: _env_path("HVE_HOME", Path.home() / ".hve")
    )
    db_path: Path = field(
        default_factory=lambda: _env_path("HVE_DB_PATH", Path.home() / ".hve" / "data" / "hve.db")
    )
    knowledge_dir: Path = field(
        default_factory=lambda: _env_path("HVE_KNOWLEDGE_DIR", Path.home() / ".hve" / "knowledge")
    )
    reports_dir: Path = field(
        default_factory=lambda: _env_path("HVE_REPORTS_DIR", Path.home() / ".hve" / "reports")
    )
    backups_dir: Path = field(
        default_factory=lambda: _env_path("HVE_BACKUPS_DIR", Path.home() / ".hve" / "backups")
    )
    http_host: str = field(default_factory=lambda: os.environ.get("HVE_HTTP_HOST", DEFAULT_LOOPBACK_HOST))
    http_port: int = field(
        default_factory=lambda: _env_int("HVE_HTTP_PORT", DEFAULT_HTTP_PORT)
    )

    # Model backend (loopback-only on Mercury).
    model_endpoint: str = field(
        default_factory=lambda: os.environ.get("HVE_MODEL_ENDPOINT", "http://127.0.0.1:8089/v1")
    )
    model_context_tokens: int = field(
        default_factory=lambda: _env_int("HVE_MODEL_CONTEXT", 8192)
    )

    # Reporting (D9: hourly, idempotent).
    report_hourly: bool = field(
        default_factory=lambda: _env_bool("HVE_REPORT_HOURLY", True)
    )

    # Safety: never allow the loopback host to be widened in alpha (D7).
    def __post_init__(self) -> None:
        if self.http_host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError(
                f"HVE_HTTP_HOST must be loopback-only in alpha, got {self.http_host!r}; "
                "Issue #1 D7 mandates 127.0.0.1."
            )
        # Create the directory parts only. Do NOT call mkdir on the db file
        # itself — that would create a *directory* named "hve.db" and
        # sqlite3.connect() would then fail with "unable to open database
        # file".
        for d in (self.home, self.knowledge_dir, self.reports_dir,
                  self.backups_dir):
            d.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def data_dir(self) -> Path:
        return self.home / "data"

    @property
    def reports_md(self) -> Path:
        return self.reports_dir / "report.md"

    @property
    def reports_html(self) -> Path:
        return self.reports_dir / "report.html"

    @property
    def schema_migrations_sql(self) -> Path:
        return Path(__file__).parent / "migrations" / "001_initial.sql"


def load() -> HveConfig:
    """Build an :class:`HveConfig` from the environment."""
    return HveConfig()
