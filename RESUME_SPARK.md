# HVE LIFE OS — SPARK DEPLOYMENT HANDOFF (reboot-safe resume)
Captured: 2026-08-23. Read this FIRST when resuming.

## Mission
Directory-contained DGX Spark deployment of HVE Life OS on a SEPARATE,
Ollama-independent native llama.cpp. Serve Qwen3.8-2B-Distill Q4_K_M at
EXACT 65536-token context, initial 1024 max-output. Mercury PARKED (files
preserved, reversible isolation only). Reuse contract for Linux/Ubuntu-Windows.
Hans approves commits/pushes; NOT yet approved.

## Hard rules (Hans)
1. HVE owns files ONLY under ~/hve-life-os. Never /usr/bin,/etc,/opt,system python.
2. Ollama fully OFF-LIMITS (no use/link/modify/depend). Proven independent.
3. No NEW system packages (ninja was missing; used `make` instead — do NOT apt get).
4. Loopback only by default (127.0.0.1:8090 HVE, 127.0.0.1:8089 model). LAN=explicit opt-in.
5. Reversible: preserve all Mercury files; no deletions/irreversible moves.
6. Context EXACT 65536 (not 64448). Max output 1024 (initial).

## Identity / env (verified)
- Remote origin: https://github.com/humanvalueexchange/HVE-LIFE-OS.git (main -> origin/main)
- Working dir: /home/hans/humanvalueexchange/workspaces/hvelifeospoc  (branch main)
- Host: spark-5054, aarch64, GB10 128GB unified. python3.12.3 system.
- GB10 is NOT a CUDA device for llama.cpp (Ollama itself runs CPU/NEON). So we
  built separate CPU/NEON llama.cpp. (If Hans later forces CUDA-try, that's a deviation.)

## DECISIONS APPROVED by Hans (2026-08-23)
- (a) separate native llama.cpp under ~/hve-life-os; Ollama untouched.
- standalone llama-server model on 127.0.0.1:8089, default loopback.

## DEPLOYMENT TREE (all under ~/hve-life-os) — what exists now
- src/llama.cpp   (clone b10603/c060ca9) ; src/build/bin/llama-server + llama-cli (BUILT, CPU/NEON)
- models/Qwen3.8-2B-Distill-Q4_K_M.gguf  sha256 4aa0fb13c431514262f259d420ecc95a8714df58ac2a2384514e20b93983f0ff (VERIF)
- app/  (hve package copied in) — NOTE: does NOT yet contain the containment fix (see BUG)
- env/  (python3.12.3 venv, pip 26.2.1) — `hve` resolves to ~/hve-life-os/app (not system)
- runtime/hve.env  (HVE_HOME=~/hve-life-os/data, endpoint 127.0.0.1:8089/v1, ctx 65536, out 1024, port 8090, HVE_LAN=0)
- runtime/bin/start-model.sh start-hve.sh stop-all.sh (chmod +x; use HVE_HOME)
- data/  (logs present; NO db here yet — init went to wrong place, see BUG)
- data/logs/llama-server.{log,pid}  (server STILL RUNNING, pid in file)

## REPO CHANGES (git status in workdir) — NOT COMMITTED
  M deployment/manifest.yaml   (rewrote -> Spark target)
  M hve/config.py              (containment fix: dirs derive from HVE_HOME)
  ?? AGENTS.md  ?? PROJECT_STATUS.md  ?? docs/runbook-spark.md  ?? experimental/  ?? service/spark/
Mercury preserved in place: deployment/mercury/**, docs/*-mercury.md, service/hve-*.service/.timer, patches/hermes-context-floor.patch

## THE BUG (containment) — FIXED in repo, NOT yet applied to live
Root: config.py db/knowledge/reports/backups defaulted to ~/.hve regardless of HVE_HOME.
Effect: `hve init` with HVE_HOME=~/hve-life-os/data wrote DB to ~/.hve/data/hve.db (LEAK, still on disk, 45056 bytes).
Fix: config.py now has `_resolve_base_home()`; db_path/knowledge_dir/reports_dir/backups_dir default to None and are derived from `home` in __post_init__ via object.__setattr__ (frozen dataclass). `__post_init__` also keeps loopback-only assertion. Lint OK.
NOT DONE: copy fixed hve/ into ~/hve-life-os/app/, re-run `hve init` (expect db in ~/hve-life-os/data/), then REMOVE the leaked ~/.hve/data/hve.db.

## VALIDATION DONE (real output)
- llama-server independence: ldd -> only libgomp/libstdc++/libm/libgcc_s/libc; strings|grep ollama = none; pid on 8089 = ours.
- /v1/models OK; server log: n_slots=1, n_ctx_slot=65536, n_threads=20 (exact 64K, CPU).
- Completion OK, 1024 cap honored (finish_reason=stop).
- `hve health --json` -> (after pre-fix init) db ok, model ok, report warn "no report.html yet".
- Ollama untouched: still only 127.0.0.1:11434 bound; HVE never referenced Ollama libs/ports/env.

## VALIDATION NOT YET DONE (finish these before final approval)
1. cp repo hve/config.py -> ~/hve-life-os/app/hve/config.py (or re-cp whole hve/ dir)
   then HVE_HOME=~/hve-life-os/data env/bin/python -m hve init  => expect db in ~/hve-life-os/data/
   then rm ~/.hve/data/hve.db  (leak). Re-run `hve health --json` -> expect ok=True, report warn still.
2. `hve report generate` -> clears report warn.
3. Skill into active Hermes profile (hermes skills install hve-life-os) + `hve agent ask`
   PLAIN response AND tool-call smoke. (Not yet run.)
4. Run repo `pytest` (workspace verification command). (Not yet run.)
5. Produce final `git status` + `git diff` + full validation report -> present to Hans.
6. STOP. No commit/push until Hans explicitly approves the final diff.

## RESTART COMMANDS (after reboot)
# model (if not already running)
~/hve-life-os/runtime/bin/start-model.sh
# confirm
curl -s http://127.0.0.1:8089/v1/models | head -c 300
# HVE venv entrypoint
HVE_HOME=~/hve-life-os/data PYTHONPATH=~/hve-life-os/app ~/hve-life-os/env/bin/python -m hve health --json
# stop all
~/hve-life-os/runtime/bin/stop-all.sh

## OPEN QUESTION (ask Hans at resume)
Backend: we used CPU/NEON. Do you still want an ATTEMPTED CUDA build for GB10,
or is CPU/NEON (what actually runs, matches Ollama's own behavior) acceptable as the
"separate native stack"? (CPU is the one that actually serves on this box.)
