# NATIONAL OPEN DATA INNOVATION CHALLENGE 2 — ENERGY & ENVIRONMENT

# GridIQ — Solutions Report

**Team Eukaryote1.0 | Gaborone, Botswana | September 2026**

*Plan the grid as one system, not three separate bets.*

**Anchor: 642 GWh of electricity was lost in FY2023 — 14.51% of units — by BPC's own accounting.**

## Executive Summary

Botswana plans its electricity system as a series of separate projects. Generation,
storage and grid are decided one at a time, so the country stays over-reliant on
coal at Morupule and on imported power, rural villages wait for a last mile that
is never the cheapest option, and the network is run without knowing which assets
matter most.

GridIQ is one shared, data-grounded model of that system, with four engines
reading the same topology, demand and injection points:

1. **System-wide optimisation** — what to build, where, how much and how to connect, against one objective.
2. **Flow, congestion & losses** — where constraints bind and what they cost.
3. **Asset-risk screening** — which assets are structurally critical, plus the data contract that would unlock prediction.
4. **VillageFit** — the right technology for each unconnected village, scored against the cost of a line.

Because all four read the same substrate, no recommendation can silently
contradict another. This is what makes GridIQ a platform rather than four scripts.

Our differentiator is that the model's loss output is **checkable against a figure
BPC has already published** (642 GWh, FY2023). So the demo is a falsifiable test,
not a presentation: if the numbers reconcile, every other engine inherits the
credibility of a substrate that just proved itself.

**One-sentence pitch:** GridIQ helps BPC and Ministry planners — and the
households and villages they serve — who struggle with a grid planned
project-by-project, by providing one shared model of generation, storage, grid
and demand, so that supply is planned at the lowest system cost, losses fall, and
the last mile is served by the right technology.

## 1. Problem Definition & Context

### 1.1 Supply is planned project-by-project

Botswana's fleet is dominated by two coal stations — Morupule A (132 MW) and
Morupule B (600 MW) — plus diesel peaking. Installed capacity sits around 892 MW
against peak demand of 678 MW (2024), yet on a five-year rolling average domestic
generation has covered only about 62% of supply. The rest is imported, and in Q1
2026 80.9% of imports came from Eskom alone. Local generation has covered as
little as ~44% of distribution in a quarter. Meanwhile, new projects are appraised
on resource potential alone: a strong solar site far from load can force a costly
line upgrade the resource map never shows.

| Who is affected | How they are harmed |
|---|---|
| Households and businesses | Unreliable supply and import-priced electricity. |
| BPC and Ministry planners | Must choose what to build next with no system-cost view. |
| Budget and tariff payers | Grid spend that a better-placed project would not have needed. |

| Failure mode | Consequence | Scale |
|---|---|---|
| One dominant generation site | A single coal fleet's availability sets national supply. | National |
| One dominant import corridor | Cost and reliability exposed to one supplier. | National |
| Project-by-project appraisal | Stranded grid spend; sub-optimal siting. | Every new project |

### 1.2 The network is operated reactively

There is limited published visibility of where the network is congested, or which
assets have no redundant path. Faults are answered after they happen. Public asset
age, condition, inspection and failure data for BPC and other Botswana utilities is
limited: no open dataset was found.

| Who is affected | How they are harmed |
|---|---|
| Households and businesses | Outages they cannot anticipate or avoid. |
| BPC crews | Respond to failures instead of pre-empting them. |
| Planners | Cannot rank where maintenance or redundancy pays. |

| Failure mode | Consequence | Scale |
|---|---|---|
| No criticality view | A non-redundant asset can island a load pocket. | Network-wide |
| No condition data | Maintenance is reactive, not prioritised. | Every asset |

### 1.3 The last mile is stuck

As of October 2024, 463 of Botswana's 565 gazetted villages were connected —
102 still unconnected, roughly one in six. These are exactly the low-density,
far-flung settlements skipped in earlier phases, where line extension is
disproportionately expensive. Government's stated fix is solar off-grid
electrification, applied as the default rather than chosen per village.

