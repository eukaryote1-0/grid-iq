# Dataset Provenance — GridIQ

Recorded: 2026-09-13. All files fetched with `curl` (User-Agent: browser). Licences are CC-BY 4.0 unless noted. Each GeoJSON was downloaded from the World Bank file host and cleaned by truncating a trailing `System.IO.MemoryStream` artefact (raw copies kept as `*.geojson.raw`).

## 1. Botswana Electricity Transmission Network

- **File:** `datasets/grid/botswana_grid.geojson` (raw: `.geojson.raw`)
- **Source:** World Bank / ESMAP via energydata.info — <https://energydata.info/dataset/botswana-electricity-transmission-network-2007>
- **Direct URL:** `https://datacatalogfiles.worldbank.org/ddh-published/0040468/DR0050472/botswanagrid.geojson`
- **Origin:** BPA (Bonneville Power Administration) 2006 Annual Report, supplemented by ESKOM (Dec 2006 `tx_lines.shp`). Release year 2007; catalogue updated 2024-09-26.
- **Licence:** CC-BY 4.0. **CRS:** EPSG:4326.
- **Content:** 68 line features (62 existing, 6 planned), 7 voltage classes (22–500 kV), 49 named nodes, ~6,013 km total including cross-border and planned segments.
- **Validation vs BPC published stats** (BPC: 1,246 km @400 kV; 2,200 @220 kV; 2,162 @132 kV):

| Voltage | Dataset existing (km) | BPC published (km) | Note |
|---|---|---|---|
| 400 kV | 198.6 | 1,246 | ~84% of the current 400 kV network post-dates 2006 |
| 220 kV | 836.8 | 2,200 | ~62% missing from dataset |
| 132 kV | 1,209.3 | 2,162 | ~44% missing from dataset |
| 66 kV | 804.7 | — | not in BPC headline stat |
| 33 kV | 1,969.6 | — | distribution-level |
| 22 kV | 17.6 | — | distribution-level |
| 500 kV (planned) | 652.2 | — | WESTCOR Inga Southern Highway / Auas–Gaborone |
| 220 kV (planned) | 286.5 | — | |
| 66 kV (planned) | 37.5 | — | |

- **Findings:** The 2006-vintage layer captures only ~40% of the current 400/220/132 kV network, so it is a **cross-check, not the primary topology**. It is nonetheless valuable for: cross-border corridors (Matimba–Phokoje 400 kV from Eskom; Francistown–Bulawayo 220 kV and Phokoje–Insukamini 400 kV to Zimbabwe; Auas–Gaborone 500 kV planned from Namibia), 33/66 kV detail, and the planned 500 kV WESTCOR corridor. OpenStreetMap/OpenInfraMap remains the primary topology.

## 2. Africa Electricity Transmission and Distribution Grid Map

- **Files:** `datasets/grid/africa_grid_existing.geojson`, `datasets/grid/africa_grid_planned.geojson`
- **Source:** World Bank / ESMAP — <https://energydata.info/dataset/africa-electricity-transmission-and-distribution-grid-map-2017> (release 2017; updated 2024-09-26). Supersedes AICD 2007. Sources include AICD, OpenStreetMap, WAPP, World Bank project archives.
- **Licence:** CC-BY 4.0. **CRS:** EPSG:4326.
- **Content:** existing = 56,863 features; planned = 5,138 features; tagged with `country`, `status`, `source`, `operator`, `voltage_kV`, `length_km`. Botswana subset is identical to layer 1 above (68 existing features, ~5,037 km; 12 planned, ~976 km). Useful for regional/cross-border context and for validating the OSM-derived topology elsewhere.

## 3. Botswana Techno-Economic Dataset for Long-Term Energy Systems Modelling

- **File:** `datasets/benchmarks/botswana_techno_economic.xlsx`
- **Source:** Zenodo record 10547474, DOI 10.5281/zenodo.10547474 (Saad, R. et al.; Loughborough University / Climate Compatible Growth; OSeMOSYS/TEMBA). Published 2024-01-22. Licence CC-BY 4.0.
- **Content:** 15 sheets — electricity generation, consumption by sector, capacity by sub-technology (IRENA), imports/exports (IEA), import prices, CO2 factors, fuel prices, refineries, transmission & distribution, power plants, **cost of RE power plants (2015–2050)**, fossil reserves, RE supply potential.
- **Key values used:** transmission capital cost **365 US$/kW (2020)** and distribution **2,502 US$/kW (2020)**, with O&M, operational life and efficiency (source: TEMBA); renewable and fossil plant capital costs 2015–2050 (IRENA/TEMBA). These let GridIQ replace "capex assumed (generic benchmark)" with a **Botswana-specific, cited techno-economic dataset**.
- **Caveat:** these are modelling assumptions with a 2020 base year, not BPC's actual project costs; still labelled as assumptions in outputs.

## 4. Sources noted but not yet ingested

- **gridfinder** global predicted grid (World Bank/ESMAP, CC-BY 4.0; Zenodo 3538890) — optional fallback where OSM is sparse; explicitly not for power-flow.
- **SciGRID / GridKit / POMATO** default per-km resistance/reactance by voltage class — to calibrate assumed line parameters (methodological benchmark).
- **Global Electrification Platform / OnSSET** (World Bank/ESMAP) — least-cost electrification method for Engine 4.
- **ENTSO-E Transparency Platform / AEMO** — load, flow and loss-factor methodology analogues.

## Reproduction

```
curl -sL -A "Mozilla/5.0" -o datasets/grid/botswana_grid.geojson \
  https://datacatalogfiles.worldbank.org/ddh-published/0040468/DR0050472/botswanagrid.geojson
curl -sL "https://zenodo.org/api/records/10547474/files/Technoeconomic_data_assumptions_Botswana_v1.xlsx/content" \
  -o datasets/benchmarks/botswana_techno_economic.xlsx
# then strip the trailing non-JSON line before parsing
```
