from __future__ import annotations

import math
from typing import Any

from app.logic import (
    baseline_payload, storage_benchmarks_payload,
)

from engines.payloads import (
    community_benchmarks_payload, renewable_benchmarks_payload, sapp_transfer_limits_payload,
)

from engines.e4_siting import (
    nearest_grid_distance_km,
)
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
