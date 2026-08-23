"""Smoke-test for the migration manager (D8=A: schema_migrations)."""

from hve.db import ensure_schema
from hve.migrations import manager as mig
import sqlite3


def test_applies_and_is_idempotent(cfg):
    applied = ensure_schema(cfg)
    assert applied == [(1, "001_initial")]
    # Re-applying is a no-op.
    assert ensure_schema(cfg) == []
    # Schema version is 1.
    assert mig.current_version(cfg) == 1
    assert mig.status_expected(cfg) == 1


def test_schema_migrations_table_exists(cfg):
    ensure_schema(cfg)
    conn = sqlite3.connect(cfg.db_path)
    cur = conn.execute(
        "SELECT name FROM sqlite_schema WHERE type='table' AND name='schema_migrations'"
    )
    assert cur.fetchone() is not None
    rows = conn.execute(
        "SELECT version, name, checksum FROM schema_migrations"
    ).fetchall()
    assert rows and rows[0][0] == 1 and rows[0][1] == "001_initial"
    assert len(rows[0][2]) == 64  # sha256
    conn.close()


def test_foreign_keys_on(cfg):
    from hve.db import open_db
    conn = open_db(cfg)
    ensure_schema(cfg)
    fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk == 1


def test_wal_mode(cfg):
    from hve.db import open_db
    conn = open_db(cfg)
    ensure_schema(cfg)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"
