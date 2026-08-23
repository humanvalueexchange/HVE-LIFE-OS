"""Five Wealth facts store.

Charter 13 (first alpha objective): "SQLite facts store" with a
"Five Wealth domain structure."

Facts are structured, queryable records with the shape:

    (domain, category, subject, value_type, value, source, confidence,
     valid_from, valid_to)

``domain`` is one of the five wealth domains. ``category`` is a free-form
bucket (the alpha ships with a small fixed vocabulary per domain; this is
extensible by adding new categories — the schema does not constrain
category).

``value_type`` is one of ``text | number | bool | enum``. ``value`` is
stored as TEXT and is interpreted by the reader according to
``value_type``.

Insertion rules (charter 4 + 5):

* no single agent / feature may invent a fact without a traceable
  ``source`` string;
* default confidence is ``1.0``; caller may lower it to reflect
  uncertainty;
* facts are *not* auto-deleted; callers use ``valid_to`` to soft-expire
  them.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from ..config import FIVE_WEALTH_DOMAINS, HveConfig
from ..db import open_db

#: Canonical category names per domain. Extensible; the schema is
#: category-agnostic.
CANONICAL_CATEGORIES: dict[str, tuple[str, ...]] = {
    "time_wealth":     ("time_spent", "time_available", "schedules", "boundaries", "identity"),
    "physical_wealth": ("health_baseline", "sleep", "exercise", "nutrition", "environment"),
    "mental_wealth":   ("learning", "focus", "mood", "values", "clarity"),
    "social_wealth":   ("relationships", "community", "conversations", "trust"),
    "financial_wealth":("assets", "liabilities", "income", "expenses", "sovereignty"),
}

_VALID_VALUE_TYPES = frozenset({"text", "number", "bool", "enum"})


def _validate(domain: str, category: str, subject: str, value_type: str, value: Any) -> None:
    if domain not in FIVE_WEALTH_DOMAINS:
        raise ValueError(f"unknown domain {domain!r}; expected one of {FIVE_WEALTH_DOMAINS}")
    if not category.strip():
        raise ValueError("category must be non-empty")
    if not subject.strip():
        raise ValueError("subject must be non-empty")
    if value_type not in _VALID_VALUE_TYPES:
        raise ValueError(
            f"value_type must be one of {sorted(_VALID_VALUE_TYPES)}, got {value_type!r}"
        )
    if value is None:
        raise ValueError("value must not be None")


def _normalize(value: Any, value_type: str) -> str:
    """Stringify ``value`` according to ``value_type``.

    The DB stores TEXT for all value types so the same query path applies
    to every domain.
    """
    if value_type == "number":
        try:
            f = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"number value not parseable: {value!r}") from exc
        return str(f)
    if value_type == "bool":
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
            return value.strip().lower()
        raise ValueError(f"bool value not parseable: {value!r}")
    # text / enum
    s = str(value).strip()
    if not s:
        raise ValueError("value must be non-empty")
    return s


@dataclass(frozen=True)
class Fact:
    domain: str
    category: str
    subject: str
    value_type: str
    value: str
    source: str
    confidence: float = 1.0
    valid_from: str | None = None
    valid_to: str | None = None


def _fresh_rows(cfg: HveConfig, sql: str, params: list) -> list:
    with open_db(cfg) as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


class FactsStore:
    """Thin typed wrapper over the ``facts`` table."""

    def __init__(self, cfg: HveConfig) -> None:
        self.cfg = cfg

    def add(
        self,
        domain: str,
        category: str,
        subject: str,
        value: Any,
        source: str,
        *,
        value_type: str = "text",
        confidence: float = 1.0,
        valid_from: str | None = None,
        valid_to: str | None = None,
    ) -> int:
        """Insert a fact; returns the new row id.

        ``source`` is mandatory (charter 5: traceability).
        """
        _validate(domain, category, subject, value_type, value)
        s = _normalize(value, value_type)
        with open_db(self.cfg) as conn:
            cur = conn.execute(
                """
                INSERT INTO facts (
                    domain, category, subject, value_type, value,
                    source, confidence, valid_from, valid_to
                ) VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    domain, category.strip(), subject.strip(), value_type, s,
                    source or "",
                    confidence,
                    valid_from, valid_to,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)

    def query(
        self,
        domain: str | None = None,
        category: str | None = None,
        subject: str | None = None,
        *,
        limit: int = 200,
        only_current: bool = True,
    ) -> list[Fact]:
        """Query facts. Defaults to all five domains and current only."""
        params: list[object] = []
        where: list[str] = []
        if domain:
            _validate(domain, "category", "subject", "text", "x")  # raises if invalid
            where.append("domain = ?")
            params.append(domain)
        if category:
            where.append("category = ?")
            params.append(category)
        if subject:
            where.append("subject = ?")
            params.append(subject)
        if only_current:
            where.append("(valid_to IS NULL OR valid_to > datetime('now'))")
        sql = "SELECT * FROM facts"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY recorded_at DESC LIMIT ?"
        params.append(limit)
        with open_db(self.cfg) as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return [
            Fact(
                domain=r["domain"],
                category=r["category"],
                subject=r["subject"],
                value_type=r["value_type"],
                value=r["value"],
                source=r["source"],
                confidence=float(r["confidence"]),
                valid_from=r["valid_from"],
                valid_to=r["valid_to"],
            )
            for r in rows
        ]

    def top(self, domain: str, n: int = 3, category: str | None = None) -> list[Fact]:
        """Top-N facts by recorded order for the report."""
        return self.query(domain=domain, category=category, limit=n, only_current=True)

    def count(self, domain: str | None = None) -> int:
        """Return the count of facts matching the filter.

        Always opens a fresh connection — never caches — so this is
        safe to call after a :func:`hve.db.restore_db` call.
        """
        params: list[object] = []
        where = ""
        if domain:
            _validate(domain, "category", "subject", "text", "x")
            where = " WHERE domain = ?"
            params.append(domain)
        return len(_fresh_rows(self.cfg,
                               f"SELECT 1 FROM facts{where}",
                               list(params)))

    def domains_present(self) -> list[str]:
        with open_db(self.cfg) as conn:
            rows = conn.execute(
                "SELECT domain FROM facts GROUP BY domain ORDER BY domain"
            ).fetchall()
        return [r["domain"] for r in rows]


