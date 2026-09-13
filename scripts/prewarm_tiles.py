#!/usr/bin/env python3
"""Bounded, polite prewarm of the local OSM tile cache.

Caches Botswana at z5-z8 and the three demo points at z9-z12 so map pans and
zooms are served from disk by the /tiles proxy. Throttled and capped to respect
the OpenStreetMap tile usage policy; attribution stays with OpenStreetMap.

Usage:
    python scripts/prewarm_tiles.py            # skip tiles already cached
    python scripts/prewarm_tiles.py --force    # refetch
"""
from __future__ import annotations

import argparse
import math
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
TILES = ROOT / "data" / "cache" / "tiles"
UA = "GridIQ-Botswana/1.8 (bounded demo tile cache; contact: hackathon team)"
HOSTS = ("https://a.tile.openstreetmap.org", "https://b.tile.openstreetmap.org", "https://c.tile.openstreetmap.org")
CAP = 4000
THROTTLE_S = 0.2

BOTSWANA = (-26.95, 19.8, -17.7, 29.5)          # lat_min, lon_min, lat_max, lon_max
DEMO_POINTS = {                                  # name: (lat, lon)
    "ukhwi": (-23.55587, 20.49873),
    "gaborone": (-24.6282, 25.9231),
    "morupule": (-22.520735, 27.03615),
}


def deg2num(lat: float, lon: float, z: int) -> tuple[int, int]:
    n = 1 << z
    x = int((lon + 180.0) / 360.0 * n)
    lat_r = math.radians(lat)
    y = int((1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * n)
    return max(0, min(n - 1, x)), max(0, min(n - 1, y))


def wanted() -> list[tuple[int, int, int]]:
    tiles: set[tuple[int, int, int]] = set()
    lat_min, lon_min, lat_max, lon_max = BOTSWANA
    for z in range(5, 9):
        x0, y0 = deg2num(lat_max, lon_min, z)   # north-west
        x1, y1 = deg2num(lat_min, lon_max, z)   # south-east
        for x in range(min(x0, x1), max(x0, x1) + 1):
            for y in range(min(y0, y1), max(y0, y1) + 1):
                tiles.add((z, x, y))
    for _, (lat, lon) in DEMO_POINTS.items():
        for z in range(9, 13):
            cx, cy = deg2num(lat, lon, z)
            for x in range(cx - 2, cx + 3):
                for y in range(cy - 2, cy + 3):
                    if 0 <= x < (1 << z) and 0 <= y < (1 << z):
                        tiles.add((z, x, y))
    return sorted(tiles)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    TILES.mkdir(parents=True, exist_ok=True)
    todo = wanted()[:CAP]
    fetched = skipped = failed = 0
    with httpx.Client(timeout=httpx.Timeout(15, connect=5), headers={"User-Agent": UA}, follow_redirects=True) as client:
        for z, x, y in todo:
            path = TILES / str(z) / str(x) / f"{y}.png"
            if path.exists() and not args.force:
                skipped += 1
                continue
            ok = False
            for host in HOSTS:
                try:
                    r = client.get(f"{host}/{z}/{x}/{y}.png")
                    if r.status_code == 200 and r.content:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        tmp = path.with_suffix(".tmp")
                        tmp.write_bytes(r.content)
                        tmp.replace(path)
                        ok = True
                        break
                except Exception:
                    continue
            fetched += 1 if ok else 0
            failed += 0 if ok else 1
            time.sleep(THROTTLE_S)
    size = sum(p.stat().st_size for p in TILES.rglob("*.png"))
    print(f"tiles wanted={len(todo)} fetched={fetched} skipped={skipped} failed={failed} cache={size/1e6:.1f} MB")
    return 0 if failed == 0 or fetched > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
