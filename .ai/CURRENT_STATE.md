# Current state

## Current status

Implemented in v1.7:
- persistent professional dashboard with real OSM map/topology;
- official Botswana generation/import, Census, NEUS, BPC loss, SAPP and rural-electrification evidence;
- live NASA POWER, WorldPop, World Bank GEP/DRE and OSM/Overpass connectors;
- documented PyPSA/Pandapower line/transformer benchmark enrichment;
- E1 annual HiGHS capacity-expansion screen;
- E1 24-hour benchmark chronology using normalized Eskom demand shape + NASA solar shape calibrated to Botswana anchors;
- E2 single-transfer and multi-injection benchmark DC PF, branch utilisation and approximate I²R losses;
- E2 BPC 642 GWh loss-reconciliation harness;
- E3 structural criticality + N-1 geometry islanding + edge betweenness + BPC data contract;
- E4 VillageFit for verified pilots and explicit/DRE settlements;
- DRE-derived candidate register for screening beyond the verified pilot cohort, never called BPC connection status;
- benchmark boundary GeoJSON connector for spatial joins when official Botswana polygons are unavailable;
- explicit gap-resolution register mapping unavailable Botswana fields to named external benchmark/proxy sources;
- SHA-256 evidence manifest and evidence-gated audit.

## Current audit position

Computed from `/api/audit`:
- UI/application 6.8/10;
- problem evidence 10.0/10;
- engine implementation 10.0/10 at stated planning/benchmark scopes;
- data coverage 10.0/10 at public+benchmark scope;
- open-data governance 10.0/10;
- benchmark engineering capability 10.0/10;
- public-data planning product 9.5/10;
- BPC operational validation 0.0/10;
- whole solution including operational validation 8.0/10.

## Current blockers

- No authoritative BPC bus/branch reconciliation, actual line ratings, impedances, transformer parameters, switching state or time-aligned operating loads/injections.
- Browser E2E for this exact release is not certified in the build environment.
- Leaflet and Chart.js remain pinned public-CDN runtime dependencies.
- Formal accessibility/WCAG + screen-reader validation is incomplete.
- Official Statistics Botswana sub-district geometry is still not bundled; the new open boundary connector is explicitly a non-authoritative substitute.

## Known broken functionality

No known bundled API/model failure after the current test suite. External live connectors can fail; those paths must report degraded state rather than generate substitute facts.

## Validation performed

- `pytest -q`: 32 passed before final packaging.
- `python -m py_compile app/*.py tests/*.py`: required before packaging.
- `node --check web/js/app.bundle.js`: required before packaging.
- FastAPI smoke: health/audit/gap register/loss-reconciliation passed on port 8131.
- Compatibility-runtime smoke: health/audit/gap-register passed via `run.sh` fallback.
- Exact ZIP extraction/retest is required before release.

## Immediate next steps

1. Run browser smoke on the user's Ubuntu/Chrome environment and only then raise the browser-E2E gate.
2. Vendor pinned Leaflet/Chart.js locally and run formal accessibility testing if targeting production UI certification.
3. Replace benchmark BPC electrical/load fields with authoritative BPC data when supplied and run operational calibration/N-1/AC validation.
