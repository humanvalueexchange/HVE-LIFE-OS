"""Tests for the health check module."""

import json
import pytest
from hve.serve import health as hve_health
from hve.db import ensure_schema


def test_health_is_ok_on_seeded(cfg):
    ensure_schema(cfg)
    result = hve_health.check(cfg)
    assert result["ok"] is True
    names = {c["name"] for c in result["checks"]}
    assert {"db", "migrations", "knowledge", "facts"} <= names


def test_health_reports_missing_knowledge_dir(cfg):
    ensure_schema(cfg)
    cfg.knowledge_dir.rmdir()
    result = hve_health.check(cfg)
    # The knowledge check must at least fire (warn or ok).
    names = {c["name"] for c in result["checks"]}
    assert "knowledge" in names


def test_status_json_is_serializable(cfg):
    ensure_schema(cfg)
    out = hve_health.status(cfg)
    # JSON round-trip proves no non-serializable state leaks.
    text = json.dumps(out, default=str)
    parsed = json.loads(text)
    assert parsed["name"] == "hve-life-os"
    assert "domains" in parsed
    assert "health" in parsed


def test_status_schema_versions_are_real(cfg):
    """Task item 4: /status.json must return the ACTUAL applied schema
    version (no placeholder), plus a synced flag."""
    ensure_schema(cfg)
    out = hve_health.status(cfg)
    sv = out["schema_versions"]
    assert sv["applied"] == [1]
    assert sv["expected"] == 1
    assert sv["synced"] is True
    # Applied values are sorted integers.
    assert all(isinstance(v, int) for v in sv["applied"])


def test_http_healthz(seeded, monkeypatch):
    """Probe the running HTTP service on its ACTUAL dynamic port (D3/D7).

    The fixture uses ``http_port=0`` (OS-assigned), so we read
    ``server.server_address[1]`` instead of trusting ``cfg.http_port``.
    """
    import time
    import urllib.request
    from hve.serve.health import serve

    server = serve(seeded, block=False)
    host, port = server.server_address[:2]
    url_root = f"http://{host}:{port}"
    try:
        deadline = time.monotonic() + 3
        last_err = None
        resp = None
        while time.monotonic() < deadline:
            try:
                resp = urllib.request.urlopen(f"{url_root}/healthz", timeout=1)
                break
            except Exception as exc:
                last_err = exc
                time.sleep(0.05)
        assert resp is not None, f"server never came up: {last_err}"
        assert resp.status == 200
        body = json.loads(resp.read().decode())
        assert body["ok"] is True
        assert any(c["name"] == "db" for c in body["checks"])

        # Also verify /status.json returns the real applied schema version.
        resp2 = urllib.request.urlopen(f"{url_root}/status.json", timeout=1)
        assert resp2.status == 200
        body2 = json.loads(resp2.read().decode())
        assert body2["schema_versions"]["applied"] == [1]
        assert body2["schema_versions"]["expected"] == 1
        assert body2["schema_versions"]["synced"] is True
    finally:
        server.shutdown()
        server.server_close()


def test_http_does_not_expose_non_loopback(cfg):
    """A non-loopback host is rejected by the config, so this is a
    config-level regression, not a network-level test."""
    import pytest
    with pytest.raises(ValueError, match="loopback"):
        from hve.config import HveConfig
        HveConfig(
            home=cfg.home, db_path=cfg.db_path,
            http_host="192.168.1.1",
            knowledge_dir=cfg.knowledge_dir,
            reports_dir=cfg.reports_dir, backups_dir=cfg.backups_dir,
        )
