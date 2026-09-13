# Frontend JavaScript

`app.bundle.js` is the runtime source for the hackathon release. It is intentionally self-contained so the local launcher does not require Node/npm.

Important invariants:
- no synthetic hourly demand or solar fallback series;
- localStorage persists user analysis point, NASA response, scenario inputs/results, and current view;
- the Leaflet map is destroyed/recreated when the `#energyMap` DOM node is replaced by navigation;
- OSM geometry/topology is evidence only, never an electrical bus/branch model;
- Chart.js/Leaflet are pinned CDN dependencies in this release and are a known production-hardening gap.
