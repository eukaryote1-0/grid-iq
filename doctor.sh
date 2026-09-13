#!/usr/bin/env bash
set +e
cd "$(dirname "$0")" || exit 1
PORT="${PORT:-8000}"
echo "=== GridIQ doctor ==="
echo "Project: $(pwd)"
echo "OS: $(uname -srmo 2>/dev/null)"
echo "Python candidates:"
for p in python3 python3.14 python3.13 python3.12 python3.11; do
  command -v "$p" >/dev/null 2>&1 && printf '  %-10s %s\n' "$p" "$("$p" --version 2>&1)"
done
echo "curl: $(command -v curl 2>/dev/null || echo missing)"
if [ -x .venv/bin/python ]; then
  echo "venv: $(.venv/bin/python --version 2>&1)"
  .venv/bin/python - <<'PY'
for m in ('fastapi','pydantic','uvicorn','httpx'):
    try:
        x=__import__(m); print(f"  {m}: {getattr(x,'__version__','installed')}")
    except Exception as e:
        print(f"  {m}: MISSING ({e})")
PY
else
  echo "venv: not created"
fi
if [ -f gridiq.pid ]; then
  PID=$(cat gridiq.pid); echo "PID file: $PID"; kill -0 "$PID" 2>/dev/null && echo "process: alive" || echo "process: not running"
else
  echo "PID file: none"
fi
curl -fsS "http://127.0.0.1:$PORT/api/health" 2>/dev/null && echo || echo "health: unavailable on port $PORT"
if [ -f gridiq.log ]; then
  echo "--- last 80 log lines ---"
  tail -80 gridiq.log
else
  echo "No log yet."
fi
