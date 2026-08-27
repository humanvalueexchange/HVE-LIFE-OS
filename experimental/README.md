# Experimental / Parked targets

Mercury is now a **parked, experimental edge target** for HVE Life OS. It is NOT the active release; the active reference is the DGX Spark.

## What is preserved (reversible, nothing deleted)

All Mercury originals are left in place:

- `deployment/mercury/` — Mercury overlay, Mercury-node vendor tree, config.
- `docs/runbook-mercury.md`, `docs/rollback-mercury.md`, `docs/m2-backlog.md`.
- `service/hve-*.service` and `service/hve-*.timer` (Mercury-shaped units).
- `patches/hermes-context-floor.patch` (Mercury 8K context-floor opt-in).

This directory is a **pointer and status marker**, not a copy of those files. Nothing here removes or rewrites the originals.

## How to re-activate Mercury (later)

1. Restore the Mercury deployment manifest values (Qwen2.5-3B, 8K, `/opt/mercury/models`) in `deployment/manifest.yaml` under `targets.mercury` as `alpha`.
2. Re-enable `patches/hermes-context-floor.patch` (`HERMES_MINIMUM_CONTEXT_LENGTH=8192`) only if the chosen upstream revision still enforces a 64K minimum.
3. Re-point the HVE model endpoint at the Mercury llama.cpp (loopback) service.
4. Follow `docs/runbook-mercury.md` for user/units/rollback on that host.

## Safety invariants honored while parking

- No Mercury file was deleted or irreversibly moved.
- No system package or system service was created, modified, or removed.
- Ollama was not touched (not in the HVE dependency graph).