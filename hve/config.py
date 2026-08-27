"""HVE Life OS configuration.

All runtime paths are resolved from environment variables so the same code
works in the directory-contained DGX Spark reference deployment and in
isolated development homes. No secrets are read here.

The Spark runtime sets ``HVE_HOME=/home/hans/hve-life-os/data`` and keeps
SQLite, Markdown, reports, logs, and backups under that directory. Generic
development defaults remain under ``~/.hve``.
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
DEFAULT_MODEL_NAME = "Qwen3.8-2B-Distill-Q4_K_M"
DEFAULT_MODEL_BACKEND = "llama.cpp-cpu-neon"
DEFAULT_MODEL_CONTEXT = 65536
DEFAULT_MAX_OUTPUT_TOKENS = 1024
DEFAULT_MODEL_CHECKSUM = (
    "4aa0fb13c431514262f259d420ecc95a8714df58ac2a2384514e20b93983f0ff"
)

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


def _resolve_base_home() -> Path:
    """Base home for the HVE runtime.

    ``HVE_HOME`` (if set and non-empty) is the base; otherwise
    ``Path.home()/.hve``. This is the single source for ALL runtime dirs so
    the deployment is directory-contained wherever ``HVE_HOME`` points.
    """
    raw = os.environ.get("HVE_HOME")
    if raw:
        p = Path(raw).expanduser()
        return p if p.is_absolute() else Path.cwd() / p
    return Path.home() / ".hve"


def _env_path(
    name: str, default: Path | None, *, root: Path | None = None
) -> Path | None:
    raw = os.environ.get(name)
    if raw:
        p = Path(raw).expanduser()
        return p if p.is_absolute() else (root or _resolve_base_home()) / p
    return default


def _configured_home() -> Path:
    return _env_path("HVE_HOME", Path.home() / ".hve")


def _default_db_path() -> Path:
    configured_home = _configured_home()
    if os.environ.get("HVE_HOME"):
        return configured_home / "hve.db"
    return configured_home / "data" / "hve.db"


@dataclass(frozen=True)
class HveConfig:
    """Immutable runtime configuration.

    Built with :func:`load` so it can be overridden per-process via env
    variables (the systemd EnvironmentFile pattern).

    Directory containment: ``home`` (from ``HVE_HOME``), ``db_path``,
    ``knowledge_dir``, ``reports_dir`` and ``backups_dir`` all anchor to the
    base home so the runtime never writes outside the deployment root.
    """

    home: Path = field(
        default_factory=lambda: _env_path("HVE_HOME", Path.home() / ".hve")
    )
    db_path: Path = field(
        default_factory=lambda: _env_path("HVE_DB_PATH", None)
    )
    knowledge_dir: Path = field(
        default_factory=lambda: _env_path("HVE_KNOWLEDGE_DIR", None)
    )
    reports_dir: Path = field(
        default_factory=lambda: _env_path("HVE_REPORTS_DIR", None)
    )
    backups_dir: Path = field(
        default_factory=lambda: _env_path("HVE_BACKUPS_DIR", None)

    )
    http_host: str = field(default_factory=lambda: os.environ.get("HVE_HTTP_HOST", DEFAULT_LOOPBACK_HOST))
    http_port: int = field(
        default_factory=lambda: _env_int("HVE_HTTP_PORT", DEFAULT_HTTP_PORT)
    )

    # Model backend (loopback-only on the Spark reference deployment).
    model_endpoint: str = field(
        default_factory=lambda: os.environ.get("HVE_MODEL_ENDPOINT", "http://127.0.0.1:8089/v1")
    )
    model_backend: str = field(
        default_factory=lambda: os.environ.get(
            "HVE_MODEL_BACKEND", DEFAULT_MODEL_BACKEND
        )
    )
    model_context_tokens: int = field(
        default_factory=lambda: _env_int("HVE_MODEL_CONTEXT", DEFAULT_MODEL_CONTEXT)
    )
    model_name: str = field(
        default_factory=lambda: os.environ.get("HVE_MODEL_NAME", DEFAULT_MODEL_NAME)
    )
    model_max_output_tokens: int = field(
        default_factory=lambda: _env_int("HVE_MAX_OUTPUT_TOKENS", DEFAULT_MAX_OUTPUT_TOKENS)
    )
    model_path: Path | None = field(
        default_factory=lambda: (
            Path(os.environ["HVE_MODEL_PATH"]).expanduser()
            if os.environ.get("HVE_MODEL_PATH")
            else None
        )
    )
    model_checksum: str = field(
        default_factory=lambda: os.environ.get(
            "HVE_MODEL_SHA256", DEFAULT_MODEL_CHECKSUM
        )
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
        # Derive any dir that was left at the None default from `home` so the
        # whole runtime is directory-contained wherever HVE_HOME points.
        # (object.__setattr__ is required because the dataclass is frozen.)
        if self.knowledge_dir is None:
            object.__setattr__(self, "knowledge_dir", self.home / "knowledge")
        if self.reports_dir is None:
            object.__setattr__(self, "reports_dir", self.home / "reports")
        if self.backups_dir is None:
            object.__setattr__(self, "backups_dir", self.home / "backups")
        if self.db_path is None:
            object.__setattr__(self, "db_path", self.home / "hve.db")
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
