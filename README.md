# HVE Life OS

HVE Life OS is a local-first Personal Sovereignty Operating System. The
project starts on the Mercury Raspberry Pi alpha node and is designed to
remain portable to Ubuntu on Windows and macOS.

## Runtime model

HVE Life OS is built on top of the upstream
[NousResearch Hermes Agent](https://github.com/NousResearch/hermes-agent).
The application repository does not vendor the upstream Hermes source. It
contains the HVE overlay, deployment contract, model profile, and
Mercury-specific changes required to keep the system lean.

```text
Pinned Nous Hermes
        |
        +-- HVE configuration and skills
        +-- llama.cpp OpenAI-compatible endpoint
        +-- Qwen2.5 3B GGUF model
        +-- HVE Life OS application
        |
        +-- Mercury Raspberry Pi alpha
```

## Initial target: Mercury minimum profile

| Component | Alpha choice |
|---|---|
| Hardware | Raspberry Pi 5, 8 GB minimum; 16 GB preferred |
| Inference | `llama.cpp` over a local OpenAI-compatible endpoint |
| Model | Qwen2.5 3B Instruct, `Q4_K_M` GGUF |
| Context | 8,192 tokens |
| Data | Markdown files and SQLite |
| Service manager | systemd |
| Network dependency | None for core operation |

The 8K profile is an intentional portability baseline, not a permanent
product limit.

## Repository layout

```text
HVE_Life_OS_Agent_Organization_Charter_v0.4.md
deployment/
  mercury/
    README.md
    hermes-config.yaml
  manifest.yaml
patches/
  hermes-context-floor.patch
```

## Installation direction

The future installer will:

1. Install a pinned Nous Hermes release or commit.
2. Install or verify the ARM64 `llama.cpp` backend and Qwen GGUF model.
3. Apply the HVE overlay and context-floor compatibility patch when needed.
4. Install HVE Life OS files, services, health checks, and rollback metadata.
5. Run a first-boot smoke test before enabling normal operation.

Do not install from an unpinned upstream branch in production. The exact
upstream revision and model checksum belong in the deployment manifest.

## Portability roadmap

| Target | Status | Direction |
|---|---|---|
| Mercury Raspberry Pi | Alpha | Minimum local profile |
| Ubuntu on Windows | Planned | Reuse Linux installer and service contract |
| macOS | Planned | Reuse overlay and local model API with platform service adapter |

Platform-specific code must remain behind the deployment adapter. SQLite,
Markdown, Hermes interfaces, data contracts, and application behavior should
remain portable.
