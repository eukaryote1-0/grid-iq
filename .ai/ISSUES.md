# Open Issues

## ISSUE-001 — BPC operational electrical validation absent
Status: Open

Benchmark line parameters and a DC transfer sensitivity now exist, but authoritative BPC buses, conductor/circuit records, ratings, impedances, transformer parameters, switch state and reconciled injections/loads do not. Therefore operational DC/AC PF, OPF, actual congestion and N-1 validation remain blocked.

## ISSUE-002 — Remaining spatial raster/geometry ingestion
Status: Open

Global Solar/Wind Atlas rasters, Meta HR population and authoritative current Botswana administrative geometry are selected but not physically bundled/tiled.

## ISSUE-003 — Public CDN dependencies
Status: Open

Leaflet and Chart.js are runtime CDN dependencies. Controlled/offline deployment should vendor pinned assets and test integrity/offline startup.

## ISSUE-004 — Live API/upstream availability
Status: Monitoring

Overpass, OSM tiles, NASA POWER and WorldPop depend on public external services. Caching/error states exist; production use needs scheduled ingestion/service-level controls.

## ISSUE-005 — Current-release browser E2E not executable in build sandbox
Status: Open / environment

The available system Chromium hangs even on a `data:` URL and Playwright browser binaries are not installed. `scripts/browser_smoke.sh` is included for workstation validation, but v1.4 must not mark the browser-regression audit gate true until it is run successfully against this exact release.

# Resolved Issues

## ISSUE-R01 — Python 3.14 pydantic-core build failure
Resolved by Python-3.14-compatible pins, binary-wheel install path and stdlib fallback runtime.

## ISSUE-R02 — Blank frontend after launch
Resolved the JavaScript exponentiation syntax error and hardened the bootstrap path.

## ISSUE-R03 — State/map disappeared after navigation
Resolved with localStorage persistence, retained OSM application state and Leaflet map lifecycle recreation.

## ISSUE-R04 — v1.4 compatibility server missing derived-demand import
Found during runtime smoke testing and fixed; both FastAPI and stdlib runtimes now serve `/api/demand/district-context`.

## ISSUE-006 — Benchmark planning model is not operational BPC validation
Status: Open / intentional boundary

All unavailable public planning fields now have a documented benchmark/proxy/UNKNOWN resolution path. The remaining unresolved variable is authoritative BPC operating truth itself. No external benchmark can validate actual switching state, line ratings, transformer parameters, time-aligned loads, failures or condition history.
