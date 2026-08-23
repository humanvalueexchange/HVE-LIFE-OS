"""Tests for the facts store (Five Wealth)."""

import pytest
from hve.facts import store as facts_mod
from hve.config import FIVE_WEALTH_DOMAINS


def test_seed_defaults_creates_one_per_domain(cfg):
    from hve.db import ensure_schema
    ensure_schema(cfg)
    assert facts_mod.seed_defaults(cfg) >= 5
    for d in FIVE_WEALTH_DOMAINS:
        assert facts_mod.FactsStore(cfg).count(d) >= 1


def test_add_and_query(cfg):
    from hve.db import ensure_schema
    ensure_schema(cfg)
    store = facts_mod.FactsStore(cfg)
    fid = store.add(
        "time_wealth", "time_spent", "coding", 4.5,
        value_type="number", source="test",
    )
    assert fid > 0
    rows = store.query(domain="time_wealth")
    assert any(r.subject == "coding" and r.value == "4.5" for r in rows)


def test_invalid_domain_rejected(cfg):
    from hve.db import ensure_schema
    ensure_schema(cfg)
    store = facts_mod.FactsStore(cfg)
    with pytest.raises(ValueError, match="unknown domain"):
        store.add("crypto_wealth", "x", "y", "z", source="t")


def test_bool_normalises(cfg):
    from hve.db import ensure_schema
    ensure_schema(cfg)
    store = facts_mod.FactsStore(cfg)
    store.add("mental_wealth", "mood", "ok", True,
              value_type="bool", source="t")
    row = store.query(domain="mental_wealth", subject="ok")[0]
    assert row.value in {"true", "True"}


def test_number_rejects_string(cfg):
    store = facts_mod.FactsStore(cfg)
    with pytest.raises(ValueError):
        store.add("time_wealth", "x", "y", "not-a-number",
                  value_type="number", source="t")


def test_valid_to_soft_expires(cfg):
    from hve.db import ensure_schema
    ensure_schema(cfg)
    store = facts_mod.FactsStore(cfg)
    store.add("social_wealth", "relationships", "expired", "row",
              source="t", valid_to="1999-01-01T00:00:00Z")
    assert store.query(domain="social_wealth") == []
    rows = store.query(domain="social_wealth", only_current=False)
    assert len(rows) == 1
