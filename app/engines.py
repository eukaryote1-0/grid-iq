from __future__ import annotations

import math
from collections import defaultdict, deque
from typing import Any

from .logic import (
    _haversine_km,
    _load_json,
    _parse_voltage_values_kv,
    DATA,
    baseline_payload,
    storage_benchmarks_payload,
)


def bpc_losses_payload() -> dict[str, Any]:
    return _load_json(DATA / "official" / "bpc_system_losses.json")


def rural_electrification_payload() -> dict[str, Any]:
    return _load_json(DATA / "official" / "rural_electrification.json")


def agriculture_payload() -> dict[str, Any]:
    return _load_json(DATA / "official" / "agriculture_2025.json")


def agriculture_district_payload() -> dict[str, Any]:
    return _load_json(DATA / "official" / "agriculture_district_2015.json")


def biogas_benchmarks_payload() -> dict[str, Any]:
    return _load_json(DATA / "benchmarks" / "biogas_benchmarks.json")


def sapp_transfer_limits_payload() -> dict[str, Any]:
    return _load_json(DATA / "official" / "sapp_transfer_limits.json")


def renewable_benchmarks_payload() -> dict[str, Any]:
    return _load_json(DATA / "benchmarks" / "renewable_costs.json")


def community_benchmarks_payload() -> dict[str, Any]:
    return _load_json(DATA / "benchmarks" / "community_costs.json")


def bpc_grid_public_payload() -> dict[str, Any]:
    return _load_json(DATA / "official" / "bpc_grid_public_snapshot.json")


def gep_reference_payload() -> dict[str, Any]:
    return _load_json(DATA / "reference" / "gep_botswana_dataset.json")


def transformer_benchmarks_payload() -> dict[str, Any]:
    return _load_json(DATA / "benchmarks" / "transformer_benchmarks.json")


def load_profile_benchmarks_payload() -> dict[str, Any]:
    return _load_json(DATA / "benchmarks" / "load_profile_benchmarks.json")


def biomass_residue_benchmarks_payload() -> dict[str, Any]:
    return _load_json(DATA / "benchmarks" / "biomass_residue_benchmarks.json")



def loss_reconciliation_payload(modelled_loss_gwh: float | None = None, model_scope: str = "transmission") -> dict[str, Any]:
    src = bpc_losses_payload()
    anchor = src["validation_anchor"]
    out: dict[str, Any] = {
        "anchor": anchor,
        "history": src["annual"],
        "cross_checks": src.get("report_cross_checks", []),
        "model_scope": model_scope,
        "modelled_loss_gwh": modelled_loss_gwh,
        "status": "model_result_not_supplied",
        "comparison": None,
        "scope_warning": src["metadata"]["scope_warning"],
        "source": src["metadata"]["primary_source"],
    }
    if modelled_loss_gwh is not None:
        if modelled_loss_gwh < 0:
            raise ValueError("modelled_loss_gwh must be non-negative")
        diff = modelled_loss_gwh - float(anchor["loss_gwh_table"])
        err = abs(diff) / float(anchor["loss_gwh_table"]) * 100.0
        out["status"] = "comparison_available_not_directly_equivalent" if model_scope == "transmission" else "comparison_available"
        out["comparison"] = {
            "difference_gwh": round(diff, 3),
            "absolute_error_pct_of_bpc_anchor": round(err, 2),
            "within_10pct_of_bpc_td_anchor": err <= 10.0,
            "interpretation": (
                "A transmission-only technical-loss model is not directly equivalent to BPC's combined T&D/system-loss accounting. "
                "Use the difference as a reconciliation diagnostic, not proof that the model is calibrated."
                if model_scope == "transmission" else
                "Comparison uses the supplied model scope. Confirm that accounting boundaries match before treating the error as calibration evidence."
            ),
        }
    return out


def _crf(rate: float, years: int) -> float:
    if years <= 0:
        raise ValueError("years must be positive")
    if abs(rate) < 1e-12:
        return 1.0 / years
    return rate * (1 + rate) ** years / ((1 + rate) ** years - 1)


def _year_rows(year: int) -> list[dict[str, Any]]:
    base = baseline_payload()
    return [r for r in base["quarterly"] if str(r["period"]).startswith(str(year))]


