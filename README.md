# GridIQ Botswana — Evidence-Driven Planning UI v1.4

> **Repository:** `eukaryote1-0/grid-iq` (private) · **Team:** Eukaryote1.0
> **Before contributing:** `CONTRIBUTING.md`, `AGENTS.md`, `.ai/START_HERE.md`
> Land changes via PR with green CI (branch protection needs a paid plan for private repos).
> Large datasets are fetched with `make data`.

GridIQ is a national energy-planning prototype that treats **generation + storage + grid + demand** as one planning problem while keeping observed Botswana evidence, deterministic derivations, external engineering benchmarks, model outputs and unknowns visibly separate.

## v1.4 highlights

- Professional responsive browser UI with persistent navigation/scenario/selection state.
- OpenStreetMap basemap + live Overpass power lines, substations, plants and generators.
- Geometry-derived topology: line length, nodes, segments, connected components, endpoints and junctions.
- **Engineering Benchmark Mode:** supported OSM 132/220/400 kV line geometry can be enriched with documented PyPSA/PyPSA-Earth standard electrical parameters in conservative/reference/high-capacity cases.
- Dependency-free **single-voltage DC transfer sensitivity** using a user-defined MW transfer; no fake Botswana hourly bus load is created.
- Approximate I²R loss post-processing clearly separated from the lossless DC solve.
- Live NASA POWER selected-site weather/resource query.
- Live WorldPop v2 selected-area population query; population remains a demand driver, not MW.
- Official/transformed Botswana evidence: Statistics Botswana Q1 2026 electricity brief, SAPP capacity/peak snapshot, National Energy Compact, 2022 Census district population and NEUS 2022/23 household energy/access tables.
- Deterministic Census×NEUS population-weighted access-gap indicator, explicitly **not** a count of unconnected people/households and not electrical demand.
- IRENA/NREL BESS benchmark layer.
- Historical WRI Botswana power-plant rows as a labelled geolocation reference only.
- SHA-256 evidence manifest for bundled evidence/reference/benchmark/derived files.
- Audit ratings computed from explicit pass/fail evidence gates rather than typed into the frontend.

## Critical evidence boundary

The benchmark network is a **planning sensitivity model**. It is not the current BPC operating model.

GridIQ does not have authoritative BPC:

- bus/branch reconciliation;
- conductor/circuit records and line ratings;
- R/X or transformer parameters;
- switching state;
- time-aligned feeder/substation loads and injections;
- AC power-flow validation or N-1 results.

Accordingly, benchmark transfer utilization must never be described as measured BPC loading or real-time congestion.

## Current evidence-gated audit

The application calculates its audit through `/api/audit`. At release build time the current gate result is:

- UI/application layer: **7.3/10** — browser E2E for this exact release, vendored visual libraries and formal accessibility audit remain outstanding.
- Open-data governance: **10.0/10**.
- Benchmark engineering capability: **10.0/10** for its stated benchmark-sensitivity scope.
- Public-data planning product: **9.2/10**.
- BPC operational validation: **0.0/10** because the required utility engineering/load evidence has not been supplied.
- Whole solution including operational validation: **7.3/10**.

These are not claims of operational BPC accuracy. See the Audit page and `.ai/CURRENT_STATE.md`.

## Run on Ubuntu

```bash
chmod +x run.sh stop.sh doctor.sh
./run.sh
```

Open:

```text
http://127.0.0.1:8000
```

Alternative port:

```bash
PORT=8001 ./run.sh
```

Stop / diagnostics:

```bash
./stop.sh
./doctor.sh
cat gridiq.log
```

The launcher prefers FastAPI. If dependencies cannot be installed, it falls back to a dependency-free stdlib server that preserves the core local API/UI contract.

## Validation

```bash
pytest -q
python -m py_compile app/*.py tests/*.py
node --check web/js/app.bundle.js
```

Current-release browser fixture (requires working Chromium/Chrome):

```bash
BASE_URL=http://127.0.0.1:8000 ./scripts/browser_smoke.sh
```

The build sandbox could not complete Chromium execution, so the current-release browser-regression audit gate is deliberately **false** until the exact v1.4 release is tested on a working browser environment.

## Internet-dependent features

Internet is required for live:

- OSM raster tiles;
- Overpass power geometry;
- NASA POWER;
- WorldPop;
- Leaflet and Chart.js CDN assets.

The bundled evidence, provenance, audit and local screens do not become synthetic substitutes when an upstream service is unavailable.

See `docs/DATA_PROVENANCE.md`, `data/source_manifest.csv`, `data/evidence_manifest.json` and `.ai/START_HERE.md`.
