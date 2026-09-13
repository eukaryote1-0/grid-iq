# Architecture

## Implemented v1.7 runtime

```text
Browser UI (HTML/CSS/JS)
  ├─ localStorage state persistence
  ├─ Leaflet + OSM tiles (pinned public CDN runtime dependency)
  ├─ Chart.js (pinned public CDN runtime dependency)
  └─ observed / derived / benchmark / model-output / unknown labels
             ↓
FastAPI preferred runtime
or stdlib compatibility server
             ↓
Local evidence substrate
  ├─ official Botswana snapshots
  ├─ Census + NEUS tables
  ├─ BPC loss anchor/history
  ├─ SAPP transfer limits
  ├─ deterministic derived district-access context
  ├─ storage / renewable / community-cost benchmarks
  ├─ electrical + transformer benchmark libraries
  ├─ load-profile benchmark registry
  ├─ benchmark gap-resolution register
  └─ SHA-256 evidence manifest
             ↓
Live connectors
  ├─ Overpass → OSM power GeoJSON → topology
  ├─ NASA POWER → daily/hourly site resource
  ├─ WorldPop → selected-area population
  ├─ World Bank GEP → modelled resource/demand/grid-distance context
  ├─ World Bank DRE → settlement screening/candidate register
  └─ open Botswana admin GeoJSON → non-authoritative boundary substitute
             ↓
Engines
  E1 annual LP + 24h benchmark chronology
  E2 single-transfer + multi-injection benchmark DC PF + I²R post-process
     + BPC loss reconciliation
  E3 topology structural criticality / N-1 geometry / edge betweenness
  E4 VillageFit / DRE settlement screen / grid-extension / BESS / biogas evidence gate
```

### Backend
- `app/main.py`: FastAPI API/static server and live async connectors.
- `app/compat_server.py`: stdlib fallback preserving core local API behavior; advanced chronology may require preferred runtime.
- `app/logic.py`: source loading, topology, electrical enrichment, DC solvers, scenario screening and audit gates.
- `app/engines.py`: E1/E3/E4, loss reconciliation and benchmark-chronology logic.

### Frontend
- `web/index.html`: application shell + startup-failure guard.
- `web/css/app.css`: responsive control-centre UI.
- `web/js/app.bundle.js`: authoritative browser application; pages, state, engine controls, map/charts and evidence audit.

### Data
- `data/official/`: transformed public/official Botswana evidence.
- `data/derived/`: deterministic derived data products.
- `data/benchmarks/`: external benchmarks plus `gap_resolution.json`.
- `data/reference/`: historical/modelled reference metadata.
- `data/evidence_manifest.json`: release SHA-256 traceability.
- `data/cache/`: generated connector cache, never authoritative source truth.

## Model boundaries

### Planning/benchmark closure
When a public Botswana field is unavailable, GridIQ may use a named benchmark dataset if the substitution is technically meaningful and its provenance remains visible. Examples: standard line R/X/rating envelopes, normalized regional hourly demand shape, modelled DRE/GEP settlement data, and open boundary geometry.

### Operational validation
No benchmark can validate actual BPC switching state, actual transformer/line ratings, real-time load/injection, equipment condition or failure history. `bpc_operational_validation` therefore remains independent and zero until authoritative BPC evidence is supplied and reconciled.

## Target architecture — planned, not implemented

```text
raw sources → ETL/staging/provenance → PostgreSQL + PostGIS + pgRouting
                                          ↓
                         FastAPI + Celery/Redis workers
                    E1 LP | E2 PF/OPF | E3 criticality | E4 siting
                                          ↓
                     vector tiles + COG/TiTiler rasters
                                          ↓
                           Next.js + MapLibre/Deck.GL
```

Do not describe the target PostGIS/worker/tile stack as implemented.
