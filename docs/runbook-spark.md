# HVE Life OS — DGX Spark Runbook (active alpha)

Audience: Hans (operator) and the Spark deployment loop. This is the single
source of truth for day-to-day operation on the **DGX Spark** reference target.
Mercury is parked (see `experimental/`). This runbook never touches Ollama.

## Top-line contract

```
┌──────────────────────┐     ┌────────────────────────────┐     ┌──────────────────────────┐
│  hve-tui (launcher)  │     │  HVE service (loopback)    │     │  native llama.cpp       │
│  + Hermes TUI        │────►│  127.0.0.1:8090           │────►│  127.0.0.1:8089 /v1     │
│  (profile hve-alpha, │     │  /healthz /status.json    │     │  Qwen3.8-2B-Distill     │
│   skill hve-life-os) │     │  /report                  │     │  ctx=65536 out=1024     │
└──────────────────────┘     └────────────────────────────┘     └──────────────────────────┘
        (Ollama NOT used anywhere in the HVE stack)
```

Deployment root `~/hve-life-os` is the ONLY place HVE writes.

| Property | Value |
|---|---|
| Host | DGX Spark (aarch64, 128 GB unified) |
| Root | `~/hve-life-os` |
| Model | Qwen3.8-2B-Distill Q4_K_M, sha256 `4aa0fb13c431514262f259d420ecc95a8714df58ac2a2384514e20b93983f0ff` |
| Backend | separate native llama.cpp (CPU/NEON; no Ollama, no CUDA) |
| Context | 65536 (exact) |
| Max output | 1024 (initial) |
| Model endpoint | `http://127.0.0.1:8089/v1` (llama.cpp) |
| HVE service | `127.0.0.1:8090` loopback only |
| Python | self-contained venv `~/hve-life-os/env` |

## 1. Independence from Ollama (verifiable)

HVE's llama.cpp is a separate build under `~/hve-life-os/src/build` and is
linked only against system libc/curl/openssl. Ollama must not appear anywhere
in its runtime:

```
ldd ~/hve-life-os/src/build/bin/llama-server | grep -i ollama   # expect NO output
ldd ~/hve-life-os/src/build/bin/llama-server | grep -i ggml     # expect NO libggml from /usr/local/lib/ollama
env | grep OLLAMA                                                # HVE startup does not rely on these
```

## 2. Interactive TUI (v1 alpha — day-to-day entry point)

The confirmed working alpha v1 path goes through the **launcher**:

```
hve-tui                     # interactive Hermes TUI (needs a TTY)
hve-tui --health            # HVE health check only, no TUI (see §5)
hve-tui --smoke             # health + model + one smoke ask
```

The launcher (canonical source: `runtime/bin/hve-tui` in this repo; live
copy: `~/hve-life-os/runtime/bin/hve-tui`; global wrapper:
`~/.local/bin/hve-tui`):

- Starts the separate native `llama-server` on `127.0.0.1:8089` if it is
  not already up (**never Ollama** — no Ollama binary, library, model,
  service, or port is referenced anywhere in the HVE stack).
- Refreshes the `hve-alpha` Hermes profile (config + `hve-life-os` skill)
  from the canonical repo checkout each launch — the only write outside
  `~/hve-life-os`, fully idempotent and reversible.
- Exits cleanly when the TUI is closed; it leaves the model server running
  (stop it with `stop-all.sh`, §4).
- **Shebang invariant:** the launcher MUST keep its Bash shebang
  `#!/usr/bin/env bash` as line 1. If the live copy is ever regenerated,
  copy it from `runtime/bin/hve-tui` (repo) — a mangled shebang silently
  breaks the `set -euo pipefail` block.

Alpha v1 contract (what the TUI is verified against):

