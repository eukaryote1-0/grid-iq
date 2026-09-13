# GridIQ v1.7 validation report

## Automated

- Python unit/API/model tests: **32 passed** with `pytest -q`.
- Python compile: `python -m py_compile app/*.py tests/*.py`.
- Frontend syntax: `node --check web/js/app.bundle.js`.
- FastAPI smoke: health, audit, 10-entry benchmark gap register and BPC loss-reconciliation endpoint passed.
- Compatibility runtime smoke: health/audit/gap-register passed through `run.sh` fallback in the offline build environment.
- Compatibility runtime smoke: core local UI/API contract.

## Evidence gates

The audit intentionally separates public/benchmark planning capability from BPC operational validation. Benchmark substitution cannot make `bpc_operational_validation` non-zero.

## Browser

Current-release browser E2E is **NOT VERIFIED** in the build sandbox. Use `scripts/browser_smoke.sh` on a workstation with a working Chromium/Chrome, and record `reports/browser_e2e.json` only after the exact v1.7 release passes.
