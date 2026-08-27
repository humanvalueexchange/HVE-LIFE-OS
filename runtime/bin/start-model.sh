#!/usr/bin/env bash
# Start the separate native llama.cpp model server (loopback 127.0.0.1:8089).
set -euo pipefail
source /home/hans/hve-life-os/runtime/hve.env
BIN=/home/hans/hve-life-os/src/build/bin/llama-server
mkdir -p "$HVE_HOME/logs"
echo "[start-model] launching native llama.cpp (no Ollama)"
nohup "$BIN" \
  --model "$HVE_MODEL_PATH" \
  --port 8089 --host 127.0.0.1 \
  --ctx-size 65536 --parallel 1 \
  --no-warmup \
  > "$HVE_HOME/logs/llama-server.log" 2>&1 &
echo $! > "$HVE_HOME/logs/llama-server.pid"
echo "[start-model] pid $(cat "$HVE_HOME/logs/llama-server.pid")"