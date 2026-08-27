"""Shared test fixtures.

Each test gets a throwaway HVE home directory (``~/.hve`` equivalent) in
a temp dir, so no test touches a real ``~/.hve``.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture()
def hve_home(tmp_path: Path) -> Path:
    """Isolated HVE home + sub-directories for a single test."""
    home = tmp_path / "hve-home"
    (home / "data").mkdir(parents=True)
    (home / "knowledge").mkdir(parents=True)
    (home / "reports").mkdir(parents=True)
    (home / "backups").mkdir(parents=True)
    return home


@pytest.fixture()
def cfg(hve_home: Path):
    """An :class:`HveConfig` rooted at the isolated home."""
    from hve.config import HveConfig
    import os as _os
    _os.environ.setdefault("HVE_HERMES_BIN", str(Path("/nonexistent/hermes")))
    c = HveConfig(
        home=hve_home,
        db_path=hve_home / "data" / "hve.db",
        knowledge_dir=hve_home / "knowledge",
        reports_dir=hve_home / "reports",
        backups_dir=hve_home / "backups",
        http_host="127.0.0.1",
        http_port=0,
        model_endpoint="http://127.0.0.1:8999/v1",
        model_context_tokens=65536,
    )
    for d in (c.home, c.knowledge_dir, c.reports_dir, c.backups_dir,
              c.home / "data"):
        d.mkdir(parents=True, exist_ok=True)
    return c


@pytest.fixture()
def seeded(cfg):
    """A fully initialized HVE home (schema + seeded facts + kb)."""
    from hve.db import ensure_schema
    from hve.facts import store as facts_mod
    from hve.kbase import loader as kb
    ensure_schema(cfg)
    # Copy the repo placeholders into the isolated knowledge dir.
    src = REPO_ROOT / "knowledge_base"
    dst = cfg.knowledge_dir
    for f in src.glob("*.md"):
        if f.name == "README.md":
            continue
        shutil.copy2(f, dst / f.name)
    facts_mod.seed_defaults(cfg)
    kb.upsert(cfg)
    return cfg
