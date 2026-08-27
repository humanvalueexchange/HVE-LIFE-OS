# PROJECT_STATUS.md — HVE Life OS

> Read-only task ledger. Keep this current. Hans is the approver of
> everything that leaves this checkout.

## Mission (current)

Build a **minimum-spec, directory-contained DGX Spark deployment** of HVE Life
OS on a **separate, Ollama-independent native llama.cpp** stack, serving
**Qwen3.8-2B-Distill Q4_K_M** at **65536-token** context, then validate it
end-to-end and prove the same contract can be reused for Linux and
Ubuntu-on-Windows. **Mercury is parked** (files preserved, isolated to
experimental).

## Hard constraints

- Deployment root `~/hve-life-os` is the only place HVE writes.
- No HVE files in `/usr/bin`, `/etc`, `/opt`, system Python, or system tests.
- Ollama is not used, linked, modified, or depended on.
- Loopback only by default; LAN is an explicit opt-in.
- Context = **65536** (exact); initial max output = **1024**.
- Model sha256 = `4aa0fb13c431514262f259d420ecc95a8714df58ac2a2384514e20b93983f0ff`.

## Ledger

| ID | Status | Note |
|---|---|---|
| M1 (report, backup/restore, Mercury units) | committed | HEAD `67a7d38` |
| S0 — repo: AGENTS.md / PROJECT_STATUS.md / manifest | done | Mercury preserved in `experimental/` + `deployment/mercury/` |
| S1 — separate llama.cpp build into `~/hve-life-os` | done | CPU/NEON on GB10; `ldd` clean of Ollama; `127.0.0.1:8089` |
| S2 — model + venv + app + env into `~/hve-life-os` | done | self-contained; checksum `4aa0fb13…` verified |
| S3 — validate: /v1/models, 65536 ctx, 1024 cap | done | against the real process; `n_ctx_slot=65536` in server log |
| S3b — containment + init + leaked-`~/.hve` cleanup | done | `config.py` fix in repo and app; db in `~/hve-life-os/data`; no leak left on disk |
| S4 — report generate | done | report generated into `~/hve-life-os/data/reports/` |
| S4b — HVE health (`hve health --json` → `ok: true`) | done | db, migrations, knowledge, facts, model, report, env all ok |
| S4c — skill + plain response + tool-call smoke | done | `hve agent ask` both paths, real Hermes, `--yolo` for non-TTY approval gate |
| S4d — repo `pytest` | done | 48 passed (installed pytest into the HVE venv only) |
| S4e — launcher (`hve-tui`) | done | Bash shebang intact; canonical source now `runtime/bin/hve-tui` (repo) |
| S4f — interactive TUI v1 exchange (fresh shell) | done | launched `hve-tui`, skill preloaded, exchange OK, cleaned exit |
| S5 — git diff + status + final report to Hans | **awaiting approval** | this presentation; no commit/push |
| Mercury (node integration, M2-01) | **parked** | experimental edge target |

## Alpha v1 — interactive confirmation (2026-08-25)

Observed successful interactive v1 test: `hve-tui` from a fresh shell — the
launcher confirmed the model endpoint already up, refreshed the `hve-alpha`
Hermes profile + `hve-life-os` skill from this repo, opened the TUI with
context 65,536 / initial output 1,024; a plain exchange against
`127.0.0.1:8089/v1` succeeded; TUI exited cleanly without leaving processes.
`hve-tui --health` reports `ok: true`.

## Open / known issues (only genuinely unresolved)

- **Qwen3.8 model fence quirk** (from Honcho deriver, Aug 22): the model
  wraps strict-JSON output in ` ``` ` fences despite `format:"json"`.
  Fix = strip fences + tighten prompt in `hve/agent/ask.py`. Awaiting
  Hans's authorization — not yet implemented.
- **Commit approval:** this diff has not been committed or pushed; Hans is
  the approver (AGENTS.md rule 6).

## Safety notes

- Never read/print/commit secrets. `.env` and credential files stay out.
- Personal data lives in `~/hve-life-os/data/knowledge/`, **never in Git**.
- Rollback = restore prior release + (optionally) prior SQLite snapshot
  (`--i-understand`). See `docs/rollback-spark.md`.