| Property | Value |
|---|---|
| Context | **65,536 tokens (exact)** — not 64,448 |
| Initial max output | **1,024 tokens** (bounded; raise only by explicit change) |
| Model endpoint | `http://127.0.0.1:8089/v1` (llama.cpp, loopback) |
| HVE service | `127.0.0.1:8090` (loopback) |
| Launcher | `hve-tui` |
| Health | `hve-tui --health` |

## 3. Start / stop (standalone; no systemd)

```
# start the model (127.0.0.1:8089, ctx=65536, out-capped in the app)
~/hve-life-os/runtime/bin/start-model.sh
# start the HVE loopback service (127.0.0.1:8090)
~/hve-life-os/runtime/bin/start-hve.sh
# stop both (kills llama-server + HVE service by pidfile, removes data: none)
~/hve-life-os/runtime/bin/stop-all.sh
```

### Restart procedure (full cycle)

```
~/hve-life-os/runtime/bin/stop-all.sh
~/hve-life-os/runtime/bin/start-model.sh   # wait for 127.0.0.1:8089
~/hve-life-os/runtime/bin/start-hve.sh     # wait for 127.0.0.1:8090
hve-tui --health                           # must report ok
```

### LAN opt-in (NOT default)

To expose to the LAN you must, in order: (1) set `HVE_LAN=1`, (2) provide an
`HVE_API_TOKEN`, (3) bind `0.0.0.0`. All three are commented off by default in
`runtime/hve.env`. The code refuses a non-loopback bind without a token.

## 4. Model verification (before trusting the release)

```
sha256sum ~/hve-life-os/models/Qwen3.8-2B-Distill-Q4_K_M.gguf
# expected: 4aa0fb13c431514262f259d420ecc95a8714df58ac2a2384514e20b93983f0ff
curl -s http://127.0.0.1:8089/v1/models | jq .data[0].id
# expected: Qwen3.8-2B-Distill-Q4_K_M (or the GGUF path)
```

## 5. HVE health (all must be `ok`)

```
hve-tui --health                       # same check, via the launcher (the exact health command)
hve-tui --smoke                        # health + model + smoke ask in one go
# direct equivalent (no launcher), all loopback:
HVE_HOME=~/hve-life-os/data PYTHONPATH=~/hve-life-os/app \
  ~/hve-life-os/env/bin/python -m hve health --json | jq '.ok'   # true
# HVE HTTP service (if the service is running):
curl -s http://127.0.0.1:8090/healthz | jq
```

## 6. Skill + response + tool-call smoke

```
# skill loads + plain response (direct HVE CLI against the alpha environment)
HVE_HOME=~/hve-life-os/data PYTHONPATH=~/hve-life-os/app \
  ~/hve-life-os/env/bin/python -m hve agent ask "What is the Five Wealth Framework?"
# via the launcher (spins up the model if needed, then health + smoke ask)
hve-tui --smoke
# confirm an interactions row was written
HVE_HOME=~/hve-life-os/data PYTHONPATH=~/hve-life-os/app \
  ~/hve-life-os/env/bin/python -m hve agent --list-recent 3
```

The skill is installed into the active Hermes profile via
`hermes skills install hve-life-os` (operator action; not a side effect of
`hve init`).

## 7. SQLite backup / restore

```
HVE_HOME=~/hve-life-os/data PYTHONPATH=~/hve-life-os/app \
  ~/hve-life-os/env/bin/python -m hve db backup
HVE_HOME=~/hve-life-os/data PYTHONPATH=~/hve-life-os/app \
  ~/hve-life-os/env/bin/python -m hve db restore <snapshot> --i-understand
```

## 8. Rollback

See `docs/rollback-spark.md`. Summary: stop services and timers, restore the
prior release dir + (optionally) the prior SQLite snapshot, restart, and health-
check. Rollback never deletes data.

## 9. Secrets

HVE reads no secrets at runtime. Config is env-driven. The agent prompt/response
audit path redacts known key shapes (`hve/agent/ask.py::_strip_secrets`) before
persisting. Personal knowledge lives in `~/hve-life-os/data/knowledge/`, never
in Git.
