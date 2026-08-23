# HVE Life OS Agent Guardrails

## Repository identity

- Canonical repository: `https://github.com/humanvalueexchange/HVE-LIFE-OS`
- This repository is the HVE Life OS deployment and application repository.
- `hve-knowledge-and-operations` is the separate HVE knowledge and coordination repository.

## Before giving or running commands

1. Verify the repository with `git remote -v`.
2. Verify the target machine explicitly: Mercury, Spark, or Ubuntu laptop.
3. Verify the target user, source path, destination path, and service name.
4. Inspect `PROJECT_STATUS.md` and the relevant deployment manifest.
5. Never infer a hostname, IP address, model path, or architecture from another machine.

## Current deployment boundaries

- Mercury is the Raspberry Pi edge node.
- Spark is the DGX host.
- The Ubuntu laptop is a separate primary Hermes deployment target.
- Commands for one target must not be presented as commands for another target.

## Change safety

- Keep model context claims truthful; do not advertise 64K unless the backend is configured and verified at 64K.
- Preserve a rollback copy before changing systemd units or model configuration.
- Bind services to localhost by default; LAN exposure must be an explicit opt-in.
- Do not commit credentials, tokens, private keys, or personal data.
