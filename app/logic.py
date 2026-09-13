from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CACHE = DATA / "cache"
CACHE.mkdir(exist_ok=True)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def catalog_payload() -> dict[str, Any]:
    rows = _load_json(DATA / "catalog.json")
    return {"datasets": rows, "count": len(rows)}


def baseline_payload() -> dict[str, Any]:
    return _load_json(DATA / "official" / "botswana_energy_baseline.json")


def storage_benchmarks_payload() -> dict[str, Any]:
    return _load_json(DATA / "benchmarks" / "storage_benchmarks.json")


def plant_reference_payload() -> dict[str, Any]:
    return _load_json(DATA / "reference" / "wri_gppd_botswana_historical.json")


def neus_payload() -> dict[str, Any]:
    return _load_json(DATA / "official" / "botswana_neus_2022_23.json")


def census_districts_payload() -> dict[str, Any]:
    return _load_json(DATA / "official" / "botswana_census_district_population_2022.json")


def district_access_context_payload() -> dict[str, Any]:
    return _load_json(DATA / "derived" / "district_access_pressure_2022_23.json")


def cache_read(name: str, max_age: int) -> Any | None:
    p = CACHE / name
    if p.exists() and time.time() - p.stat().st_mtime < max_age:
        return _load_json(p)
    return None


def cache_write(name: str, payload: Any) -> None:
    (CACHE / name).write_text(json.dumps(payload), encoding="utf-8")