| Who is affected | How they are harmed |
|---|---|
| Rural households | No grid power; limited study, enterprise and health services. |
| Rural students | A government laptop with nowhere to charge it. |
| The state budget | Pays for a generic rollout instead of the cheapest fit. |

| Failure mode | Consequence | Scale |
|---|---|---|
| One technology prescribed everywhere | Poor fit where sun is weak and wind/biomass is strong. | ~100 villages |
| No per-village comparison | Line extension assumed, not tested against mini-grids. | ~100 villages |

## 2. Solution Description

### 2.1 The shared substrate

GridIQ builds one network model of Botswana: buses (substations, generation,
import gateways, load nodes) and edges (400/220/132 kV lines), with district
demand, access gaps and resource potential attached. Every engine reads this same
substrate, so a siting recommendation from Engine 1 can be re-priced by Engine 2
and re-located by Engine 4 without contradiction. *(The topology is drawn from
OpenStreetMap/OpenInfraMap — the closest open substitute for BPC's own grid data —
cross-checked against the World Bank/AICD Botswana grid layer (2006-vintage, which
captures only ~40% of the current 400/220/132 kV network), and patched with BPC's
public post-2021 additions: North West Phase 1, Mochudi and Tlokweng.)*

### 2.2 Engine 1 — System-wide optimisation

- **What it is:** a screening capacity-expansion model over representative periods.
- **What it computes:** the combination of generation, storage and grid capacity that delivers demand at the lowest total system cost — minimising imports plus capital cost plus losses.
- **Inputs:** topology, district demand, solar/wind resource, existing fleet, import volumes, candidate sites, regional cost benchmarks.
- **User-facing artifact:** a ranked build plan — site, technology, MW, connection point and projected import reduction per Pula.

### 2.3 Engine 2 — Flow, congestion & losses

- **What it is:** a linearised DC power-flow / OPF model over the real topology.
- **What it computes:** where flow concentrates, which constraints bind, loss per line, and the redispatch cost when a constraint forces costly supply. *(Power is not "routed": current divides across all parallel paths by impedance, so we model constraints, not shortest paths.)*
- **Inputs:** topology, assumed r/x by voltage class, demand, injections.
- **User-facing artifact:** a loss and congestion panel, reconciled against BPC's published figure (642 GWh, FY2023; World Bank 15.35%, 2021; AFREC ~630 GWh / 13.8%, 2023). Scope is stated openly: our model is transmission-level, BPC's figure is T&D.

### 2.4 Engine 3 — Asset-risk screening, with a data contract

- **What it is:** topology-based criticality, not a prediction model.
- **What it computes:** a ranked watch-list of lines, substations and transformers by structural criticality (no redundant path) and estimated stress.
- **Inputs:** topology alone.
- **User-facing artifact:** a ranked watch-list plus a one-page data contract listing the exact BPC fields (age, condition, inspections, failure history, ratings, impedances) that would upgrade the proxy into prediction.

### 2.5 Engine 4 — VillageFit

- **What it is:** a per-village technology recommender.
- **What it computes:** the best-fit mix of solar, wind, biomass, biogas or hybrid for each unconnected village, scored against the cost of extending the line — including how the village uses power (e.g. evening study, where solar alone fails).
- **Inputs:** settlement layer (OSM/HDX), population density, Solar Atlas/NASA POWER, livestock and crop data, distance to grid, terrain.
- **User-facing artifact:** an off-grid shortlist with right-sized systems, and a "no-build" alternative fed back into Engine 1.

**Integration note:** VillageFit is activated from the same substrate as the
national engines. A village's power is not a separate rural project; it is a
system-cost decision the national plan currently makes project-by-project — and
GridIQ makes it comparable.

### 2.6 The decision GridIQ is designed to change

