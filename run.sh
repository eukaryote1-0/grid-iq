#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8000}"
HOST="${HOST:-127.0.0.1}"
PY="${PYTHON:-python3}"

if ! command -v "$PY" >/dev/null 2>&1; then
  echo "ERROR: Python 3 is required."
  exit 1
fi

PYVER="$($PY -c 'import sys; print(".".join(map(str,sys.version_info[:3])))')"
echo "GridIQ launcher · Python $PYVER"

# Clean up a stale PID before doing anything else.
if [ -f gridiq.pid ]; then
  OLD_PID="$(cat gridiq.pid 2>/dev/null || true)"
  if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo "GridIQ already running (PID $OLD_PID) at http://$HOST:$PORT"
    exit 0
  fi
  rm -f gridiq.pid
fi

RUNTIME="compat"

# Preferred path: FastAPI in an isolated venv. The pinned Pydantic release has
# CPython 3.14 wheels; binary-only install prevents accidental Rust/C builds.
if "$PY" -m venv .venv >/dev/null 2>&1; then
  VENV_PY="$(pwd)/.venv/bin/python"

  # If a previous release made this venv with a different interpreter, rebuild it.
  VENV_MM="$($VENV_PY -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)"
  BASE_MM="$($PY -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
  if [ "$VENV_MM" != "$BASE_MM" ]; then
    echo "Rebuilding stale virtual environment ($VENV_MM -> $BASE_MM)..."
    rm -rf .venv
    "$PY" -m venv .venv
    VENV_PY="$(pwd)/.venv/bin/python"
  fi

  echo "Checking FastAPI runtime..."
  if ! "$VENV_PY" -c 'import fastapi,uvicorn,httpx,pydantic' >/dev/null 2>&1; then
    echo "Installing Python runtime (binary wheels only)..."
    # Upgrade pip if possible, but do not make startup depend on this optional step.
    PIP_DEFAULT_TIMEOUT=5 "$VENV_PY" -m pip install -q --retries 1 --disable-pip-version-check --upgrade pip >/dev/null 2>&1 || true
    if PIP_DEFAULT_TIMEOUT=5 "$VENV_PY" -m pip install --retries 1 --only-binary=:all: --disable-pip-version-check -r requirements.txt; then
      :
    else
      echo
      echo "WARNING: FastAPI dependencies could not be installed."
      echo "Falling back to GridIQ's dependency-free compatibility runtime."
      echo "The browser UI and API contract remain available; FastAPI is preferred for development."
    fi
  fi

  if "$VENV_PY" -c 'import fastapi,uvicorn,httpx,pydantic' >/dev/null 2>&1; then
    RUNTIME="fastapi"
  fi
else
  echo "WARNING: Could not create .venv. Using dependency-free compatibility runtime."
fi

: > gridiq.log
if [ "$RUNTIME" = "fastapi" ]; then
  echo "Starting FastAPI runtime..."
  nohup "$VENV_PY" -m uvicorn app.main:app --host "$HOST" --port "$PORT" >> gridiq.log 2>&1 &
else
  echo "Starting dependency-free compatibility runtime..."
  nohup env HOST="$HOST" PORT="$PORT" "$PY" -m app.compat_server >> gridiq.log 2>&1 &
fi
echo $! > gridiq.pid

for i in {1..50}; do
  if curl -fsS "http://$HOST:$PORT/api/health" >/tmp/gridiq_health.$$ 2>/dev/null; then
    echo
    echo "GridIQ running: http://$HOST:$PORT"
    echo "Runtime: $(cat /tmp/gridiq_health.$$)"
    echo "Live OSM, NASA POWER and WorldPop layers require internet access."
    rm -f /tmp/gridiq_health.$$
    exit 0
  fi
  sleep 0.3
done

rm -f /tmp/gridiq_health.$$ 2>/dev/null || true
echo
printf 'ERROR: GridIQ did not become healthy.\nLog: %s/gridiq.log\n\n' "$(pwd)"
cat gridiq.log
exit 1
