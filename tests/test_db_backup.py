"""Tests for the SQLite backup / restore path (D10=B)."""

import datetime
import json
import shutil
import sqlite3
import time
from pathlib import Path

import pytest

from hve.db import backup_db, restore_db, ensure_schema
from hve.facts import store as facts_mod


def test_backup_creates_snapshot(cfg):
    ensure_schema(cfg)
    facts_mod.FactsStore(cfg).add(
        "time_wealth", "time_spent", "marker-fact", 1,
        value_type="number", source="test",
    )
    dest = backup_db(cfg)
    assert dest.exists()
    # The snapshot is a valid SQLite DB.
    conn = sqlite3.connect(dest)
    cur = conn.execute(
        "SELECT COUNT(*) FROM facts WHERE subject='marker-fact'"
    )
    assert cur.fetchone()[0] == 1
    conn.close()


def test_restore_requires_confirmation(cfg):
    ensure_schema(cfg)
    dest = backup_db(cfg)
    # Without confirmation, refuse.
    with pytest.raises(PermissionError, match="confirm"):
        restore_db(cfg, dest, confirm=False)


def test_restore_preserves_prior_db(cfg):
    ensure_schema(cfg)
    store = facts_mod.FactsStore(cfg)
    store.add("time_wealth", "time_spent", "before", 1,
              value_type="number", source="test")
    dest = backup_db(cfg)

    # Add *another* fact (the "newer personal data" the operator wants to
    # keep on the other side).
    store.add("time_wealth", "time_spent", "later", 2,
              value_type="number", source="test")
    n_before = store.count()
    assert n_before == 2

    # Restore the older snapshot.
    preserved = restore_db(cfg, dest, confirm=True)
    assert preserved.exists()

    # After restore, only the "before" fact remains.
    rows = store.query(domain="time_wealth")
    assert [r.subject for r in rows] == ["before"]
    # The preserved pre-restore file still holds both facts.
    conn = sqlite3.connect(preserved)
    n = conn.execute("SELECT COUNT(*) FROM facts ").fetchone()[0]
    assert n == 2
    conn.close()


def test_missing_snapshot_raises(cfg):
    ensure_schema(cfg)
    with pytest.raises(FileNotFoundError):
        restore_db(cfg, cfg.backups_dir / "nope.sqlite3", confirm=True)
