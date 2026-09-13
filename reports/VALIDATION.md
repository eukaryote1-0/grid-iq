# GridIQ v1.4 validation report

Date: 2026-09-13

## Verified

- `pytest -q`: 27 passed.
- `python -m py_compile app/*.py tests/*.py`: pass.
- `node --check web/js/app.bundle.js`: pass.
- FastAPI live runtime: health endpoint pass.
- FastAPI `/api/audit`, `/api/engineering/benchmarks`, `/api/demand/district-context`: pass.
- FastAPI benchmark network enrichment and DC transfer tested using a test-only connected 220 kV fixture: pass.
- stdlib compatibility runtime: health/audit/benchmark/derived-demand routes pass.
- HTTP security headers: CSP, frame denial, MIME sniffing denial, referrer policy and no-store observed.
- Evidence manifest generated with SHA-256 for bundled evidence/benchmark/reference/derived data files.

## Not verified

- Current v1.4 full browser E2E: NOT VERIFIED in the build sandbox. The system Chromium hangs even on a `data:` page and the installed Playwright package has no browser binary. `scripts/browser_smoke.sh` is included for a workstation with working Chromium/Chrome. The `/api/audit` browser-regression gate therefore remains false.
- Live Overpass/NASA POWER/WorldPop responses were not exercised from the container runtime because external network access is environment-dependent. Connector contracts and degraded paths are implemented; live upstream verification should be repeated on the user's internet-connected Ubuntu system.
- BPC operational power-flow accuracy: NOT VERIFIABLE because authoritative BPC bus/branch/rating/impedance/load data are not bundled.

## Current computed audit

- UI/application: 7.3/10
- Open-data governance: 10.0/10
- Benchmark engineering capability: 10.0/10
- Public-data planning product: 9.2/10
- BPC operational validation: 0.0/10
- Whole solution including operational validation: 7.3/10

The 9.2 public-data score applies only to the stated planning-product scope and does not imply measured BPC operating-state accuracy.
