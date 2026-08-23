#!/usr/bin/env bash
# HVE Life OS — explicit-confirmation rollback.
#
# D10=B: the rollback restores the *prior* application + config snapshot
# and (optionally) a SQLite snapshot. Restore of SQLite *never* happens
# silently: the operator must pass --i-understand.
#
# Usage:
#   sudo /home/hve/bin/hve-rollback.sh [--restore-db SNAP]
#
# The script is intentionally small; it shells out to `systemctl` and
# `python3 -m hve`. All heavy lifting is in the CLI.

set -euo pipefail

I_UNDERSTAND=0

usage() {
  cat <<EOF
HVE Life OS rollback (Mercury alpha)
Usage: $(basename "$0") [--restore-db SNAPSHOT_PATH] [--i-understand]
  --restore-db   Also restore that SQLite snapshot (default: app/config only)
  --i-understand Required when restoring the database. Preserves the
                 current DB under ~/.hve/backups/hve-restore/.
EOF
}

for arg in "$@"; do
  case "$arg" in
    --restore-db=*) DB_SNAP="${arg#--restore-db=}" ;;
    --restore-db)    shift; DB_SNAP="${1:-}" ;;
    --i-understand)  I_UNDERSTAND=1 ;;
    -h|--help)       usage; exit 0 ;;
    *)               usage; exit 2 ;;
  esac
done

echo "Stopping HVE services and timers ..."
sudo systemctl stop hve-lifeos.service hve-report.service hve-db-backup.service
sudo systemctl stop hve-report.timer hve-db-backup.timer

if [ "${I_UNDERSTAND:-0}" != "1" ] && [ -n "${DB_SNAP:-}" ]; then
  echo "Refusing to restore SQLite snapshot without --i-understand." >&2
  exit 2
fi

echo "Switching current -> prior release ..."
# The installer maintains /opt/hve/releases/<ts>/ and /opt/hve/current;
# this script expects that layout. If the prior dir is missing, fail.
PREV="$(ls -1t /opt/hve/releases 2>/dev/null | sed -n '2p' || true)"
if [ -z "${PREV:-}" ]; then
  echo "No prior release found under /opt/hve/releases." >&2
  exit 1
fi
ln -sfn "/opt/hve/releases/${PREV}" /opt/hve/current
echo "  prior release: /opt/hve/releases/${PREV}"

if [ -n "${DB_SNAP:-}" ]; then
  echo "Restoring SQLite snapshot (explicitly confirmed) ..."
  HVE_HOME=/home/hve/.hve sudo -u hve bash -c \
    "PYTHONPATH=/opt/hve/current /usr/bin/python3 -m hve db restore '${DB_SNAP}' --i-understand"
fi

echo "Running post-rollback health check ..."
HVE_HOME=/home/hve/.hve sudo -u hve bash -c \
  "PYTHONPATH=/opt/hve/current /usr/bin/python3 -m hve health --json"

echo "Starting hve-lifeos.service ..."
sudo systemctl start hve-lifeos.service

echo "Rollback complete."
echo "  If the rollback did not produce a healthy service, inspect:"
echo "     journalctl -u hve-lifeos.service"
echo "     journalctl -u hve-report.service"
echo "     HVE_HOME=/home/hve/.hve sudo -u hve bash -c 'PYTHONPATH=/opt/hve/current /usr/bin/python3 -m hve status'"