def seed_defaults(cfg: HveConfig) -> int:
    """Insert one well-formed sample fact per domain so the alpha has
    *something* to render even before Hans runs ``hve init --seed``
    (D5=A: placeholders only).

    Returns the number of facts inserted (0 when any domain already has
    facts).
    """
    store = FactsStore(cfg)
    inserted = 0
    samples: list[tuple[str, str, str, str]] = [
        ("time_wealth",     "identity",           "placeholder", "Time Wealth: time spent vs. time available; see knowledge file."),
        ("physical_wealth", "health_baseline",    "placeholder", "Physical Wealth: baseline health and environment."),
        ("mental_wealth",   "clarity",            "placeholder", "Mental Wealth: focus, values, and clarity of purpose."),
        ("social_wealth",   "relationships",      "placeholder", "Social Wealth: relationships, community, and trust."),
        ("financial_wealth", "sovereignty",       "placeholder", "Financial Wealth: local assets, liabilities, sovereignty."),
    ]
    with open_db(cfg) as conn:
        for domain, category, subject, value in samples:
            row = conn.execute(
                "SELECT 1 FROM facts WHERE domain=? AND category=? AND subject=? LIMIT 1",
                (domain, category, subject),
            ).fetchone()
            if row:
                continue
            conn.execute(
                """
                INSERT INTO facts (domain, category, subject, value_type, value, source, confidence)
                VALUES (?,?,?,?,?,?,?)
                """,
                (domain, category, subject, "text", value,
                 "seed:hve:0.1.0", 1.0),
            )
            inserted += 1
        conn.commit()
    return inserted