def overpass_to_geojson(payload: dict[str, Any]) -> dict[str, Any]:
    features: list[dict[str, Any]] = []
    for e in payload.get("elements", []):
        tags = e.get("tags", {})
        ptype = tags.get("power")
        if e.get("type") == "way" and e.get("geometry"):
            coords = [[p["lon"], p["lat"]] for p in e["geometry"]]
            if len(coords) < 2:
                continue
            closed = coords[0] == coords[-1]
            geom = {
                "type": "Polygon" if closed and ptype not in {"line", "minor_line"} else "LineString",
                "coordinates": [coords] if closed and ptype not in {"line", "minor_line"} else coords,
            }
        elif e.get("type") in {"node", "way", "relation"}:
            lat = e.get("lat") or (e.get("center") or {}).get("lat")
            lon = e.get("lon") or (e.get("center") or {}).get("lon")
            if lat is None or lon is None:
                continue
            geom = {"type": "Point", "coordinates": [lon, lat]}
        else:
            continue
        features.append(
            {
                "type": "Feature",
                "id": f"osm-{e.get('type')}-{e.get('id')}",
                "geometry": geom,
                "properties": {
                    "osm_id": e.get("id"),
                    "osm_type": e.get("type"),
                    "power": ptype,
                    "name": tags.get("name") or tags.get("ref") or ptype or "Power asset",
                    "voltage": tags.get("voltage"),
                    "operator": tags.get("operator"),
                    "circuits": tags.get("circuits"),
                    "source": "OpenStreetMap / Overpass",
                    "evidence": "mapped_public_data",
                    "tags": tags,
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}


def _haversine_km(a: list[float], b: list[float]) -> float:
    lon1, lat1 = map(math.radians, a)
    lon2, lat2 = map(math.radians, b)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371.0088 * 2 * math.asin(math.sqrt(h))


def _voltage_bucket(raw: Any) -> str:
    values: list[int] = []
    for part in str(raw or "").replace(",", ";").split(";"):
        try:
            values.append(int(float(part.strip())))
        except (ValueError, TypeError):
            pass
    if not values:
        return "unmapped"
    v = max(values)
    if v >= 350_000:
        return "400 kV class"
    if v >= 180_000:
        return "220 kV class"
    if v >= 110_000:
        return "132 kV class"
    if v >= 50_000:
        return "66 kV class"
    return "below 66 kV / other"


def geojson_evidence_summary(fc: dict[str, Any]) -> dict[str, Any]:
    line_count = asset_count = 0
    mapped_km = 0.0
    km_by_voltage: dict[str, float] = {}
    power_types: dict[str, int] = {}

    # Geometry-only graph. Each visible polyline vertex becomes a graph node.
    # This is intentionally NOT a power-flow bus/branch model.
    adjacency: dict[tuple[float, float], set[tuple[float, float]]] = {}
    for feature in fc.get("features", []):
        geom = feature.get("geometry", {})
        props = feature.get("properties", {})
        ptype = props.get("power") or "unknown"
        power_types[ptype] = power_types.get(ptype, 0) + 1
        if geom.get("type") == "LineString":
            line_count += 1
            coords = geom.get("coordinates", [])
            bucket = _voltage_bucket(props.get("voltage"))
            feature_km = 0.0
            for a, b in zip(coords, coords[1:]):
                feature_km += _haversine_km(a, b)
                # 5 decimal degrees is metre-scale enough for exact OSM vertices while
                # absorbing harmless float representation differences.
                na = (round(a[0], 5), round(a[1], 5))
                nb = (round(b[0], 5), round(b[1], 5))
                adjacency.setdefault(na, set()).add(nb)
                adjacency.setdefault(nb, set()).add(na)
            mapped_km += feature_km
            km_by_voltage[bucket] = km_by_voltage.get(bucket, 0.0) + feature_km
        else:
            asset_count += 1

    nodes = len(adjacency)
    segments = sum(len(v) for v in adjacency.values()) // 2
    endpoints = sum(1 for v in adjacency.values() if len(v) == 1)
    junctions = sum(1 for v in adjacency.values() if len(v) >= 3)
    isolated = sum(1 for v in adjacency.values() if len(v) == 0)
    components = 0
    seen: set[tuple[float, float]] = set()
    for node in adjacency:
        if node in seen:
            continue
        components += 1
        stack = [node]
        seen.add(node)
        while stack:
            cur = stack.pop()
            for nxt in adjacency[cur]:
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)

    return {
        "line_features": line_count,
        "asset_features": asset_count,
        "mapped_line_length_km": round(mapped_km, 1),
        "mapped_line_length_by_voltage_km": {k: round(v, 1) for k, v in sorted(km_by_voltage.items())},
        "power_type_counts": power_types,
        "topology": {
            "geometry_nodes": nodes,
            "geometry_segments": segments,
            "connected_components": components,
            "endpoints": endpoints,
            "junctions_degree_3_plus": junctions,
            "isolated_geometry_nodes": isolated,
            "method": "OSM line-geometry graph: vertices rounded to 5 decimal degrees and adjacent polyline vertices connected.",
            "warning": "This topology view describes mapped geometry connectivity only. It is not a validated BPC bus/branch electrical model and cannot support power flow without ratings/impedance/bus reconciliation."
        },
    }


def validate_scenario(payload: dict[str, Any] | None) -> dict[str, float]:
    """Validate non-synthetic planning inputs.

    Defaults are either current published Botswana system values or explicit
    neutral user-scenario values. No hourly demand or solar profile is fabricated.
    """
    base = baseline_payload()
    sapp = base["sapp_capacity"]
    bench = storage_benchmarks_payload()["utility_scale_bess_2024"]
    payload = payload or {}
    spec = {
        "solar_build_mw": (0.0, 0.0, 3000.0),
        "storage_mw": (0.0, 0.0, 2000.0),
        "storage_mwh": (0.0, 0.0, 12000.0),
        "peak_demand_mw": (float(sapp["current_peak_demand_mw"]), 50.0, 3000.0),
        "operating_capacity_mw": (float(sapp["operating_capacity_mw"]), 0.0, 3000.0),
        "reserve_requirement_mw": (float(sapp["peak_plus_reserves_mw"] - sapp["current_peak_demand_mw"]), 0.0, 1000.0),
        "roundtrip_efficiency": (float(bench["round_trip_efficiency_pct_nrel_atb"]) / 100.0, 0.5, 0.99),
        "storage_cost_usd_per_kwh": (float(bench["global_total_installed_cost_usd_per_kwh"]), 50.0, 2000.0),
    }
    out: dict[str, float] = {}
    for key, (default, lo, hi) in spec.items():
        try:
            value = float(payload.get(key, default))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{key} must be numeric") from exc
        if not lo <= value <= hi:
            raise ValueError(f"{key} must be between {lo:g} and {hi:g}")
        out[key] = value
    return out


def scenario_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Evidence-bounded screening scenario; intentionally not an hourly dispatch model."""
    inp = validate_scenario(payload)
    peak = inp["peak_demand_mw"]
    operating = inp["operating_capacity_mw"]
    reserve = inp["reserve_requirement_mw"]
    storage_mw = inp["storage_mw"]
    storage_mwh = inp["storage_mwh"]
    rte = inp["roundtrip_efficiency"]
    storage_cost = inp["storage_cost_usd_per_kwh"]

    peak_gap = max(0.0, peak - operating)
    reserve_gap = max(0.0, peak + reserve - operating)
    duration = storage_mwh / storage_mw if storage_mw > 0 else None
    deliverable = storage_mwh * rte
    peak_gap_coverage_hours = deliverable / peak_gap if peak_gap > 0 else None
    capex = storage_mwh * 1000.0 * storage_cost

    # Solar is deliberately not credited as firm MW without an adequacy/resource
    # model. This prevents nameplate capacity from being misrepresented.
    return {
        "inputs": inp,
        "summary": {
            "current_peak_capacity_gap_mw": round(peak_gap, 1),
            "capacity_gap_including_reserve_mw": round(reserve_gap, 1),
            "storage_duration_hours": round(duration, 2) if duration is not None else None,
            "benchmark_deliverable_storage_mwh": round(deliverable, 1),
            "screening_hours_covering_current_peak_gap": round(peak_gap_coverage_hours, 2) if peak_gap_coverage_hours is not None and storage_mwh > 0 else None,
            "benchmark_storage_capex_usd": round(capex, 0),
            "solar_nameplate_added_mw": round(inp["solar_build_mw"], 1),
        },
        "gates": {
            "can_calculate_bess_duration_and_benchmark_cost": True,
            "can_calculate_imports_avoided": False,
            "can_calculate_solar_energy_yield": False,
            "can_calculate_line_congestion": False,
            "can_calculate_reliability_capacity_credit": False,
        },
        "meta": {
            "model": "Evidence-bounded planning screen",
            "not": "hourly dispatch, capacity adequacy study, power flow or OPF",
            "warning": "No synthetic hourly load or solar profile is used. Solar is not treated as firm capacity. Import displacement and congestion remain unavailable until a validated load profile, renewable profile and electrical network parameters are ingested.",
            "input_provenance": {
                "peak_and_operating_capacity_defaults": "SAPP Demand & Supply Botswana/BPC snapshot",
                "battery_cost_default": "IRENA Renewable Power Generation Costs in 2024 global utility-scale BESS installed-cost benchmark",
                "roundtrip_efficiency_default": "NREL 2024 ATB utility-scale battery benchmark",
                "solar_build_mw": "user scenario input"
            }
        },
    }

# ---------------------------------------------------------------------------
# Engineering benchmark mode (v1.4)
# ---------------------------------------------------------------------------

def electrical_benchmarks_payload() -> dict[str, Any]:
    return _load_json(DATA / "benchmarks" / "electrical_benchmarks.json")


def _parse_voltage_values_kv(raw: Any) -> list[int]:
    out: list[int] = []
    for part in str(raw or "").replace(",", ";").split(";"):
        part = part.strip()
        if not part:
            continue
        try:
            v = float(part)
        except (TypeError, ValueError):
            continue
        # OSM power voltage tags are normally volts. Be forgiving with kV-like
        # values while preserving a traceable conversion.
        if v > 1000:
            v /= 1000.0
        kv = int(round(v))
        if kv > 0 and kv not in out:
            out.append(kv)
    return sorted(out)


def _parse_circuits(raw: Any) -> tuple[int, str]:
    """Return effective parallel circuit count and provenance status.

    When OSM does not map a circuit count, benchmark mode uses one circuit. This
    is deliberately surfaced as a benchmark assumption rather than evidence.
    """
    try:
        vals = [int(float(x.strip())) for x in str(raw or "").replace(",", ";").split(";") if x.strip()]
        vals = [v for v in vals if v > 0]
        if vals:
            return max(vals), "osm_tag"
    except (TypeError, ValueError):
        pass
    return 1, "benchmark_assumption_unmapped_circuits_equal_1"


def _line_length_km(coords: list[list[float]]) -> float:
    return sum(_haversine_km(a, b) for a, b in zip(coords, coords[1:]))


def _benchmark_case_for_voltage(voltage_kv: int, case: str) -> dict[str, Any] | None:
    lib = electrical_benchmarks_payload()
    row = lib.get("voltage_classes", {}).get(str(voltage_kv))
    if not row:
        return None
    selected = row.get("cases", {}).get(case)
    if not selected:
        return None
    return {**selected, "observed_voltage_kv": voltage_kv, "security_factor_s_max_pu": lib["security_factor_s_max_pu"], "base_mva": lib["base_mva"]}


def enrich_power_geojson(fc: dict[str, Any], case: str = "reference") -> dict[str, Any]:
    if case not in {"conservative", "reference", "high_capacity"}:
        raise ValueError("case must be conservative, reference or high_capacity")
    features: list[dict[str, Any]] = []
    supported = 0
    unsupported = 0
    by_voltage: dict[str, int] = {}
    for feature in fc.get("features", []):
        f = json.loads(json.dumps(feature))
        geom = f.get("geometry", {})
        props = f.setdefault("properties", {})
        if geom.get("type") != "LineString":
            features.append(f)
            continue
        coords = geom.get("coordinates", [])
        length_km = _line_length_km(coords)
        voltages = _parse_voltage_values_kv(props.get("voltage"))
        # Prefer a directly supported mapped voltage; if multiple are present,
        # use the highest supported class and retain the full mapped list.
        supported_voltages = [v for v in voltages if str(v) in electrical_benchmarks_payload().get("voltage_classes", {})]
        voltage_kv = max(supported_voltages) if supported_voltages else None
        props["derived_length_km"] = round(length_km, 3)
        props["mapped_voltage_values_kv"] = voltages
        if voltage_kv is None:
            unsupported += 1
            props["benchmark"] = {
                "supported": False,
                "case": case,
                "reason": "No mapped voltage matching the benchmark library (132/220/400 kV).",
                "evidence_class": "unknown",
            }
            features.append(f)
            continue
        params = _benchmark_case_for_voltage(voltage_kv, case)
        assert params is not None
        circuits, circuits_status = _parse_circuits(props.get("circuits"))
        r_total = params["r_ohm_per_km"] * length_km / circuits
        x_total = params["x_ohm_per_km"] * length_km / circuits
        nominal = math.sqrt(3) * voltage_kv * params["i_nom_ka"] * circuits
        secure = nominal * params["security_factor_s_max_pu"]
        props["benchmark"] = {
            "supported": True,
            "case": case,
            "observed_voltage_kv": voltage_kv,
            "line_type": params["line_type"],
            "r_ohm_per_km": params["r_ohm_per_km"],
            "x_ohm_per_km": params["x_ohm_per_km"],
            "i_nom_ka": params["i_nom_ka"],
            "effective_circuits": circuits,
            "circuits_status": circuits_status,
            "benchmark_r_total_ohm": round(r_total, 6),
            "benchmark_x_total_ohm": round(x_total, 6),
            "benchmark_nominal_mva": round(nominal, 2),
            "benchmark_secure_mva": round(secure, 2),
            "security_factor_s_max_pu": params["security_factor_s_max_pu"],
            "evidence_class": "benchmark_enrichment",
            "warning": "Electrical values are standard-type benchmarks applied to observed OSM geometry; they are not BPC asset measurements.",
        }
        supported += 1
        by_voltage[str(voltage_kv)] = by_voltage.get(str(voltage_kv), 0) + 1
        features.append(f)
    return {
        "type": "FeatureCollection",
        "features": features,
        "meta": {
            "benchmark_case": case,
            "supported_line_features": supported,
            "unsupported_line_features": unsupported,
            "supported_by_voltage": by_voltage,
            "source": "OSM geometry/tags enriched with PyPSA-Earth/PyPSA standard electrical benchmark types",
            "evidence_classes": ["observed", "derived", "benchmark", "unknown"],
            "warning": "This is a planning benchmark model, not a representation of real-time BPC operating state.",
        },
    }


NODE_SNAP_PLACES = 3  # ~100 m: heal small OSM junction gaps (labelled modelling assumption)


def _node_key(coord: list[float]) -> tuple[float, float]:
    # Vertices are snapped to ~100 m so mapped segments that meet at a junction
    # with sub-100 m coordinate gaps form one electrical graph. This is a
    # labelled planning assumption, not a BPC bus reconciliation.
    return (round(float(coord[0]), NODE_SNAP_PLACES), round(float(coord[1]), NODE_SNAP_PLACES))


def _benchmark_branches(fc: dict[str, Any], voltage_kv: int, case: str) -> list[dict[str, Any]]:
    params = _benchmark_case_for_voltage(voltage_kv, case)
    if params is None:
        raise ValueError(f"No electrical benchmark for {voltage_kv} kV")
    branches: list[dict[str, Any]] = []
    base_mva = float(params["base_mva"])
    zbase = (voltage_kv ** 2) / base_mva
    for feature in fc.get("features", []):
        geom = feature.get("geometry", {})
        props = feature.get("properties", {})
        if geom.get("type") != "LineString":
            continue
        volts = _parse_voltage_values_kv(props.get("voltage"))
        if voltage_kv not in volts:
            continue
        coords = geom.get("coordinates", [])
        if len(coords) < 2:
            continue
        circuits, circuits_status = _parse_circuits(props.get("circuits"))
        nominal_mva = math.sqrt(3) * voltage_kv * params["i_nom_ka"] * circuits
        secure_mva = nominal_mva * params["security_factor_s_max_pu"]
        # Emit one branch per mapped vertex pair so segments that meet at an
        # interior junction vertex form a connected graph. Endpoint-only
        # branches fragment the national network at shared crossing vertices.
        emitted = 0
        for a, b in zip(coords, coords[1:]):
            length_km = _line_length_km([a, b])
            if length_km <= 0:
                continue
            r_ohm = params["r_ohm_per_km"] * length_km / circuits
            x_ohm = params["x_ohm_per_km"] * length_km / circuits
            x_pu = x_ohm / zbase
            if x_pu <= 0:
                continue
            branches.append({
                "feature_id": feature.get("id"),
                "name": props.get("name") or feature.get("id") or "Mapped line",
                "from": _node_key(a),
                "to": _node_key(b),
                "from_coord": a,
                "to_coord": b,
                "length_km": length_km,
                "r_ohm": r_ohm,
                "x_ohm": x_ohm,
                "x_pu": x_pu,
                "secure_rating_mw": secure_mva,  # DC active-power screening approximation
                "nominal_mva": nominal_mva,
                "circuits": circuits,
                "circuits_status": circuits_status,
                "line_type": params["line_type"],
                "voltage_kv": voltage_kv,
            })
            emitted += 1
        if emitted == 0:
            continue
    return branches


def _components(branches: list[dict[str, Any]]) -> tuple[dict[tuple[float, float], int], list[list[tuple[float, float]]]]:
    adj: dict[tuple[float, float], set[tuple[float, float]]] = {}
    for br in branches:
        a, b = br["from"], br["to"]
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    comp_of: dict[tuple[float, float], int] = {}
    comps: list[list[tuple[float, float]]] = []
    for start in adj:
        if start in comp_of:
            continue
        cid = len(comps)
        stack = [start]
        comp_of[start] = cid
        nodes: list[tuple[float, float]] = []
        while stack:
            cur = stack.pop()
            nodes.append(cur)
            for nxt in adj[cur]:
                if nxt not in comp_of:
                    comp_of[nxt] = cid
                    stack.append(nxt)
        comps.append(nodes)
    return comp_of, comps


def _nearest_node(nodes: list[tuple[float, float]], lat: float, lon: float) -> tuple[tuple[float, float], float]:
    if not nodes:
        raise ValueError("No benchmark topology nodes available")
    target = [lon, lat]
    best = min(nodes, key=lambda n: _haversine_km([n[0], n[1]], target))
    return best, _haversine_km([best[0], best[1]], target)


def _cg_solve(matvec, b: list[float], tol: float = 1e-10, max_iter: int | None = None) -> tuple[list[float], int, float]:
    """Dependency-free conjugate-gradient solver for the reduced DC Laplacian."""
    n = len(b)
    if n == 0:
        return [], 0, 0.0
    max_iter = max_iter or max(100, n * 12)
    x = [0.0] * n
    r = b[:]
    p = r[:]
    rsold = sum(v * v for v in r)
    if rsold <= tol * tol:
        return x, 0, math.sqrt(rsold)
    for it in range(1, max_iter + 1):
        ap = matvec(p)
        denom = sum(p[i] * ap[i] for i in range(n))
        if abs(denom) < 1e-18:
            break
        alpha = rsold / denom
        for i in range(n):
            x[i] += alpha * p[i]
            r[i] -= alpha * ap[i]
        rsnew = sum(v * v for v in r)
        if math.sqrt(rsnew) < tol:
            return x, it, math.sqrt(rsnew)
        beta = rsnew / rsold
        for i in range(n):
            p[i] = r[i] + beta * p[i]
        rsold = rsnew
    return x, it, math.sqrt(sum(v * v for v in r))


def benchmark_transfer_study(
    fc: dict[str, Any],
    *,
    voltage_kv: int,
    case: str,
    transfer_mw: float,
    source_lat: float,
    source_lon: float,
    sink_lat: float,
    sink_lon: float,
) -> dict[str, Any]:
    """Run a benchmark-only DC transfer sensitivity on one mapped voltage layer.

    This deliberately avoids fabricating operational load. A user-specified MW
    transfer is injected at the nearest mapped node and withdrawn at the sink.
    Output therefore means "network response to this benchmark transfer", not
    current BPC loading or congestion.
    """
    if voltage_kv not in {132, 220, 400}:
        raise ValueError("voltage_kv must be one of 132, 220 or 400")
    if case not in {"conservative", "reference", "high_capacity"}:
        raise ValueError("case must be conservative, reference or high_capacity")
    if not 1 <= float(transfer_mw) <= 2000:
        raise ValueError("transfer_mw must be between 1 and 2000")
    branches = _benchmark_branches(fc, voltage_kv, case)
    if not branches:
        return {"supported": False, "reason": f"No OSM line features with mapped {voltage_kv} kV voltage tag were available."}
    comp_of, comps = _components(branches)
    nodes = list(comp_of)
    source_node, source_dist = _nearest_node(nodes, source_lat, source_lon)
    sink_node, sink_dist = _nearest_node(nodes, sink_lat, sink_lon)
    if comp_of[source_node] != comp_of[sink_node]:
        return {
            "supported": False,
            "reason": "Nearest source and sink nodes are in different mapped OSM components at the selected voltage. GridIQ will not fabricate a missing electrical connection.",
            "source_nearest": {"lon": source_node[0], "lat": source_node[1], "distance_km": round(source_dist, 2), "component": comp_of[source_node]},
            "sink_nearest": {"lon": sink_node[0], "lat": sink_node[1], "distance_km": round(sink_dist, 2), "component": comp_of[sink_node]},
            "mapped_components": len(comps),
        }
    cid = comp_of[source_node]
    component_nodes = comps[cid]
    node_set = set(component_nodes)
    component_branches = [b for b in branches if b["from"] in node_set and b["to"] in node_set]
    slack = sink_node
    active = [n for n in component_nodes if n != slack]
    idx = {n: i for i, n in enumerate(active)}
    weighted_adj: dict[tuple[float, float], list[tuple[tuple[float, float], float]]] = {n: [] for n in component_nodes}
    for br in component_branches:
        susceptance = 1.0 / br["x_pu"]
        weighted_adj[br["from"]].append((br["to"], susceptance))
        weighted_adj[br["to"]].append((br["from"], susceptance))

    def matvec(x: list[float]) -> list[float]:
        out = [0.0] * len(active)
        for node, i in idx.items():
            theta_i = x[i]
            total = 0.0
            for other, bij in weighted_adj[node]:
                theta_j = 0.0 if other == slack else x[idx[other]]
                total += bij * (theta_i - theta_j)
            out[i] = total
        return out

    base_mva = float(electrical_benchmarks_payload()["base_mva"])
    rhs = [0.0] * len(active)
    if source_node != slack:
        rhs[idx[source_node]] += float(transfer_mw) / base_mva
    # The sink withdrawal is at the slack and therefore omitted from the reduced RHS.
    theta_vec, iterations, residual = _cg_solve(matvec, rhs)
    theta = {slack: 0.0, **{n: theta_vec[i] for n, i in idx.items()}}
    flows: list[dict[str, Any]] = []
    total_loss = 0.0
    for br in component_branches:
        flow_pu = (theta[br["from"]] - theta[br["to"]]) / br["x_pu"]
        flow_mw = flow_pu * base_mva
        util = abs(flow_mw) / br["secure_rating_mw"] if br["secure_rating_mw"] > 0 else None
        # Post-process approximate I²R loss using benchmark R and unity PF. DC PF
        # itself is lossless; this value is explicitly labelled approximate.
        loss_mw = (flow_mw ** 2) * br["r_ohm"] / (voltage_kv ** 2) if voltage_kv else 0.0
        total_loss += loss_mw
        flows.append({
            "feature_id": br["feature_id"],
            "name": br["name"],
            "flow_mw": round(flow_mw, 3),
            "abs_flow_mw": round(abs(flow_mw), 3),
            "benchmark_secure_rating_mw": round(br["secure_rating_mw"], 3),
            "utilization_pct": round(util * 100, 2) if util is not None else None,
            "approx_i2r_loss_mw": round(loss_mw, 4),
            "length_km": round(br["length_km"], 3),
            "line_type": br["line_type"],
            "circuits": br["circuits"],
            "circuits_status": br["circuits_status"],
        })
    flows.sort(key=lambda row: row.get("utilization_pct") or 0, reverse=True)
    max_util = flows[0]["utilization_pct"] if flows else 0.0
    return {
        "supported": True,
        "mode": "benchmark_dc_transfer",
        "inputs": {
            "voltage_kv": voltage_kv,
            "case": case,
            "transfer_mw": float(transfer_mw),
            "source": {"lat": source_lat, "lon": source_lon},
            "sink": {"lat": sink_lat, "lon": sink_lon},
        },
        "mapping": {
            "source_nearest": {"lon": source_node[0], "lat": source_node[1], "distance_km": round(source_dist, 2)},
            "sink_nearest": {"lon": sink_node[0], "lat": sink_node[1], "distance_km": round(sink_dist, 2)},
            "component_nodes": len(component_nodes),
            "component_branches": len(component_branches),
            "all_mapped_components_at_voltage": len(comps),
        },
        "summary": {
            "max_benchmark_utilization_pct": max_util,
            "branches_at_or_above_100_pct": sum(1 for r in flows if (r["utilization_pct"] or 0) >= 100),
            "branches_at_or_above_80_pct": sum(1 for r in flows if (r["utilization_pct"] or 0) >= 80),
            "approx_total_i2r_loss_mw": round(total_loss, 4),
            "cg_iterations": iterations,
            "solver_residual": residual,
        },
        "flows": flows,
        "top_flows": flows[:20],
        "meta": {
            "evidence_class": "model_output_from_observed_geometry_plus_benchmark_parameters_plus_user_transfer",
            "physics": "single-voltage DC power-flow sensitivity; sink used as slack bus",
            "losses": "DC solve is lossless; I²R loss is a separate post-processing approximation using benchmark resistance",
            "not": "measured line loading, real-time BPC congestion, AC voltage-security assessment, or validated BPC OPF",
            "warning": "Treat results as planning sensitivity only. Unmapped circuit counts default to one benchmark circuit and are flagged per branch.",
        },
    }



def benchmark_multi_injection_study(
    fc: dict[str, Any],
    *,
    voltage_kv: int,
    case: str,
    injections: list[dict[str, float]],
) -> dict[str, Any]:
    """Benchmark multi-injection DC power-flow on one mapped voltage layer.

    Each injection must provide lat, lon and mw. Positive MW is injection; negative MW
    is withdrawal. Values are explicit scenario inputs or externally-derived benchmark
    values; this function does not invent loads. Net MW must balance to ~0.
    """
    if voltage_kv not in {132, 220, 400}:
        raise ValueError("voltage_kv must be one of 132, 220 or 400")
    if case not in {"conservative", "reference", "high_capacity"}:
        raise ValueError("case must be conservative, reference or high_capacity")
    if len(injections) < 2:
        raise ValueError("At least two injections/withdrawals are required")
    total = sum(float(x.get("mw", 0.0)) for x in injections)
    if abs(total) > 1e-6:
        raise ValueError(f"Benchmark injections must balance to zero MW; net={total:.6f}")
    branches = _benchmark_branches(fc, voltage_kv, case)
    if not branches:
        return {"supported": False, "reason": f"No OSM line features with mapped {voltage_kv} kV voltage tag were available."}
    comp_of, comps = _components(branches)
    nodes = list(comp_of)
    mapped=[]
    for row in injections:
        lat=float(row["lat"]); lon=float(row["lon"]); mw=float(row["mw"])
        node, dist=_nearest_node(nodes, lat, lon)
        mapped.append({"input":{"lat":lat,"lon":lon,"mw":mw,"name":row.get("name")},"node":node,"distance_km":dist,"component":comp_of[node]})
    comps_used={m["component"] for m in mapped if abs(m["input"]["mw"])>1e-9}
    if len(comps_used)!=1:
        return {"supported":False,"reason":"Non-zero benchmark injections map to different disconnected OSM components at this voltage. GridIQ will not fabricate transformer/line connections.","mapped_injections":[{"name":m["input"].get("name"),"mw":m["input"]["mw"],"nearest":{"lon":m["node"][0],"lat":m["node"][1]},"distance_km":round(m["distance_km"],2),"component":m["component"]} for m in mapped]}
    cid=next(iter(comps_used))
    component_nodes=comps[cid]; node_set=set(component_nodes)
    component_branches=[b for b in branches if b["from"] in node_set and b["to"] in node_set]
    # Pick the largest withdrawal as slack because benchmark demand sinks naturally absorb balance.
    withdrawals=[m for m in mapped if m["input"]["mw"]<0]
    slack=(min(withdrawals,key=lambda m:m["input"]["mw"])["node"] if withdrawals else component_nodes[0])
    active=[n for n in component_nodes if n!=slack]; idx={n:i for i,n in enumerate(active)}
    weighted_adj={n:[] for n in component_nodes}
    for br in component_branches:
        bij=1.0/br["x_pu"]
        weighted_adj[br["from"]].append((br["to"],bij)); weighted_adj[br["to"]].append((br["from"],bij))
    def matvec(x):
        out=[0.0]*len(active)
        for node,i in idx.items():
            ti=x[i]; totalv=0.0
            for other,bij in weighted_adj[node]:
                tj=0.0 if other==slack else x[idx[other]]
                totalv+=bij*(ti-tj)
            out[i]=totalv
        return out
    base_mva=float(electrical_benchmarks_payload()["base_mva"]); rhs=[0.0]*len(active)
    aggregated={}
    for m in mapped:
        aggregated[m["node"]]=aggregated.get(m["node"],0.0)+m["input"]["mw"]
    for node,mw in aggregated.items():
        if node!=slack: rhs[idx[node]] += mw/base_mva
    solver_name = "pure-python-cg"
    try:
        import numpy as np
        from scipy.sparse import csr_matrix
        from scipy.sparse.linalg import spsolve
        n = len(active) + 1
        rows=[];cols=[];vals=[];diag=[0.0]*n
        node_pos={node:i for i,node in enumerate(component_nodes)}
        slackpos=node_pos[slack]
        for br in component_branches:
            i=node_pos[br["from"]]; j=node_pos[br["to"]]; b=1.0/br["x_pu"]
            rows += [i, j]; cols += [j, i]; vals += [-b, -b]
            diag[i]+=b; diag[j]+=b
        L = csr_matrix((vals,(rows,cols)),shape=(n,n)) + csr_matrix((diag,(range(n),range(n))),shape=(n,n))
        rhs_full=np.zeros(n)
        for node,mw in aggregated.items():
            if node!=slack: rhs_full[node_pos[node]] += mw/base_mva
        L=L.tolil(); L[slackpos,:]=0.0; L[slackpos,slackpos]=1.0; rhs_full[slackpos]=0.0; L=L.tocsr()
        theta_full=spsolve(L, rhs_full)
        if not np.all(np.isfinite(theta_full)):
            raise RuntimeError("sparse solve returned non-finite values")
        theta={node: float(theta_full[node_pos[node]]) for node in component_nodes}
        iterations=1; residual=0.0; solver_name="scipy-sparse-direct"
    except Exception:
        theta_vec,iterations,residual=_cg_solve(matvec,rhs)
        theta={slack:0.0,**{n:theta_vec[i] for n,i in idx.items()}}
    flows=[]; total_loss=0.0
    for br in component_branches:
        flow_pu=(theta[br["from"]]-theta[br["to"]])/br["x_pu"]; flow_mw=flow_pu*base_mva
        util=abs(flow_mw)/br["secure_rating_mw"] if br["secure_rating_mw"]>0 else None
        loss_mw=(flow_mw**2)*br["r_ohm"]/(voltage_kv**2) if voltage_kv else 0.0
        total_loss+=loss_mw
        flows.append({"feature_id":br["feature_id"],"name":br["name"],"flow_mw":round(flow_mw,3),"abs_flow_mw":round(abs(flow_mw),3),"benchmark_secure_rating_mw":round(br["secure_rating_mw"],3),"utilization_pct":round(util*100,2) if util is not None else None,"approx_i2r_loss_mw":round(loss_mw,4),"length_km":round(br["length_km"],3),"line_type":br["line_type"],"circuits":br["circuits"],"circuits_status":br["circuits_status"]})
    flows.sort(key=lambda r:r.get("utilization_pct") or 0,reverse=True)
    return {
        "supported":True,"mode":"benchmark_dc_multi_injection",
        "inputs":{"voltage_kv":voltage_kv,"case":case,"net_injection_mw":round(total,6)},
        "mapped_injections":[{"name":m["input"].get("name"),"mw":m["input"]["mw"],"nearest":{"lon":m["node"][0],"lat":m["node"][1]},"distance_km":round(m["distance_km"],2),"component":m["component"]} for m in mapped],
        "network_scope":{"component_nodes":len(component_nodes),"component_branches":len(component_branches),"all_mapped_components_at_voltage":len(comps)},
        "summary":{"max_benchmark_utilization_pct":flows[0]["utilization_pct"] if flows else 0.0,"branches_at_or_above_100_pct":sum(1 for r in flows if (r["utilization_pct"] or 0)>=100),"branches_at_or_above_80_pct":sum(1 for r in flows if (r["utilization_pct"] or 0)>=80),"approx_total_i2r_loss_mw":round(total_loss,4),"cg_iterations":iterations,"solver_residual":residual,"solver":solver_name},
        "flows":flows,"top_flows":flows[:30],
        "meta":{"evidence_class":"model_output_from_observed_geometry_plus_benchmark_parameters_plus_explicit_or_derived_scenario_injections","not":"measured BPC dispatch, measured line loading, real-time congestion, validated AC power flow or operational OPF","warning":"Use this to test planning cases. If injection values come from benchmark/modelled demand, preserve that provenance in the calling workflow."}
    }

def evidence_manifest_payload() -> dict[str, Any]:
    p = DATA / "evidence_manifest.json"
    return _load_json(p) if p.exists() else {"files": [], "status": "not_generated"}


def audit_payload() -> dict[str, Any]:
    """Evidence-gated requirements traceability for GridIQ v1.7.

    Benchmark substitution can close a planning capability, but never upgrades the
    BPC-operational-validation score. This keeps "addressed" separate from "observed".
    """
    import importlib.util
    manifest = evidence_manifest_payload()
    scipy_ok = importlib.util.find_spec("scipy") is not None
    networkx_ok = importlib.util.find_spec("networkx") is not None
    gap_file = DATA / "benchmarks" / "gap_resolution.json"
    gap_ok = gap_file.exists()
    browser_file = ROOT / "reports" / "browser_e2e.json"
    browser_ok = False
    if browser_file.exists():
        try:
            b = _load_json(browser_file)
            browser_ok = bool(b.get("pass")) and str(b.get("version")) == "1.7.0"
        except Exception:
            browser_ok = False

    requirements = [
        {"id":"P1_STATS","area":"Problem 1 evidence","requirement":"Quarterly generation/import evidence through Q1 2026","status":"implemented","evidence":"Statistics Botswana bundled quarterly series"},
        {"id":"P1_HISTORY","area":"Problem 1 evidence","requirement":"Five-year domestic supply share and historical low-quarter share","status":"implemented","evidence":"/api/supply/metrics; deterministic transform of published quarterly data"},
        {"id":"BPC_GRID_PUBLIC","area":"Grid evidence","requirement":"Published BPC transmission km/substation/project context","status":"implemented","evidence":"/api/bpc/grid-public; official public BPC snapshot"},
        {"id":"LOSS_ANCHOR","area":"Validation","requirement":"BPC 642 GWh / 14.51% FY2023 loss anchor and history","status":"implemented","evidence":"data/official/bpc_system_losses.json"},
        {"id":"LOSS_RECON","area":"Engine 2","requirement":"Loss-reconciliation harness against BPC anchor","status":"implemented_screening_scope","evidence":"/api/e2/loss-reconciliation; transmission-vs-T&D scope mismatch is reported"},
        {"id":"E1","area":"Engine 1","requirement":"Annual least-cost generation/storage/import capacity-expansion LP","status":"implemented_screening_scope" if scipy_ok else "runtime_dependency_missing","evidence":"/api/e1/optimize; SciPy/HiGHS; observed annual balance + published/benchmark costs"},
        {"id":"E1_SPATIAL","area":"Engine 1","requirement":"Spatial candidate build screen with mapped connection feature and benchmark connection cost","status":"implemented_screening_scope","evidence":"/api/e1/site-screen; explicit coordinates + OSM nearest-line distance + benchmark unit cost"},
        {"id":"E1_FULL","area":"Engine 1","requirement":"Chronological storage dispatch/capacity-expansion planning surrogate","status":"implemented_benchmark_chronological_scope" if scipy_ok else "runtime_dependency_missing","evidence":"/api/e1/representative-day; normalized Eskom hourly demand benchmark + NASA solar shape calibrated to Botswana published anchors"},
        {"id":"E2_DC","area":"Engine 2","requirement":"DC power-flow sensitivity over mapped topology with benchmark electrical parameters","status":"implemented_screening_scope","evidence":"/api/engineering/transfer; OSM geometry + PyPSA standard R/X/current sensitivity"},
        {"id":"E2_SYSTEM","area":"Engine 2","requirement":"Multi-injection benchmark DC system-flow engine","status":"implemented_benchmark_system_scope","evidence":"/api/e2/system-benchmark; balanced explicit/modelled injections + OSM geometry + standard electrical parameters"},
        {"id":"E2_LOSS","area":"Engine 2","requirement":"Per-branch benchmark utilisation and I²R loss post-process","status":"implemented_screening_scope","evidence":"E2 transfer/system benchmark exposes branch flow/utilisation/loss; not measured BPC loading"},
        {"id":"E3","area":"Engine 3","requirement":"Bridges, articulation points, N-1 structural islanding and edge-betweenness watch-list","status":"implemented" if networkx_ok else "implemented_degraded_no_betweenness","evidence":"/api/e3/criticality; topology-only structural criticality"},
        {"id":"E3_CONTRACT","area":"Engine 3","requirement":"Formal BPC engineering/condition data contract","status":"implemented","evidence":"docs/data_contracts/BPC_ENGINEERING_DATA_CONTRACT.md"},
        {"id":"RURAL_STATUS","area":"Problem 3 evidence","requirement":"463/565 electrified and six verified off-grid pilot villages","status":"implemented","evidence":"data/official/rural_electrification.json"},
        {"id":"DRE","area":"Engine 4 data","requirement":"Open settlement-cluster search for VillageFit candidate selection","status":"implemented_connected_source","evidence":"World Bank Botswana DRE Atlas /api/dre/settlements"},
        {"id":"E4","area":"Engine 4","requirement":"Per-settlement solar/wind/grid-extension screening, optional right-sizing and BESS","status":"implemented_screening_scope","evidence":"/api/e4/villagefit supports verified pilots and explicit/DRE settlement inputs"},
        {"id":"E4_ALL_VILLAGES","area":"Engine 4","requirement":"Planning substitute where exhaustive current BPC village connection register is unavailable","status":"implemented_candidate_screening_scope","evidence":"/api/dre/candidate-register derives a transparent priority register from DRE population, transmission distance and night-light indicators; not connection-status truth"},
        {"id":"E4_BIO","area":"Engine 4","requirement":"Biogas/biomass evidence pathway","status":"implemented_evidence_gated_scope","evidence":"Historical district cattle + FAO biogas yield + explicit collectable-manure input; no silent village allocation"},
        {"id":"GEP","area":"Resources/Demand","requirement":"World Bank GEP point-level modelled GHI/WindCF/grid-distance/demand context","status":"implemented_connected_source","evidence":"/api/gep/point and metadata"},
        {"id":"SOLAR_WIND","area":"Resources","requirement":"Site renewable-resource screening","status":"implemented_with_open_substitutes","evidence":"NASA POWER live + World Bank GEP live; Global Solar/Wind Atlas remain optional higher-resolution upgrade"},
        {"id":"POP","area":"Demand","requirement":"Official Census + high-resolution/modelled spatial population","status":"implemented_with_substitute","evidence":"Official Census + WorldPop live + DRE settlement population"},
        {"id":"ADMIN","area":"GIS","requirement":"Administrative geometry for spatial joins when official Statistics Botswana polygon is unavailable","status":"implemented_with_non_authoritative_geometry_substitute","evidence":"/api/gis/boundaries-benchmark; open Botswana GeoJSON is explicitly labelled non-authoritative"},
        {"id":"AGRI","area":"Community resources","requirement":"Current national livestock + historical district cattle context","status":"implemented_historical_spatial_proxy","evidence":"2025 national livestock + 2015 official district cattle table"},
        {"id":"SAPP_LIMITS","area":"Regional grid","requirement":"BPC–Eskom transfer-limit snapshot","status":"implemented","evidence":"Published SAPP corridor limits bundled; not summed into a false national limit"},
        {"id":"BENCH_GAPS","area":"Benchmark governance","requirement":"Every unavailable planning field has an explicit benchmark/proxy/UNKNOWN resolution rule","status":"implemented" if gap_ok else "missing","evidence":"data/benchmarks/gap_resolution.json"},
        {"id":"PROVENANCE","area":"Governance","requirement":"Measured / derived / modelled / benchmark / unknown provenance and file hashes","status":"implemented","evidence":"Catalog + source manifest + SHA-256 evidence manifest + source limitations"},
        {"id":"STATE","area":"UI","requirement":"Page/engine state persistence across navigation","status":"implemented","evidence":"localStorage persists selected page, inputs and engine results"},
        {"id":"MAP","area":"UI/GIS","requirement":"Real map, mapped public power infrastructure and topology","status":"implemented","evidence":"Leaflet + OSM/Overpass + geometry topology"},
        {"id":"UI_E2E","area":"UI validation","requirement":"Current-release browser E2E regression is executed against the exact release","status":"implemented" if browser_ok else "not_verified_environment","evidence":"reports/browser_e2e.json must exist, pass, and match v1.7.0"},
        {"id":"UI_VENDOR","area":"UI reliability","requirement":"Critical frontend libraries are vendored/local rather than public-CDN runtime dependencies","status":"runtime_cdn_dependency","evidence":"Leaflet and Chart.js still load from pinned public CDNs; core HTML/API still fail visibly rather than silently"},
        {"id":"UI_A11Y","area":"UI accessibility","requirement":"Formal automated/manual accessibility audit","status":"implemented_partial","evidence":"Semantic buttons/labels/focus handling are present; formal WCAG tool + screen-reader certification not completed"},
        {"id":"BPC_MODEL","area":"Operational validation","requirement":"Validated BPC bus/branch ratings, impedances, transformer/switch state and time-aligned loads","status":"not_public_benchmark_surrogate_available","evidence":"Planning surrogate exists through PyPSA/Pandapower/Eskom/NASA/DRE benchmarks, but no benchmark can validate BPC operational truth"},
    ]

    fully_closed={
        "implemented","implemented_screening_scope","implemented_connected_source",
        "implemented_evidence_gated_scope","implemented_with_open_substitutes",
        "implemented_with_substitute","implemented_historical_spatial_proxy",
        "implemented_benchmark_chronological_scope","implemented_benchmark_system_scope",
        "implemented_candidate_screening_scope","implemented_with_non_authoritative_geometry_substitute",
    }
    def fraction(status: str) -> float:
        if status in fully_closed: return 1.0
        if status.startswith("implemented_degraded"): return 0.8
        if status.startswith("runtime_dependency"): return 0.25
        if status == "implemented_partial": return 0.6
        if status == "runtime_cdn_dependency": return 0.5
        if status.startswith("not_verified_environment"): return 0.0
        # Operational BPC truth is intentionally zero even when a planning surrogate exists.
        if status.startswith("not_public_"): return 0.0
        return 0.0
    req={r["id"]:r for r in requirements}
    groups={
        "ui_application":["STATE","MAP","PROVENANCE","UI_E2E","UI_VENDOR","UI_A11Y"],
        "problem_evidence":["P1_STATS","P1_HISTORY","BPC_GRID_PUBLIC","LOSS_ANCHOR","RURAL_STATUS","AGRI","SOLAR_WIND","POP"],
        "engine_implementation":["E1","E1_SPATIAL","E1_FULL","LOSS_RECON","E2_DC","E2_SYSTEM","E2_LOSS","E3","E3_CONTRACT","E4","E4_ALL_VILLAGES","E4_BIO"],
        "data_coverage":["GEP","DRE","SOLAR_WIND","POP","ADMIN","AGRI","SAPP_LIMITS","RURAL_STATUS","LOSS_ANCHOR","BENCH_GAPS"],
        "open_data_governance":["PROVENANCE","BENCH_GAPS","LOSS_ANCHOR","SAPP_LIMITS"],
        "benchmark_engineering_capability":["E1_FULL","E2_DC","E2_SYSTEM","E2_LOSS","E3","E4","ADMIN","BENCH_GAPS"],
        "bpc_operational_validation":["BPC_MODEL"],
    }
    scores={}
    for name,ids in groups.items():
        vals=[fraction(req[i]["status"]) for i in ids]
        scores[name]=round(10*sum(vals)/len(vals),1)
    scores["public_data_planning_product"]=round(.15*scores["ui_application"]+.20*scores["problem_evidence"]+.35*scores["engine_implementation"]+.15*scores["data_coverage"]+.15*scores["open_data_governance"],1)
    scores["whole_solution"]=round(.15*scores["ui_application"]+.18*scores["problem_evidence"]+.27*scores["engine_implementation"]+.15*scores["data_coverage"]+.10*scores["open_data_governance"]+.15*scores["bpc_operational_validation"],1)
    return {
        "scores":scores,
        "requirements":requirements,
        "counts":{
            "requirements":len(requirements),
            "closed_at_stated_scope":sum(1 for r in requirements if r["status"] in fully_closed),
            "degraded":sum(1 for r in requirements if r["status"].startswith("implemented_degraded") or r["status"].startswith("runtime_dependency")),
            "operationally_unvalidated":sum(1 for r in requirements if r["status"].startswith("not_public_")),
        },
        "release_gates":{
            "sha256_manifest":manifest.get("status")=="generated",
            "scipy_highs_available":scipy_ok,
            "networkx_available":networkx_ok,
            "browser_e2e_verified_current_release":browser_ok,
            "frontend_vendor_assets_local":False,
            "benchmark_gap_register_present":gap_ok,
            "bpc_operational_case_validated":False,
        },
        "position":"Unavailable public operational fields are now addressed for planning through explicit benchmark/proxy modes wherever technically defensible. This does not convert them into BPC-observed data, so operational-validation remains 0 until BPC provides and validates the engineering/SCADA inputs."
    }
