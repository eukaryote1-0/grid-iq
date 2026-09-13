# Session
Date: 2026-09-13
Objective: Resolve startup failure on the user's Ubuntu host running CPython 3.14.

## Starting state
The release pinned Pydantic 2.11.7 and `uvicorn[standard]`. pip attempted a local pydantic-core Rust build and failed because `cc` was unavailable.

## Work performed
- Updated dependency pins to Python-3.14-capable FastAPI/Pydantic releases.
- Removed Uvicorn native extras.
- Added binary-wheel-only preferred installation.
- Extracted domain/scenario logic into `app/logic.py`.
- Added dependency-free `app/compat_server.py` with the same browser API contract.
- Hardened `run.sh`, `doctor.sh`, and `stop.sh`.
- Added logic and API tests.

## Validation
VERIFIED:
- Python compileall.
- 6/6 unit/API tests.
- Compatibility HTTP runtime `/api/health`.
- Catalog reports 12 sources.
- Scenario returns 24 hourly rows.
- Launcher tested with package installation deliberately disabled; automatic fallback started and stopped successfully.

NOT VERIFIED:
- Exact pip installation on the user's CPython 3.14 host; the selected Pydantic release has published CPython 3.14 wheels, but this build environment cannot access PyPI directly.

## Remaining work
Continue real dataset ingestion and browser E2E/visual validation.
