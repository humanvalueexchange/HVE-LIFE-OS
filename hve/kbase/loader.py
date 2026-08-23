"""Markdown knowledge base loader.

Design (charter 8.2 + Issue #1 D5):

* canonical knowledge files live in ``~/.hve/knowledge/`` (NOT in Git);
* this loader scans a directory of ``*.md`` files, records a stable
  SHA-256 checksum of the content, and upserts them into the
  ``knowledge`` table;
* the loader is content-agnostic: it does NOT parse business logic out
  of the markdown, only indexes structure (title, domain, checksum).
  Business meaning is added by :mod:`hve.facts`.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from ..config import FIVE_WEALTH_DOMAINS, HveConfig
from ..db import open_db

_DOMAIN_BY_STEM: dict[str, str] = {
    "time_wealth": "time_wealth",
    "physical_wealth": "physical_wealth",
    "mental_wealth": "mental_wealth",
    "social_wealth": "social_wealth",
    "financial_wealth": "financial_wealth",
}


def domain_for_file(path: Path) -> str:
    """Map a knowledge file path to one of the five domains.

    Any file not explicitly mapped to a domain is treated as
    ``general`` — that is *not* a valid CHECK value in the ``knowledge``
    table, so the caller must filter these out before ingesting if they
    want them in the DB. The loader itself records them with
    ``domain='general'`` *only* when the domain cannot be inferred from
    the filename, and skips the CHECK by using a sentinel that the
    migrations would have to allow.

    To keep the CHECK simple we only ingest the five canonical files;
    other files are surfaced in the health check as ``warn``.
    """
    stem = path.stem.lower()
    if stem in _DOMAIN_BY_STEM:
        return _DOMAIN_BY_STEM[stem]
    if path.name.lower() == "identity.md":
        # Identity is a cross-domain anchor; store under time_wealth for
        # now (Hans's time is the primary resource being optimized).
        return "time_wealth"
    return "general"


def sha256_of(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def iter_markdown(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(p for p in root.glob("*.md") if p.is_file())


def parse_title(text: str) -> str:
    """Extract the first ``# Heading`` as the document title, else the
    first non-empty line, else ``Untitled``."""
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        return s.lstrip("#").strip() or "Untitled"
    return "Untitled"


@dataclass(frozen=True)
class KnowledgeRecord:
    path: str          # repo-relative stable id
    title: str
    domain: str
    checksum: str
    content: str


def scan(root: Path) -> list[KnowledgeRecord]:
    """Read the directory and build records without touching the DB."""
    out: list[KnowledgeRecord] = []
    for p in iter_markdown(root):
        text = p.read_text(encoding="utf-8")
        out.append(
            KnowledgeRecord(
                path=str(p.name),
                title=parse_title(text),
                domain=domain_for_file(p),
                checksum=sha256_of(p),
                content=text,
            )
        )
    return out


def upsert(cfg: HveConfig, records: list[KnowledgeRecord] | None = None) -> dict:
    """Upsert records into the ``knowledge`` table.

    Returns ``{"upserted": n, "skipped_general": n}`` for reporting.
    """
    records = records if records is not None else scan(cfg.knowledge_dir)
    upserted = 0
    skipped = 0
    with open_db(cfg) as conn:
        for rec in records:
            if rec.domain == "general":
                skipped += 1
                continue
            conn.execute(
                """
                INSERT INTO knowledge (path, title, domain, checksum, content)
                VALUES (?,?,?,?,?)
                ON CONFLICT(path) DO UPDATE SET
                    title     = excluded.title,
                    domain    = excluded.domain,
                    checksum  = excluded.checksum,
                    content   = excluded.content,
                    ingested_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
                """,
                (rec.path, rec.title, rec.domain, rec.checksum, rec.content),
            )
            upserted += 1
    return {"upserted": upserted, "skipped_general": skipped}


def load(cfg: HveConfig) -> int:
    """One-shot scan + upsert; returns number of records upserted."""
    res = upsert(cfg)
    return res["upserted"]


def count(cfg: HveConfig) -> dict[str, int]:
    """Return per-domain counts (useful for report rendering)."""
    with open_db(cfg) as conn:
        rows = conn.execute(
            "SELECT domain, COUNT(*) AS n FROM knowledge GROUP BY domain"
        ).fetchall()
    return {r["domain"]: r["n"] for r in rows}
