# HVE Life OS

HVE Life OS is a local-first Personal Sovereignty OS built on the Five
Wealth Framework: **Time, Physical, Mental, Social, and Financial** wealth.
It keeps personal data and the core interaction loop local while making
wealth visible, measurable, and actionable.

## Current Alpha v1 target

The active reference deployment is the directory-contained DGX Spark runtime:

```text
/home/hans/hve-life-os/
├── app/       # HVE application checkout used by the runtime
├── data/      # SQLite, knowledge, reports, logs, and backups
├── models/    # verified local GGUF artifact
├── runtime/   # environment and operator launchers
└── src/       # native llama.cpp build
```

This Git repository is the source and deployment contract. It is separate
from the reference runtime directory; editing this checkout does not change
the live runtime.

## Runtime contract

| Component | Current contract |
|---|---|
| Host | DGX Spark reference deployment (aarch64) |
| Inference | Native `llama.cpp`, CPU/NEON; **not CUDA** |
| Model | `Qwen3.8-2B-Distill-Q4_K_M` GGUF |
| Model SHA-256 | `4aa0fb13c431514262f259d420ecc95a8714df58ac2a2384514e20b93983f0ff` |
| Context | Exactly `65536` tokens |
| Initial output cap | `1024` tokens |
| Model endpoint | `http://127.0.0.1:8089/v1` |
| HVE HTTP service | `http://127.0.0.1:8090` |
| Persistence | SQLite and Markdown under `HVE_HOME` |
| Network policy | Loopback-only; no cloud dependency |
| Ollama | Prohibited/off-limits; not a dependency |

See [`deployment/manifest.yaml`](deployment/manifest.yaml) and
[`docs/architecture-spark.md`](docs/architecture-spark.md) for the
machine-readable and narrative contracts.

## Architecture

```text
Hermes profile (hve-alpha)
        │ hve-life-os skill
        ▼
HVE CLI / operator TUI ───────► HVE HTTP service :8090
        │                              │
        │ local OpenAI-compatible      ├── healthz / status.json / report
        ▼                              ▼
native llama.cpp :8089          SQLite + Five Wealth data
        │
Qwen3.8-2B-Distill-Q4_K_M
```

The HVE skill is the canonical interaction path. The reference runtime
supports health checks, the local model endpoint, the HVE service, Hermes
skill/plain/tool-call paths, and an operator TUI. The repository itself
contains the HVE CLI/service and skill contract; runtime-only launchers are
kept under `/home/hans/hve-life-os/runtime/bin/`.

## Quick start on the reference runtime

Run these commands on the DGX Spark host, from the reference directory:

```bash
cd /home/hans/hve-life-os
source runtime/hve.env
runtime/bin/start-model.sh
runtime/bin/start-hve.sh
runtime/bin/hve-tui --health
curl -s http://127.0.0.1:8090/healthz
curl -s http://127.0.0.1:8090/status.json
```

Use `runtime/bin/hve-tui --smoke` for the local model plus HVE smoke path, or
run `runtime/bin/hve-tui` for the interactive operator TUI. These launchers
must remain loopback-only and must not be replaced with Ollama.

## Repository layout

```text
AGENTS.md                         contributor and safety guardrails
deployment/manifest.yaml          active Alpha v1 runtime contract
docs/architecture-spark.md        active architecture and roadmap
PROJECT_STATUS.md                 current project status
hve/                              HVE application and HTTP service
hermes-skills/hve-life-os/        canonical Hermes skill
knowledge_base/                   non-personal Five Wealth templates
tests/                            repository test suite
deployment/mercury/               parked/experimental historical artifacts
service/                          parked legacy Mercury service templates
```

## Product direction

The primary user experience is a local-first website/PWA. The CLI and TUI
remain operator and power-user surfaces. Statoshi.info is dashboard
UX/information-architecture inspiration, not a runtime dependency.

Planned workflow:

1. Contextual right-side dashboard chat.
2. Advisor Teams transcript → reviewed Excel collector.
3. Client import preview with consent and provenance.
4. Local Five Wealth data workflow and scorecard.

Excel trackers are initial scorecard and client-discovery interchange
models, not a replacement for the local data store.

## Mercury status

Mercury Raspberry Pi artifacts are **parked/experimental**. Their files and
technical history remain in the repository for reference, rollback, and
future edge-adapter work; they are not the current Alpha v1 target. See
[`deployment/mercury/README.md`](deployment/mercury/README.md),
[`docs/runbook-mercury.md`](docs/runbook-mercury.md), and
[`docs/rollback-mercury.md`](docs/rollback-mercury.md).

## Development

The project has no build system or deployment installer in this repository.
When Python test dependencies are available, run the existing suite with:

```bash
python3 -m pytest -q
```

Do not commit personal data, credentials, model artifacts, or live runtime
state. Do not commit or push changes made while reviewing the reference
deployment.
