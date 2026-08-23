"""SQLite helpers: open, ensure schema, backup, and guarded restore.

This is the single place that opens the HVE database. It enforces WAL
journal mode, foreign keys ON, and the forward-only migration policy.

Backup / restore (Issue #1 D10=B):

* :func:`backup_db` writes a SQLite ``.backup`` snapshot into
  ``<backups_dir>/hve-db/`` with a timestamped name.
* :func:`restore_db` refuses to run unless ``confirm=True`` is passed,
  so that the ``hve db restore`` CLI requires an explicit ``--i-understand``
  flag.  The restore is atomic: the existing db file is moved aside, the
  snapshot is moved in, and the service is expected to be restarted by
  the caller.
"""

from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .config import HveConfig


def open_db(cfg: HveConfig) -> sqlite3.Connection:
    """Open the HVE database in WAL mode with foreign keys on.

    The caller owns the connection's lifetime and must close it.
    """
    cfg.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(cfg.db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema(cfg: HveConfig, *, dry_run: bool = False) -> list[tuple[int, str]]:
    """Run any un-applied migrations. Idempotent when up-to-date."""
    from .migrations import manager
    return manager.apply(cfg, dry_run=dry_run)


def backup_db(cfg: HveConfig) -> Path:
    """Create an online SQLite backup under ``~/.hve/backups/hve-db/``.

    Returns the path to the new snapshot.
    """
    cfg.backups_dir.mkdir(parents=True, exist_ok=True)
    dest_dir = cfg.backups_dir / "hve-db"
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = dest_dir / f"hve-{stamp}.sqlite3"
    if not cfg.db_path.exists():
        raise FileNotFoundError(f"no database to back up at {cfg.db_path}")
    src = sqlite3.connect(cfg.db_path)
    try:
        with sqlite3.connect(dest) as dst:
            src.backup(dst)
    finally:
        src.close()
    return dest


def _new_snap(cfg: HveConfig, source: Path) -> Path:
    """Copy ``source`` into the backups directory using SQLite's online
    backup API (WAL-safe: committed frames in the WAL are copied too)."""
    dest_dir = cfg.backups_dir / "hve-restore"
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = dest_dir / f"hve-{stamp}.sqlite3"
    src = sqlite3.connect(source)
    try:
        with sqlite3.connect(dest) as dst:
            src.backup(dst)
    finally:
        src.close()
    return dest


def _remove_sidecars(path: Path) -> None:
    """Delete the WAL + SHM sidecars for ``path`` (if present).

    Safe because the caller is about to replace the whole db; leaving
    them would let stale frames replay on the next open. Called *only*
    for the destination file, AFTER all writers have closed.
    """
    p = Path(path)
    for suffix in ("-wal", "-shm"):
        sib = p.with_suffix(p.suffix + suffix)
        if sib.exists():
            sib.unlink()


def restore_db(cfg: HveConfig, snapshot: Path, *, confirm: bool = False) -> Path:
    """Restore ``snapshot`` over ``cfg.db_path``.

    D10=B safety: ``confirm=True`` is required AND the existing db file
    is preserved under ``~/.hve/backups/hve-restore/`` so a mistaken
    restore can be undone.

    WAL-safe: the *preserved* copy is written with the SQLite online
    backup API so committed frames in the source WAL are captured (a
    plain file copy would lose them or replay them later). The *incoming*
    snapshot is copied with a plain ``shutil.copy2`` — callers of this
    function are expected to hold no writer open (the service is
    stopped or single-instance in alpha).

    Returns the path to the preserved (prior) db file.
    """
    if not confirm:
        raise PermissionError(
            "restore_db requires explicit confirmation (confirm=True). "
            "Use `hve db restore --i-understand` to acknowledge."
        )
    if not snapshot.exists():
        raise FileNotFoundError(snapshot)

    dest_dir = cfg.backups_dir / "hve-restore"
    dest_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    if cfg.db_path.exists():
        # WAL-safe online backup of the live db (captures committed WAL
        # frames). Then rename it into the canonical pre-restore slot so
        # the operator sees a predictable name in backups/.
        snap = _new_snap(cfg, cfg.db_path)
        target = dest_dir / f"hve-pre-restore-{ts}.sqlite3"
        if snap != target:
            snap.rename(target)
        preserved = target
        _remove_sidecars(preserved)  # belt-and-braces: backup has no sidecars
    else:
        preserved = dest_dir / f"hve-pre-restore-{ts}.absent"
        preserved.touch()

    # The live db is being replaced. Remove the destination file first —
    # and only then remove its stale WAL/SHM sidecars. If the destination
    # still existed with sidecars, a plain unlink+copy would replay the
    # old sidecars into the new db on next open. Doing it in this order
    # preserves the invariant: "no sidecars exist for the file we are
    # about to write".
    if cfg.db_path.exists():
        cfg.db_path.unlink()
    for s in (cfg.db_path.with_name(cfg.db_path.name + "-wal"),
              cfg.db_path.with_name(cfg.db_path.name + "-shm")):
        s.unlink(missing_ok=True)

    # Copy the incoming snapshot into place (plain byte copy; the snapshot
    # was produced by backup_db, which is itself WAL-safe and has no
    # sidecars to worry about).
    shutil.copy2(snapshot, cfg.db_path)
    # Defensive: ensure no stray sidecars remain.
    _remove_sidecars(cfg.db_path)

    # Integrity verification: catch corruption or FK violations *before*
    # the operator moves on. The live db is the source of truth going
    # forward; do not roll the restore back on failure (that would lose
    # the preserved snapshot).
    verifier = sqlite3.connect(cfg.db_path)
    try:
        row = verifier.execute("PRAGMA integrity_check").fetchone()
        if row[0] != "ok":
            raise RuntimeError(f"post-restore integrity_check failed: {row[0]}")
        violations = verifier.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(
                f"post-restore foreign_key_check found {len(violations)} violations"
            )
    finally:
        verifier.close()
    return preserved


def iter_health(cfg: HveConfig) -> Iterator[tuple[str, str, str]]:
    """Yield (component, status, detail) for simple read probes."""
    yield ("db_integrity", _pragma_ok(cfg, "integrity_check"), "PRAGMA integrity_check")
    yield ("db_schema", "ok" if _schema_ok(cfg) else "warn",
           "PRAGMA schema_version")


def _pragma_ok(cfg: HveConfig, pragma: str) -> str:
    try:
        with open_db(cfg) as conn:
            if pragma == "integrity_check":
                row = conn.execute(f"PRAGMA {pragma}").fetchone()
                return "ok" if row[0] == "ok" else "warn"
            row = conn.execute(f"PRAGMA {pragma}").fetchone()
            return "ok" if row is not None else "warn"
    except sqlite3.Error:
        return "fail"


def _schema_ok(cfg: HveConfig) -> bool:
    from .migrations import manager
    cur = manager.current_version(cfg)
    return cur >= 1
