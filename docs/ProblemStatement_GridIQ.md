# NATIONAL OPEN DATA INNOVATION CHALLENGE 2 — ENERGY & ENVIRONMENT

# PROBLEM STATEMENT DEFINITION — GridIQ

**Team Eukaryote1.0 | Gaborone, Botswana**

## Data honesty legend

- **REAL** — confirmed open dataset, verified in the OIC2 hub (available now)
- **DEMANDED** — does not exist as open data; we formally call for its release
- **ASSUMED** — benchmark/model assumption where no Botswana data exists (stated as such)
- **EXTERNAL** — published by BPC/government but not held in the hub (cited directly)

Health and environmental burden is stated as **motivation, not as a finding**: no
air-quality monitoring data for Morupule exists in any open source, and we do not
quantify it.

## Main problem statement

Botswana's electricity system is planned as a series of separate projects rather
than as one interconnected system. The result is over-reliance on coal-fired
generation at Morupule, continued dependence on imported power, a rural
population still waiting for the last mile, and a network operated without
visibility of where it is constrained or which assets are critical.

The people who feel this are Batswana households and businesses (unreliable,
expensive power) and the BPC and Ministry planners who must choose what to build
next (no system-cost view to choose with). The result is expensive, unreliable
and inequitable power, and investment that optimises individual resource cases
instead of total system cost.

## Problem statement 1 — Supply is planned project-by-project, so it cannot reliably or cheaply cover demand

Generation still cannot cover demand at home, and the new supply that would fix
that is chosen without seeing the grid. Two coal stations — Morupule A (132 MW)
and Morupule B (600 MW) — plus diesel peaking dominate the fleet, with installed
capacity around 892 MW against peak demand of 678 MW (2024). On a five-year
rolling average domestic generation has covered only about 62% of supply; the
rest is imported, and in Q1 2026 80.9% of imports came from Eskom alone, at high
and volatile cost. Local generation has covered as little as ~44% of distribution
in a quarter.

At the same time, each new project — a solar farm, a coal plant, a battery site —
is appraised on its own resource case (good sun, cheap coal reserves), not on
what it costs the whole system once transmission capacity, congestion and storage
are counted. Solar resources sit far from load, so a strong site can force a
costly line upgrade that the resource map alone never shows.

**Who is affected:** households and industry (unreliable, expensive power); BPC
and Ministry planners (no system-cost view to choose with); the budget and tariff
payers (grid spend that a better-placed project would not have needed).

**Cause:** the first least-cost integrated resource plan is not due until 2026, so
generation, storage and grid are decided as separate projects — with one dominant
generation site and one dominant import corridor. This is also why "more coal AND
more renewables AND fewer imports" only works as one plan, not three.

### Datasets used to validate this problem

| Dataset | Source | Type | How it validates |
|---|---|---|---|
| Electricity generation & distribution by source, quarterly back to 2016 | Statistics Botswana | REAL | Q1 2026 = 90.8% coal, 9.1% solar; local generation covered 80.4% of distribution (best quarter on record); series shows quarters as low as ~44%. |
| Africa Energy Balance 2025 | AFREC, African Union | REAL | 2023 national balance: whole-economy import dependence, plant efficiency ~25%, delivery losses ~13.8%. |
| BPC Integrated Annual Report 2023 | Botswana Power Corporation | EXTERNAL | Publishes T&D losses of 642 GWh in FY2023 (14.51% of units); historical series 509–676 GWh. Our loss anchor. |
| OpenInfraMap & Global Power Plant Database | OpenInfraMap / WRI | REAL | Existing Botswana plants with capacity and fuel type, plus transmission-grid geometry — the fleet and grid we are optimising. |
| Southern African Power Pool (SAPP) | SAPP | REAL | Published load data and interconnection-capacity reports across the regional grid — the alternative corridors. |
| Eskom Data Portal (South Africa) | Eskom | EXTERNAL / regional benchmark | Quantifies the single-corridor import exposure. |
| Global Solar Atlas, Global Wind Atlas & NASA POWER | World Bank / DTU; NASA | REAL | Resource rasters and point series for candidate siting — the resource case that must be tested against grid cost. |
| IRENA & Regional Renewable-Investment Data | IRENA | REAL | Capacity and cost benchmarks for the optimisation. |
| Grid infrastructure & demand data | Botswana Power Corporation | DEMANDED | No BPC dataset confirmed available. We call for line ratings, impedances and substation loads to be released. |
| Grid generation statistics & average demand figures | BOCRA | DEMANDED | No public dataset available. |
| Business register data on energy-sector / large industrial consumers | Statistics Botswana | DEMANDED | No public dataset identified — needed to size industrial demand. |
| Line ratings/impedances; capex per MW and per km | Engineering references / regional benchmarks | ASSUMED | Where no Botswana cost data exists, use published benchmarks and label them. |

### Proposed conceptual solution

**System-wide optimisation engine (Engine 1) and flow, congestion & loss layer
(Engine 2).** One digital model of generation, storage, grid capacity and demand
that jointly answers what to build, where, how much and how to connect —
minimising imports and total system cost, instead of judging each project on its
own resource case. A linearised DC power-flow / OPF model over the real topology
shows where flow concentrates, which constraints bind, loss per line, and the
redispatch cost when a constraint forces costly supply. (Note: power is not
"routed" — current divides across all parallel paths by impedance; we model
constraints, not shortest paths.)

The engine's loss output is reconciled against BPC's own published figure:
**642 GWh lost in FY2023 (14.51% of units), BPC Integrated Annual Report 2023** —
independently cross-checked by the World Bank (T&D losses 15.35% as of 2021) and
AFREC (~630 GWh, 13.8% of supply, 2023). Scope note carried openly: BPC's figure
covers transmission *and* distribution, and Statistics Botswana's series excludes
network losses entirely, so the model reports its transmission-level result as a
bracket against BPC's T&D total.

