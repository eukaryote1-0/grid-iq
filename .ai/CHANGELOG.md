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

## 2026-09-13 — v1.7 benchmark gap-resolution iteration

### Added
- benchmark gap-resolution register;
- E2 balanced multi-injection benchmark DC power-flow endpoint;
- E1 24-hour benchmark chronology surfaced in the UI;
- DRE-derived settlement candidate register;
- non-authoritative open boundary GeoJSON connector;
- Eskom/PyPSA-Earth demand-benchmark catalog entries.

### Changed
- audit now separates planning closure from BPC operational validation;
- unavailable planning inputs are resolved with named benchmarks/proxies wherever defensible;
- public planning product score is evidence-gated and does not raise operational validation.

### Validation
- exact final validation recorded in `reports/VALIDATION.md` and `.ai/CURRENT_STATE.md`.

## 2026-09-13 — v1.7 merge + platform bootstrap (team repo)

### Added
- repository scaffolding for `eukaryote1-0/grid-iq`: `CONTRIBUTING.md`, `AGENTS.md`, `Makefile`, CI workflow, PR/issue templates, CODEOWNERS, `.gitattributes`;
- committed external datasets with SHA-256 manifests: filtered OSM power lines (132/220/400 kV), OSM substations, World Bank/AICD Botswana grid layer, Botswana techno-economic workbook (Zenodo/Loughborough CCG);
- `scripts/fetch_data.sh`, `scripts/verify_manifests.py`, `make data`, `make verify`;
- `engines/` package with the GridIQ E2 cross-check loss engine (`/api/engines/loss-reconciliation`);
- `docs/ProblemStatement_GridIQ.md`, `docs/Solutions_Report_GridIQ.md`, `docs/DATA_RECONCILIATION.md`, `docs/PROVENANCE_EXTERNAL_DATASETS.md`.

### Changed
- merged the v1.7 tree (E1–E4 planning engines, benchmark gap-resolution register, new official/benchmark/reference datasets);
- `requirements.txt` now pins numpy/scipy/networkx for the planning engines.

### Notes
- BPC 2024 T&D losses (793 GWh, 16.62%) are now sourced to BPC IR 2024/25 in `data/official/bpc_system_losses.json`, resolving the earlier unverified figure; the 2023 anchor (642 GWh, 14.51%) is unchanged pending team decision.

### Refactor
- `app/engines.py` split into the `engines/` package (payloads, E1, E2, E3, E4, supply) per `AGENTS.md`; `app/main.py`/`app/compat_server.py` rewired; the independent E2 transmission-loss cross-check kept at `/api/engines/loss-reconciliation`.

### Docs
- Solutions Report: added three user journeys (planner, community, custodian) modelled on BEAM's flow sections; split the technology stack into implemented-today vs target architecture; surfaced the 2024 BPC loss figure (793 GWh / 16.62%) now that it is sourced.
