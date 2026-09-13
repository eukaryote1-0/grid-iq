# GridIQ Botswana — Evidence-Driven Planning UI v1.7

> **Repository:** `eukaryote1-0/grid-iq` (private) · **Team:** Eukaryote1.0
> **Before contributing:** `CONTRIBUTING.md`, `AGENTS.md`, `.ai/START_HERE.md`
> Land changes via PR with green CI (branch protection needs a paid plan for private repos).
> Large datasets are fetched with `make data`; committed checksums are checked with `make verify`.

GridIQ treats **generation + storage + grid + demand** as one planning problem. v1.7 closes public-data gaps with named benchmark datasets or deterministic proxies where technically defensible, while keeping BPC operational truth separate.

## Evidence rule

**Observed Botswana data → deterministic derived data → named external benchmark/modelled data → UNKNOWN if no defensible substitute exists.**

A benchmark may close a planning capability. It does **not** become measured BPC data.

## v1.7 implemented scope

- Real OSM/Overpass power geometry and topology.
- PyPSA/Pandapower benchmark R/X/current envelopes for mapped 132/220/400 kV lines.
- Single-transfer and **multi-injection benchmark DC power-flow** with branch utilisation and approximate I²R loss post-processing.
- BPC 642 GWh / 14.51% FY2023 loss anchor + loss-reconciliation harness.
- E1 annual least-cost capacity-expansion screening with SciPy/HiGHS.
- E1 24-hour benchmark chronology using a normalized Eskom hourly demand benchmark + NASA POWER solar shape, calibrated to published Botswana anchors.
- E3 bridges, articulation points, deterministic N-1 geometry islanding and edge-betweenness watch-list.
- E4 VillageFit with verified pilot villages, World Bank DRE settlement search, GEP/NASA resource context, grid-extension benchmark cost and evidence-gated biogas pathway.
- DRE-derived candidate register for broader settlement screening when a verified current BPC unconnected-village register is unavailable. This is **not** relabelled as connection status.
- WorldPop, Census, NEUS, SAPP, Botswana electricity statistics, agricultural context and renewable/BESS benchmarks.
- Non-authoritative open Botswana boundary GeoJSON connector used only as a benchmark geometry substitute until the official Statistics Botswana polygon is supplied.
- `data/benchmarks/gap_resolution.json` documents each unavailable field, the benchmark used, what it enables, and what it still cannot claim.
- Persistent application state across navigation and explicit provenance/audit pages.

## Current evidence-gated audit

Calculated by `/api/audit` from named requirements and release gates:

- UI/application: **6.8/10** — the exact release lacks browser E2E certification, locally vendored Leaflet/Chart.js, and a formal WCAG/screen-reader audit.
- Problem evidence: **10.0/10** at the documented open-data/problem-validation scope.
- Engine implementation: **10.0/10** at the explicitly stated **planning / benchmark / screening scopes**.
- Data coverage: **10.0/10** at the public-data + benchmark-substitution scope.
- Open-data governance: **10.0/10**.
- Benchmark engineering capability: **10.0/10** for planning sensitivities.
- Public-data planning product: **9.5/10**.
- **BPC operational validation: 0.0/10** — benchmarks cannot validate real BPC ratings, switching state, transformer parameters or time-aligned operating loads.
- Whole solution including BPC operational validation: **8.0/10**.

The 9.5 planning score is not a claim of SCADA/EMS-grade accuracy.

## Run on Ubuntu

```bash
chmod +x run.sh stop.sh doctor.sh
./run.sh
```

Open `http://127.0.0.1:8000`.

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

## Validation

```bash
pytest -q
python -m py_compile app/*.py tests/*.py
node --check web/js/app.bundle.js
```

The build environment cannot certify the current browser E2E gate; `scripts/browser_smoke.sh` is included for a workstation with a working Chromium/Chrome.

## Internet-dependent features

Live OSM/Overpass, NASA POWER, WorldPop, World Bank GEP/DRE, the benchmark boundary connector, and current Leaflet/Chart.js CDN assets require internet. If an upstream source is unavailable, GridIQ reports a degraded state rather than substituting fabricated data.

See `docs/DATA_PROVENANCE.md`, `data/source_manifest.csv`, `data/evidence_manifest.json`, `data/benchmarks/gap_resolution.json`, and `.ai/START_HERE.md`.
