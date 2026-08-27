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


def test_http_healthz(seeded):
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


# ---------------------------------------------------------------------------
# B2 — 8090 service health visibility + `hve serve` CLI wiring
# ---------------------------------------------------------------------------


def test_health_warns_when_service_down(cfg):
    """With the 8090 service intentionally stopped, check() must emit a
    WARN (not FAIL) for http_service, and still report ok=True overall —
    ordinary developer health checks must not fail merely because the
    service is down.
    """
    from hve.serve import health as hve_health
    object.__setattr__(cfg, "http_port", 18090)
    ensure_schema(cfg)
    result = hve_health.check(cfg)
    assert result["ok"] is True
    svc = next((c for c in result["checks"] if c["name"] == "http_service"), None)
    assert svc is not None, "http_service check missing from result"
    assert svc["status"] == "warn", svc
    assert "not listening" in svc["detail"]


def test_health_ok_when_service_up(seeded):
    """With the service listening (dynamic port mode), check() must
    report OK for http_service and read the 200 from the live server.
    """
    import time
    import urllib.request
    from hve.serve import health as hve_health

    server = hve_health.serve(seeded, block=False)
    try:
        host, port = server.server_address[:2]
        # Publish the bound port so check()'s probe targets the live socket.
        object.__setattr__(seeded, "http_port", port)
        deadline = time.monotonic() + 3
        last_err = None
        while time.monotonic() < deadline:
            try:
                urllib.request.urlopen(f"http://{host}:{port}/healthz", timeout=1)
                break
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                time.sleep(0.05)
        else:
            pytest.fail(f"server did not come up: {last_err}")
        result = hve_health.check(seeded)
        assert result["ok"] is True
        svc = next((c for c in result["checks"] if c["name"] == "http_service"), None)
        assert svc is not None
        assert svc["status"] == "ok", svc
        assert "-> 200" in svc["detail"]
    finally:
        server.shutdown()
        server.server_close()


def test_health_model_and_service_checks_are_distinct(seeded):
    """The 8089 model check and the 8090 http_service check are separate
    entries — a model failure must not be conflated with a service
    failure, and vice versa.
    """
    from hve.serve import health as hve_health
    # Ensure the probe fires by giving the config a real (non-zero) port.
    server = hve_health.serve(seeded, block=False)
    try:
        host, port = server.server_address[:2]
        object.__setattr__(seeded, "http_port", port)
        result = hve_health.check(seeded)
    finally:
        server.shutdown()
        server.server_close()
    names = {c["name"] for c in result["checks"]}
    assert "model" in names
    assert "http_service" in names


def test_serve_cli_parser_exposes_subcommand():
    """`hve serve` must be a registered subcommand (B2 parser wiring)."""
    from hve import cli as hve_cli
    parser = hve_cli.build_parser()
    args = parser.parse_args(["serve"])
    assert args.command == "serve"
    assert args.host is None
    assert args.port is None


def test_serve_cli_rejects_non_loopback(cfg):
    """A non-loopback --host must be rejected BEFORE any socket is
    opened (D7 / loopback-only alpha contract).
    """
    from hve import cli as hve_cli
    parser = hve_cli.build_parser()
    args = parser.parse_args(["serve", "--host", "192.168.1.1"])
    rc = hve_cli.cmd_serve(cfg, args)
    assert rc == 2


def test_serve_cli_delegates_to_existing_loop(cfg, monkeypatch):
    """`hve serve` must delegate to the existing ``hve.serve.loop``
    implementation — not open a second service.
    """
    import hve.serve.loop as serve_loop
    called = []
    monkeypatch.setattr(serve_loop, "main", lambda: called.append("main") or 0)
    monkeypatch.setenv("HVE_HTTP_HOST", "127.0.0.1")
    from hve import cli as hve_cli
    parser = hve_cli.build_parser()
    args = parser.parse_args(["serve"])
    rc = hve_cli.cmd_serve(cfg, args)
    assert rc == 0
    assert called == ["main"]


def test_serve_cli_publishes_port_override(cfg, monkeypatch):
    """A --port override must be published as HVE_HTTP_PORT so the
    loop reads it through the normal config path (no second socket).
    """
    import hve.serve.loop as serve_loop
    monkeypatch.setattr(serve_loop, "main", lambda: 0)
    monkeypatch.delenv("HVE_HTTP_PORT", raising=False)
    from hve import cli as hve_cli
    parser = hve_cli.build_parser()
    args = parser.parse_args(["serve", "--port", "18090"])
    hve_cli.cmd_serve(cfg, args)
    import os
    assert os.environ.get("HVE_HTTP_PORT") == "18090"
