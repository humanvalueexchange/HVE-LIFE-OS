"""Forward-only SQLite schema migrations.

Design (Issue #1 D8=A):

* each migration is an idempotent ``CREATE TABLE IF NOT EXISTS`` block with
  a ``PRAGMA foreign_keys = ON`` preamble;
* :class:`schema_migrations` (D8) records every applied version and the
  SHA-256 checksum of the SQL file it was applied from;
* migrations are additive and forward-only; rollback is done by restoring
  a snapshot via :func:`hve.db.backup` / :mod:`hve.db.restore` (D10=B),
  never by DDL rollback.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from ..config import HveConfig


class MigrationError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _migrations_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "migrations"


def _discover() -> list[Path]:
    """Return migration files ordered by version name (``NNN_name.sql``)."""
    files = sorted(_migrations_dir().glob("*.sql"), key=lambda p: p.name)
    for f in files:
        prefix = f.name.split("_", 1)[0]
        if not prefix.isdigit() or int(prefix) <= 0:
            raise MigrationError(f"invalid migration filename: {f.name}")
    return files


def _applied(cfg: HveConfig) -> dict[int, tuple[str, str]]:
    """Return {version: (name, checksum)} for migrations already applied."""
    conn = sqlite3.connect(cfg.db_path)
    try:
        cur = conn.execute(
            "SELECT name FROM sqlite_schema WHERE type='table' AND name='schema_migrations'"
        )
        if cur.fetchone() is None:
            return {}
        rows = conn.execute(
            "SELECT version, name, checksum FROM schema_migrations"
        ).fetchall()
    finally:
        conn.close()
    return {int(v): (name, chk) for v, name, chk in rows}


def _version_of(path: Path) -> int:
    name = path.name  # 001_initial.sql
    prefix = name.split("_", 1)[0]
    try:
        return int(prefix)
    except ValueError as exc:
        raise MigrationError(f"cannot parse version from {name}") from exc


def apply(cfg: HveConfig, *, dry_run: bool = False) -> list[tuple[int, str]]:
    """Apply any un-applied migrations.

    Returns the list of (version, name) pairs applied in this call
    (empty when up-to-date).
    """
    pending: list[tuple[int, Path, str]] = []
    applied = _applied(cfg)
    for f in _discover():
        ver = _version_of(f)
        sha = _sha256(f)
        if ver in applied:
            # Guard against drift: if the file changed after we recorded its
            # checksum, fail loudly instead of silently re-running it.
            rec = applied[ver]
            recorded_chk = rec[1] if isinstance(rec, tuple) else rec
            if recorded_chk != sha:
                raise MigrationError(
                    f"migration {f.name} checksum drift: "
                    f"recorded={recorded_chk[:12]}.. current={sha[:12]}.."
                )
            continue
        pending.append((ver, f, sha))

    if not pending:
        return []

    if dry_run:
        return [(v, f.stem) for v, f, _ in pending]

    pending.sort(key=lambda t: t[0])
    with sqlite3.connect(cfg.db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " version    INTEGER PRIMARY KEY,"
            " name       TEXT NOT NULL UNIQUE,"
            " applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),"
            " checksum   TEXT NOT NULL)"
        )
        for ver, f, sha in pending:
            sql = f.read_text(encoding="utf-8")
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_migrations (version, name, checksum) VALUES (?,?,?)",
                (ver, f.stem, sha),
            )
            conn.commit()
    return [(v, f.stem) for v, f, _ in pending]


def status(cfg: HveConfig) -> dict:
    """Return a human-readable migration status.

    Useful for ``hve status`` and the /status.json endpoint.
    """
    applied = _applied(cfg)
    return {
        "expected_version": len(_discover()) and max(_version_of(f) for f in _discover()) or 0,
        "applied_versions": sorted(applied.keys()),
        "up_to_date": bool(applied) and max(applied.keys()) == status_expected(cfg),
    }


def status_expected(cfg: HveConfig) -> int:
    files = _discover()
    return max((_version_of(f) for f in files), default=0)


def current_version(cfg: HveConfig) -> int:
    applied = _applied(cfg)
    return max(applied.keys()) if applied else 0