## Problem statement 2 — The network is operated reactively

Without a published view of where the network is congested, or which assets have
no redundant path, faults are answered after they happen rather than anticipated.
No asset age, condition, inspection or failure history is published for BPC or
any Botswana utility.

**Who is affected:** households and businesses that experience outages; BPC crews
who respond instead of pre-empt.

**Cause:** no criticality or condition data. A prediction model is impossible
without a training signal that does not exist.

### Datasets used to validate this problem

| Dataset | Source | Type | How it validates |
|---|---|---|---|
| OpenInfraMap (OSM transmission grid) | OpenInfraMap / OSM | REAL | Topology alone supports criticality: which assets have no redundant path and would cause an outage, not just a cost. |
| Electricity generation & distribution by source, quarterly | Statistics Botswana | REAL | Observed generation/throughput swings that indicate system stress. |
| Southern African Power Pool (SAPP) | SAPP | REAL | Interconnection-capacity reports — where regional backup could relieve local stress. |
| Grid infrastructure & demand data | Botswana Power Corporation | DEMANDED | Asset condition, ratings, inspection and failure history absent. |
| Asset age / condition / failure history | — | DEMANDED | No public source exists for any Botswana utility. |

### Proposed conceptual solution

**Asset-risk screening layer, with a data contract (Engine 3).** A ranked
watch-list of lines, substations and transformers by structural criticality and
estimated stress, computed from topology alone. Shipped with a one-page data
contract listing the exact BPC fields (age, condition, inspections, failure
history, ratings, impedances) that would upgrade the proxy score into a real
predictive model. Honest ask, not an overclaim.

## Problem statement 3 — The last mile is stuck

As of October 2024, 463 of Botswana's 565 gazetted villages were connected,
leaving 102 unconnected — roughly one in six. Grid extension to these remaining
villages is disproportionately expensive; they are exactly the low-density,
far-flung settlements skipped in earlier phases. National access sits at 73.9%
(NEUS 2022/23) / 76% (Africa Energy Portal), falling to 14.3% in Ngwaketse West.
Government's stated fix is solar off-grid electrification, treated as the default
answer everywhere rather than chosen per village.

**Who is affected:** rural households, and students like Gomolemo — issued a
government laptop under the School Digitisation programme, in a village with no
power to charge it. A laptop reached him before the grid did. *(Representative
scenario based on documented evidence; not a documented individual.)*

**Cause:** no systematic per-village comparison of solar, wind, biomass or hybrid
against the cost of extending the line.

### Datasets used to validate this problem

| Dataset | Source | Type | How it validates |
|---|---|---|---|
| National Energy Use Survey Main Report 2022/23 | Statistics Botswana | REAL | 73.9% national access, 14.3% Ngwaketse West; total national consumption 43,001.7 TJ/yr (66% biomass), by region and fuel. |
| Africa Energy Portal: Botswana Country Page | AfDB / AUDA | REAL | 76% national electricity access; 15%/36%/50% renewable targets for 2030/2036/2040. |
| 2022 Population & Housing Census | Statistics Botswana | REAL | 2,359,609 persons, district-level breakdowns — demand and access denominators. |
| Administrative & Census Sub-District Boundaries (shapefile) | Statistics Botswana GIS | REAL | 32 validated sub-district polygons for spatial joins. |
| Meta High-Resolution Population Density | Meta / HDX | REAL | 30 m population density — settle demand where people actually are. |
| OpenStreetMap / HDX Botswana Extracts | OpenStreetMap / HDX | REAL | ~1.5 M mapped buildings, roads, water sources and markets — the settlement layer for per-village scoring. |
| Global Solar Atlas & NASA POWER | World Bank / DTU; NASA | REAL | Per-site irradiance and time series for solar sizing; evening-load mismatch drives solar-plus-storage. |
| Agricultural Census 2025 (livestock) / FAO livestock production | Statistics Botswana / FAO | REAL | 1.64 M cattle nationally — district biogas feedstock potential. |
| Tracking SDG7: Energy Progress Report | World Bank / ESMAP / IEA / IRENA / WHO | REAL | Access and clean-cooking indicators for national context. |
| BPC rural electrification / SE4ALL gap analysis | BPC / SEforALL | REAL + DEMANDED | Gazetted vs connected status; live connection records would sharpen targeting. |

### Proposed conceptual solution

**Community-level fit layer — VillageFit (Engine 4).** For each still-unconnected
village, score solar, wind, biomass, biogas or hybrid against that village's own
resource data, distance from the grid, and load profile — including how the
village actually uses power (e.g. evening study). Where a line is not the cheapest
way to serve a settlement, recommend a right-sized mini-grid instead. Every
recommendation traces back to a named dataset.

## How the platform answers all three

GridIQ is **one shared network model** with four engines reading the same
topology, demand and injection points:

| Engine | What it addresses | Problem |
|---|---|---|
| Engine 1 — System-wide optimisation | Joint siting, sizing and connection against one objective | Problem 1 |
| Engine 2 — Flow, congestion & losses | Binding constraints, loss per line, redispatch cost (the falsifiable wedge) | Problem 1 |
| Engine 3 — Asset-risk screening + data contract | Structural criticality and proxy risk | Problem 2 |
| Engine 4 — VillageFit community-level fit | Per-village technology fit vs line extension | Problem 3 |

Because all four read the same substrate, no recommendation can silently
contradict another — this is what makes it a platform, not four scripts.
