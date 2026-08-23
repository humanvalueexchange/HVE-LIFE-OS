# HVE Life OS — Mercury Rollback Runbook (alpha)

Audience: Hans (operator). This is a short, safe, confirmed sequence to
undo a recent change on Mercury. It assumes the change was made on this
repository (the HVE app) — it does **not** cover a Mercury OS reinstall or
a Hermes upgrade.

## When to roll back

Use this sequence when **any** of the following is true and the new state
is worse than the old state:

* `/healthz` returns 503 repeatedly
* `hve agent ask` fails consistently (not a prompt problem)
* The db schema is corrupted or a bad migration applied
* The report contents are wrong after a `hve report generate`
* Any change that was made "temporarily" and is now unwanted

Do **not** roll back if the goal is to *upgrade* the model or the Hermes
commit — that is a separate, explicitly-approved task (charter 12
requires Hans to approve consequential changes).

## Pre-rollback safety

1. **Stop all HVE writers.** Do this first, every time.
   ```
   sudo systemctl stop hve-lifeos.service hve-report.service hve-db-backup.service
   sudo systemctl stop hve-report.timer hve-db-backup.timer
   ```
2. **Snapshot the current (bad) state** so you can inspect it later.
   ```
   HVE_HOME=/home/hve/.hve sudo -u hve \
     env PYTHONPATH=/opt/hve/current /usr/bin/python3 -m hve db backup
   ```
   The backup lands in `~/.hve/backups/hve-db/` and stays there.
3. **Record the current version** for the incident log.
   ```
   HVE_HOME=/home/hve/.hve sudo -u hve \
     env PYTHONPATH=/opt/hve/current /usr/bin/python3 -m hve status
   HVE_HOME=/home/hve/.hve sudo -u hve \
     env PYTHONPATH=/opt/hve/current /usr/bin/python3 -m hve report generate
   ```

## Rollback the database only

When the application bits are fine but the db is not:

```
HVE_HOME=/home/hve/.hve sudo -u hve \
  env PYTHONPATH=/opt/hve/current /usr/bin/python3 -m hve db restore \
    ~/.hve/backups/hve-db/<prior-snapshot>.sqlite3 \
    --i-understand
```

- The `--i-understand` flag is required. It is the D10=B explicit
  confirmation. There is no short form and no skip.
- The current (bad) db is preserved (WAL-safe) under
  `~/.hve/backups/hve-restore/hve-pre-restore-<UTC-stamp>.sqlite3`.
- Restore runs `PRAGMA integrity_check` and `PRAGMA foreign_key_check`
  on the incoming db **before** reporting success. If either fails, no
  swap happened.
- Restart the service:
  ```
  sudo systemctl start hve-lifeos.service
  curl -s http://127.0.0.1:8090/healthz | jq
  ```

## Roll back the application bits

When the app code/schema is the problem (not the db):

1. Stop the service and timers (as above).
2. Restore the prior db snapshot (as above) if the schema is involved.
3. Revert the repo to the prior known-good commit **only on the target
   host**, and restart:
   ```
   cd /opt/hve/current
   git checkout <known-good-commit>
   sudo systemctl start hve-lifeos.service
   ```
   The HVE package is imported from the working tree (no pip install step
   in alpha), so a git revert + service restart is atomic enough for the
   alpha.

## Roll back the Hermes overlay (if the change was an overlay)

The Mercury Hermes runtime has a **local** context-floor overlay
(`patches/hermes-context-floor.patch`). Rolling back the *HVE* alpha does
*not* automatically revert that overlay. If the overlay is part of the
incident:

```
cd ~/.hermes/hermes-agent
git status
# If the patch was applied, revert it:
git checkout -- .
# Then restart the Hermes gateway / agent as applicable.
```

## Verification after rollback

Run this exact sequence and confirm every line looks right before
declaring success:

```
HVE_HOME=/home/hve/.hve sudo -u hve \
  env PYTHONPATH=/opt/hve/current /usr/bin/python3 -m hve health
curl -s http://127.0.0.1:8090/healthz | jq .ok        # expect true
curl -s http://127.0.0.1:8090/status.json | jq .schema_versions
HVE_HOME=/home/hve/.hve sudo -u hve \
  env PYTHONPATH=/opt/hve/current /usr/bin/python3 -m hve status
HVE_HOME=/home/hve/.hve sudo -u hve \
  env PYTHONPATH=/opt/hve/current /usr/bin/python3 -m hve db status
```

If any of these fail, **stop and escalate** to Hans. Do not "fix forward"
inside the rollback path.

## Recording the rollback

Write a short incident note (Hans's call on where):

- Time (UTC) of the change that caused the issue
- Time (UTC) of the rollback
- The prior snapshot path
- The healthz result after rollback
- Root-cause hypothesis (or "unknown")

## What this runbook does NOT cover

- Upgrading or downgrading the model artifact (D1)
- Upgrading or downgrading the Hermes upstream commit (D2)
- Changing the loopback port, host, or service user
- Changing the Five Wealth schema (that is a schema migration, not a
  rollback)

Those are consequential changes under charter 12 and require a separate,
explicitly approved runbook.
