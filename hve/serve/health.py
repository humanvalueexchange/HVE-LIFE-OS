"""Health checks and HTTP handlers.

Loopback-only HTTP service (Issue #1 D3=B, D7=B):

    GET /healthz      -> {"status": "ok", ...}
    GET /status.json  -> full status snapshot (schema, knowledge, facts,
                         last report, model, environment)
    GET /report       -> the static ``report.html`` (or 503 when it
                         does not exist)

The host is validated by :class:`hve.config.HveConfig` to be
``127.0.0.1`` / ``localhost`` / ``::1`` — the service is not intended
to be reachable from outside Mercury.
"""

from __future__ import annotations

import json
import os
import platform
import socket
from dataclasses import dataclass, asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from ..config import FIVE_WEALTH_DOMAINS, HveConfig
from ..facts import store as facts_mod
from ..kbase import loader as kb
from ..migrations import manager as mig_manager
from ..report import render as report


@dataclass(frozen=True)
class ComponentHealth:
    name: str
    status: str
    detail: str = ""


def _ok(name: str, detail: str = "") -> ComponentHealth:
    return ComponentHealth(name, "ok", detail)


def _warn(name: str, detail: str) -> ComponentHealth:
    return ComponentHealth(name, "warn", detail)


def _fail(name: str, detail: str) -> ComponentHealth:
    return ComponentHealth(name, "fail", detail)


def check(cfg: HveConfig) -> dict[str, Any]:
    """Run all component checks and return a dict (JSON-serializable)."""
    out: dict[str, Any] = {"ok": True, "checks": []}

    def add(c: ComponentHealth) -> None:
        out["checks"].append(asdict(c))
        if c.status == "fail":
            out["ok"] = False

    # 1. database
    try:
        conn = __import__("sqlite3").connect(cfg.db_path)
        cur = conn.execute(
            "SELECT name FROM sqlite_schema WHERE type='table' AND name='schema_migrations'"
        )
        if cur.fetchone() is None:
            add(_fail("db", "schema_migrations missing; run `hve init`"))
        else:
            ver = conn.execute(
                "SELECT MAX(version) FROM schema_migrations"
            ).fetchone()[0]
            integ = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if integ == "ok":
                add(_ok("db", f"schema_v{ver}, integrity ok"))
            else:
                add(_fail("db", f"integrity_check = {integ}"))
        conn.close()
    except Exception as exc:  # noqa: BLE001
        add(_fail("db", f"open error: {exc}"))

    # 2. migrations
    try:
        expected = mig_manager.status_expected(cfg)
        current = mig_manager.current_version(cfg)
        if current == expected:
            add(_ok("migrations", f"v{current}"))
        elif current < expected:
            add(_warn("migrations", f"v{current} < expected v{expected}"))
        else:
            add(_fail("migrations", f"v{current} > expected v{expected}"))
    except Exception as exc:  # noqa: BLE001
        add(_fail("migrations", f"status error: {exc}"))

    # 3. knowledge base directory
    if cfg.knowledge_dir.exists():
        n_files = len(kb.iter_markdown(cfg.knowledge_dir))
        add(_ok("knowledge", f"{n_files} md files in {cfg.knowledge_dir.name}/"))
    else:
        add(_warn("knowledge", f"directory missing: {cfg.knowledge_dir}"))

    # 4. facts (optional in alpha)
    try:
        n_facts = facts_mod.FactsStore(cfg).count()
        add(_ok("facts", f"{n_facts} facts total"))
    except Exception as exc:  # noqa: BLE001
        add(_fail("facts", f"count error: {exc}"))

    # 5. model endpoint (best-effort; may be absent in dev)
    try:
        import urllib.request
        url = cfg.model_endpoint.rstrip("/") + "/models"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=2) as resp:  # noqa: S310
            if 200 <= resp.status < 300:
                add(_ok("model", f"GET {url} -> {resp.status}"))
            else:
                add(_fail("model", f"GET {url} -> {resp.status}"))
    except Exception as exc:  # noqa: BLE001
        add(_warn("model", f"endpoint unreachable (expected in dev): {exc.__class__.__name__}"))

    # 6. last report
    rep = cfg.reports_html
    if rep.exists():
        add(_ok("report", f"{rep} last-modified {rep.stat().st_mtime:.0f}s ago"))
    else:
        add(_warn("report", "no report.html yet; run `hve report generate`"))

    # 7. environment sanity
    add(_ok("env", f"python={platform.python_version()} host={socket.gethostname()} "
                   f"uid={os.getuid()}"))
    if os.getuid() == 0:
        add(_warn("env", "running as root — charter 10.1 rule 2 prefers a service user"))
    return out


