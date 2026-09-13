from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from app.logic import (
    _parse_voltage_values_kv,
)
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
