"""Tests for the report renderer (idempotent, D9=B)."""

from hve.report import render as report
from hve.db import ensure_schema


def test_generate_writes_both_files(cfg):
    ensure_schema(cfg)
    res = report.generate(cfg)
    assert cfg.reports_md.exists()
    assert cfg.reports_html.exists()
    assert res["wrote"]["report.md"] is True
    assert res["wrote"]["report.html"] is True


def test_generate_is_idempotent(cfg):
    ensure_schema(cfg)
    report.generate(cfg)
    res2 = report.generate(cfg)
    assert res2["wrote"]["report.md"] is False
    assert res2["wrote"]["report.html"] is False
    # Files are unchanged.
    md = cfg.reports_md.read_bytes()
    assert report._sha256_bytes(md)[:12] == res2["md_sha256"]


def test_html_is_self_contained(cfg):
    ensure_schema(cfg)
    report.generate(cfg)
    html = cfg.reports_html.read_text()
    assert "<!doctype html>" in html
    # No external asset references.
    assert "http://" not in html.replace("http://127.0.0.1", "")
    assert "https://" not in html
    # No script tags (self-contained).
    assert "<script" not in html


def test_md_contains_all_five_domains(cfg):
    ensure_schema(cfg)
    report.generate(cfg)
    md = cfg.reports_md.read_text()
    for d in ("Time Wealth", "Physical Wealth", "Mental Wealth",
              "Social Wealth", "Financial Wealth"):
        assert d in md


def test_md_lists_schema_version_and_model(cfg):
    ensure_schema(cfg)
    report.generate(cfg)
    md = cfg.reports_md.read_text()
    assert "Schema version: 1" in md
    assert "Qwen2.5 3B" in md
    # The SHA-256 prefix from the manifest is present.
    assert "626b4a6678b8" in md
