#!/usr/bin/env python3
"""Build the committed offline demo fixtures (network required, run once).

Starts the app, asks it to fetch NASA POWER / World Bank GEP / Eskom benchmark
data for the six verified pilot villages, then copies the resulting cache files
into data/demo/cache/ so the demo can run with the network off.

Usage:
    python scripts/build_demo_fixtures.py            # fetch what is missing
    python scripts/build_demo_fixtures.py --force    # refetch everything
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache"
DEMO_CACHE = ROOT / "data" / "demo" / "cache"
RURAL = ROOT / "data" / "official" / "rural_electrification.json"
PORT = 8777
BASE = f"http://127.0.0.1:{PORT}"


def wait_health(client: httpx.Client, timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if client.get("/api/health", timeout=2).status_code == 200:
                return
        except Exception:
            time.sleep(0.4)
    raise SystemExit("app did not become healthy")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="refetch even if a fixture exists")
    args = ap.parse_args()

    villages = json.loads(RURAL.read_text(encoding="utf-8"))["pilot_villages"]
    CACHE.mkdir(parents=True, exist_ok=True)
    DEMO_CACHE.mkdir(parents=True, exist_ok=True)

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        with httpx.Client(base_url=BASE, timeout=90) as client:
            wait_health(client)
            print("app up; fetching fixtures")
            for v in villages:
                lat, lon = float(v["lat"]), float(v["lon"])
                nasa_key = f"nasa_{lat:.4f}_{lon:.4f}_30.json".replace("-", "m").replace(".", "p")
                gep_key = f"gep_{lat:.4f}_{lon:.4f}.json".replace("-", "m").replace(".", "p")
                if args.force or not (DEMO_CACHE / nasa_key).exists():
                    r = client.get("/api/nasa/power", params={"lat": lat, "lon": lon, "days": 30})
                    print(f"  NASA {v['name']}: {r.status_code}")
                if args.force or not (DEMO_CACHE / gep_key).exists():
                    r = client.get("/api/gep/point", params={"lat": lat, "lon": lon})
                    print(f"  GEP  {v['name']}: {r.status_code}")
            if args.force or not (DEMO_CACHE / "eskom_hourly_shape.json").exists():
                r = client.get("/api/benchmarks/eskom-hourly-shape")
                print(f"  Eskom hourly shape: {r.status_code}")
            # Gaborone point for the optional E1 chronology (14-day window).
            r = client.get("/api/nasa/power", params={"lat": -24.6282, "lon": 25.9231, "days": 14})
            print(f"  NASA Gaborone 14d: {r.status_code}")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    copied = 0
    for src in sorted(CACHE.iterdir()):
        if not src.is_file() or src.name == "osm_power.json":
            continue  # live OSM is intentionally not the offline fixture
        shutil.copy2(src, DEMO_CACHE / src.name)
        copied += 1
    print(f"copied {copied} cache files to {DEMO_CACHE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