*These are reasoned inferences from the data and policy context, not measured
findings.*

> **Today**, BPC's transmission-planning engineer must decide whether a proposed
> solar plant can connect to an existing corridor, using resource maps and manual
> experience, but there is **no public view** of network headroom or of the
> system-cost consequence of one connection option versus another. *(Grounding: the
> OIC2 hub names the grid planner as this track's target user, and BPC grid and load
> data are not openly available.)*
>
> **GridIQ combines** the transmission topology, district demand and resource
> layers to **estimate** the binding constraint and the redispatch/loss cost of
> each option, under stated line-rating assumptions.
>
> **This allows** the decision to be made on system cost, not resource potential.

> **Today**, a student in an unconnected village like Gomolemo must decide how to
> study in the evening, and there is **no published comparison** of whether his
> village is better served by a line or a mini-grid. **GridIQ's VillageFit** scores
> each unconnected village's own resource mix against line-extension cost.
> *(Representative scenario based on documented evidence — 102 unconnected villages,
> 14.3% access in Ngwaketse West — not a documented individual; the laptop detail is
> illustrative.)*

## 3. Data & Technical Explanation

### 3.1 Data sources

Taxonomy: **REAL** = confirmed in the OIC2 hub; **EXTERNAL** = open Botswana/utility
source outside the hub, cited directly; **BENCHMARK** = regional or methodological
analogue, not Botswana data; **DEMANDED** = not openly available as of Sept 2026 (we
call for its release); **ASSUMED** = model assumption, labelled.

| Dataset | Source | Type |
|---|---|---|
| Electricity generation & distribution by source, quarterly 2016–2026 | Statistics Botswana | REAL |
| National Energy Use Survey 2022/23 (district demand, access) | Statistics Botswana | REAL |
| Africa Energy Balance 2025 (plant efficiency, losses) | AFREC, African Union | REAL |
| OpenInfraMap & Global Power Plant Database | OpenInfraMap / WRI | REAL |
| Global Solar Atlas, Global Wind Atlas, NASA POWER | World Bank/DTU; NASA | REAL |
| SAPP load & interconnection-capacity reports | SAPP | REAL |
| 2022 Census, sub-district shapefile, Meta population density, OSM/HDX extracts | Statistics Botswana / Meta / OSM | REAL |
| Agricultural Census 2025 (livestock), FAO livestock production | Statistics Botswana / FAO | REAL |
| BPC Integrated Annual Report 2023 (T&D losses) | BPC | EXTERNAL |
| Botswana Electricity Transmission Network (2006, cross-check) | World Bank / energydata.info | EXTERNAL |
| Botswana techno-economic dataset (T&D and plant costs) | Zenodo / Loughborough CCG | EXTERNAL |
| Eskom Data Portal (import-side benchmark) | Eskom | EXTERNAL |
| Africa Electricity Transmission & Distribution Grid Map (2017) | World Bank / ESMAP | BENCHMARK |
| gridfinder predicted global grid | World Bank / ESMAP | BENCHMARK |
| SciGRID / GridKit / POMATO line parameters (r, x by voltage) | Open research | BENCHMARK |
| Global Electrification Platform / OnSSET | World Bank / ESMAP | BENCHMARK |
| ENTSO-E Transparency Platform / AEMO | Europe / Australia | BENCHMARK |
| Grid infrastructure & demand data (ratings, loads) | BPC | DEMANDED |
| Grid generation statistics & average demand | BOCRA | DEMANDED |
| Business register: large industrial consumers | Statistics Botswana | DEMANDED |
| Line ratings/impedances | Benchmarked from SciGRID/POMATO defaults | ASSUMED |

### 3.2 Regional & benchmark sources

