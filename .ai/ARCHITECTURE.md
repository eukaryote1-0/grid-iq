# Architecture

## Implemented v1.4 runtime

```text
Browser UI (HTML/CSS/JS)
  ├─ localStorage state persistence
  ├─ Leaflet + OSM tiles (external runtime dependency)
  ├─ Chart.js (external runtime dependency)
  └─ evidence / benchmark / unknown labels
             ↓
FastAPI preferred runtime
or stdlib compatibility server
             ↓
Local evidence substrate
  ├─ official Botswana snapshots
  ├─ Census + NEUS source tables
  ├─ deterministic derived district access context
  ├─ storage benchmark
  ├─ electrical benchmark library
  ├─ historical plant reference
  └─ SHA-256 evidence manifest
             ↓
Live connectors
  ├─ Overpass → GeoJSON → geometry topology
  ├─ NASA POWER → site-resource series
  └─ WorldPop v2 → selected-area population
             ↓
Benchmark engineering path
  OSM observed geometry/voltage
      + derived line length/connectivity
      + external PyPSA standard line parameters
      + explicit user transfer MW
             ↓
  single-voltage DC transfer sensitivity
      + benchmark thermal screen
      + approximate I²R post-process
```

### Backend
- `app/main.py`: FastAPI API/static server and live async connectors.
- `app/compat_server.py`: stdlib fallback preserving core API behavior.
- `app/logic.py`: evidence loading, transformations, topology, electrical enrichment, DC transfer solver, scenario screening and audit gates.

### Frontend
- `web/index.html`: shell + startup-error protection.
- `web/css/app.css`: responsive control-centre design.
- `web/js/app.bundle.js`: authoritative application bundle; state, views, map, charts and API interaction.

### Data
- `data/official/`: transformed published Botswana evidence.
- `data/derived/`: deterministic combinations of published evidence; never source truth.
- `data/benchmarks/`: external engineering/technology benchmarks.
- `data/reference/`: non-current cross-check/reference sources.
- `data/evidence_manifest.json`: release SHA-256 traceability for bundled data inputs.
- `data/cache/`: runtime connector cache; generated, not authoritative source input.

## Model boundaries

The benchmark DC transfer model deliberately does not construct fake national load. A user chooses transfer MW, source and sink. It solves only a connected OSM component at one supported voltage. If source/sink map to separate components it refuses to invent a connection. DC PF is lossless; resistance-based I²R loss is a separately labelled post-process.

Observed/derived/benchmark/model-output fields remain distinct. Benchmark line parameters never overwrite OSM source tags.

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
