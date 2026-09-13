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
BPC has already published** (642 GWh / 14.51% in 2023; 793 GWh / 16.62% in 2024).
So the demo is a falsifiable test, not a presentation: if the numbers reconcile,
every other engine inherits the credibility of a substrate that just proved
itself. All four engines are implemented in the working prototype; the current
focus is verification and closing the remaining data gaps.

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
publicly listed additions (North West Phase 1, Mochudi–Phakalane 132 kV, Mochudi and
Ramotswa and Tlokweng substations).*

### 2.2 Engine 1 — System-wide optimisation (implemented: screening scope)

- **What it is:** an annual least-cost capacity-expansion LP, plus a 24-hour benchmark chronology.
- **What it computes:** the mix of solar, wind, storage and imports for a given year that meets peak and reserve at least cost — imports plus capital plus losses — rather than judging one project at a time.
- **Inputs:** observed annual generation/import balance, SAPP peak and reserve anchors, published renewable/storage cost benchmarks, and user scenario limits.
- **User-facing artifact:** a ranked build mix for the year, plus a representative-day dispatch chronology. It is deliberately not a chronological production-cost model, and says so in the output.

### 2.3 Engine 2 — Flow, congestion & losses (implemented: benchmark scope)

- **What it is:** a linearised DC power-flow screen over the mapped topology — a single-transfer study and a balanced multi-injection system study.
- **What it computes:** branch flows, utilisation and I2R loss sensitivity from explicit injections. *(Power is not "routed": current divides across all parallel paths by impedance, so we model constraints, not shortest paths.)*
- **Inputs:** mapped 132/220/400 kV geometry, standard-type R/X/current envelopes in three sensitivity cases, and explicit injections.
- **User-facing artifact:** a flow/utilisation view and a loss-reconciliation panel against BPC's published series — **2023 anchor 642 GWh / 14.51%**, **2024 793 GWh / 16.62%** (now sourced to BPC IR 2024/25) — cross-checked by AFREC (~630 GWh / 13.8%, 2023) and the World Bank (15.35%, 2021). Scope is stated openly: benchmark model, not BPC state; transmission-only versus BPC's T&D. Our independent transmission-loss engine is kept as a separate cross-check at `GET /api/engines/loss-reconciliation`.

### 2.4 Engine 3 — Asset-risk screening, with a data contract (implemented)

- **What it is:** topology-based structural criticality, not a prediction model.
- **What it computes:** bridges, articulation points, N-1 geometry islanding and edge betweenness, ranked into a maintenance/redundancy watch-list.
- **Inputs:** mapped topology alone.
- **User-facing artifact:** a ranked watch-list plus the **BPC engineering data contract** (`docs/data_contracts/BPC_ENGINEERING_DATA_CONTRACT.md`) — the exact fields (bus/branch IDs, ratings, R/X, switch state, time-aligned loads, condition and failure history) that would upgrade the proxy into a validated model.

### 2.5 Engine 4 — VillageFit (implemented)

- **What it is:** a per-settlement technology recommender.
- **What it computes:** the best-fit mix of solar, wind, biogas, biomass or hybrid — with storage — scored against the cost of extending the line, including how the village uses power (e.g. evening study, where solar alone fails). Biogas is computed only when an explicit collectable manure mass is supplied.
- **Inputs:** a pilot-village register or custom settlement, live NASA POWER resource context, World Bank GEP/DRE planning indicators, distance to mapped lines, and benchmark community costs.
- **User-facing artifact:** a right-sized recommendation with the conditions that would change it; the "no-build" alternative feeds back into Engine 1.

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

**Implemented today (v1.7).**

| Layer | Technology | Role |
|---|---|---|
| Runtime | Python + FastAPI/Uvicorn | API and static server. |
| Fallback runtime | Dependency-free stdlib server | Same core API contract if FastAPI cannot be installed. |
| Evidence substrate | Bundled JSON + SHA-256 manifests | Observed/derived/benchmark/reference separation and traceability. |
| Engine 1 | scipy `linprog` (HiGHS) | Annual least-cost capacity-expansion screen. |
| Engine 2 | scipy sparse DC power flow | Single-transfer and balanced multi-injection benchmark studies + I2R post-processing. |
| Engine 3 | networkx (+ pure-Python fallback) | Bridges, articulation points, N-1 islanding, edge betweenness. |
| Engine 4 | Python + bundled benchmark/cost tables | VillageFit settlement screening. |
| API surface | FastAPI routes under `/api/e1`, `/api/e2`, `/api/e3`, `/api/e4`, `/api/engines` | Planning engines and the independent loss cross-check. |
| Frontend | HTML/CSS/vanilla JS control centre (Leaflet + Chart.js) | Overview, Network, Optimizer, Criticality, VillageFit, Generation, Storage, Demand, Data, Audit. |
| Live connectors | OSM/Overpass, NASA POWER, WorldPop, World Bank GEP/DRE, Eskom benchmark chronology | External evidence with degraded states, never substitutes. |

