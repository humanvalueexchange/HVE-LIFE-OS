"""Report renderer: ``report.md`` + static ``report.html``.

Design (Issue #1 D3=B + D9=B):

* :func:`generate` is *idempotent* — if the on-disk report already
  matches the current state it is not rewritten (preserving
  ``mtime``). The hourly systemd timer (D9) calls this path on every
  tick.
* Output is self-contained (inline CSS, no external assets, no JS).
* Only placeholders / structured facts / knowledge titles appear — no
  raw personal knowledge text is inlined, only a *count* per domain
  and the first 3 facts, to keep the HTML small for local-first operation.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from ..config import FIVE_WEALTH_DOMAINS, HveConfig
from ..facts import store as facts_mod
from ..kbase import loader as kb


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _title_for(domain: str) -> str:
    # "time_wealth" -> "Time Wealth"; "financial_wealth" -> "Financial Wealth"
    title = domain.replace("_wealth", " Wealth").replace("_", " ")
    # Title-case the domain words ("time wealth" -> "Time Wealth").
    return " ".join(w.capitalize() for w in title.split())


@dataclass(frozen=True)
class ReportInput:
    now: str
    facts_by_domain: dict[str, list[facts_mod.Fact]]
    knowledge_by_domain: dict[str, int]
    schema_version: int
    model: dict


def _gather(cfg: HveConfig) -> ReportInput:
    store = facts_mod.FactsStore(cfg)
    facts_by_domain: dict[str, list[facts_mod.Fact]] = {}
    for domain in FIVE_WEALTH_DOMAINS:
        facts_by_domain[domain] = store.top(domain, n=3)
    knowledge_by_domain = _kb_counts(cfg)
    from ..migrations import manager
    return ReportInput(
        now=_ts(),
        facts_by_domain=facts_by_domain,
        knowledge_by_domain=knowledge_by_domain,
        schema_version=manager.current_version(cfg),
        model={
            "name": cfg.model_name,
            "backend": cfg.model_backend,
            "context_tokens": cfg.model_context_tokens,
            "max_output_tokens": cfg.model_max_output_tokens,
            "endpoint": cfg.model_endpoint,
            "checksum": cfg.model_checksum,
        },
    )


def _kb_counts(cfg: HveConfig) -> dict[str, int]:
    try:
        return kb.count(cfg)
    except Exception:
        return {d: 0 for d in FIVE_WEALTH_DOMAINS}


def render_md(inp: ReportInput) -> str:
    out: list[str] = []
    out.append("# HVE Life OS — Five Wealth Report")
    out.append("")
    out.append(f"Generated: {inp.now}")
    out.append(f"Schema version: {inp.schema_version}")
    out.append(f"Model: {inp.model['name']} — {inp.model['context_tokens']} tokens — "
               f"initial output cap {inp.model['max_output_tokens']} — "
               f"SHA-256 `{inp.model['checksum'][:12]}…`")
    out.append(f"Backend: {inp.model['backend']} — {inp.model['endpoint']}")
    out.append("")
    for domain in FIVE_WEALTH_DOMAINS:
        title = _title_for(domain)
        n = inp.knowledge_by_domain.get(domain, 0)
        facts = inp.facts_by_domain.get(domain) or []
        out.append(f"## {title}")
        out.append("")
        out.append(f"Knowledge files: **{n}** (placeholders)")
        if facts:
            out.append("")
            out.append("| Subject | Value | Source | Confidence |")
            out.append("|---|---|---|---:|")
            for f in facts:
                out.append(
                    f"| {f.subject} | {f.value} | `{f.source}` | {f.confidence:.2f} |"
                )
        else:
            out.append("")
            out.append("_No facts recorded for this domain yet._")
        out.append("")
    out.append("---")
    out.append("")
    out.append("HVE Life OS — local-first Personal Sovereignty Operating System. "
               "No cloud or Ollama dependency. DGX Spark Alpha v1 reference.")
    out.append("")
    return "\n".join(out)


def render_html(inp: ReportInput) -> str:
    cards: list[str] = []
    for domain in FIVE_WEALTH_DOMAINS:
        title = _title_for(domain)
        n = inp.knowledge_by_domain.get(domain, 0)
        facts = inp.facts_by_domain.get(domain) or []
        if facts:
            rows = "".join(
                f"<tr><td>{_esc(f.subject)}</td><td>{_esc(f.value)}</td>"
                f"<td><code>{_esc(f.source)}</code></td><td>{f.confidence:.2f}</td></tr>"
                for f in facts
            )
            body = (f"<table><thead><tr><th>Subject</th><th>Value</th>"
                    f"<th>Source</th><th>Conf</th></tr></thead>"
                    f"<tbody>{rows}</tbody></table>")
        else:
            body = "<p class='muted'>No facts yet.</p>"
        cards.append(
            f"<section class='card'><h2>{_esc(title)}</h2>"
            f"<p class='muted'>Knowledge files: {n}</p>{body}</section>"
        )
    cards_html = "\n".join(cards)
    model_line = (
        f"{_esc(inp.model['name'])} · {inp.model['context_tokens']} tokens · "
        f"initial output cap {inp.model['max_output_tokens']} · "
        f"SHA-256 <code>{_esc(inp.model['checksum'])}</code> · "
        f"{_esc(inp.model['backend'])} · <code>{_esc(inp.model['endpoint'])}</code>"
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>HVE Life OS — Five Wealth Report</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root {{ color-scheme: light dark; }}
body {{ font: 16px/1.5 -apple-system, "Segoe UI", Roboto, sans-serif;
       margin: 2rem auto; max-width: 72rem; padding: 0 1rem; }}
h1 {{ margin-top: 0.5rem; }}
.meta {{ color: #888; font-size: 0.9rem; }}
.card {{ border: 1px solid #ddd; border-radius: 8px; padding: 1rem;
        margin-bottom: 1rem; }}
.card h2 {{ margin-top: 0.35rem; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 0.5rem; }}
th, td {{ border-bottom: 1px solid #eee; padding: 0.35rem 0.5rem;
         text-align: left; }}
.muted {{ color: #888; font-size: 0.9rem; }}
footer {{ margin-top: 2rem; color: #888; font-size: 0.85rem; }}
</style>
</head>
<body>
<h1>HVE Life OS — Five Wealth Report</h1>
<p class="meta">Generated {inp.now} · Schema v{inp.schema_version} ·
{model_line}</p>
{cards_html}
<footer>HVE Life OS — local-first Personal Sovereignty Operating System.
DGX Spark Alpha v1 reference. No cloud or Ollama dependency.</footer>
</body>
</html>
"""


def _esc(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def generate(cfg: HveConfig, *, force: bool = False) -> dict:
    """Render and (re)write ``report.md`` + ``report.html`` if changed.

    Idempotent (D9): when the content hash matches the on-disk files,
    no write occurs. Returns a small summary dict for the CLI / health.
    """
    inp = _gather(cfg)
    md = render_md(inp).encode("utf-8")
    html = render_html(inp).encode("utf-8")
    md_hash = _sha256_bytes(md)
    html_hash = _sha256_bytes(html)

    cfg.reports_dir.mkdir(parents=True, exist_ok=True)
    wrote = {"report.md": False, "report.html": False}
    for name, data in (("report.md", md), ("report.html", html)):
        target = cfg.reports_dir / name
        if not force and target.exists() and target.read_bytes() == data:
            continue
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(target)
        wrote[name] = True
    return {
        "generated_at": inp.now,
        "wrote": wrote,
        "md_sha256": md_hash[:12],
        "html_sha256": html_hash[:12],
        "schema_version": inp.schema_version,
    }
