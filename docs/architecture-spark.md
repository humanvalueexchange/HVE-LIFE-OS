# HVE Life OS Alpha v1 — DGX Spark Architecture

## Status

This is the active architecture for the directory-contained reference
deployment at `/home/hans/hve-life-os`. Mercury Raspberry Pi is
parked/experimental and is documented separately for historical context.

## Runtime boundaries

```text
/home/hans/hve-life-os/
├── app/       HVE Python application
├── data/      HVE_HOME: database, knowledge, reports, logs, backups
├── models/    Qwen3.8-2B-Distill-Q4_K_M.gguf
├── runtime/   env file and operator launchers
└── src/       native llama.cpp build
```

Hermes runs through the `hve-alpha` profile and the `hve-life-os` skill.
The HVE service and model server bind to loopback:

```text
Hermes → HVE skill/CLI → llama.cpp OpenAI-compatible API :8089
                         HVE HTTP service                 :8090
                         SQLite + Markdown under HVE_HOME
```

## Runtime contract

- Backend: native `llama.cpp` CPU/NEON; CUDA is not used.
- Model: `Qwen3.8-2B-Distill-Q4_K_M` GGUF.
- Artifact SHA-256:
  `4aa0fb13c431514262f259d420ecc95a8714df58ac2a2384514e20b93983f0ff`.
- Context: exactly `65536` tokens.
- Initial output cap: `1024` tokens.
- Model endpoint: `http://127.0.0.1:8089/v1`.
- HVE endpoint: `http://127.0.0.1:8090`.
- Ollama is prohibited/off-limits and is not a dependency.
- HVE data remains under the reference directory via `HVE_HOME`; no cloud
  service is required for core operation.

## Verified Alpha v1 surfaces

The reference runtime has verified:

- contained `HVE_HOME` paths;
- HVE health and status checks;
- the local model endpoint;
- the loopback HVE HTTP service;
- Hermes skill, plain, and tool-call paths;
- the operator TUI.

This repository contains the HVE application and skill contract. Runtime-only
launchers and the deployed model build remain under `/home/hans/hve-life-os`.

## Product roadmap

The primary experience is a local-first website/PWA. The CLI/TUI remains the
operator and power-user surface while the PWA is developed. Statoshi.info is
inspiration for dashboard information architecture, not a dependency.

Planned workflow:

1. Add contextual right-side dashboard chat.
2. Convert advisor Teams transcripts into a reviewed Excel collector.
3. Present a client import preview with consent and provenance.
4. Import approved data into the local Five Wealth workflow.

Excel trackers are initial scorecard and client-discovery interchange
models; they are not the source of truth.
