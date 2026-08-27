# HVE Life OS Project Status

Last reviewed: 2026-08-26

## Canonical project

- Repository: `https://github.com/humanvalueexchange/HVE-LIFE-OS`
- Product: local-first Personal Sovereignty OS
- Framework: Five Wealth — Time, Physical, Mental, Social, Financial
- Active reference root: `/home/hans/hve-life-os`
- Deployment shape: directory-contained on DGX Spark

## Active Alpha v1 runtime

| Component | Current state |
|---|---|
| Host | DGX Spark reference deployment |
| Backend | Native `llama.cpp` CPU/NEON, not CUDA |
| Model | `Qwen3.8-2B-Distill-Q4_K_M` |
| SHA-256 | `4aa0fb13c431514262f259d420ecc95a8714df58ac2a2384514e20b93983f0ff` |
| Context | Exactly 65536 tokens |
| Initial output cap | 1024 tokens |
| Model API | `127.0.0.1:8089` |
| HVE API | `127.0.0.1:8090` |
| Data | `HVE_HOME`-contained SQLite, Markdown, reports, logs, backups |
| Ollama | Prohibited/off-limits |

The reference runtime has verified health checks, a local model endpoint, the
HVE service, Hermes skill/plain/tool-call paths, and an operator TUI. The
reference runtime is separate from this Git checkout; this repository does
not claim to contain the runtime-only TUI launcher.

## Repository verification boundary

This checkout contains the HVE application, skill, deployment contract,
knowledge templates, legacy Mercury artifacts, and existing tests. It
currently collects 48 tests when the repository's pytest dependency is
available. A 60-test result is not claimed here because 60 tests are not
present in this checkout.

## Product direction

The primary UX is a local-first website/PWA. The CLI/TUI remains available
for operators and power users. Statoshi.info is dashboard
UX/information-architecture inspiration only.

Planned next workflow:

- contextual right-side dashboard chat;
- advisor Teams transcript → reviewed Excel collector;
- client import preview, consent, and provenance;
- local Five Wealth data workflow.

Excel trackers are initial scorecard and client-discovery interchange
models.

## Mercury

Mercury Raspberry Pi is **parked/experimental**, not the active target.
Historical deployment, rollback, Mercury Node, and context-floor artifacts
are intentionally preserved under `deployment/mercury/`, `docs/*mercury*`,
and the parked service templates. They must not be read as current Spark
deployment instructions.

## Uncertainties

- The reference runtime is outside this repository and is not modified by
  documentation changes here.
- Systemd units in `service/` describe the parked Mercury layout; the
  directory-contained Spark launchers are runtime-owned and are not generated
  by this repository.
