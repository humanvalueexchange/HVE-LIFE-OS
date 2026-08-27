#!/usr/bin/env bash
# Start the HVE loopback service (127.0.0.1:8090).
set -euo pipefail
source /home/hans/hve-life-os/runtime/hve.env
mkdir -p "$HVE_HOME/logs"
cd /home/hans/hve-life-os/app
HVE_HOME="$HVE_HOME" nohup /home/hans/hve-life-os/env/bin/python -m hve serve \
  --host 127.0.0.1 --port 8090 > "$HVE_HOME/logs/hve-serve.log" 2>&1 &
echo $! > "$HVE_HOME/logs/hve-serve.pid"
echo "[start-hve] pid $(cat "$HVE_HOME/logs/hve-serve.pid")"