**Target architecture (planned, not implemented).** PostgreSQL + PostGIS +
pgRouting; Celery/Redis workers; vector tiles + COG/TiTiler rasters; Next.js +
MapLibre/Deck.GL. This is the scale-out path, not the current build — the report
does not present it as delivered.

### 3.4 How people use GridIQ

GridIQ is used through a control-centre UI. Three journeys matter most, and each
runs end to end on the implemented prototype.

**Planner flow — decide the next connection (Engines 1 + 2 + 3).**

1. The planner opens **Overview** and reads the national position: generation/import mix, published T&D losses (BPC 2023 anchor 642 GWh / 14.51%; 2024 793 GWh / 16.62%) and SAPP peak/reserve anchors.
2. On **Network**, they load the mapped grid (`/api/osm/power`) and see voltage classes, topology and evidence labels — no BPC operating state is implied.
3. They run a **benchmark system study** (`/api/e2/system-benchmark`) with explicit injections to see branch flows, utilisation and loss sensitivity, then `POST /api/e2/loss-reconciliation` to compare a modelled loss against BPC's published series.
4. On **Optimizer**, they run the least-cost screen (`/api/e1/optimize`) for the year, and optionally the representative-day chronology (`/api/e1/representative-day`), to get the generation/storage/import mix.
5. They test a candidate site (`/api/e1/site-screen`) to see the grid-connection cost and whether a smaller local option wins.
6. They open **Criticality** (`/api/e3/criticality`) for the bridges/N-1/betweenness watch-list, and take the **BPC engineering data contract** as the concrete ask that would upgrade the screen to operational validation.

**Community flow — power one village (Engine 4, VillageFit).**

1. On **VillageFit**, the user selects a verified pilot village or enters a custom settlement (name, lat/lon, population).
2. GridIQ pulls live NASA POWER resource context and World Bank GEP/DRE planning indicators.
3. It scores solar, wind, biogas and hybrid against the cost of extending the line — biogas only when an explicit collectable manure mass is supplied.
4. It returns a right-sized recommendation and the conditions that would change it; the "no-build" alternative feeds back into the national plan (Engine 1).

**Custodian flow — verify any number (Data + Audit).**

1. On **Data**, the user sees the dataset catalog and the **benchmark gap-resolution register** — which gap each benchmark closes, and what it must never claim.
2. On **Audit**, they see scores computed from named evidence gates, with **BPC operational validation held at 0.0**.
3. Every figure traces to its source and its SHA-256 manifest entry; unavailable fields stay labelled, and no benchmark is upgraded to a measured BPC fact.

**The one complete use case** (used verbatim as the pitch spine): *Gomolemo's
village -> the planner's screen -> the decision.*

### 3.5 What is real vs simulated

| Category | Content |
|---|---|
| Real (open, hub) | Topology, generation fleet, district demand, access rates, resource layers, historical generation/import/loss series. |
| External (open, outside hub) | BPC loss series including 2024 (793 GWh / 16.62%); AICD/BPA 2006 grid layer; rural electrification and SAPP transfer-limit snapshots; Botswana techno-economic workbook. |
| Benchmarked (analogue) | Africa grid map, gridfinder, SciGRID/POMATO line parameters, PyPSA transformer/biogas/biomass/community/renewable cost tables, GEP/OnSSET method, normalized Eskom hourly shape, ENTSO-E/AEMO methods. |
| Assumed (labelled) | Line ratings/impedances, settlement demand allocation, demand growth, loss-load factor. |
| Unknown (held) | BPC ratings, switching state, substation loads, asset condition and failure history. BPC operational validation stays 0.0. |
| Simulated (demo) | Scenario outputs — build mixes, branch flows, criticality rankings and off-grid shortlists are model products, not measured results. |

## 4. Implementation & Next Steps

### 4.1 Current status

