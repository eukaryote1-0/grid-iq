#!/usr/bin/env python3
"""Build the Botswana settlement register for the VillageFit dropdown.

Source: World Bank / ESMAP Botswana DRE Atlas settlement clusters (CC BY 4.0),
fetched from the energydata.info CKAN datastore. Modelled planning clusters, not
a BPC connection-status register. The six verified off-grid pilots are flagged.

Usage:
    python scripts/build_settlements.py
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "official" / "botswana_settlements.json"
RURAL = ROOT / "data" / "official" / "rural_electrification.json"
RESOURCE = "42a50c1b-7920-4e2c-a465-e15f1f9d8711"
ENDPOINT = "https://energydata.info/en/api/3/action/datastore_search"
KEEP = (
    "village_name", "lat", "lon", "admin_cgaz_1", "admin_cgaz_2", "population",
    "num_buildings", "distance_to_existing_transmission_lines", "demand",
    "num_connections", "pv_value", "crop_types", "geohash",
)


def haversine_km(a, b) -> float:
    lon1, lat1 = map(math.radians, a)
    lon2, lat2 = map(math.radians, b)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371.0088 * 2 * math.asin(math.sqrt(h))


def main() -> int:
    pilots = json.loads(RURAL.read_text(encoding="utf-8"))["pilot_villages"]
    with httpx.Client(timeout=90, headers={"User-Agent": "GridIQ-Botswana/1.8"}) as client:
        r = client.post(ENDPOINT, json={"resource_id": RESOURCE, "limit": 32000})
        r.raise_for_status()
        body = r.json()
    if not body.get("success"):
        raise SystemExit("DRE datastore returned success=false")
    records = body["result"]["records"]

    rows = []
    for rec in records:
        try:
            lat, lon = float(rec.get("lat")), float(rec.get("lon"))
        except (TypeError, ValueError):
            continue
        name = (rec.get("village_name") or "Unnamed settlement").strip()
        row = {
            "id": rec.get("geohash") or f"s{len(rows)}",
            "name": name,
            "lat": lat,
            "lon": lon,
            "district": (rec.get("admin_cgaz_2") or rec.get("admin_cgaz_1") or "").strip(),
            "population": rec.get("population"),
            "buildings": rec.get("num_buildings"),
            "grid_km": rec.get("distance_to_existing_transmission_lines"),
            "demand": rec.get("demand"),
            "connections": rec.get("num_connections"),
            "pv_value": rec.get("pv_value"),
            "crop_types": rec.get("crop_types"),
        }
        for p in pilots:
            same_name = p["name"].lower() == name.lower() or name.lower() in [a.lower() for a in p.get("aliases", [])]
            near = haversine_km((lon, lat), (float(p["lon"]), float(p["lat"]))) < 5.0
            if same_name or near:
                row["verified_pilot"] = p["id"]
                row["population"] = row.get("population") or p.get("population_2022")
                if not same_name and (name.lower().startswith("location #") or name.lower().startswith("unnamed")):
                    row["drc_name"] = name
                    row["name"] = p["name"]
                    name = p["name"]
                break
        rows.append(row)

    rows.sort(key=lambda x: (x.get("population") or 0), reverse=True)
    payload = {
        "metadata": {
            "title": "Botswana settlement register (VillageFit dropdown)",
            "source": "World Bank / ESMAP Botswana DRE Atlas settlement clusters",
            "source_url": "https://energydata.info/dataset/botswana-distributed-renewable-energy-dre",
            "publisher": "World Bank Group / ESMAP / VIDA",
            "licence": "CC-BY-4.0",
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "records": len(rows),
            "verified_pilots_included": sum(1 for r in rows if r.get("verified_pilot")),
            "warning": "DRE settlement clusters are modelled open planning data, not a verified BPC list of unconnected villages. VillageFit labels them accordingly.",
        },
        "villages": rows,
    }
    OUT.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} settlements, "
          f"{payload['metadata']['verified_pilots_included']} verified pilots matched, "
          f"{OUT.stat().st_size/1e6:.2f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
