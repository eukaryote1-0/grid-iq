# Decisions

## DEC-001 — Evidence before visual completeness
Date: 2026-09-13
Status: Accepted

### Decision
Unknown BPC engineering values remain unknown. The product must not manufacture congestion, line loading, transformer condition, hourly demand or power-flow values to make the UI look complete.

### Consequence
Unsupported outputs are visibly gated and the scenario engine is limited to calculations supported by published inputs/benchmarks.

## DEC-002 — OSM topology is geometry topology
Date: 2026-09-13
Status: Accepted

### Decision
Derive nodes/segments/components/junctions from OSM mapped line geometry for visualization/data-quality screening only. Do not use it as an electrical bus/branch model.

### Reason
OSM does not supply a complete validated BPC model with required impedances, ratings, switch states and load/injection reconciliation.

## DEC-003 — Remove synthetic hourly load/solar profile
Date: 2026-09-13
Status: Accepted

### Decision
The previous generated 24-hour demand/solar/dispatch series was removed.

### Consequence
Import displacement, dispatch and congestion remain unavailable until a defensible time-series input/model exists.

## DEC-004 — Persist navigation/scenario analysis state
Date: 2026-09-13
Status: Accepted

### Decision
Use browser localStorage for selected page, analysis point, NASA result, scenario inputs/result and topology toggle; retain loaded OSM data in application state and recreate detached Leaflet maps after navigation.

### Reason
The prior SPA rebuilt DOM sections and lost map/state when navigating away and back.

## DEC-005 — Transform published tables into local machine-readable evidence
Date: 2026-09-13
Status: Accepted

### Decision
Transcribe/normalize published Statistics Botswana/BPC, SAPP, Energy Compact, Census and NEUS values into versioned JSON with source URLs and explicit transformation notes.

### Reason
This allows the UI/API to operate deterministically without replacing source values with synthetic placeholders.

## DEC-006 — Benchmark electrical model is a separate evidence class
Date: 2026-09-13
Status: Accepted

### Context
OSM gives useful Botswana power geometry/voltage tags but not the complete electrical parameters required by DC PF/OPF.

### Decision
Enrich supported OSM voltage classes with documented PyPSA/PyPSA-Earth line-type parameters in three sensitivity cases. Preserve these under a benchmark namespace and label every result as planning-model output, never BPC measurement.

### Reason
This permits technically meaningful network sensitivity without silently inventing utility asset data.

### Consequence
The public-data planning model can perform benchmark transfer/thermal/loss sensitivity, but BPC operational validation remains a separate failed audit gate until utility data arrive.

## DEC-007 — Do not create a fake Botswana hourly load to enable PF
Date: 2026-09-13
Status: Accepted

### Decision
The current benchmark DC solver uses a user-defined transfer between two mapped nodes instead of fabricating hourly bus loads from population.

### Reason
Census/NEUS/WorldPop are demand drivers, not metered MW. Using them directly as MW would create false precision.

## DEC-008 — Census × NEUS may produce a prioritisation index, not people/load counts
Date: 2026-09-13
Status: Accepted

### Decision
Join district population to NEUS household connection percentages only for a labelled population-weighted access-gap index. Retain unmatched districts rather than force uncertain geography.

### Consequence
The index can rank spatial access pressure, but it cannot be called unconnected population, unconnected households, or electrical demand.

## DEC-009 — Audit scores must be computed from evidence gates
Date: 2026-09-13
Status: Accepted

### Decision
Do not hard-code 9.x scores in the UI. `audit_payload()` computes component scores from named pass/fail gates and separates public-data planning capability from BPC operational validation.

## DEC-007 — Benchmark substitution closes planning gaps, not operational truth

Date: 2026-09-13
Status: Accepted

### Context
Several BPC operational fields required by the full power-system model are not publicly available.

### Decision
Use named external benchmark datasets or deterministic open-data proxies to keep planning workflows executable when technically defensible. Preserve a separate BPC operational-validation gate at zero until authoritative BPC data are supplied and reconciled.

### Consequences
- E1 can run benchmark chronology with regional/modelled load shape calibrated to Botswana anchors.
- E2 can run benchmark single/multi-injection DC studies over OSM geometry.
- DRE/GEP can produce settlement planning candidates without asserting connection status.
- Benchmark line/transformer parameters must never be displayed as measured BPC values.
