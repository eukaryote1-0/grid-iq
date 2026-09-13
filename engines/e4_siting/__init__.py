from __future__ import annotations

import math
from typing import Any

from app.logic import (
    storage_benchmarks_payload,
)

from engines.payloads import (
    agriculture_district_payload, agriculture_payload, biogas_benchmarks_payload, community_benchmarks_payload, renewable_benchmarks_payload, rural_electrification_payload,
)
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