Where Botswana does not publish a layer, we use labelled analogues rather than
leaving a blank — never presenting them as Botswana data. The **Africa grid map**
(World Bank/ESMAP) cross-checks our OSM topology and adds cross-border corridors.
**SciGRID / GridKit / POMATO** provide default per-km resistance and reactance by
voltage class, so assumed line parameters are calibrated rather than guessed. The
**Global Electrification Platform / OnSSET** supplies the least-cost electrification
method for Engine 4. **ENTSO-E** and **AEMO** are methodological analogues for load
shapes, congestion and loss factors. For context: other countries do publish full
open grid views — the EU mandates it (ENTSO-E), and the US and Australia publish
transmission and constraint data — so Botswana's gap is one of publication, not
possibility.

### 3.3 Technology stack

| Layer | Technology | Role |
|---|---|---|
| Geospatial database | PostgreSQL + PostGIS + pgRouting | Substrate of record: topology, demand, resources, scenario results. |
| API | FastAPI + GeoAlchemy2 | Graph queries, scenario management, validation endpoints. |
| Job queue | Celery + Redis | Runs optimisation, power-flow and siting jobs off-request. |
| Engine 1 | linopy + HiGHS | LP capacity-expansion screening. |
| Engine 2 | PyPSA / pandapower | DC power flow, congestion, losses. |
| Engine 3 | networkx / igraph | Criticality, bridges, N-1 islanding. |
| Engine 4 | GeoPandas + rasterio | Raster sampling and per-village scoring. |
| Frontend | Next.js + MapLibre / Deck.GL | Map layers, panels, what-if slider. |
| Tiles | pg_tileserv + TiTiler | Vector tiles from PostGIS; COG rasters for the Solar Atlas. |
| Data integration | Overpass API, NASA POWER API, SAPP, Stats Botswana portal | Reproducible ingestion with provenance. |

### 3.4 How the system works end-to-end

1. **Ingest** — open datasets are pulled and normalised; every row carries a provenance tag (measured, inferred, assumed).
2. **Substrate** — topology is built, cleaned (endpoints snapped, duplicates merged, connectivity checked) and patched with post-2021 additions.
3. **Layers** — demand is allocated to buses via population density; resources are attached per node and district.
4. **Engines** — E2 runs first and its loss output is reconciled against 642 GWh. Only then do E1 (build plan), E3 (criticality) and E4 (VillageFit) run on the validated substrate.
5. **Scenarios** — every dashboard slider is a parameter bundle, so "what-if: add 100 MW here" never requires re-coding.
6. **Presentation** — the map, the loss-reconciliation panel and the build plan are served to the dashboard.

### 3.5 What is real vs simulated

| Category | Content |
|---|---|
| Real (open data) | Topology, generation fleet, district demand, access rates, resource layers, historical generation/import/loss series. |
| External (open, outside hub) | BPC loss series; AICD/BPA 2006 grid layer; Botswana techno-economic costs and T&D parameters. |
| Benchmarked (analogue) | Africa grid map, gridfinder, SciGRID/POMATO line parameters, GEP/OnSSET method, ENTSO-E/AEMO methods. |
| Assumed (labelled) | Line ratings/impedances, bus-level demand allocation, future demand growth. |
| Simulated (demo) | Scenario outputs — build plans, criticality rankings and off-grid shortlists are model products, not measured results. |

## 4. Implementation & Next Steps

### 4.1 Current status

- Problem validation completed against named open datasets (this brief).
- Architecture fixed: one substrate, four engines, Option B stack.
- Data mapped and verified in the OIC2 hub, including one external anchor (BPC 642 GWh).
- Regional/benchmark data ingested and validated: the World Bank/AICD Botswana grid layer (cross-check) and a Botswana techno-economic dataset (costs and T&D parameters, Zenodo). Provenance recorded in `datasets/PROVENANCE.md`.
- Prototype: substrate build and the loss-reconciliation panel are the first build targets at the hackathon.

### 4.2 Limitations and mitigation

