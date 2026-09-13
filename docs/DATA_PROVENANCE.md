# Data provenance and transformations

GridIQ's governing rule is: **unknown is not zero, and missing data is not permission to fabricate it.**

## Physically bundled Botswana evidence

### Statistics Botswana / BPC — Electricity Generation & Distribution Q1 2026
Stored as `data/official/botswana_energy_baseline.json`.

Used for national quarterly generation/import history, Q1 2026 generation mix, imports and distribution. Values are transformed from published tables into machine-readable JSON. No interpolation is used.

### SAPP — Botswana/BPC Demand & Supply
A published current snapshot is bundled in `botswana_energy_baseline.json` for installed capacity, operating capacity, peak demand, peak plus reserve and the published capacity shortfall.

### Botswana National Energy Compact
Published planning values are bundled in `botswana_energy_baseline.json`: transmission lengths by voltage class, system-loss context, access and renewable targets, named interconnectors/projects, and long-run demand context.

### Statistics Botswana — 2022 Population and Housing Census
`data/official/botswana_census_district_population_2022.json` contains the published 2022 district population table. Population is used only as demand context. It is not converted into MW in this release.

### Statistics Botswana — National Energy Use Survey 2022/23
`data/official/botswana_neus_2022_23.json` contains transformed published tables for:

- district grid-connection rates;
- national household electricity access;
- renewable technology penetration by locality type;
- reasons households are not connected to the grid;
- selected household energy-use context.

The report contains an internal published-total discrepancy: Table 14 prints 634,150 total households, while 468,344 connected + 165,732 not connected = 634,076, and the narrative also states 634,076. GridIQ uses the internally consistent 634,076 value and records 634,150 separately rather than silently hiding the discrepancy.

These are survey estimates, not BPC feeder/substation measurements.

### WRI Global Power Plant Database
`data/reference/wri_gppd_botswana_historical.json` contains the two historical Botswana rows used only to cross-check plant locations. The dataset is stale and is not used as the current national capacity source.

## Live public APIs

### OpenStreetMap / Overpass
`GET /api/osm/power` downloads mapped public power infrastructure and converts Overpass elements to GeoJSON. GridIQ computes geometry-only topology and mapped line length. The transformation does not invent ratings or power-system parameters.

### NASA POWER
`GET /api/nasa/power?lat=...&lon=...` retrieves gridded daily solar irradiation, temperature and 10 m wind speed. These are planning-grade resource variables, not a bankability study.

## External benchmarks

### IRENA + NREL ATB
`data/benchmarks/storage_benchmarks.json` supplies transparent BESS cost/performance benchmarks where Botswana procurement/performance data are unavailable. They are explicitly labelled external benchmarks.

## Selected but not yet physically ingested

- Global Solar Atlas / Global Wind Atlas raster layers.
- Meta High Resolution Population Density raster/CSV.
- Authoritative current Botswana administrative geometry.
- OSM/HDX roads/settlements extract for offline analysis.
- South African DEL hourly load profile, if licensing/source quality is acceptable, only as a clearly labelled regional benchmark.

## Data still required for real power-flow/OPF

A production electrical model requires a BPC data contract including at minimum bus/substation IDs, voltage, line/transformer connectivity, thermal ratings, R/X or equivalent impedances, transformer parameters, time-aligned load/injection, generator limits, interconnector limits and model reconciliation identifiers. Until those exist, UI topology must not be interpreted as electrical feasibility.

## v1.4 enrichment — documented engineering benchmark layer

### PyPSA-Earth / PyPSA standard transmission parameters
`data/benchmarks/electrical_benchmarks.json` contains a deliberately small benchmark library derived from documented PyPSA/PyPSA-Earth standard transmission assumptions. It is used only when an OSM line has a mapped voltage that GridIQ can match to a supported benchmark family.

For every enriched line GridIQ preserves separate fields for:

- observed OSM voltage/geometry/tags;
- derived geodesic line length;
- benchmark line type, resistance, reactance and current limit;
- benchmark circuit-count assumption where OSM does not map circuits;
- model-output transfer flow/utilisation/loss sensitivity.

The benchmark layer does **not** overwrite the source OSM properties and does not claim the selected conductor or rating is installed on the BPC network. Three cases (`conservative`, `reference`, `high_capacity`) are available so unknown conductor choice is exposed as sensitivity rather than hidden as false precision.

The DC transfer study is intentionally a user-defined injection/withdrawal sensitivity on one mapped voltage layer. It does not fabricate a Botswana hourly load curve. It refuses to bridge disconnected OSM components. DC power flow is lossless; the displayed I²R loss is a separate approximation using the same documented benchmark resistance.

### WorldPop spatial population API
GridIQ can query WorldPop around a user-selected coordinate. The returned population count remains a **population/demand-driver variable**. It is not multiplied by an arbitrary per-capita factor and called electrical load. Census and NEUS remain the official Botswana demographic/access anchors; WorldPop adds sub-district spatial distribution where useful.

## Evidence integrity manifest
`data/evidence_manifest.json` is generated from the exact bundled evidence/reference/benchmark files and records SHA-256 plus byte size. It excludes itself from hashing to avoid recursive mutation. The manifest is release traceability, not a claim that upstream sources have been independently audited by GridIQ.

## Evidence classes used by the application

- **Observed / official Botswana snapshot:** published Botswana/SAPP values transcribed without interpolation.
- **Observed public GIS:** mapped OSM geometry/tags as returned by the connector.
- **Derived Botswana:** deterministic calculations from observed geometry/tables, such as line length or topology degree.
- **External engineering benchmark:** documented technology/network parameters used only when Botswana-specific engineering parameters are unavailable.
- **Model output:** result of a stated calculation using observed/derived/benchmark inputs.
- **Unknown:** retained as unknown when neither derivation nor a defensible benchmark is available.

At no point should an external benchmark be relabelled as a BPC measurement.

### Census + NEUS district enrichment
`data/derived/district_access_pressure_2022_23.json` deterministically joins the 2022 Census district population table to the NEUS 2022/23 household grid-connection percentages. Exact labels are preferred. Three spelling/format label normalisations are explicitly recorded (`Barolong`→`Borolong`, `Serowe-Palapye`→`Serowe Palapye`, `Ngamiland East`→`Ngami East`). `Southern`, `Delta`, and `CKGR` remain unmatched rather than being forced onto uncertain NEUS geography.

The derived `population_weighted_access_gap_index = population × (1 - household connection rate)` is a prioritisation indicator only. Because the inputs mix people and household percentages, it must **never** be displayed or described as a count of unconnected people/households, and it is not electrical demand.

## v1.7 benchmark gap-resolution policy

`data/benchmarks/gap_resolution.json` is the authoritative register for public-data gaps. Each entry records the missing Botswana field, the external benchmark/proxy source, what the substitute enables, and the remaining evidence boundary.

Examples:
- BPC R/X/rating gaps → PyPSA/Pandapower standard line types for planning envelopes only.
- BPC transformer gaps → standard transformer types for sensitivity only.
- Botswana hourly load-shape gap → normalized Eskom metering-based hourly shape and PyPSA-Earth modelled-demand methodology; Botswana magnitude is anchored to published Botswana statistics.
- Official boundary-file gap → open Botswana administrative GeoJSON, explicitly non-authoritative.
- Current exhaustive unconnected-village register gap → World Bank DRE settlement candidate screening, explicitly not BPC connection-status truth.
- BPC asset-condition/failure-history gap → structural topology criticality, not predictive maintenance.

A benchmark may replace an input for a **planning scenario**. It never replaces the provenance class of the missing observation.
