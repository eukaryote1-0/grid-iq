# Operations

## Start
```bash
chmod +x run.sh stop.sh doctor.sh
./run.sh
```
Default: `http://127.0.0.1:8000`

Alternative port:
```bash
PORT=8001 ./run.sh
```

## Stop / diagnose
```bash
./stop.sh
./doctor.sh
cat gridiq.log
```

## Validate
```bash
pytest -q
python -m py_compile app/*.py tests/*.py
node --check web/js/app.bundle.js
```

FastAPI smoke example:
```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8124
curl -fsS http://127.0.0.1:8124/api/health
curl -fsS http://127.0.0.1:8124/api/audit
```

Compatibility runtime:
```bash
HOST=127.0.0.1 PORT=8125 python -m app.compat_server
```

Current-release browser fixture (requires a working Chromium/Chrome):
```bash
BASE_URL=http://127.0.0.1:8000 ./scripts/browser_smoke.sh
```
The build sandbox's system Chromium currently hangs before DOM output, so a failure there is an environment limitation and must remain recorded as NOT VERIFIED rather than silently passed.

## Important behavior
- Preferred runtime: FastAPI/Uvicorn.
- Fallback runtime: stdlib `python -m app.compat_server`.
- Python 3.14 is supported by current pins.
- Live map/resource/population layers require internet.
- External API failures are not permission to generate replacement values.
- Benchmark engineering mode is a planning sensitivity, not the BPC operational state.