| Limitation | Impact | Mitigation |
|---|---|---|
| Line ratings/impedances are not openly published | Constraints are estimated. | Calibrate from SciGRID/POMATO defaults; report a bracketed range; publish a data contract for BPC. |
| Substation-level demand is limited (not openly published) | Demand is allocated, not measured. | Dasymetric allocation from NEUS + population density, labelled an assumption. |
| Failure history is not openly available | Prediction is not supportable today. | Criticality screening only; state it plainly. |
| Botswana-specific capex data is limited | Build-plan costs are indicative. | Use the Botswana techno-economic dataset (T&D and plant costs) plus regional benchmarks, all labelled. |
| OSM topology predates new lines | Missing post-2021 assets. | Manual patch (North West Phase 1, Mochudi, Tlokweng); AICD/BPA layer as cross-check. |
| Representative periods, not 8,760 h | Not a full expansion model. | Position as a screening tool; do not imply more. |
| Model is transmission-level; BPC losses are T&D | Direct reconciliation is approximate. | Report the transmission bracket against BPC's T&D total and explain the scope. |
| Topology is OSM/AICD-derived, not BPC's own | Approximate; not enough for precise power flow without ratings. | State it openly; the data contract is the path to BPC's real model. |

**Limitations we accept.** We would rather name these than have a judge find them.
The topology is an open approximation, not BPC's own; line parameters are
benchmarked; demand is allocated from district data; there is no hourly Botswana
load series, so representative periods use labelled analogue profiles; and the
distribution network is modelled only as an aggregate. None of these stop the
falsifiable test we lead with — reconciling modelled losses against BPC's published
642 GWh — and each has a named path to improvement.

### 4.3 Roadmap

| Phase | Timeline | Activities | Success metric |
|---|---|---|---|
| 1. Substrate + test | Hackathon Day 1 | Ingest, build/clean topology, allocate demand, run loss reconciliation. | Modelled loss within a stated bracket of 642 GWh. |
| 2. Engines + interface | Hackathon Days 2–3 | E2 flow/congestion, E3 criticality, E4 siting, E1 screening; map and panels. | All four engines run on one substrate; dashboard live. |
| 3. Pilot (proposed) | 12 weeks post-hackathon | Reconcile with BPC; one-region screening; agree the data contract. | Deployment-ready pilot plan with partner metrics. |

### 4.4 Partners and required resources

- **Botswana Power Corporation** — grid data, loss reconciliation, data contract.
- **Ministry of Minerals & Energy** — planning context and policy alignment.
- **BERA** — regulatory data and tariff context.
- **Statistics Botswana** — demand, census and settlement data.
- **SAPP** — interconnection capacity and regional trade options.
- **BDIH / organisers** — mentorship, government introductions, post-hackathon support.
- **In-country renewable developers** — delivery partners for whatever the siting engine recommends.
- **BIUST** — pending climate-risk and land-cover layers for siting.

## 5. Impact & The Ask

**One anchor number.** **642 GWh** of electricity was lost in FY2023 — **14.51% of
units** — by BPC's own Integrated Annual Report 2023, cross-checked by the World
Bank (15.35%, 2021) and AFREC (~630 GWh, 13.8%, 2023). GridIQ's first job is to
reproduce that number from open data, because a model that can reproduce the
losses BPC already reports can be trusted on the decisions it recommends.

**One scale sentence.** GridIQ scales by planning the existing grid as one system,
with every recommendation traced to a named open dataset — no new data collection
required to start.

**One 12-week ask.** Over 12 weeks, working with BPC and Statistics Botswana, we
will reconcile the model's loss output against BPC's published 642 GWh, complete a
system-cost screening for one region's next connection decision, and agree the
data contract that turns asset-risk screening into prediction — producing a
deployment-ready pilot plan with partner-ready metrics.

## 6. AI Disclosure

AI tools were used to assist with research synthesis, document drafting and code
scaffolding. Every data claim in this report is cited to a named source, and the
team has reviewed and owns every figure and design decision. No confidential or
personal data was used.
