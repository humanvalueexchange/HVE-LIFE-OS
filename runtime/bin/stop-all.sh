#!/usr/bin/env bash
# Stop HVE model server + HVE loopback service. No data removal.
set -uo pipefail
HVE_HOME=/home/hans/hve-life-os/data
for f in "$HVE_HOME/logs/llama-server.pid" "$HVE_HOME/logs/hve-serve.pid"; do
  if [ -f "$f" ]; then
    pid=$(cat "$f")
    if kill -0 "$pid" 2>/dev/null; then kill "$pid"; echo "stopped pid $pid"; fi
    rm -f "$f"
  fi
done
echo "[stop-all] done"