#!/usr/bin/env python3
"""Prepare the local cache so the GridIQ demo runs without the network.

- Builds data/cache/osm_power.json from the committed OSM extracts.
- Copies committed fixtures (NASA / GEP / Eskom) into data/cache with fresh
  mtimes so the app's cache TTLs accept them.

Usage:
    python scripts/prewarm_demo.py            # offline (uses committed fixtures)
    python scripts/prewarm_demo.py --check    # verify only, change nothing
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache"
DEMO_CACHE = ROOT / "data" / "demo" / "cache"
GRID = ROOT / "data" / "grid" / "botswana_osm_power_132_220_400.geojson"
SUBSTATIONS = ROOT / "data" / "grid" / "botswana_osm_substations.geojson"
RURAL = ROOT / "data" / "official" / "rural_electrification.json"


def build_osm_cache() -> dict:
    """Reshape the committed OSM extracts into the app's /api/osm/power shape."""
    lines = json.loads(GRID.read_text(encoding="utf-8"))["features"]
    subs = json.loads(SUBSTATIONS.read_text(encoding="utf-8"))["features"] if SUBSTATIONS.exists() else []
    features = []
    for f in lines:
        p = dict(f.get("properties") or {})
        p.setdefault("power", "line")
        p["evidence"] = "mapped_public_data"
        if "source" not in p:
            p["source"] = "OpenStreetMap via Overpass API"
        features.append({"type": "Feature", "id": f.get("id"), "geometry": f["geometry"], "properties": p})
    for f in subs:
        p = dict(f.get("properties") or {})
        p["power"] = "substation"
        features.append({"type": "Feature", "id": f.get("id"), "geometry": f["geometry"], "properties": p})
    return {
        "data": {"type": "FeatureCollection", "features": features},
        "meta": {
            "source": "OpenStreetMap via Overpass API (demo fixture compiled from committed extract)",
            "fetched_at": time.time(),
            "cache": "fixture",
            "warning": "Mapped public infrastructure only. Ratings, impedance, loading and asset condition are not inferred.",
        },
    }


def _cache_key(name: str) -> str:
    # The app builds cache names with key.replace("-", "m").replace(".", "p"),
    # which also transforms the trailing ".json" into "pjson".
    return name.replace("-", "m").replace(".", "p")


def required_keys() -> list[str]:
    villages = json.loads(RURAL.read_text(encoding="utf-8"))["pilot_villages"]
    keys = ["osm_power.json"]
    for v in villages:
        lat, lon = float(v["lat"]), float(v["lon"])
        keys.append(_cache_key(f"nasa_{lat:.4f}_{lon:.4f}_30.json"))
    keys.append(_cache_key("nasa_-24.6282_25.9231_14.json"))
    return keys


def optional_keys() -> list[str]:
    """GEP and the Eskom shape are nice-to-have; their upstreams are frequently blocked."""
    villages = json.loads(RURAL.read_text(encoding="utf-8"))["pilot_villages"]
    keys = ["eskom_hourly_shape.json"]
    for v in villages:
        lat, lon = float(v["lat"]), float(v["lon"])
        keys.append(_cache_key(f"gep_{lat:.4f}_{lon:.4f}.json"))
    return keys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="verify only; do not write")
    args = ap.parse_args()

    if args.check:
        missing = [k for k in required_keys() if not (CACHE / k).exists()]
        opt_missing = [k for k in optional_keys() if not (CACHE / k).exists()]
        if missing:
            print("MISSING required fixtures:")
            for m in missing:
                print("  -", m)
            return 1
        print("required fixtures OK")
        if opt_missing:
            print("optional fixtures not present (live upstream frequently blocked):")
            for m in opt_missing:
                print("  -", m)
        return 0

    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / "osm_power.json").write_text(json.dumps(build_osm_cache()), encoding="utf-8")
    print("wrote data/cache/osm_power.json (from committed extracts)")

    if not DEMO_CACHE.exists():
        print("WARNING: no committed demo fixtures found. Run scripts/build_demo_fixtures.py once with network.")
        return 1
    copied = 0
    for src in sorted(DEMO_CACHE.iterdir()):
        if not src.is_file():
            continue
        dst = CACHE / src.name
        shutil.copyfile(src, dst)
        os.utime(dst, None)  # fresh mtime so the app's cache TTL accepts it
        copied += 1
    print(f"copied {copied} fixture cache files into data/cache")

    missing = [k for k in required_keys() if not (CACHE / k).exists()]
    if missing:
        print("WARNING: still missing required cache entries:")
        for m in missing:
            print("  -", m)
        return 1
    opt_missing = [k for k in optional_keys() if not (CACHE / k).exists()]
    if opt_missing:
        print(f"note: {len(opt_missing)} optional fixtures absent (GEP/Eskom); demo degrades gracefully.")
    print("prewarm complete (offline demo ready)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
