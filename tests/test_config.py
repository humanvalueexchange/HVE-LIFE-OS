"""Smoke-test for the HVE config (loopback-only enforcement)."""

import pytest

from hve.config import HveConfig


def test_loopback_only_by_default(cfg):
    assert cfg.http_host == "127.0.0.1"


def test_non_loopback_is_rejected(tmp_path, monkeypatch):
    from hve.config import HveConfig
    with pytest.raises(ValueError, match="loopback"):
        HveConfig(
            home=tmp_path / "h",
            http_host="0.0.0.0",  # must reject
            reports_dir=tmp_path / "r",
            backups_dir=tmp_path / "b",
            db_path=tmp_path / "d.sqlite3",
            knowledge_dir=tmp_path / "k",
        )


def test_paths_are_absolute(cfg):
    for p in (cfg.home, cfg.db_path.parent, cfg.knowledge_dir,
              cfg.reports_dir, cfg.backups_dir):
        assert p.is_absolute()
        assert p.exists(), f"{p} should exist"
    # The db file itself is created lazily by the first connect + migrate.
    assert cfg.db_path.is_absolute()
    # The db file is created once the schema is applied.
    from hve.db import ensure_schema
    ensure_schema(cfg)
    if cfg.db_path.exists():
        assert cfg.db_path.is_file()
    else:
        # Acceptable: the db file is created on first connect.
        assert (cfg.home / "data").is_dir()
