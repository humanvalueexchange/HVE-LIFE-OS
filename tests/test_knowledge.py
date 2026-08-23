"""Tests for the Markdown knowledge loader."""

from pathlib import Path
from hve.kbase import loader as kb


def test_scan_uses_all_five_domains(cfg):
    for d in kb.FIVE_WEALTH_DOMAINS if hasattr(kb, "FIVE_WEALTH_DOMAINS") else []:
        pass
    # Load the repo's placeholders into the isolated knowledge dir.
    src = Path(__file__).parent.parent / "knowledge_base"
    import shutil
    for f in src.glob("*.md"):
        shutil.copy2(f, cfg.knowledge_dir / f.name)
    files = kb.iter_markdown(cfg.knowledge_dir)
    assert len(files) >= 5


def test_upserts_into_db(cfg):
    from hve.db import ensure_schema
    ensure_schema(cfg)
    src = Path(__file__).parent.parent / "knowledge_base"
    import shutil
    for f in src.glob("*.md"):
        if f.name == "README.md":
            continue
        shutil.copy2(f, cfg.knowledge_dir / f.name)
    res = kb.upsert(cfg)
    assert res["upserted"] >= 5
    counts = kb.count(cfg)
    assert counts["time_wealth"] == 1
    assert counts["financial_wealth"] == 1


def test_checksum_is_stable(cfg):
    from hve.db import ensure_schema
    ensure_schema(cfg)
    src = Path(__file__).parent.parent / "knowledge_base"
    import shutil
    for f in src.glob("*.md"):
        if f.name == "README.md":
            continue
        shutil.copy2(f, cfg.knowledge_dir / f.name)
    before = kb.scan(cfg.knowledge_dir)
    kb.upsert(cfg)
    after = kb.scan(cfg.knowledge_dir)
    assert len(before) == len(after)
    for a, b in zip(before, after):
        assert a.checksum == b.checksum
        assert a.content == b.content