- Problem validation completed against named open datasets (see the Problem Statement brief).
- **Four engines are implemented and running on one shared substrate:** E1 least-cost capacity screen + representative-day chronology, E2 benchmark flow/losses, E3 structural criticality, E4 VillageFit — plus an independent transmission-loss cross-check.
- **Data:** a 30-dataset catalog and a benchmark gap-resolution register; committed external datasets (filtered OSM grid + substations, AICD/BPA layer, Botswana techno-economic workbook) with SHA-256 manifests; large regional layers fetched by script.
- **Team repo:** `eukaryote1-0/grid-iq`, with CI, a PR-only workflow, tests and manifest verification.
- **Audit:** public-data planning product ~ 9.5/10; BPC operational validation held at **0.0**; browser E2E on the exact release still to be run on a workstation.

### 4.2 Limitations and mitigation

| Limitation | Impact | Mitigation |
|---|---|---|
| Line ratings/impedances are not openly published | Constraints are estimated. | Standard-type envelopes in three cases; bracketed range; data contract for BPC. |
| Substation-level demand is limited (not openly published) | Demand is allocated, not measured. | Settlement/substation allocation from official context, labelled an assumption. |
| Failure history is not openly available | Prediction is not supportable today. | Criticality screening only; state it plainly. |
| Botswana-specific capex data is limited | Build-mix costs are indicative. | Botswana techno-economic workbook plus regional benchmarks, all labelled as assumptions. |
| No Botswana hourly load series | Chronology cannot use metered national demand. | Normalized regional shape scaled to Botswana annual/peak anchors, labelled `benchmark_chronology`. |
| OSM topology predates new lines | Missing post-2021 assets. | AICD/BPA cross-check; BPC public snapshot lists completed projects to patch. |
| Annual LP + representative day, not 8,760 h | Not a full production-cost model. | Position as a screening tool; the output contract says so. |
| Model is transmission-level; BPC losses are T&D | Direct reconciliation is approximate. | Report the transmission bracket against BPC's T&D series (642 GWh 2023; 793 GWh 2024) and explain the scope. |
| Topology is OSM/AICD-derived, not BPC's own | Approximate; not enough for precise power flow without ratings. | State it openly; the data contract is the path to BPC's real model. |
| Browser E2E not verified in the build sandbox | Final visual regression unconfirmed. | Run `scripts/browser_smoke.sh` on a workstation before presenting. |

**Limitations we accept.** We would rather name these than have a judge find them.
The topology is an open approximation, not BPC's own; line parameters are
benchmarked; demand is allocated from official context; there is no Botswana
hourly load series, so chronology uses a labelled analogue shape; and the
distribution network is modelled only as an aggregate. None of these stop the
falsifiable test we lead with — reconciling a modelled transmission loss against
BPC's published T&D series (642 GWh / 14.51% for 2023, 793 GWh / 16.62% for 2024)
— and each has a named path to improvement.

### 4.3 Roadmap

| Phase | Timeline | Activities | Success metric |
|---|---|---|---|
| 1. Substrate + engines | Done | Topology, demand layers, E1–E4 on one substrate; benchmark gap-resolution register. | Four engines run on one substrate; 40 tests green; manifests verified. |
| 2. Interface + verification | Hackathon | Wire the loss cross-check into the reconciliation panel; run browser E2E on a workstation. | A verified demo path from Overview to Criticality and VillageFit. |
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

**One anchor number.** BPC's own reports put T&D losses at **642 GWh (14.51%) in
2023** and **793 GWh (16.62%) in 2024**, independently cross-checked by the World
Bank (15.35%, 2021) and AFREC (~630 GWh, 13.8%, 2023). GridIQ's first job is to
reproduce that range from open data, because a model that can reproduce the losses
BPC already reports can be trusted on the decisions it recommends. *(Headline year
to be fixed with the team.)*

**One scale sentence.** GridIQ scales by planning the existing grid as one system,
with every recommendation traced to a named open dataset — no new data collection
required to start.

**One 12-week ask.** Over 12 weeks, working with BPC and Statistics Botswana, we
will reconcile the model's loss output against BPC's published 642/793 GWh series,
complete a system-cost screening for one region's next connection decision, and
agree the data contract that turns asset-risk screening into a validated model —
producing a deployment-ready pilot plan with partner-ready metrics.

## 6. AI Disclosure

AI tools were used to assist with research synthesis, document drafting and code
scaffolding. Every data claim in this report is cited to a named source, and the
team has reviewed and owns every figure and design decision. No confidential or
personal data was used.