def status(cfg: HveConfig) -> dict[str, Any]:
    """Return the richer ``/status.json`` snapshot."""
    rep_md = cfg.reports_md.exists()
    rep_html = cfg.reports_html.exists()
    # Real applied migration data (task item 4 — no placeholder).
    applied = sorted(int(k) for k in mig_manager._applied(cfg).keys())
    expected = mig_manager.status_expected(cfg)
    return {
        "name": "hve-life-os",
        "version": "0.1.0",
        "schema_versions": {
            "applied": applied,
            "expected": expected,
            "synced": applied[-1] == expected if applied and expected else False,
        },
        "domains": {
            d: {
                "knowledge_files": _kb_count_for(cfg, d),
                "top_facts": _top_facts(cfg, d, 3),
            }
            for d in FIVE_WEALTH_DOMAINS
        },
        "reports": {
            "report.md": rep_md,
            "report.html": rep_html,
        },
        "model": {
            "endpoint": cfg.model_endpoint,
            "context_tokens": cfg.model_context_tokens,
        },
        "env": {
            "python": platform.python_version(),
            "host": socket.gethostname(),
            "uid": os.getuid(),
            "http": f"{cfg.http_host}:{cfg.http_port}",
        },
        "health": check(cfg),
    }


def _kb_count_for(cfg: HveConfig, domain: str) -> int:
    try:
        return kb.count(cfg).get(domain, 0)
    except Exception:  # noqa: BLE001
        return 0


def _top_facts(cfg: HveConfig, domain: str, n: int) -> list[dict]:
    try:
        rows = facts_mod.FactsStore(cfg).top(domain, n=n)
        return [
            {
                "category": r.category,
                "subject": r.subject,
                "value": r.value,
                "source": r.source,
                "confidence": r.confidence,
            }
            for r in rows
        ]
    except Exception:  # noqa: BLE001
        return []


# ---------------------------------------------------------------------------
# HTTP layer


class HveRequestHandler(BaseHTTPRequestHandler):
    """Loopback-only request handler.

    The host validation happens at :class:`HveConfig` parse time, so a
    misconfigured ``HVE_HTTP_HOST`` will fail before ``serve()`` is even
    called. This handler itself performs no further host checks — it
    serves whatever the bound socket permits.
    """

    def log_message(self, format: str, *args: Any) -> None:  # type: ignore[override]
        # Default writes to stderr and adds request metadata. We keep it
        # but reduce noise with a compact prefix.
        print(f"[hve] {self.address_string()} {format % args}", flush=True)

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code: int, obj: dict) -> None:
        body = json.dumps(obj, indent=2, default=str).encode("utf-8")
        self._send(code, body, "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        path = self.path
        if path == "/healthz":
            result = check(self.server.hve_config)
            self._send_json(200 if result["ok"] else 503, result)
        elif path == "/status.json":
            self._send_json(200, status(self.server.hve_config))
        elif path in ("/report", "/report.html", "/"):
            p = self.server.hve_config.reports_html
            if not p.exists():
                self._send(503, b"report.html missing; run `hve report generate`\n",
                           "text/plain; charset=utf-8")
                return
            self._send(200, p.read_bytes(), "text/html; charset=utf-8")
        elif path == "/favicon.ico":
            self._send(404, b"", "image/x-icon")
        else:
            self._send(404, b"not found\n", "text/plain; charset=utf-8")


class HveServer(ThreadingHTTPServer):
    """A :class:`ThreadingHTTPServer` that carries the HVE config.

    Using the class rather than a free-standing ``socketserver`` keeps
    the handler's access to :class:`HveConfig` clean.
    """

    daemon_threads = True

    hve_config: HveConfig  # set in __init__

    def __init__(self, addr: tuple[str, int], cfg: HveConfig) -> None:
        super().__init__(addr, HveRequestHandler)
        self.hve_config = cfg


def serve(cfg: HveConfig, *, block: bool = True) -> HveServer:
    """Start the loopback HTTP service.

    ``block=False`` is used from tests: it returns the server after
    binding so the caller may probe it from another thread.
    """
    server = HveServer((cfg.http_host, cfg.http_port), cfg)
    if not block:
        import threading
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
    server._cfg = cfg  # type: ignore[attr-defined]
    return server
