# HVE Life OS Project Status

Last verified: 2026-08-23

## Canonical project

- Repository: `https://github.com/humanvalueexchange/HVE-LIFE-OS`
- Deployment repository, distinct from `hve-knowledge-and-operations`.
- Default branch: `main`

## Active objective

Deploy HVE Life OS on an Ubuntu laptop with an AMD CPU, 32 GB system RAM,
and an NVIDIA RTX 4070 laptop GPU with 8 GB VRAM. The preferred runtime is
native CUDA-enabled llama.cpp with Qwen3.8-2B Q4_K_M at a truthful 64K context.

## Host map

| Host | Role | Current status |
|---|---|---|
| Mercury | Raspberry Pi 5 edge node with AI HAT+ 2 | Qwen3.8-2B via CPU llama.cpp works at 32K but is too slow for interactive Hermes |
| Spark | DGX Spark model and inference host | Not the target for the laptop deployment |
| Ubuntu laptop | Primary Hermes/HVE Life OS target | Deployment installer still needed |

## Mercury findings

- Mercury's current llama.cpp service can load Qwen3.8-2B at 32K.
- Hermes can be allowed below its 64K default using the Mercury-specific
  `HERMES_MINIMUM_CONTEXT_LENGTH` overlay, but the 32K CPU path is too slow.
- The AI HAT+ 2 should not be assumed to accelerate arbitrary GGUF files;
  Hailo-compatible HEF models use a separate runtime and model pipeline.

## Laptop deployment requirements

- Use a separate Ubuntu deployment adapter; do not run the ARM64 Mercury installer.
- Verify NVIDIA driver, CUDA capability, RAM, disk, and model checksum.
- Configure llama.cpp with GPU offload, Flash Attention, one active slot, and
  a bounded output token budget.
- Configure Hermes with `model.context_length: 65536` only after the backend
  reports a 65536-token context.
- Keep the service localhost-only by default, with explicit LAN opt-in.
- Include health checks, inference smoke tests, and rollback metadata.

## Command discipline

Every operational command must name its execution host and verify actual
hostnames, IP addresses, users, paths, and service names before use.
