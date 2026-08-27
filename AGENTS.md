# AGENTS.md — HVE Life OS (Spark reference deployment)

> **Canonical checkout.** This file is the operating contract for any coding
> agent working in this repository. Read it fully before editing.

## Mission

HVE Life OS is a **local-first Personal Sovereignty Operating System** built as
a pinned overlay on the upstream [NousResearch Hermes
Agent](https://github.com/NousResearch/hermes-agent). It keeps purpose,
judgment, values, data ownership, and direction with the human (Hans), and uses
agents only to accelerate intelligence, analysis, coordination, and execution.
The Five Wealth Framework — Time, Physical, Mental, Social, Financial — is made
visible, measurable, and actionable.

## Active target: DGX Spark (reference)

| Property | Value |
|---|---|
| Host | DGX Spark (`spark-5054`, aarch64, 128 GB unified) |
| Working dir | `/home/hans/humanvalueexchange/workspaces/hvelifeospoc` |
| Deployment root | `~/hve-life-os` — **the only place HVE writes** |
| Inference | **separate, self-contained llama.cpp** (no Ollama) |
| Model | Qwen3.8-2B-Distill `Q4_K_M` GGUF |
| Context | **65536 tokens** (exact) |
| Max output | **1024 tokens** (initial; bounded) |
| Port | **8089** (llama.cpp), **8090** (HVE loopback service) |
| Bind | `127.0.0.1` by default; LAN only on explicit, documented opt-in |

## Hard rules (non-negotiable)

1. **Directory-contained.** Every HVE-owned file — binaries, model, app,
   Python, config, data, backups, logs, skill — lives **inside
   `~/hve-life-os`**. Never write HVE files to `/usr/bin`, `/etc`, `/opt`,
   system Python, or system services.
2. **Ollama is off-limits.** Do not use, link, modify, or depend on Ollama's
   binaries, libraries, models, service, environment, or ports. HVE's llama.cpp
   stack must build and run independently of Ollama. (Ollama may keep running
   for unrelated work; HVE simply does not touch it.)
3. **No system packages added** for the HVE runtime. The Python environment is
   a self-contained venv under `~/hve-life-os`; the CUDA/CPU toolchain used is
   the one already present on the box (gcc/gcmake/make) — not new system
   packages.
4. **Loopback only by default.** A non-loopback bind or an auth-less LAN
   exposure requires a separate, documented, human-approved interface design.
5. **Reversible.** Preserve all Mercury files. Archive or isolate them only via
   reversible repository changes — never delete or irreversibly move data.
6. **Human approves the blast radius.** Hans approves commits, pushes, and any
   destructive or consequential action before it happens.

## What NOT to do

- Do not call `delegate_task` to another agent; keep the work loop in this
  session.
- Do not invent requirements or model metadata. Verify against the artifact and
  the running endpoint.
- Do not expose secrets, credentials, or personal data (charter 10.1 rule 2,
  D5=A).
- Do not `pip install -r /usr/...` or write to system site-packages.
- Do not point the HVE endpoint at an Ollama port or binary.

## Verification gates (run before claiming success)

1. **Independence:** the llama-server process must not link any `libggml-*`
   under `/usr/local/lib/ollama/`; its `LD_LIBRARY_PATH` must not reference
   Ollama; it must not read `OLLAMA_*` env.
2. **Model checksum:** `sha256sum` of the GGUF matches the manifest
   (`4aa0fb13c431514262f259d420ecc95a8714df58ac2a2384514e20b93983f0ff`).
3. **Endpoint:** `GET http://127.0.0.1:8089/v1/models` returns Qwen3.8-2B.
4. **Context:** a request using a large `n_ctx` behaves within 65536; output is
   bounded at 1024.
5. **HVE health:** `hve health --json` reports `ok: true` across db, migrations,
   knowledge, facts, model, report, env.
6. **Skill + response + tool-call smoke:** `hve agent ask` loads the
   `hve-life-os` skill, returns a plain response, and one structured
   tool-call path succeeds.
7. **Git:** `git status` clean-or-expected, `git diff` shown to Hans, and
   **no commit/push until Hans approves the final diff.**

## Layout of the deployment root (`~/hve-life-os`)

```
~/hve-life-os/
  llama.cpp/       separate native llama.cpp build (binaries + libs)
  models/          Qwen3.8-2B-Distill-Q4_K_M.gguf (+sha256, +.sha256)
  app/             HVE application (hve/ package + pyproject)
  env/             self-contained Python venv + `hve` + pytest
  runtime/
    hve.env        HVE_HOME, HVE_MODEL_ENDPOINT, HVE_HERMES_BIN, ports, LAN (off)
    bin/           hve, start.sh, stop.sh, model.sh, health.sh
  hermes-skills/hve-life-os/   skill installed into the named Hermes profile
  data/            HVE_HOME: hve.db (+wal/shm), knowledge/, reports/, backups/
  docs/            runbook-spark.md, rollback-spark.md
  MANIFEST.yaml    pinned: llama.cpp rev, model sha, python, endpoint, context
```

## Status

- **M1** committed (report service, SQLite backup/restore, Mercury units).
- **Spark alpha** = active (this mission).
- **Mercury** = **parked / experimental edge target** (files preserved, isolated).
- See `PROJECT_STATUS.md` for the live task ledger.