def capacity_expansion_screen(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Engine 1: annual least-cost capacity-expansion *screening* LP.

    This is deliberately not a chronological production-cost model. It uses observed
    annual Botswana energy balance, current SAPP peak/reserve values, published
    renewable/cost benchmarks, and user-controlled scenario limits. Storage is valued
    only for peak/reserve adequacy because no public Botswana hourly load profile is
    bundled. That limitation is part of the output contract.
    """
    payload = payload or {}
    base = baseline_payload()
    ren = renewable_benchmarks_payload()
    bess = storage_benchmarks_payload()["utility_scale_bess_2024"]

    source_year = int(payload.get("source_year", 2025))
    rows = _year_rows(source_year)
    if len(rows) != 4:
        raise ValueError(f"A complete four-quarter observed balance is required for source_year={source_year}")
    domestic_mwh = float(sum(r["generation_mwh"] for r in rows))
    imports_mwh = float(sum(r["imports_mwh"] for r in rows))
    demand_mwh = domestic_mwh + imports_mwh

    sapp = base["sapp_capacity"]
    operating_mw = float(payload.get("operating_capacity_mw", sapp["operating_capacity_mw"]))
    peak_plus_reserve_mw = float(payload.get("peak_plus_reserve_mw", sapp["peak_plus_reserves_mw"]))
    import_capacity_limit_mw = float(payload.get("import_capacity_limit_mw", sapp_transfer_limits_payload()["bpc_eskom"][-1]["applicable_transfer_limit_mw"]))
    import_energy_price = float(payload.get("import_energy_price_usd_per_mwh", 100.0))
    max_solar_mw = float(payload.get("max_solar_mw", 2500.0))
    max_wind_mw = float(payload.get("max_wind_mw", 0.0))
    max_bess_mw = float(payload.get("max_bess_mw", 1000.0))
    duration_h = float(payload.get("bess_duration_h", 4.0))
    discount_rate = float(payload.get("real_discount_rate", ren["finance_screening"]["real_discount_rate_pct"] / 100.0))

    if min(import_capacity_limit_mw, import_energy_price, max_solar_mw, max_wind_mw, max_bess_mw, duration_h) < 0:
        raise ValueError("capacity/cost/duration scenario inputs must be non-negative")
    if not 0 <= discount_rate <= 0.3:
        raise ValueError("real_discount_rate must be between 0 and 0.30")

    solar = ren["ireNA_2024_global"]["solar_pv"]
    wind = ren["ireNA_2024_global"]["onshore_wind"]
    pvout = float(ren["botswana_resource_screening"]["solar_pvout_kwh_per_kwp_year"])
    # 1 kW -> pvout kWh/y, therefore 1 MW -> pvout MWh/y.
    solar_yield_mwh_per_mw = pvout
    wind_yield_mwh_per_mw = 8760.0 * float(wind["global_average_capacity_factor_pct"]) / 100.0

    solar_ann_usd_per_mw = float(solar["installed_cost_usd_per_kw"]) * 1000.0 * _crf(discount_rate, int(solar["lifetime_years_screening"]))
    wind_ann_usd_per_mw = float(wind["installed_cost_usd_per_kw"]) * 1000.0 * _crf(discount_rate, int(wind["lifetime_years_screening"]))
    bess_energy_ann_usd_per_mwh = float(bess["global_total_installed_cost_usd_per_kwh"]) * 1000.0 * _crf(discount_rate, 15)
    # Power conversion cost is deliberately not added separately because the IRENA
    # installed-cost benchmark in this release is $/kWh. Avoid double counting.

    # Decision vector: [solar_mw, wind_mw, bess_mw, bess_mwh, import_mwh]
    # Energy balance covers the historical import gap only; existing observed domestic
    # generation is fixed as the base fleet contribution.
    c = [solar_ann_usd_per_mw, wind_ann_usd_per_mw, 0.0, bess_energy_ann_usd_per_mwh, import_energy_price]
    A_ub = []
    b_ub = []
    # -(solar yield + wind yield + imports) <= -historical import gap
    A_ub.append([-solar_yield_mwh_per_mw, -wind_yield_mwh_per_mw, 0.0, 0.0, -1.0])
    b_ub.append(-imports_mwh)
    # duration * bess_mw - bess_mwh <= 0
    A_ub.append([0.0, 0.0, duration_h, -1.0, 0.0])
    b_ub.append(0.0)
    # Peak/reserve adequacy: operating + import cap + BESS power >= peak+reserve.
    # -> -bess_mw <= -(gap after import transfer capability)
    required_bess_mw = max(0.0, peak_plus_reserve_mw - operating_mw - import_capacity_limit_mw)
    A_ub.append([0.0, 0.0, -1.0, 0.0, 0.0])
    b_ub.append(-required_bess_mw)
    # Annual imports cannot exceed the selected transfer capability in every hour.
    A_ub.append([0.0, 0.0, 0.0, 0.0, 1.0])
    b_ub.append(import_capacity_limit_mw * 8760.0)

    bounds = [
        (0.0, max_solar_mw),
        (0.0, max_wind_mw),
        (0.0, max_bess_mw),
        (0.0, max_bess_mw * max(duration_h, 1.0) * 3.0),
        (0.0, imports_mwh),
    ]

    try:
        from scipy.optimize import linprog
    except Exception as exc:  # pragma: no cover - exercised only in degraded runtime
        return {
            "status": "solver_dependency_unavailable",
            "engine": "E1",
            "detail": f"SciPy/HiGHS is required for E1: {exc}",
            "inputs": payload,
            "evidence_boundary": "The application remains usable, but E1 cannot be called fully implemented in this runtime until the solver dependency is available.",
        }

    result = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method="highs")
    if not result.success:
        return {
            "status": "infeasible_or_failed",
            "engine": "E1",
            "solver_message": result.message,
            "inputs": payload,
        }

    solar_mw, wind_mw, bess_mw, bess_mwh, import_mwh_opt = [float(x) for x in result.x]
    solar_energy = solar_mw * solar_yield_mwh_per_mw
    wind_energy = wind_mw * wind_yield_mwh_per_mw
    renewable_energy = solar_energy + wind_energy
    import_reduction = max(0.0, imports_mwh - import_mwh_opt)
    annualized_build_cost = solar_mw * solar_ann_usd_per_mw + wind_mw * wind_ann_usd_per_mw + bess_mwh * bess_energy_ann_usd_per_mwh
    annual_import_cost = import_mwh_opt * import_energy_price
    baseline_import_cost = imports_mwh * import_energy_price
    total_annual_screen_cost = annualized_build_cost + annual_import_cost
    avoided_import_cost = baseline_import_cost - annual_import_cost

    plan = []
    if solar_mw > 1e-6:
        plan.append({"technology": "solar_pv", "build_mw": round(solar_mw, 2), "annual_energy_mwh": round(solar_energy, 0), "site": "national screening portfolio", "connection_point": "not spatially resolved in annual E1", "evidence": "Botswana PVOUT screening benchmark + IRENA cost"})
    if wind_mw > 1e-6:
        plan.append({"technology": "onshore_wind", "build_mw": round(wind_mw, 2), "annual_energy_mwh": round(wind_energy, 0), "site": "national screening portfolio", "connection_point": "not spatially resolved in annual E1", "evidence": "IRENA global CF/cost benchmark; wind mode explicitly enabled by scenario"})
    if bess_mw > 1e-6:
        plan.append({"technology": "bess", "build_mw": round(bess_mw, 2), "build_mwh": round(bess_mwh, 2), "duration_h": round(bess_mwh / bess_mw, 2) if bess_mw else None, "site": "capacity-support screening", "connection_point": "not spatially resolved in annual E1", "evidence": "IRENA/NREL benchmark; peak/reserve constraint"})

    return {
        "status": "solved",
        "engine": "E1",
        "model": "annual_energy_plus_peak_capacity_expansion_lp",
        "solver": "SciPy linprog / HiGHS",
        "source_year": source_year,
        "observed_baseline": {
            "domestic_generation_mwh": round(domestic_mwh, 1),
            "imports_mwh": round(imports_mwh, 1),
            "supply_requirement_mwh": round(demand_mwh, 1),
            "operating_capacity_mw": operating_mw,
            "peak_plus_reserve_mw": peak_plus_reserve_mw,
        },
        "scenario_assumptions": {
            "import_transfer_limit_mw": import_capacity_limit_mw,
            "import_energy_price_usd_per_mwh": import_energy_price,
            "max_solar_mw": max_solar_mw,
            "max_wind_mw": max_wind_mw,
            "max_bess_mw": max_bess_mw,
            "bess_duration_h": duration_h,
            "real_discount_rate": discount_rate,
        },
        "solution": {
            "solar_mw": round(solar_mw, 2),
            "wind_mw": round(wind_mw, 2),
            "bess_mw": round(bess_mw, 2),
            "bess_mwh": round(bess_mwh, 2),
            "imports_mwh": round(import_mwh_opt, 1),
            "imports_avoided_mwh": round(import_reduction, 1),
            "imports_avoided_pct_of_baseline": round(import_reduction / imports_mwh * 100.0, 2) if imports_mwh else 0.0,
            "renewable_energy_mwh": round(renewable_energy, 1),
            "annualized_build_cost_usd": round(annualized_build_cost, 0),
            "annual_import_cost_usd": round(annual_import_cost, 0),
            "total_annual_screen_cost_usd": round(total_annual_screen_cost, 0),
            "avoided_import_cost_usd_at_scenario_price": round(avoided_import_cost, 0),
        },
        "ranked_build_plan": plan,
        "validation": {
            "energy_balance_residual_mwh": round(domestic_mwh + solar_energy + wind_energy + import_mwh_opt - demand_mwh, 6),
            "minimum_bess_power_for_selected_import_limit_mw": round(required_bess_mw, 2),
            "spatial_connection_cost_included": False,
            "chronological_storage_dispatch_included": False,
            "grid_congestion_included": False,
        },
        "evidence_boundary": (
            "E1 is fully implemented as an annual energy + peak-capacity LP screening engine. It is not the full 4-8 representative-period model described in the Solutions Report because no measured/licensed Botswana chronological load profile is bundled. "
            "Storage is therefore valued only for peak/reserve adequacy; line congestion and spatial connection cost must be evaluated by E2/site screening before a build recommendation is investment-grade."
        ),
    }



def spatialize_e1_plan(
    e1_result: dict[str, Any],
    *,
    site_name: str,
    lat: float,
    lon: float,
    osm_fc: dict[str, Any] | None,
    grid_cost_case: str = "reference",
    resource_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Attach one explicit candidate location to a solved E1 screening portfolio.

    This is connection-cost screening, not a BPC connection study. It never infers
    electrical headroom from OpenStreetMap.
    """
    if e1_result.get("status") != "solved":
        raise ValueError("E1 must be solved before applying a spatial candidate")
    if not (-90 <= float(lat) <= 90 and -180 <= float(lon) <= 180):
        raise ValueError("invalid candidate coordinates")
    costs = community_benchmarks_payload()["mv_grid_extension"]
    rate_key = {"low":"low_usd_per_km","reference":"reference_usd_per_km","high":"high_usd_per_km"}.get(grid_cost_case)
    if rate_key is None:
        raise ValueError("grid_cost_case must be low, reference or high")
    grid = nearest_grid_distance_km(float(lat), float(lon), osm_fc) if osm_fc else {"distance_km":None,"status":"osm_power_not_loaded"}
    conn_cost = None
    if grid.get("distance_km") is not None:
        conn_cost = float(grid["distance_km"]) * float(costs[rate_key]) * float(costs["network_transformer_multiplier_reference"])
    sol = e1_result["solution"]
    ren = renewable_benchmarks_payload()["ireNA_2024_global"]
    bess = storage_benchmarks_payload()["utility_scale_bess_2024"]
    upfront = (
        float(sol.get("solar_mw",0))*1000*float(ren["solar_pv"]["installed_cost_usd_per_kw"])
        + float(sol.get("wind_mw",0))*1000*float(ren["onshore_wind"]["installed_cost_usd_per_kw"])
        + float(sol.get("bess_mwh",0))*1000*float(bess["global_total_installed_cost_usd_per_kwh"])
    )
    if conn_cost is not None:
        upfront += conn_cost
    avoided = float(sol.get("imports_avoided_mwh",0))
    spatial_plan=[]
    for row in e1_result.get("ranked_build_plan",[]):
        r=dict(row)
        r.update({
            "candidate_site":site_name,
            "candidate_lat":float(lat),
            "candidate_lon":float(lon),
            "connection_screen":grid,
            "grid_extension_cost_usd_screen":round(conn_cost,0) if conn_cost is not None else None,
            "connection_point":"nearest mapped OSM power-line geometry; engineering connection bus/spare capacity not validated",
        })
        spatial_plan.append(r)
    return {
        **e1_result,
        "spatial_candidate":{
            "name":site_name,"lat":float(lat),"lon":float(lon),
            "resource_evidence":resource_evidence or {"status":"not_supplied"},
            "grid_connection":grid,
            "grid_cost_case":grid_cost_case,
            "grid_extension_cost_usd_screen":round(conn_cost,0) if conn_cost is not None else None,
        },
        "ranked_build_plan":spatial_plan,
        "solution":{**sol,
            "upfront_build_plus_connection_capex_usd_screen":round(upfront,0),
            "annual_imports_avoided_mwh_per_million_usd_upfront_screen":round(avoided/(upfront/1_000_000),1) if upfront>0 else None,
        },
        "spatial_evidence_boundary":"Site coordinates and OSM distance are evidence/derivation. Unit grid cost is a benchmark. No OSM tag is interpreted as spare electrical capacity; BPC connection feasibility remains unknown."
    }

def _graph_from_power_geojson(fc: dict[str, Any], voltage_kv: int | None = None) -> tuple[dict[tuple[float, float], set[tuple[float, float]]], dict[frozenset, list[dict[str, Any]]]]:
    adj: dict[tuple[float, float], set[tuple[float, float]]] = defaultdict(set)
    edge_features: dict[frozenset, list[dict[str, Any]]] = defaultdict(list)
    for f in fc.get("features", []):
        geom = f.get("geometry", {})
        if geom.get("type") != "LineString":
            continue
        props = f.get("properties", {})
        if voltage_kv is not None and voltage_kv not in _parse_voltage_values_kv(props.get("voltage")):
            continue
        coords = geom.get("coordinates", [])
        for a, b in zip(coords, coords[1:]):
            na = (round(float(a[0]), 5), round(float(a[1]), 5))
            nb = (round(float(b[0]), 5), round(float(b[1]), 5))
            if na == nb:
                continue
            adj[na].add(nb); adj[nb].add(na)
            edge_features[frozenset((na, nb))].append(f)
    return dict(adj), dict(edge_features)


def _bridges_and_articulations(adj: dict[tuple[float, float], set[tuple[float, float]]]):
    time_idx = 0
    disc: dict[Any, int] = {}
    low: dict[Any, int] = {}
    parent: dict[Any, Any] = {}
    bridges: list[tuple[Any, Any]] = []
    arts: set[Any] = set()

    def dfs(u):
        nonlocal time_idx
        children = 0
        time_idx += 1
        disc[u] = low[u] = time_idx
        for v in adj.get(u, set()):
            if v not in disc:
                parent[v] = u
                children += 1
                dfs(v)
                low[u] = min(low[u], low[v])
                if u not in parent and children > 1:
                    arts.add(u)
                if u in parent and low[v] >= disc[u]:
                    arts.add(u)
                if low[v] > disc[u]:
                    bridges.append((u, v))
            elif parent.get(u) != v:
                low[u] = min(low[u], disc[v])

    for u in adj:
        if u not in disc:
            dfs(u)
    return bridges, arts


def _component_nodes(adj: dict[Any, set[Any]], start: Any, blocked_edge: frozenset | None = None, blocked_node: Any | None = None) -> set[Any]:
    if start == blocked_node:
        return set()
    seen = {start}
    stack = [start]
    while stack:
        u = stack.pop()
        for v in adj.get(u, set()):
            if v == blocked_node:
                continue
            if blocked_edge is not None and frozenset((u, v)) == blocked_edge:
                continue
            if v not in seen:
                seen.add(v); stack.append(v)
    return seen


def structural_criticality_payload(fc: dict[str, Any], voltage_kv: int | None = None, limit: int = 30) -> dict[str, Any]:
    """Engine 3: topology criticality / N-1 structural islanding screen.

    No failure probability is estimated. Rankings are based on graph structure only.
    """
    adj, edge_features = _graph_from_power_geojson(fc, voltage_kv)
    if not adj:
        return {"engine": "E3", "status": "no_network", "watchlist": [], "articulation_points": []}
    bridges, arts = _bridges_and_articulations(adj)

    # Connected component sizes for context.
    comps: list[set[Any]] = []
    seen: set[Any] = set()
    for n in adj:
        if n in seen: continue
        c = _component_nodes(adj, n)
        comps.append(c); seen |= c
    comp_of = {}
    for idx, c in enumerate(comps):
        for n in c: comp_of[n] = idx

    watch = []
    for u, v in bridges:
        comp = comps[comp_of[u]]
        side = _component_nodes(adj, u, blocked_edge=frozenset((u, v)))
        other = comp - side
        smaller = min(len(side), len(other))
        larger = max(len(side), len(other))
        affected_fraction = smaller / len(comp) if comp else 0.0
        feats = edge_features.get(frozenset((u, v)), [])
        names = sorted({(f.get("properties", {}).get("name") or f.get("id") or "mapped line") for f in feats})
        volts = sorted({vv for f in feats for vv in _parse_voltage_values_kv(f.get("properties", {}).get("voltage"))})
        watch.append({
            "type": "bridge_segment",
            "from": [u[0], u[1]], "to": [v[0], v[1]],
            "mapped_feature_names": names,
            "mapped_voltage_kv": volts,
            "component_nodes": len(comp),
            "islanded_geometry_nodes_if_out": smaller,
            "remaining_geometry_nodes": larger,
            "structural_impact_pct": round(affected_fraction * 100, 2),
            "score": round(50 + 50 * affected_fraction, 2),
            "interpretation": "Removing this mapped segment disconnects the geometry graph. This is structural criticality, not failure probability or customer outage count."
        })
    watch.sort(key=lambda x: (x["score"], x["islanded_geometry_nodes_if_out"]), reverse=True)

    # Edge betweenness adds a second, independent topology-criticality signal.
    # Exact computation is used for modest graphs; deterministic sampled Brandes
    # centrality is used for larger graphs to keep the UI responsive.
    betweenness_rows = []
    betweenness_method = "unavailable"
    try:
        import networkx as nx
        G = nx.Graph()
        for u, nbrs in adj.items():
            for v in nbrs:
                if u <= v:
                    G.add_edge(u, v)
        if G.number_of_nodes() <= 2500:
            bc = nx.edge_betweenness_centrality(G, normalized=True)
            betweenness_method = "networkx exact edge betweenness"
        else:
            k = min(96, G.number_of_nodes())
            bc = nx.edge_betweenness_centrality(G, k=k, normalized=True, seed=42)
            betweenness_method = f"networkx sampled edge betweenness (k={k}, seed=42)"
        for (u,v), value in bc.items():
            feats=edge_features.get(frozenset((u,v)),[])
            names=sorted({(f.get("properties",{}).get("name") or f.get("id") or "mapped line") for f in feats})
            betweenness_rows.append({
                "from":[u[0],u[1]],"to":[v[0],v[1]],
                "edge_betweenness":round(float(value),6),
                "mapped_feature_names":names,
                "interpretation":"Topology centrality only; high values mean many graph shortest paths traverse the segment, not that electrical power or customers do."
            })
        betweenness_rows.sort(key=lambda r:r["edge_betweenness"], reverse=True)
    except Exception as exc:
        betweenness_method = f"not available in runtime: {type(exc).__name__}"

    art_rows = []
    for n in arts:
        comp = comps[comp_of[n]]
        # count fragments after node removal within its component
        remaining = set(comp) - {n}
        frags = []
        while remaining:
            st = next(iter(remaining))
            frag = _component_nodes(adj, st, blocked_node=n) & comp
            frags.append(len(frag)); remaining -= frag
        frags.sort(reverse=True)
        separated = len(comp) - 1 - (frags[0] if frags else 0)
        art_rows.append({
            "coord": [n[0], n[1]],
            "component_nodes": len(comp),
            "fragments_after_outage": len(frags),
            "geometry_nodes_outside_largest_fragment": separated,
            "structural_impact_pct": round((separated / len(comp) * 100.0) if comp else 0.0, 2),
        })
    art_rows.sort(key=lambda x: (x["structural_impact_pct"], x["fragments_after_outage"]), reverse=True)

    return {
        "engine": "E3",
        "status": "solved",
        "voltage_filter_kv": voltage_kv,
        "graph": {"nodes": len(adj), "segments": sum(len(v) for v in adj.values()) // 2, "components": len(comps)},
        "bridge_count": len(bridges),
        "articulation_point_count": len(arts),
        "watchlist": watch[:max(1, min(limit, 200))],
        "articulation_points": art_rows[:max(1, min(limit, 200))],
        "edge_betweenness": betweenness_rows[:max(1, min(limit, 200))],
        "method": "Tarjan bridge/articulation analysis + deterministic N-1 geometry partition size + " + betweenness_method,
        "evidence_boundary": "Topology-only structural criticality. No asset age, condition, failure probability, thermal stress, customer count or measured load is inferred.",
        "data_contract": "/docs/data_contracts/BPC_ENGINEERING_DATA_CONTRACT.md",
    }


def _point_segment_distance_km(point: tuple[float, float], a: list[float], b: list[float]) -> float:
    # Local equirectangular projection centred on the point; appropriate for
    # nearest-segment screening over Botswana-scale local distances.
    lon0, lat0 = point
    latr = math.radians(lat0)
    kx = 111.32 * max(0.01, math.cos(latr))
    ky = 111.32
    ax, ay = (float(a[0]) - lon0) * kx, (float(a[1]) - lat0) * ky
    bx, by = (float(b[0]) - lon0) * kx, (float(b[1]) - lat0) * ky
    vx, vy = bx - ax, by - ay
    denom = vx * vx + vy * vy
    if denom <= 1e-12:
        return math.hypot(ax, ay)
    t = max(0.0, min(1.0, -(ax * vx + ay * vy) / denom))
    x, y = ax + t * vx, ay + t * vy
    return math.hypot(x, y)


def nearest_grid_distance_km(lat: float, lon: float, fc: dict[str, Any]) -> dict[str, Any]:
    best = None
    best_feature = None
    for f in fc.get("features", []):
        geom = f.get("geometry", {})
        if geom.get("type") != "LineString": continue
        coords = geom.get("coordinates", [])
        for a, b in zip(coords, coords[1:]):
            d = _point_segment_distance_km((lon, lat), a, b)
            if best is None or d < best:
                best = d; best_feature = f
    if best is None:
        return {"distance_km": None, "status": "no_mapped_power_lines"}
    p = best_feature.get("properties", {}) if best_feature else {}
    return {
        "distance_km": round(best, 2),
        "status": "derived_from_osm_geometry",
        "nearest_feature_id": best_feature.get("id") if best_feature else None,
        "nearest_feature_name": p.get("name") or p.get("ref") or "mapped power line",
        "nearest_feature_voltage": p.get("voltage"),
        "warning": "Straight-line distance to mapped OSM power-line geometry; not an engineered route or BPC connection quote."
    }


def _mean_numeric(rows: list[dict[str, Any]], key: str) -> float | None:
    vals = [float(r[key]) for r in rows if r.get(key) is not None and isinstance(r.get(key), (int, float)) and float(r[key]) > -900]
    return sum(vals) / len(vals) if vals else None


def villagefit_screen(
    village_id: str,
    *,
    osm_fc: dict[str, Any] | None = None,
    nasa_rows: list[dict[str, Any]] | None = None,
    grid_cost_case: str = "reference",
    annual_kwh_per_household: float | None = None,
    peak_kw_per_household: float | None = None,
    evening_energy_share_pct: float | None = None,
    village_override: dict[str, Any] | None = None,
    gep_point: dict[str, Any] | None = None,
    collectable_cattle_manure_kg_per_day: float | None = None,
    biogas_yield_case: str = "reference",
) -> dict[str, Any]:
    """Engine 4 public-data community-fit screen for a verified pilot or explicit custom settlement.

    Resource ranking is evidence-gated. Biomass/biogas remain unranked without local
    feedstock data. Electrical right-sizing is computed only when the caller supplies
    an explicit demand-intensity benchmark.
    """
    rural = rural_electrification_payload()
    if village_override is not None:
        village = dict(village_override)
        required = {"id", "name", "population_2022", "lat", "lon"}
        missing = sorted(required - set(village))
        if missing:
            raise ValueError(f"Custom settlement is missing required fields: {', '.join(missing)}")
        if float(village["population_2022"]) <= 0:
            raise ValueError("Custom settlement population must be positive")
        village.setdefault("source_status", "explicit user/open-data settlement input")
        village.setdefault("pilot_group", "not applicable")
        village.setdefault("district_context", "not supplied")
        village.setdefault("aliases", [])
        scope_label = "explicit settlement input"
    else:
        village = next((v for v in rural["pilot_villages"] if v["id"] == village_id), None)
        if not village:
            raise ValueError(f"Unknown verified pilot village: {village_id}")
        scope_label = "verified six-village pilot cohort"
    costs = community_benchmarks_payload()
    ren = renewable_benchmarks_payload()
    storage = storage_benchmarks_payload()["utility_scale_bess_2024"]

    grid = nearest_grid_distance_km(village["lat"], village["lon"], osm_fc) if osm_fc else {"distance_km": None, "status": "osm_power_not_loaded"}
    grid_cost_cfg = costs["mv_grid_extension"]
    rate_key = {"low": "low_usd_per_km", "reference": "reference_usd_per_km", "high": "high_usd_per_km"}.get(grid_cost_case)
    if rate_key is None: raise ValueError("grid_cost_case must be low, reference or high")
    grid_cost = None
    if grid.get("distance_km") is not None:
        grid_cost = float(grid["distance_km"]) * float(grid_cost_cfg[rate_key]) * float(grid_cost_cfg["network_transformer_multiplier_reference"])

    ghi = _mean_numeric(nasa_rows or [], "ghi")
    wind = _mean_numeric(nasa_rows or [], "wind_ms")
    gep_record = (gep_point or {}).get("record") if isinstance(gep_point, dict) else None
    gep_ghi = None
    gep_wind_cf = None
    if isinstance(gep_record, dict):
        try:
            gep_ghi = float(gep_record.get("GHI")) if gep_record.get("GHI") not in (None, "") else None
        except (TypeError, ValueError):
            gep_ghi = None
        try:
            gep_wind_cf = float(gep_record.get("WindCF")) if gep_record.get("WindCF") not in (None, "") else None
        except (TypeError, ValueError):
            gep_wind_cf = None
    resource_rows = []
    if ghi is not None:
        # Transparent screening only: classify daily GHI into bands; do not turn
        # short-window NASA observations into annual bankable yield.
        if ghi >= 6.0: sscore = 90
        elif ghi >= 5.0: sscore = 75
        elif ghi >= 4.0: sscore = 55
        else: sscore = 35
        resource_rows.append({"technology":"solar_pv","score":sscore,"status":"ranked","evidence":f"NASA POWER mean GHI over supplied window = {ghi:.2f} kWh/m²/day","warning":"Short-window gridded resource screen, not annual bankable yield."})
    elif gep_ghi is not None:
        if gep_ghi >= 6.0: sscore = 90
        elif gep_ghi >= 5.0: sscore = 75
        elif gep_ghi >= 4.0: sscore = 55
        else: sscore = 35
        resource_rows.append({"technology":"solar_pv","score":sscore,"status":"ranked_modelled_open_data","evidence":f"World Bank GEP nearest-cell GHI = {gep_ghi:.2f}","warning":"GEP is a public least-cost electrification modelling input, not a site measurement or bankable yield study."})
    else:
        resource_rows.append({"technology":"solar_pv","score":None,"status":"resource_data_required","evidence":"Load NASA POWER / World Bank GEP point evidence or ingest Global Solar Atlas raster."})
    if wind is not None:
        if wind >= 8.0: wscore=90
        elif wind >= 7.0: wscore=75
        elif wind >= 6.0: wscore=60
        elif wind >= 4.0: wscore=40
        else: wscore=20
        resource_rows.append({"technology":"wind","score":wscore,"status":"ranked","evidence":f"NASA POWER WS10M mean over supplied window = {wind:.2f} m/s","warning":"10 m wind screening only; turbine hub-height measurements/model are required for project design."})
    elif gep_wind_cf is not None:
        cf = gep_wind_cf * 100.0 if gep_wind_cf <= 1.0 else gep_wind_cf
        if cf >= 35: wscore=90
        elif cf >= 30: wscore=75
        elif cf >= 20: wscore=55
        elif cf >= 10: wscore=35
        else: wscore=20
        resource_rows.append({"technology":"wind","score":wscore,"status":"ranked_modelled_open_data","evidence":f"World Bank GEP nearest-cell WindCF = {cf:.1f}%","warning":"GEP wind capacity factor is a model input, not measured turbine performance."})
    else:
        resource_rows.append({"technology":"wind","score":None,"status":"resource_data_required","evidence":"Load NASA POWER / World Bank GEP point evidence or Global Wind Atlas resource data."})

    # Biomass/biogas are evidence-gated. Historical district cattle can be shown as
    # spatial context but is never silently allocated to a village. A directly supplied
    # collectable-manure mass unlocks a quantified FAO biogas-volume screen.
    district_agri = agriculture_district_payload()
    district_context = str(village.get("district_context", "")).strip()
    district_alias = {"Ghanzi":"Ghanzi", "Ngamiland West":"Ngamiland West"}.get(district_context)
    historical_district = next((r for r in district_agri["district_cattle_2015"] if r["district"] == district_alias), None) if district_alias else None
    biogas_detail = None
    if collectable_cattle_manure_kg_per_day is not None:
        if collectable_cattle_manure_kg_per_day <= 0:
            raise ValueError("collectable_cattle_manure_kg_per_day must be positive")
        bio = biogas_benchmarks_payload()
        y = bio["fao_biogas_yield_m3_per_kg_cattle_dung"]
        yv = {"low":y["low"],"reference":y["reference"],"high":y["high"]}.get(biogas_yield_case)
        if yv is None:
            raise ValueError("biogas_yield_case must be low, reference or high")
        m3d = float(collectable_cattle_manure_kg_per_day) * float(yv)
        biogas_detail={"collectable_manure_kg_per_day":float(collectable_cattle_manure_kg_per_day),"yield_case":biogas_yield_case,"yield_m3_per_kg":float(yv),"biogas_m3_per_day_screen":round(m3d,2),"evidence_class":"explicit_local_input_plus_fao_benchmark","warning":"Biogas volume screen only. Electrical output is not inferred without methane composition, conversion efficiency and measured operating conditions."}
        resource_rows.append({"technology":"biogas","score":None,"status":"quantified_volume_not_ranked","evidence":f"Explicit collectable manure input + FAO {biogas_yield_case} cattle-dung yield gives {m3d:.1f} m³/day biogas screen."})
    else:
        resource_rows.append({"technology":"biogas","score":None,"status":"local_feedstock_missing","evidence":"No verified village collectable-manure mass. Historical district cattle context is shown separately where an exact district match exists."})
    resource_rows.append({"technology":"biomass","score":None,"status":"local_feedstock_missing","evidence":"No verified village crop/woody residue mass is bundled; national or district context is not converted into village feedstock."})

    # Hybrid is only rankable when solar is rankable; it gets no artificial bonus.
    solar_row = next(r for r in resource_rows if r["technology"]=="solar_pv")
    resource_rows.append({
        "technology":"solar_plus_bess",
        "score": solar_row["score"] if solar_row["score"] is not None else None,
        "status":"ranked_with_storage_benchmark" if solar_row["score"] is not None else "resource_data_required",
        "evidence":"Solar resource score + IRENA/NREL BESS technology benchmark; storage quantity requires a demand profile.",
    })

    hh_size = float(costs["households"]["botswana_average_household_size_2022"])
    estimated_households = village["population_2022"] / hh_size
    sizing: dict[str, Any] = {
        "estimated_households_from_population": round(estimated_households, 1),
        "household_size_source": "Statistics Botswana 2022 national average 3.3 persons/household",
        "status": "demand_intensity_required",
        "annual_demand_mwh": None,
        "peak_demand_kw": None,
        "solar_pv_mw_screen": None,
        "bess_mwh_screen": None,
        "bess_mw_screen": None,
    }
    mini_capex = None
    if annual_kwh_per_household is not None and peak_kw_per_household is not None:
        if annual_kwh_per_household <= 0 or peak_kw_per_household <= 0:
            raise ValueError("demand intensity values must be positive")
        annual_mwh = estimated_households * annual_kwh_per_household / 1000.0
        peak_kw = estimated_households * peak_kw_per_household
        pvout = float(ren["botswana_resource_screening"]["solar_pvout_kwh_per_kwp_year"])
        solar_mw = annual_mwh / pvout  # MWh/MW-y equivalence
        bess_mwh = None; bess_mw = None
        if evening_energy_share_pct is not None:
            if not 0 <= evening_energy_share_pct <= 100:
                raise ValueError("evening_energy_share_pct must be 0..100")
            daily_mwh = annual_mwh / 365.0
            rte = float(storage["round_trip_efficiency_pct_nrel_atb"]) / 100.0
            bess_mwh = daily_mwh * evening_energy_share_pct / 100.0 / rte
            bess_mw = max(peak_kw / 1000.0, bess_mwh / 4.0)
        solar_cost = solar_mw * 1000.0 * float(ren["ireNA_2024_global"]["solar_pv"]["installed_cost_usd_per_kw"])
        batt_cost = (bess_mwh or 0.0) * 1000.0 * float(storage["global_total_installed_cost_usd_per_kwh"])
        mini_capex = solar_cost + batt_cost
        sizing.update({
            "status": "screening_sized_from_user_or_licensed_demand_benchmark",
            "annual_demand_mwh": round(annual_mwh, 2),
            "peak_demand_kw": round(peak_kw, 1),
            "solar_pv_mw_screen": round(solar_mw, 4),
            "bess_mwh_screen": round(bess_mwh, 3) if bess_mwh is not None else None,
            "bess_mw_screen": round(bess_mw, 3) if bess_mw is not None else None,
            "demand_inputs": {"annual_kwh_per_household":annual_kwh_per_household,"peak_kw_per_household":peak_kw_per_household,"evening_energy_share_pct":evening_energy_share_pct},
            "warning": "Demand intensity is an explicit model input, not measured village load. PV uses a national PVOUT screening benchmark; use site-specific resource and measured demand before design."
        })

    ranked = sorted([r for r in resource_rows if r.get("score") is not None], key=lambda r:r["score"], reverse=True)
    comparison = {
        "grid_extension_capex_usd_screen": round(grid_cost, 0) if grid_cost is not None else None,
        "solar_bess_capex_usd_screen": round(mini_capex, 0) if mini_capex is not None else None,
        "least_capex_screen": None,
    }
    if grid_cost is not None and mini_capex is not None:
        comparison["least_capex_screen"] = "solar_plus_bess" if mini_capex < grid_cost else "grid_extension"
    return {
        "engine":"E4",
        "status":"solved",
        "village":village,
        "grid_proximity":grid,
        "grid_extension_benchmark":{"case":grid_cost_case,"usd_per_km":grid_cost_cfg[rate_key],"network_transformer_multiplier":grid_cost_cfg["network_transformer_multiplier_reference"]},
        "resource_fit":resource_rows,
        "ranked_technologies":ranked,
        "sizing":sizing,
        "capex_comparison":comparison,
        "gep_point_evidence": gep_point,
        "feedstock_context": {
            "historical_district_cattle_2015": historical_district,
            "historical_source_warning": district_agri["metadata"]["scope_warning"],
            "biogas_screen": biogas_detail,
        },
        "national_feedstock_context":agriculture_payload()["national_livestock"],
        "evidence_boundary":f"VillageFit is implemented as an evidence-gated screening engine for the {scope_label}. It does not allocate district/national livestock to a village or invent electrical load. Solar/wind can use NASA or World Bank GEP open modelling inputs; biomass remains unranked without local residue evidence; biogas volume is quantified only when explicit collectable-manure mass is supplied.",
    }

def historical_supply_metrics_payload() -> dict[str, Any]:
    base = baseline_payload()
    rows = base["quarterly"]
    enriched=[]
    for r in rows:
        total=float(r["generation_mwh"])+float(r["imports_mwh"])
        enriched.append({**r,"total_supply_mwh":round(total,1),"local_generation_share_pct":round(float(r["generation_mwh"])/total*100.0,2) if total else None})
    window=[r for r in enriched if 2018 <= int(str(r["period"])[:4]) <= 2022]
    wg=sum(float(r["generation_mwh"]) for r in window); wt=sum(float(r["total_supply_mwh"]) for r in window)
    lowest=min(enriched,key=lambda r:r["local_generation_share_pct"] if r["local_generation_share_pct"] is not None else 999)
    return {
        "quarterly":enriched,
        "five_year_2018_2022":{
            "local_generation_share_pct":round(wg/wt*100.0,2),
            "imports_share_pct":round((wt-wg)/wt*100.0,2),
            "method":"Sum Statistics Botswana quarterly local generation across 2018Q1-2022Q4 divided by total local generation + imports for the same quarters."
        },
        "lowest_quarter_local_share":lowest,
        "q1_2026":base["q1_2026"],
        "synthetic":False,
    }


def representative_day_capacity_expansion_screen(
    payload: dict[str, Any],
    demand_shape_pu: list[float],
    solar_shape_pu: list[float],
    *,
    demand_source_meta: dict[str, Any] | None = None,
    solar_source_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """24-hour chronological benchmark E1 screen with storage SOC.

    This closes the *chronological planning* gap using a regional hourly demand-shape
    benchmark and NASA/PVOUT-calibrated solar availability. It is not a measured
    Botswana dispatch model. Magnitudes are calibrated to published Botswana system
    peak and observed annual domestic generation.
    """
    if len(demand_shape_pu) != 24 or len(solar_shape_pu) != 24:
        raise ValueError("demand_shape_pu and solar_shape_pu must each contain 24 hourly values")
    if not all(math.isfinite(float(x)) and float(x) >= 0 for x in demand_shape_pu + solar_shape_pu):
        raise ValueError("hourly benchmark shapes must be finite and non-negative")
    dmax = max(float(x) for x in demand_shape_pu)
    if dmax <= 0:
        raise ValueError("demand benchmark shape must contain positive values")
    demand_shape = [float(x) / dmax for x in demand_shape_pu]
    solar_shape = [min(1.0, max(0.0, float(x))) for x in solar_shape_pu]

    source_year = int(payload.get("source_year", 2025))
    rows = _year_rows(source_year)
    if len(rows) != 4:
        raise ValueError(f"A complete four-quarter observed balance is required for source_year={source_year}")
    domestic_mwh = float(sum(r["generation_mwh"] for r in rows))
    observed_imports_mwh = float(sum(r["imports_mwh"] for r in rows))
    existing_avg_mw = domestic_mwh / 8760.0

    base = baseline_payload()
    sapp = base["sapp_capacity"]
    peak_mw = float(payload.get("peak_demand_mw", sapp["current_peak_demand_mw"]))
    import_cap_mw = float(payload.get("import_capacity_limit_mw", sapp_transfer_limits_payload()["bpc_eskom"][-1]["applicable_transfer_limit_mw"]))
    import_price = float(payload.get("import_energy_price_usd_per_mwh", 100.0))
    max_solar_mw = float(payload.get("max_solar_mw", 2500.0))
    max_bess_mw = float(payload.get("max_bess_mw", 1000.0))
    duration_h = float(payload.get("bess_duration_h", 4.0))
    discount_rate = float(payload.get("real_discount_rate", renewable_benchmarks_payload()["finance_screening"]["real_discount_rate_pct"] / 100.0))
    if min(peak_mw, import_cap_mw, import_price, max_solar_mw, max_bess_mw, duration_h) < 0:
        raise ValueError("scenario inputs must be non-negative")

    demand = [peak_mw * v for v in demand_shape]
    # The benchmark day shape is rescaled to the observed Botswana annual energy total
    # while retaining the published peak as a hard ceiling. This keeps both anchors visible.
    annual_supply_mwh = domestic_mwh + observed_imports_mwh
    rep_day_energy = sum(demand)
    annualized_rep_energy = rep_day_energy * 365.0
    energy_scale = annual_supply_mwh / annualized_rep_energy if annualized_rep_energy > 0 else 1.0
    # Do not allow energy calibration to create a peak above the published peak.
    if energy_scale <= 1.0:
        demand = [x * energy_scale for x in demand]
    calibrated_peak = max(demand)

    ren = renewable_benchmarks_payload()
    bess = storage_benchmarks_payload()["utility_scale_bess_2024"]
    solar = ren["ireNA_2024_global"]["solar_pv"]
    solar_ann_usd_per_mw = float(solar["installed_cost_usd_per_kw"]) * 1000.0 * _crf(discount_rate, int(solar["lifetime_years_screening"]))
    bess_energy_ann_usd_per_mwh = float(bess["global_total_installed_cost_usd_per_kwh"]) * 1000.0 * _crf(discount_rate, 15)
    eta_rt = float(bess["round_trip_efficiency_pct_nrel_atb"]) / 100.0
    eta_c = math.sqrt(eta_rt)
    eta_d = math.sqrt(eta_rt)

    # Variables: solarMW, bessMW, bessMWh,
    # imports[24], charge[24], discharge[24], soc[24], curtail[24]
    n = 3 + 24 * 5
    SOLAR, BESSMW, BESSMWH = 0, 1, 2
    IMP = 3
    CH = IMP + 24
    DIS = CH + 24
    SOC = DIS + 24
    CURT = SOC + 24

    c = [0.0] * n
    c[SOLAR] = solar_ann_usd_per_mw
    c[BESSMWH] = bess_energy_ann_usd_per_mwh
    for h in range(24):
        c[IMP + h] = import_price * 365.0

    A_eq: list[list[float]] = []
    b_eq: list[float] = []
    # Hourly balance.
    for h in range(24):
        row = [0.0] * n
        row[SOLAR] = solar_shape[h]
        row[IMP + h] = 1.0
        row[DIS + h] = 1.0
        row[CH + h] = -1.0
        row[CURT + h] = -1.0
        A_eq.append(row)
        b_eq.append(demand[h] - existing_avg_mw)
    # BESS duration definition.
    row = [0.0] * n
    row[BESSMWH] = 1.0
    row[BESSMW] = -duration_h
    A_eq.append(row); b_eq.append(0.0)
    # Cyclic SOC chronology.
    for h in range(24):
        row = [0.0] * n
        row[SOC + h] = 1.0
        row[SOC + ((h - 1) % 24)] = -1.0
        row[CH + h] = -eta_c
        row[DIS + h] = 1.0 / eta_d
        A_eq.append(row); b_eq.append(0.0)

    A_ub: list[list[float]] = []
    b_ub: list[float] = []
    # Charge/discharge bounded by power; SOC bounded by energy.
    for h in range(24):
        row = [0.0] * n; row[CH + h] = 1.0; row[BESSMW] = -1.0
        A_ub.append(row); b_ub.append(0.0)
        row = [0.0] * n; row[DIS + h] = 1.0; row[BESSMW] = -1.0
        A_ub.append(row); b_ub.append(0.0)
        row = [0.0] * n; row[SOC + h] = 1.0; row[BESSMWH] = -1.0
        A_ub.append(row); b_ub.append(0.0)

    bounds: list[tuple[float | None, float | None]] = [(0.0, max_solar_mw), (0.0, max_bess_mw), (0.0, max_bess_mw * duration_h)]
    bounds += [(0.0, import_cap_mw)] * 24
    bounds += [(0.0, None)] * 24  # charge
    bounds += [(0.0, None)] * 24  # discharge
    bounds += [(0.0, None)] * 24  # soc
    bounds += [(0.0, None)] * 24  # curtail

    try:
        from scipy.optimize import linprog
    except Exception as exc:  # pragma: no cover
        return {"status":"solver_dependency_unavailable","engine":"E1-representative-day","detail":str(exc)}
    res = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")
    if not res.success:
        return {"status":"infeasible_or_failed","engine":"E1-representative-day","solver_message":res.message}

    x = [float(v) for v in res.x]
    solar_mw, bess_mw, bess_mwh = x[:3]
    hourly = []
    for h in range(24):
        hourly.append({
            "hour": h,
            "demand_mw": round(demand[h], 3),
            "existing_domestic_average_mw": round(existing_avg_mw, 3),
            "solar_cf_benchmark": round(solar_shape[h], 5),
            "solar_mw": round(solar_mw * solar_shape[h], 3),
            "import_mw": round(x[IMP+h], 3),
            "charge_mw": round(x[CH+h], 3),
            "discharge_mw": round(x[DIS+h], 3),
            "soc_mwh": round(x[SOC+h], 3),
            "curtailment_mw": round(x[CURT+h], 3),
        })
    optimized_imports_mwh_y = sum(x[IMP+h] for h in range(24)) * 365.0
    # Baseline on the exact same representative demand shape and fixed domestic average.
    baseline_imports_rep_mwh_y = sum(max(0.0, demand[h] - existing_avg_mw) for h in range(24)) * 365.0
    return {
        "status":"solved",
        "engine":"E1-representative-day",
        "scope":"benchmark-calibrated 24-hour chronological planning screen",
        "solution":{
            "solar_build_mw":round(solar_mw,2),
            "bess_power_mw":round(bess_mw,2),
            "bess_energy_mwh":round(bess_mwh,2),
            "bess_duration_h":round((bess_mwh/bess_mw),2) if bess_mw>1e-9 else None,
            "annual_imports_mwh_representative":round(optimized_imports_mwh_y,0),
            "annual_import_reduction_mwh_vs_same_shape_baseline":round(max(0.0,baseline_imports_rep_mwh_y-optimized_imports_mwh_y),0),
            "annualized_screen_cost_usd":round(float(res.fun),0),
        },
        "calibration":{
            "source_year":source_year,
            "published_peak_mw":peak_mw,
            "representative_profile_peak_mw":round(calibrated_peak,3),
            "observed_annual_supply_mwh":round(annual_supply_mwh,0),
            "observed_annual_domestic_generation_mwh":round(domestic_mwh,0),
            "derived_existing_domestic_average_mw":round(existing_avg_mw,3),
            "demand_shape_source":demand_source_meta or {},
            "solar_shape_source":solar_source_meta or {},
        },
        "hourly":hourly,
        "evidence_boundary":"Chronology is benchmark/modelled, then calibrated to published Botswana peak/annual energy. It is not measured BPC hourly dispatch, bus load, reserve deployment or operational OPF.",
    }
