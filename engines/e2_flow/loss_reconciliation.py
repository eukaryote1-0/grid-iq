"""E2 — national transmission loss reconciliation.

Purpose
-------
Estimate I²R transmission losses on the mapped Botswana network and place the
result against two published loss figures:

  * BPC Integrated Annual Report 2023 — 642 GWh (14.51% of units)
  * AFREC Africa Energy Balances 2025 — ~630 GWh (13.8% of supply)

This is a **benchmark planning screen**, not a BPC measurement. Demand is
allocated across mapped substations because no substation-level load is public,
and line parameters are standard-type benchmarks. Every assumption is returned
in the payload so the number can never be read as measured BPC loading.

Topology
--------
Primary: ``data/grid/botswana_osm_power_132_220_400.geojson`` — filtered
OpenStreetMap lines (132/220/400 kV) fetched via Overpass, with substations from
``data/grid/botswana_osm_substations.geojson`` used as demand points.

Cross-check / fallback: ``data/grid/botswana_grid.geojson`` — the World Bank /
AICD-BPA 2006 layer, which covers only ~40% of the current network.

Mapped vertices are snapped to a ~1 km grid to heal the small coordinate gaps
OSM leaves at junctions; this is a labelled topological assumption.

Method
------
1. Build a graph of mapped line segments (132/220/400 kV, existing).
2. Keep the largest connected component; snap substations onto it as load buses.
3. Allocate national average demand (Q1 2026 Statistics Botswana distribution
   volume) uniformly across those load buses.
4. Inject that total at the node nearest Morupule (slack bus).
5. Solve the lossless DC power flow (B·θ = P). Preferred solver: scipy sparse
   direct; fallbacks: numpy PCG, then pure Python.
6. Post-process approximate I²R losses and annualise with a labelled
   loss-load-factor range.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

try:  # optional acceleration; the engine still works without numpy
    import numpy as _np
except Exception:  # pragma: no cover
    _np = None

try:  # preferred: sparse direct solve
    from scipy.sparse import csr_matrix as _csr
    from scipy.sparse.linalg import spsolve as _spsolve
    from scipy.spatial import cKDTree as _cKDTree
except Exception:  # pragma: no cover
    _spsolve = None
    _cKDTree = None

ROOT = Path(__file__).resolve().parents[2]
OSM_GRID_PATH = ROOT / "data" / "grid" / "botswana_osm_power_132_220_400.geojson"
SUBSTATION_PATH = ROOT / "data" / "grid" / "botswana_osm_substations.geojson"
AICD_GRID_PATH = ROOT / "data" / "grid" / "botswana_grid.geojson"
BASELINE_PATH = ROOT / "data" / "official" / "botswana_energy_baseline.json"
BENCH_PATH = ROOT / "data" / "benchmarks" / "electrical_benchmarks.json"

SUPPORTED_VOLTAGES = (132, 220, 400)
BPC_LOSS_GWH = 642.0
BPC_LOSS_PCT = 14.51
AFREC_LOSS_GWH = 630.0
AFREC_LOSS_PCT = 13.8
LLF_RANGE = (1.0, 1.8)
MORUPULE = (27.03615, -22.520735)
QUARTER_HOURS = 91 * 24
SNAP_PLACES = 3          # ~100 m vertex snapping to heal OSM junction gaps
SOLVER_TOL = 1e-6
SOLVER_MAX_ITER = 4000


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def grid_path() -> Path:
    return OSM_GRID_PATH if OSM_GRID_PATH.exists() else AICD_GRID_PATH


def _haversine_km(a, b) -> float:
    lon1, lat1 = math.radians(a[0]), math.radians(a[1])
    lon2, lat2 = math.radians(b[0]), math.radians(b[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371.0088 * 2 * math.asin(math.sqrt(h))


def _line_strings(feature: dict[str, Any]):
    geom = feature.get("geometry") or {}
    if geom.get("type") == "LineString":
        return [geom.get("coordinates") or []]
    if geom.get("type") == "MultiLineString":
        return geom.get("coordinates") or []
    return []


def _voltage_kv(props: dict[str, Any]) -> int | None:
    if props.get("voltage_kV") is not None:
        try:
            return int(float(props["voltage_kV"]))
        except (TypeError, ValueError):
            return None
    values: list[int] = []
    for part in str(props.get("voltage") or "").replace(",", ";").split(";"):
        part = part.strip()
        if not part:
            continue
        try:
            v = float(part)
        except (TypeError, ValueError):
            continue
        if v > 1000:
            v /= 1000.0
        values.append(int(round(v)))
    supported = [v for v in values if v in SUPPORTED_VOLTAGES]
    return max(supported) if supported else None


def _benchmark_library() -> tuple[dict[str, Any], float]:
    bench = _load_json(BENCH_PATH)
    return bench["voltage_classes"], float(bench["base_mva"])


def _topology(places: int) -> dict[str, Any]:
    path = grid_path()
    grid = _load_json(path)
    nodes: dict[tuple[float, float], int] = {}
    edges: list[dict[str, Any]] = []
    skipped = {"non_existing": 0, "unsupported_voltage": 0, "not_line": 0, "degenerate": 0}

    def node_index(coord) -> int:
        key = (round(float(coord[0]), places), round(float(coord[1]), places))
        idx = nodes.get(key)
        if idx is None:
            idx = len(nodes)
            nodes[key] = idx
        return idx

    for feature in grid.get("features", []):
        props = feature.get("properties", {})
        status = str(props.get("status", "Existing"))
        if status.lower() not in {"existing", "operational", "in service"}:
            skipped["non_existing"] += 1
            continue
        voltage_kv = _voltage_kv(props)
        if voltage_kv is None:
            skipped["unsupported_voltage"] += 1
            continue
        produced = 0
        for coords in _line_strings(feature):
            for a, b in zip(coords, coords[1:]):
                length_km = _haversine_km(a, b)
                if length_km <= 1e-9:
                    skipped["degenerate"] += 1
                    continue
                edges.append(
                    {
                        "from": node_index(a),
                        "to": node_index(b),
                        "length_km": length_km,
                        "voltage_kv": voltage_kv,
                        "name": props.get("from") or props.get("name") or feature.get("id") or "Mapped line",
                    }
                )
                produced += 1
        if produced == 0:
            skipped["not_line"] += 1
    return {"path": str(path.relative_to(ROOT)), "nodes": nodes, "edges": edges, "skipped": skipped, "places": places}


def _largest_component(topo: dict[str, Any]) -> list[int]:
    n = len(topo["nodes"])
    adj: list[list[int]] = [[] for _ in range(n)]
    for e in topo["edges"]:
        adj[e["from"]].append(e["to"])
        adj[e["to"]].append(e["from"])
    seen = [False] * n
    best: list[int] = []
    for start in range(n):
        if seen[start]:
            continue
        seen[start] = True
        stack = [start]
        comp: list[int] = []
        while stack:
            cur = stack.pop()
            comp.append(cur)
            for nxt in adj[cur]:
                if not seen[nxt]:
                    seen[nxt] = True
                    stack.append(nxt)
        if len(comp) > len(best):
            best = comp
    return best


def _component_edges(topo: dict[str, Any], comp: list[int]):
    relabel = {old: i for i, old in enumerate(comp)}
    edges = []
    for e in topo["edges"]:
        if e["from"] in relabel and e["to"] in relabel:
            edges.append({**e, "from": relabel[e["from"]], "to": relabel[e["to"]]})
    return edges, relabel


def _slack_index(topo: dict[str, Any], comp: list[int], relabel: dict[int, int]) -> int:
    keys = list(topo["nodes"].keys())
    best_old = min(comp, key=lambda i: _haversine_km(keys[i], MORUPULE))
    return relabel[best_old]


def _component_load_nodes(topo: dict[str, Any], comp: list[int], relabel: dict[int, int], slack: int) -> list[int]:
    """Snap mapped substations onto the component and return unique load bus indices."""
    if not SUBSTATION_PATH.exists():
        return []
    subs = _load_json(SUBSTATION_PATH)
    coords = []
    for f in subs.get("features", []):
        geom = f.get("geometry") or {}
        if geom.get("type") == "Point":
            c = geom.get("coordinates") or []
            if len(c) == 2:
                coords.append((float(c[0]), float(c[1])))
    if not coords:
        return []
    keys = list(topo["nodes"].keys())
    comp_coords = [keys[i] for i in comp]
    if _np is not None:
        arr = _np.array(comp_coords, dtype=float)
        pts = _np.array(coords, dtype=float)
        if _cKDTree is not None:
            _, idx = _cKDTree(arr).query(pts, k=1)
            snapped = [int(i) for i in idx]
        else:
            snapped = []
            for pt in pts:
                d = (arr[:, 0] - pt[0]) ** 2 + (arr[:, 1] - pt[1]) ** 2
                snapped.append(int(d.argmin()))
    else:
        snapped = []
        for pt in coords:
            best_i, best_d = 0, float("inf")
            for i, c in enumerate(comp_coords):
                d = (c[0] - pt[0]) ** 2 + (c[1] - pt[1]) ** 2
                if d < best_d:
                    best_i, best_d = i, d
            snapped.append(best_i)
    loads = sorted({relabel[comp[i]] for i in snapped if relabel[comp[i]] != slack})
    return loads


def _arrays(edges, r_per_km, x_per_km, base_mva):
    np = _np
    fi = np.array([e["from"] for e in edges], dtype=np.int64)
    ti = np.array([e["to"] for e in edges], dtype=np.int64)
    length = np.array([e["length_km"] for e in edges], dtype=np.float64)
    kv = np.array([e["voltage_kv"] for e in edges], dtype=np.float64)
    r_ohm = np.array(r_per_km, dtype=np.float64) * length
    x_ohm = np.array(x_per_km, dtype=np.float64) * length
    x_pu = x_ohm / ((kv ** 2) / base_mva)
    return fi, ti, kv, r_ohm, x_pu, 1.0 / x_pu


def _rhs_vector(m: int, slack: int, total_demand_mw: float, base_mva: float, load_nodes: list[int]):
    np = _np
    rhs = np.zeros(m + 1, dtype=np.float64)
    if load_nodes:
        per = (total_demand_mw / base_mva) / len(load_nodes)
        rhs[np.array(load_nodes, dtype=np.int64)] -= per
    else:
        per = (total_demand_mw / base_mva) / max(1, m)
        rhs[:m] -= per
    rhs[slack] = 0.0
    return rhs


def _flows_and_losses(full, fi, ti, kv, r_ohm, x_pu, base_mva):
    np = _np
    flow = (full[fi] - full[ti]) / x_pu * base_mva
    current_ka = np.abs(flow) / (np.sqrt(3.0) * kv)
    loss = (current_ka ** 2) * r_ohm
    return flow, loss


def _solve_direct(edges, r_per_km, x_per_km, base_mva, m, slack, total_demand_mw, load_nodes):
    fi, ti, kv, r_ohm, x_pu, b = _arrays(edges, r_per_km, x_per_km, base_mva)
    n = m + 1
    rows = _np.concatenate([fi, ti])
    cols = _np.concatenate([ti, fi])
    vals = _np.concatenate([-b, -b])
    diag = _np.bincount(fi, weights=b, minlength=n) + _np.bincount(ti, weights=b, minlength=n)
    L = _csr((vals, (rows, cols)), shape=(n, n)) + _csr((diag, (_np.arange(n), _np.arange(n))), shape=(n, n))
    rhs = _rhs_vector(m, slack, total_demand_mw, base_mva, load_nodes)
    L = L.tolil()
    L[slack, :] = 0.0
    L[slack, slack] = 1.0
    L = L.tocsr()
    full = _spsolve(L, rhs)
    if not _np.all(_np.isfinite(full)):
        raise RuntimeError("sparse direct solve returned non-finite values")
    flow, loss = _flows_and_losses(full, fi, ti, kv, r_ohm, x_pu, base_mva)
    return flow, loss, 1, 0.0


def _solve_pcg(edges, r_per_km, x_per_km, base_mva, m, slack, total_demand_mw, load_nodes):
    fi, ti, kv, r_ohm, x_pu, b = _arrays(edges, r_per_km, x_per_km, base_mva)
    rhs = _rhs_vector(m, slack, total_demand_mw, base_mva, load_nodes)
    diag = _np.bincount(fi, weights=b, minlength=m + 1) + _np.bincount(ti, weights=b, minlength=m + 1)
    inv_diag = _np.where(diag[:m] > 0, 1.0 / diag[:m], 1.0)
    sol = _np.zeros(m)
    r = rhs[:m].copy()
    z = r * inv_diag
    p = z.copy()
    rz = float(r @ z)
    it = 0
    for it in range(1, SOLVER_MAX_ITER + 1):
        full = _np.zeros(m + 1)
        full[:m] = p
        diff = full[fi] - full[ti]
        w = b * diff
        ap = (_np.bincount(fi, weights=w, minlength=m + 1) - _np.bincount(ti, weights=w, minlength=m + 1))[:m]
        denom = float(p @ ap)
        if abs(denom) < 1e-18:
            break
        alpha = rz / denom
        sol += alpha * p
        r -= alpha * ap
        if math.sqrt(float(r @ r)) < SOLVER_TOL:
            break
        z = r * inv_diag
        rz_new = float(r @ z)
        if abs(rz) < 1e-30:
            break
        p = z + (rz_new / rz) * p
        rz = rz_new
    full = _np.zeros(m + 1)
    full[:m] = sol
    flow, loss = _flows_and_losses(full, fi, ti, kv, r_ohm, x_pu, base_mva)
    return flow, loss, it, math.sqrt(float(r @ r))


def _solve_pure(edges, r_per_km, x_per_km, base_mva, m, slack, total_demand_mw, load_nodes):
    length = [e["length_km"] for e in edges]
    kv = [e["voltage_kv"] for e in edges]
    r_ohm = [a * b for a, b in zip(r_per_km, length)]
    b = []
    for e, x_km, l in zip(edges, x_per_km, length):
        zbase = (e["voltage_kv"] ** 2) / base_mva
        x_pu = (x_km * l) / zbase
        b.append(1.0 / max(x_pu, 1e-9))
    loads = load_nodes or [i for i in range(m) if i != slack]
    per = (total_demand_mw / base_mva) / max(1, len(loads))
    full = [0.0] * (m + 1)
    sol = [0.0] * m
    rhs = [0.0] * m
    for i in loads:
        if i < m:
            rhs[i] = -per

    def matvec(x):
        for i in range(m):
            full[i] = x[i]
        out = [0.0] * m
        for e, bij in zip(edges, b):
            i, j = e["from"], e["to"]
            d = full[i] - full[j]
            if i != slack:
                out[i] += bij * d
            if j != slack:
                out[j] -= bij * d
        return out

    r = rhs[:]
    p = r[:]
    rsold = sum(v * v for v in r)
    it = 0
    for it in range(1, SOLVER_MAX_ITER + 1):
        ap = matvec(p)
        denom = sum(p[i] * ap[i] for i in range(m))
        if abs(denom) < 1e-18:
            break
        alpha = rsold / denom
        for i in range(m):
            sol[i] += alpha * p[i]
            r[i] -= alpha * ap[i]
        rsnew = sum(v * v for v in r)
        if math.sqrt(rsnew) < SOLVER_TOL:
            break
        p = [r[i] + (rsnew / rsold) * p[i] for i in range(m)]
        rsold = rsnew
    full[:m] = sol
    flow, loss = [], []
    for e, bij, ro in zip(edges, b, r_ohm):
        f = (full[e["from"]] - full[e["to"]]) * bij * base_mva
        i_ka = abs(f) / (math.sqrt(3.0) * e["voltage_kv"])
        flow.append(f)
        loss.append((i_ka ** 2) * ro)
    return flow, loss, it, math.sqrt(sum(v * v for v in r))


def _avg_demand_mw() -> tuple[float, dict[str, Any]]:
    baseline = _load_json(BASELINE_PATH)
    distribution_mwh = float(baseline["q1_2026"]["distribution_mwh"])
    avg_mw = distribution_mwh / QUARTER_HOURS
    return avg_mw, {
        "distribution_mwh": distribution_mwh,
        "period_hours": QUARTER_HOURS,
        "source": "Statistics Botswana Electricity Generation & Distribution Stats Brief Q1 2026 (via botswana_energy_baseline.json)",
        "evidence_class": "observed",
        "note": "Average demand over the quarter. Not a peak, not a substation load.",
    }


_CACHE: dict[tuple, dict[str, Any]] = {}


def _stamp(path: Path) -> tuple[int, int]:
    try:
        st = path.stat()
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return (0, 0)


def loss_reconciliation(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Cached wrapper: the screen is deterministic for fixed input files."""
    key = (_stamp(OSM_GRID_PATH), _stamp(AICD_GRID_PATH), _stamp(BASELINE_PATH), _stamp(BENCH_PATH))
    hit = _CACHE.get(key)
    if hit is not None:
        return hit
    out = _compute_loss_reconciliation(payload)
    _CACHE.clear()
    _CACHE[key] = out
    return out


