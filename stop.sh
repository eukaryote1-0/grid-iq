#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ -f gridiq.pid ]; then
  PID="$(cat gridiq.pid)"
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID" 2>/dev/null || true
    for i in {1..20}; do kill -0 "$PID" 2>/dev/null || break; sleep .1; done
  fi
  rm -f gridiq.pid
  echo "GridIQ stopped."
else
  echo "No PID file found."
fi
