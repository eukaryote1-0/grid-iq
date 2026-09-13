#!/usr/bin/env python3
"""Record (or check) the demo-day numbers for the deck.

Usage:
    python scripts/record_demo_outputs.py           # write data/demo/expected_outputs.json
    python scripts/record_demo_outputs.py --check    # compare a live run to the record
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "data" / "demo"
PORT = 8891
BASE = f"http://127.0.0.1:{PORT}"


def wait_health(client: httpx.Client, timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if client.get("/api/health", timeout=2).status_code == 200:
                return
        except Exception:
            time.sleep(0.4)
    raise SystemExit("server did not become healthy")


def collect() -> dict:
    sc = json.loads((DEMO / "scenarios_demo.json").read_text(encoding="utf-8"))
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        with httpx.Client(base_url=BASE, timeout=180) as c:
            wait_health(c)
            c.get("/api/osm/power")
            out: dict = {"scenarios": {}, "loss": {}}
            for key, s in sc["e1_scenarios"].items():
                sol = c.post("/api/e1/optimize", json=s["payload"]).json()["solution"]
                out["scenarios"][key] = {
                    "total_annual_screen_cost_usd": sol["total_annual_screen_cost_usd"],
                    "imports_avoided_mwh": sol["imports_avoided_mwh"],
                    "solar_mw": sol["solar_mw"],
                    "bess_mwh": sol["bess_mwh"],
                }
            out["scenarios"]["delta_cost_a_minus_b_usd"] = round(
                out["scenarios"]["A"]["total_annual_screen_cost_usd"]
                - out["scenarios"]["B"]["total_annual_screen_cost_usd"], 0)
            e2 = c.post("/api/e2/system-benchmark", json=sc["e2_system_study"]).json()
            out["e2_system"] = {
                "supported": e2.get("supported"),
                "max_benchmark_utilization_pct": e2.get("summary", {}).get("max_benchmark_utilization_pct"),
                "approx_total_i2r_loss_mw": e2.get("summary", {}).get("approx_total_i2r_loss_mw"),
            }
            model = c.get("/api/engines/loss-reconciliation").json()
            out["loss"]["model_gwh_range"] = model["reconciliation"]["modelled_transmission_only_gwh_range"]
            out["loss"]["bpc_2023_gwh"] = 642
            out["loss"]["bpc_2024_gwh"] = 793
            e3 = c.get("/api/e3/criticality?limit=20").json()
            out["e3"] = {"watchlist": len(e3.get("watchlist", [])), "bridges_total": e3.get("bridge_count")}
            vb = sc["village_demand_benchmark"]
            payload = {
                "village_id": sc["demo_village"], "use_live_nasa": True, "use_live_gep": False,
                "annual_kwh_per_household": vb["annual_kwh_per_household"],
                "peak_kw_per_household": vb["peak_kw_per_household"],
                "evening_energy_share_pct": vb["evening_energy_share_pct"],
            }
            e4 = c.post("/api/e4/villagefit", json=payload).json()
            out["e4_village"] = {
                "name": e4.get("village", {}).get("name"),
                "solar_pv_mw_screen": e4.get("sizing", {}).get("solar_pv_mw_screen"),
                "bess_mwh_screen": e4.get("sizing", {}).get("bess_mwh_screen"),
                "grid_km": e4.get("grid_proximity", {}).get("distance_km"),
            }
            villages = json.loads((ROOT / "data" / "official" / "rural_electrification.json").read_text(encoding="utf-8"))["pilot_villages"]
            out["pilot_villages_scored"] = len(villages)
            return out
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    current = collect()
    target = DEMO / "expected_outputs.json"
    if args.check:
        if not target.exists():
            print("no recorded outputs; run without --check first")
            return 1
        recorded = json.loads(target.read_text(encoding="utf-8"))
        ok = True
        for key in ("e4_village", "loss", "e2_system", "e3"):
            if recorded.get(key) != current.get(key):
                ok = False
                print(f"DRIFT in {key}:\n  recorded={recorded.get(key)}\n  current ={current.get(key)}")
        print("demo outputs match the record" if ok else "demo outputs have drifted")
        return 0 if ok else 1
    target.write_text(json.dumps(current, indent=2), encoding="utf-8")
    print(f"wrote {target.relative_to(ROOT)}")
    print(json.dumps(current, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