def _compute_loss_reconciliation(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run the benchmark transmission-loss screen and reconcile it against BPC/AFREC."""
    cases = ("conservative", "reference", "high_capacity")
    avg_mw, demand_provenance = _avg_demand_mw()
    topo = _topology(SNAP_PLACES)
    comp = _largest_component(topo)
    comp_edges, relabel = _component_edges(topo, comp)
    slack = _slack_index(topo, comp, relabel)
    load_nodes = _component_load_nodes(topo, comp, relabel, slack)
    m = len(comp) - 1
    classes, base_mva = _benchmark_library()

    if _spsolve is not None and _np is not None:
        solver_name = "scipy-sparse-direct"
        solve = _solve_direct
    elif _np is not None:
        solver_name = "numpy-pcg"
        solve = _solve_pcg
    else:
        solver_name = "pure-python-cg"
        solve = _solve_pure

    results: dict[str, Any] = {}
    for case in cases:
        r_per_km, x_per_km = [], []
        for e in comp_edges:
            params = classes[str(e["voltage_kv"])]["cases"][case]
            r_per_km.append(params["r_ohm_per_km"])
            x_per_km.append(params["x_ohm_per_km"])
        flow, loss, it, residual = solve(comp_edges, r_per_km, x_per_km, base_mva, m, slack, avg_mw, load_nodes)
        flow = [float(v) for v in flow]
        loss = [float(v) for v in loss]
        total_loss = sum(loss)
        by_voltage: dict[str, float] = {}
        ranked = []
        for e, f, l in zip(comp_edges, flow, loss):
            key = f"{e['voltage_kv']} kV"
            by_voltage[key] = by_voltage.get(key, 0.0) + l
            ranked.append((abs(f), f, l, e))
        ranked.sort(reverse=True, key=lambda t: t[0])
        results[case] = {
            "supported": True,
            "approx_loss_at_average_load_mw": round(total_loss, 3),
            "loss_pct_of_average_demand": round(100.0 * total_loss / avg_mw, 2) if avg_mw else None,
            "annualised_gwh_low": round(total_loss * 8760 * LLF_RANGE[0] / 1000.0, 1),
            "annualised_gwh_high": round(total_loss * 8760 * LLF_RANGE[1] / 1000.0, 1),
            "nodes_in_solve": m,
            "branches_in_solve": len(comp_edges),
            "load_buses": len(load_nodes),
            "loss_by_voltage_mw": {k: round(v, 4) for k, v in sorted(by_voltage.items())},
            "cg_iterations": it,
            "solver_residual": residual,
            "top_flows": [
                {
                    "name": e["name"],
                    "voltage_kv": e["voltage_kv"],
                    "length_km": round(e["length_km"], 1),
                    "flow_mw": round(f, 1),
                    "abs_flow_mw": round(abs(f), 1),
                    "approx_i2r_loss_mw": round(l, 4),
                }
                for _, f, l, e in ranked[:8]
            ],
        }

    ref = results["reference"]
    reconciliation = {
        "modelled_transmission_only_gwh_range": [ref["annualised_gwh_low"], ref["annualised_gwh_high"]],
        "bpc_2023_td_gwh": BPC_LOSS_GWH,
        "bpc_2023_td_pct": BPC_LOSS_PCT,
        "afrec_2023_gwh": AFREC_LOSS_GWH,
        "afrec_2023_pct": AFREC_LOSS_PCT,
        "note": (
            "BPC and AFREC figures cover transmission AND distribution losses. This model is "
            "transmission-only, so a deliberate undercount is expected. The comparison is a "
            "falsifiable sanity check, not a claim of matching BPC's measurement."
        ),
    }

    return {
        "engine": "e2_flow.loss_reconciliation",
        "supported": True,
        "inputs": {
            "grid_dataset": topo["path"],
            "snap_places": SNAP_PLACES,
            "solver": solver_name,
            "average_demand_mw": round(avg_mw, 1),
            "demand_provenance": demand_provenance,
            "demand_allocation": "uniform across mapped substation buses" if load_nodes else "uniform across all buses (no substations available)",
            "slack_bus_note": "Generation injected at the node nearest Morupule; the mapped model does not include imports.",
            "loss_load_factor_range": list(LLF_RANGE),
            "benchmark_cases": list(cases),
        },
        "results_by_case": results,
        "reconciliation": reconciliation,
        "evidence_classes": {
            "observed": "Mapped line geometry, voltage tags, mapped substations, Statistics Botswana distribution volume.",
            "derived": "Lengths, topology, DC flows.",
            "benchmark": "Standard-type R/X parameters, security factors.",
            "assumed": "~1 km vertex snapping; uniform demand across substation buses; loss-load-factor range; Morupule slack.",
            "unknown": "BPC ratings, impedances, switching state, substation loads, imports.",
        },
        "network": {
            "snapped_nodes": len(topo["nodes"]),
            "mapped_segments": len(topo["edges"]),
            "largest_component_nodes": len(comp),
            "largest_component_branches": len(comp_edges),
            "skipped_features": topo["skipped"],
        },
        "not": (
            "measured BPC loading, real-time congestion, AC power flow, OPF, N-1, or a distribution-loss model. "
            "This is a benchmark planning screen on public data."
        ),
    }


if __name__ == "__main__":
    print(json.dumps(loss_reconciliation(), indent=2)[:5000])
