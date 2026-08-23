"""HVE Life OS — canonical CLI.

The single entry point for operators and for the Hermes skill.

Commands (alpha scope):

    hve init               Create directories, run migrations, seed facts
    hve status             Human-readable status
    hve status --json      Machine-readable status
    hve report generate    Render report.md + report.html (idempotent)
    hve report --force     Force regeneration even if unchanged
    hve health             Run all component checks
    hve health --json      Machine-readable checks
    hve agent ask P        Invoke the Hermes CLI via the HVE skill
    hve db backup          Snapshot SQLite (D10=B)
    hve db restore SP      Restore a snapshot (D10=B; --i-understand required)

All commands are safe to run as the ``hve`` service user (D6=B) and use
no network egress. The service itself (``hve serve``) is started by
systemd; the CLI is for operators.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from .config import HveConfig, load as load_config
from .db import backup_db, restore_db, ensure_schema
from .facts import store as facts_mod
from .kbase import loader as kb
from .report import render as report_render
from .serve import health as hve_health
from .agent import ask as agent_ask
from .migrations import manager as mig_manager


def _epilog() -> str:
    return (
        "HVE Life OS — local-first Personal Sovereignty Operating System.\n"
        "Mercury alpha. No cloud dependency. Run as the `hve` service user.\n"
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="hve",
        description="HVE Life OS CLI (Mercury alpha).",
        epilog=_epilog(),
        add_help=False,
    )
    p.add_argument("-h", "--help", action="help",
                   help="show this help message and exit")
    p.add_argument("--version", action="store_true",
                   help="print version and exit")

    sub = p.add_subparsers(dest="command", metavar="<command>")

    # init
    p_init = sub.add_parser("init", help="Create directories, run migrations, seed facts")
    p_init.add_argument("--dry-run", action="store_true",
                        help="Show what would be applied, do not write")

    # status
    p_status = sub.add_parser("status", help="Show HVE status")
    p_status.add_argument("--json", action="store_true",
                          help="Emit JSON")

    # report
    p_report = sub.add_parser("report", help="Generate the report files")
    p_report.add_argument("action", nargs="?", default="generate",
                          choices=["generate", "path"])
    p_report.add_argument("--force", action="store_true",
                          help="Regenerate even if unchanged")

    # health
    p_health = sub.add_parser("health", help="Run all component health checks")
    p_health.add_argument("--json", action="store_true",
                          help="Emit JSON")

    # agent
    p_agent = sub.add_parser("agent", help="Interact with the local Hermes CLI")
    p_agent.add_argument("command", nargs="?", default="ask",
                         choices=["ask"])
    p_agent.add_argument("prompt", nargs="?", default=None)
    p_agent.add_argument("--session", default=None,
                         help="Session id to tag the interaction with")
    p_agent.add_argument("--bin", default=None,
                         help="Explicit path to the hermes binary")
    p_agent.add_argument("--timeout", type=int, default=600,
                         help="Subprocess timeout (seconds)")
    p_agent.add_argument("--list-recent", type=int, default=None,
                         help="Show the N most recent interactions and exit")

    # db
    p_db = sub.add_parser("db", help="Back up / restore the SQLite database")
    p_db.add_argument("action", nargs="?", default="status",
                      choices=["backup", "restore", "status", "version"])
    p_db.add_argument("snapshot", nargs="?", default=None,
                      help="Path to a snapshot to restore (for `restore`)")
    p_db.add_argument("--i-understand", action="store_true",
                      help="REQUIRED for `restore`. Acknowledges that the "
                           "current DB will be moved aside and replaced.")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else None)

    if getattr(args, "version", False):
        print("hve 0.1.0 (Mercury alpha)")
        return 0

    if not args.command:
        parser.print_help()
        return 1

    cfg = load_config()

    if args.command == "init":
        return cmd_init(cfg, dry_run=args.dry_run)

    if args.command == "status":
        return cmd_status(cfg, as_json=args.json)

    if args.command == "report":
        return cmd_report(cfg, action=args.action, force=args.force)

    if args.command == "health":
        return cmd_health(cfg, as_json=args.json)

    if args.command == "agent":
        return cmd_agent(cfg, args)

    if args.command == "db":
        return cmd_db(cfg, args)

    # Unreachable: subparser choices guarantee a known command.
    parser.print_help()
    return 1


# ---------------------------------------------------------------------------
# Command implementations


def cmd_init(cfg: HveConfig, dry_run: bool) -> int:
    applied = ensure_schema(cfg, dry_run=dry_run)
    if dry_run:
        if not applied:
            print("up-to-date (nothing to apply)")
        else:
            for ver, name in applied:
                print(f"would apply v{ver} {name}")
        return 0
    if not applied:
        print("database already at latest schema")
    else:
        for ver, name in applied:
            print(f"applied v{ver} {name}")
    # Seed placeholder facts only when the DB is empty (D5=A).
    inserted = facts_mod.seed_defaults(cfg)
    print(f"facts seeded: {inserted}")
    # Ingest knowledge files (placeholders live in ~/.hve/knowledge in prod;
    # the repo's knowledge_base/ is the *template* — copy via hve init
    # --seed on first run, or hand-edit ~/.hve/knowledge/*.md after deploy).
    try:
        res = kb.upsert(cfg)
        print(f"knowledge upserted: {res['upserted']} files "
              f"(skipped {res['skipped_general']} 'general' files)")
    except Exception as exc:  # noqa: BLE001
        print(f"knowledge upsert skipped: {exc}")
    print(f"home={cfg.home}\ndb={cfg.db_path}")
    return 0


def cmd_status(cfg: HveConfig, as_json: bool) -> int:
    if as_json:
        print(json.dumps(hve_health.status(cfg), indent=2, default=str))
        return 0 if hve_health.check(cfg)["ok"] else 2
    print(f"HVE Life OS status — {cfg.home}")
    print()
    print(f"  schema     : v{mig_manager.current_version(cfg)} "
          f"(expected v{mig_manager.status_expected(cfg)})")
    try:
        n = facts_mod.FactsStore(cfg).count()
    except Exception:  # noqa: BLE001
        n = -1
    print(f"  facts      : {n}")
    try:
        counts = kb.count(cfg)
        for d in sorted(counts):
            print(f"  knowledge  : {d} = {counts[d]} file(s)")
    except Exception:  # noqa: BLE001
        pass
    print(f"  report.md  : {'present' if cfg.reports_md.exists() else 'missing'}")
    print(f"  report.html: {'present' if cfg.reports_html.exists() else 'missing'}")
    print(f"  http       : {cfg.http_host}:{cfg.http_port} (loopback-only)")
    return 0


def cmd_report(cfg: HveConfig, action: str, force: bool) -> int:
    if action == "path":
        print(cfg.reports_html)
        return 0
    if not cfg.reports_dir.exists() and not force:
        # Still generate; idempotent path handles the "no change" case.
        pass
    res = report_render.generate(cfg, force=force)
    print(f"report: generated_at={res['generated_at']}")
    for name, wrote in res["wrote"].items():
        print(f"  {name}: {'written' if wrote else 'unchanged'}")
    print(f"  report.md   : {cfg.reports_md}")
    print(f"  report.html : {cfg.reports_html}")
    return 0


def cmd_health(cfg: HveConfig, as_json: bool) -> int:
    result = hve_health.check(cfg)
    if as_json:
        print(json.dumps(result, indent=2, default=str))
        return 0 if result["ok"] else 1
    print(f"overall: {'OK' if result['ok'] else 'DEGRADED'}")
    for c in result["checks"]:
        mark = {"ok": "✓", "warn": "!", "fail": "✗"}[c["status"]]
        print(f"  [{mark}] {c['name']:<12}  {c['detail']}")
    return 0 if result["ok"] else 1


def cmd_agent(cfg: HveConfig, args: argparse.Namespace) -> int:
    if args.list_recent is not None:
        for r in agent_ask.recent(cfg, args.list_recent):
            print(f"  {r['created_at']}  {r['session_id'][:8]}  {r['prompt'][:60]}")
        return 0
    if args.prompt is None:
        # Read from stdin when no positional prompt given.
        if sys.stdin.isatty():
            print("error: provide a prompt (positional) or pipe one to stdin")
            return 2
        args.prompt = sys.stdin.read().strip()
    if not args.prompt:
        print("error: empty prompt")
        return 2
    try:
        res = agent_ask.ask(
            cfg,
            args.prompt,
            hermes_bin=args.bin,
            session_id=args.session,
            timeout_s=args.timeout,
        )
    except agent_ask.AgentError as exc:
        print(f"agent: {exc}", file=sys.stderr)
        return 1
    print(res.response)
    return 0


def cmd_db(cfg: HveConfig, args: argparse.Namespace) -> int:
    if args.action == "version":
        print(f"schema_v{mig_manager.current_version(cfg)}")
        return 0
    if args.action == "status":
        applied = mig_manager._applied(cfg)
        for v in sorted(applied):
            name, chk = applied[v]
            print(f"  v{v}  {name}  {chk[:12]}..")
        return 0
    if args.action == "backup":
        dest = backup_db(cfg)
        print(f"backup: {dest}")
        return 0
    if args.action == "restore":
        if args.snapshot is None:
            print("error: provide snapshot path", file=sys.stderr)
            return 2
        if not args.i_understand:
            print("error: --i-understand is required for restore. "
                  "The current DB will be moved aside (preserved) and "
                  "replaced by the snapshot.", file=sys.stderr)
            return 2
        preserved = restore_db(cfg, Path(args.snapshot), confirm=True)
        print(f"restored. preserved prior db at: {preserved}")
        return 0
    print(f"unknown db action: {args.action}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
