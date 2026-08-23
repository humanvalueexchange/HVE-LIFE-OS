# HVE Life OS — Mercury Runbook (alpha)

Audience: Hans (operator) and any future developer touching the Mercury 8K
alpha. This file is the single source of truth for day-to-day operations.

## Scope

The Mercury alpha is a **local, loopback-only** personal-wealth service.
There is no cloud, no public network surface, no multi-user, and no
personal data in the repository (see charter 10.1 rule 2 and D5=A).

```
┌────────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  hermes (agent)    │    │  hve (service)   │    │  Qwen2.5 3B      │
│  ~/.hermes         │◄───┤  127.0.0.1:8090  ├───►│  127.0.0.1:8089  │
│  Hermes v0.20.5    │    │  /healthz        │    │  llama.cpp GGUF  │
│  -q/-s/-Q chat     │    │  /status.json    │    │  Q4_K_M, 8K      │
└────────────────────┘    │  /report         │    └──────────────────┘
                          └──────────────────┘
                                   │
                                   ▼  SQLite (WAL)
                          ~/.hve/data/hve.db
```

## 1. Service user (D6=B)

The service runs as a **dedicated `hve` user**, not as `root` and not as
`hermes` (charter 10.1 rule 2: least privilege, separation of duties).

### Create (one-time)

```
sudo useradd --system --no-create-home --shell /usr/sbin/nologin hve
sudo mkdir -p /home/hve/.hve/{data,knowledge,reports,backups}
sudo chown -R hve:hve /home/hve/.hve
sudo chmod 700 /home/hve/.hve
```

### Verify

```
sudo -u hve id
ls -ld /home/hve/.hve
```

## 1b. Hermes binary and skill onboarding

Two things must be in place before `hve agent ask` works. Neither is
automatic.

### (a) `HVE_HERMES_BIN` — required

The HVE agent path invokes a fixed Hermes CLI. Resolution order in
`hve/agent/ask.py :: _find_hermes`:

1. `HVE_HERMES_BIN` (preferred; explicit pin)
2. `hermes` on `PATH` (second preference)
3. a small set of portable optional fallback locations **only as a last
   resort** — the legacy `/home/hermes/.hermes/venv/bin/hermes` is no
   longer special-cased.

On Mercury the recommended way is a single explicit pin, written into
the per-host env file consumed by the systemd units:

```
# /home/hve/.hve/env  (read by hve-lifeos.service EnvironmentFile=...)
HVE_HERMES_BIN=/home/hve/.local/bin/hermes
```

The exact path is the one that `command -v hermes` reports *for the `hve`
user* on Mercury. Verify before use:

```
sudo -u hve bash -lc 'command -v hermes; hermes --version'
```

Why the env pin and not PATH: the service units declare a standard
`PATH` (`Environment=PATH=/home/hve/.local/bin:/usr/local/sbin:...`), so
PATH discovery *also* works. But PATH can drift (a shim moved, a profile
not loaded under systemd), so an explicit `HVE_HERMES_BIN` is the
documented, auditable mechanism. The resolver treats a *pinned but
missing/broken* path as a config error and fails loudly (it names the
offending path and the three ways to fix it) rather than silently
falling through to a different binary.

Do **not** hardcode a different account's path (e.g. `/home/hermes/...`)
in a unit or env file for the `hve` user — the resolver no longer
special-cases any account path, and a wrong pin now fails loudly instead
of quietly picking the wrong binary.

### (b) `hve-life-os` skill — installed into a named Hermes profile

`hve agent ask` preloads the skill: `hermes chat -q "..." -s hve-life-os -Q`.
The skill source ships in this repo at
`hermes-skills/hve-life-os/SKILL.md`. It must be *installed into the
profile Hermes will actually run under* before prompts succeed.

**Exact install command — MARKED FOR THE DEPLOYMENT ONBOARDING LOOP.**
I deliberately do not hardcode it here, because the precise invocation
(depends on the Hermes version's skill-install API, the target profile
name, and how the agent is launched) could only be verified by *changing
Mercury's runtime state* — which this loop is forbidden to do. Before
deployment, Hans (or the onboarding loop) MUST:

1. Determine the profile Hermes uses for the Mercury agent (e.g. by
   inspecting the active `config.yaml` / launch command, read-only).
2. Install `hermes-skills/hve-life-os/SKILL.md` into **that named
   profile** using the Hermes skill-install mechanism appropriate to the
   installed version.
