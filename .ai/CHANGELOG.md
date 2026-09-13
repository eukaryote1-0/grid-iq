# Changelog

## 2026-09-13 — v1.3 evidence/data/topology iteration

### Added
- Statistics Botswana 2022 district population transform.
- Statistics Botswana NEUS 2022/23 access, district connection, renewable penetration and non-connection-reason transforms.
- `/api/neus` and `/api/census/districts` in FastAPI and compatibility runtimes.
- Demand-page district population/access visualizations based on official data.
- OSM geometry-topology metrics and topology layer.
- Browser state persistence across page navigation.

### Changed
- Scenario model is evidence-bounded rather than synthetic hourly dispatch.
- Dataset catalog now marks Census and NEUS as physically integrated.
- Audit text removes NEUS from un-ingested gaps.

### Fixed
- Map lifecycle/state loss after switching pages and returning.
- Earlier Python 3.14 runtime packaging and frontend blank-screen boot failures retained as resolved history.

### Validation
- Unit/API tests, compile checks, JS syntax check, FastAPI/compat smoke tests and Chromium fixture navigation/persistence test.

## 2026-09-13 — v1.4 benchmark/data-fusion iteration

### Added
- WorldPop v2 selected-site population connector.
- PyPSA/PyPSA-Earth electrical benchmark library for 132/220/400 kV mapped OSM voltage classes.
- Conservative/reference/high-capacity conductor sensitivity cases.
- OSM line enrichment with derived length plus benchmark R/X/current/secure-capacity fields.
- Single-voltage DC transfer solver using explicit user transfer instead of fabricated Botswana bus loads.
- Separate approximate I²R post-processing.
- Census×NEUS population-weighted access-gap derived indicator with explicit unmatched geographies.
- SHA-256 evidence manifest.
- Evidence-gated audit scores separating public-data planning from BPC operational validation.
- Browser fixture script for workstation validation.

### Changed
- Data catalog expanded to WorldPop and electrical benchmark sources.
- Demand page now surfaces deterministic Census×NEUS enrichment and WorldPop without converting either to MW.
- Network page now supports benchmark flow overlay and branch sensitivity results.
- Audit no longer hardcodes scores.

### Fixed
- Compatibility runtime missing import for the new derived-demand endpoint, found in smoke testing.

### Validation
- 27 pytest tests pass.
- Python compilation and JavaScript syntax checks pass.
- FastAPI and stdlib runtime smoke tests pass for health/audit/benchmark/derived endpoints.
- Security headers/CSP verified over HTTP.
- Current-release browser E2E remains NOT VERIFIED due sandbox browser execution failure; audit gate stays false.

## 2026-09-13 — v1.5 platform bootstrap (I0–I2)

### Added
- Repository scaffolding for the team repo (`grid-iq`): `CONTRIBUTING.md`, `AGENTS.md`, `Makefile`, `.gitignore`, `.github/workflows/ci.yml`, PR/issue templates, CODEOWNERS.
- Committed external datasets with SHA-256 manifests: filtered OSM power lines (132/220/400 kV) and substations, the World Bank/AICD Botswana grid layer, and a Botswana techno-economic workbook (Zenodo/Loughborough CCG).
- `scripts/fetch_data.sh` (large layers) and `scripts/verify_manifests.py` (CI checksum gate), plus `make data` / `make verify`.
- `engines/` package with the first engine: **E2 national transmission loss reconciliation** (`/api/engines/loss-reconciliation`), using a scipy sparse DC power flow with numpy/pure-Python fallbacks.
- `docs/ProblemStatement_GridIQ.md`, `docs/Solutions_Report_GridIQ.md`, `docs/DATA_RECONCILIATION.md`, `docs/PROVENANCE_EXTERNAL_DATASETS.md`.

### Changed
- `requirements.txt` adds numpy/scipy for the E2 sparse solve; new `requirements-dev.txt` for pytest/openpyxl.
- README documents the team repo, CI and data policy.

### Validation
- 35 pytest tests pass; manifest verification passes; `python -m compileall` and `node --check` pass; `/api/engines/loss-reconciliation` returns a bracketed transmission-only estimate against BPC 642 GWh / AFREC 630 GWh.

### Known limitations (open)
- E2 is a transmission-only screen with uniform demand allocation across mapped substations; it deliberately undercounts against BPC's T&D figure. Calibration is a follow-up task.
- The E2 dashboard panel is not yet wired; the endpoint is live.
