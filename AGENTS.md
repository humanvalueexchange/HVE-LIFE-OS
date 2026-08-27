# HVE Life OS Agent Guardrails

## Repository identity

- Canonical repository: `https://github.com/humanvalueexchange/HVE-LIFE-OS`
- This repository is the HVE Life OS deployment and application repository.
- `hve-knowledge-and-operations` is the separate HVE knowledge and coordination repository.

## Before giving or running commands

1. Verify the repository with `git remote -v`.
2. Verify the target machine explicitly. The active reference target is DGX
   Spark; Mercury is parked/experimental.
3. Verify the target user, source path, destination path, and service name.
4. Inspect `PROJECT_STATUS.md` and the relevant deployment manifest.
5. Never infer a hostname, IP address, model path, or architecture from another machine.

## Current deployment boundaries

- The active reference deployment is DGX Spark at `/home/hans/hve-life-os`.
- Mercury Raspberry Pi is parked/experimental; its artifacts are historical.
- Commands for one target must not be presented as commands for another target.
- The reference runtime uses native `llama.cpp` CPU/NEON, not CUDA.
- HVE uses no Ollama dependency; Ollama is prohibited/off-limits.
- Keep runtime data directory-contained under `HVE_HOME`.

## Change safety

- The Spark reference contract is exactly 65536 context tokens and an initial
  1024-token output cap. Do not generalize that contract to unverified hosts.
- Preserve a rollback copy before changing systemd units or model configuration.
- Bind services to localhost by default; LAN exposure must be an explicit opt-in.
- Do not commit credentials, tokens, private keys, or personal data.