3. Verify, read-only, that the profile now lists the skill:
   `hermes skills list` (or the version's equivalent) shows `hve-life-os`.
4. Run a single harmless prompt through `hve agent ask` and confirm it
   succeeds and writes an `interactions` row.

Until step 4 passes, `hve agent ask` will fail with a skill-not-found
error from the Hermes side — that is expected, not a bug in HVE.

### `hve init` does NOT touch Hermes state

`hve init` (see `hve/cli.py :: cmd_init`) only:

- runs the forward-only SQLite migrations against `~/.hve/data/hve.db`,
- seeds the placeholder facts (only when the DB is empty, D5=A),
- upserts the knowledge records from `~/.hve/knowledge/*.md`.

It **never** reads or writes `~/.hermes`, any Hermes profile, skills, or
config. Installing the skill (step b above) is a separate, operator
performed action — it is not a side effect of `hve init`, and `hve init`
must be allowed to run as the `hve` user without that prerequisite.

## 2. Loopback-only endpoints (D3=B, D7=B)

The HVE service binds to `127.0.0.1` **only**. `HveConfig.__post_init__`
refuses to start if `HVE_HTTP_HOST` is any non-loopback address, so a
misconfiguration fails fast instead of being discoverable from the LAN.

Endpoints (all `GET`, all loopback):

| Path          | Purpose                                |
| ------------- | -------------------------------------- |
| `/healthz`    | Liveness + component status (JSON)     |
| `/status.json`| Applied schema version, domain counts, model endpoint |
| `/report`     | The static `report.html` (200 / 503)   |

No auth, because there is nothing outside localhost.

## 3. Hourly idempotent report (D9=B)

`hve-report.timer` fires the **hourly** `hve-report.service`. The service
calls `hve report generate`, which is **idempotent** — when nothing has
changed, the report files are not rewritten (see `hve/report/render.py`).
This means the timer may re-fire in any order (clock skew, NTP jump) and
the visible output stays stable.

```
systemctl list-timers --all | grep hve
systemctl status hve-report.timer
journalctl -u hve-report -n 50 --no-pager
```

## 4. SQLite backup & restore (D10=B)

The database lives at `~/.hve/data/hve.db` (WAL mode; `-wal` and `-shm`
sidecars may also be present).

### Backup (daily timer)

`hve-db-backup.timer` → `hve-db-backup.service` → `hve db backup`.
Snapshots land in `~/.hve/backups/hve-db/hve-<UTC-stamp>.sqlite3`.
The backup is created with the **SQLite online backup API**
(`Connection.backup`), so committed frames in the WAL are captured even
while writers are active. See `hve/db.py :: backup_db`.

### Restore (operator-invoked, confirmed)

Restore is **never automatic**. It requires the `--i-understand` flag,
which maps to `restore_db(confirm=True)`. The prior db is preserved
(WAL-safe) under `~/.hve/backups/hve-restore/hve-pre-restore-<UTC-stamp>.sqlite3`
so a mistaken restore can be undone.

Pre-conditions before a restore (all three are required):

1. `sudo systemctl stop hve-lifeos.service hve-report.service hve-db-backup.service`
   (no writers)
2. `sudo systemctl stop hve-report.timer hve-db-backup.timer` (no timers)
3. `HVE_HOME=/home/hve/.hve sudo -u hve env PYTHONPATH=/opt/hve/current
   /usr/bin/python3 -m hve db status` — confirm the right database

Restore:

```
HVE_HOME=/home/hve/.hve sudo -u hve env PYTHONPATH=/opt/hve/current \
  /usr/bin/python3 -m hve db restore \
  ~/.hve/backups/hve-db/hve-20260822-000000.sqlite3 --i-understand
HVE_HOME=/home/hve/.hve sudo -u hve env PYTHONPATH=/opt/hve/current \
  /usr/bin/python3 -m hve db status
sudo systemctl start hve-lifeos.service
```

On failure, the prior db is still present under `~/.hve/backups/hve-restore/`;
undo is a second `hve db restore <the-prior-file> --i-understand`.

## 5. Health checks

Three layers, all readable from the CLI **or** over loopback HTTP:

```
# CLI (no network required)
sudo -u hve hve health

# HTTP (loopback only)
curl -s http://127.0.0.1:8090/healthz | jq
curl -s http://127.0.0.1:8090/status.json | jq
```

Component checks (from `hve/serve/health.py`): `db`, `migrations`,
`knowledge`, `facts`, `model`, `report`, `env`. The `model` check is
best-effort (warns if the local llama.cpp endpoint is unreachable —
expected during dev before the model service is started).

An HTTP 200 on `/healthz` means the operator can treat the service as
ready. An HTTP 503 means at least one component is in `fail`.

## 6. Rollback

If the running release misbehaves after a change:

1. **Stop** the services and timers:
   `sudo systemctl stop hve-lifeos.service hve-report.service hve-db-backup.service`
   `sudo systemctl stop hve-report.timer hve-db-backup.timer`
2. **Restore the prior db** (if a new db was introduced):
   `HVE_HOME=/home/hve/.hve sudo -u hve env PYTHONPATH=/opt/hve/current
   /usr/bin/python3 -m hve db restore <prior-snapshot> --i-understand`
3. **Restart** the service with the prior application bits (see
   `docs/rollback-mercury.md` for the full sequence, including the
   Hermes overlay revert path).

## 7. Daily operator checklist

```
sudo -u hve hve status                       # top-line
curl -s http://127.0.0.1:8090/healthz | jq .ok
curl -s http://127.0.0.1:8090/status.json | jq .schema_versions
sudo -u hve hve db status                      # db file + schema version
ls -lt ~/.hve/backups/hve-db/ | head
```

## 8. Secrets

HVE reads **no** secrets at runtime. All configuration is env-driven
(`HVE_HOME`, `HVE_HTTP_PORT`, etc.). Agent prompts and responses are
audited to `interactions` in the same db; a scrub regex
(`hve/agent/ask.py :: _strip_secrets`) redacts known key shapes before
persistence.

## 9. Upstream / model verification (D1, D2)

Before running the release, Hans re-verifies the pinned upstream commit and
the model artifact checksum on Mercury:

```
# Model checksum (must match deployment/manifest.yaml)
sha256sum /opt/mercury/models/qwen2.5-3b-instruct-q4_k_m.gguf
# Expected: 626b4a6678b86442240e33df819e00132d3ba7dddfe1cdc4fbb18e0a9615c62d

# Hermes upstream commit (read-only)
cd ~/.hermes/hermes-agent && git rev-parse HEAD
# Expected: a871948d8d4b0f774d4ec40467bab1078a9f28d5
```

If either mismatches, **stop and escalate** — do not override the pin in
the runbook. The manifest is the contract; the runbook enforces it.
