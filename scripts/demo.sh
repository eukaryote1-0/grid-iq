#!/usr/bin/env bash
# One-command demo preflight: prewarm the caches, start the app, smoke every
# screen's data path, and print the numbers the presenter will read out.
set -euo pipefail
cd "$(dirname "$0")/.."

BASE="${BASE:-http://127.0.0.1:8000}"
PY="${PYTHON:-python3}"

echo "== 1/3 prewarm (offline fixtures) =="
"$PY" scripts/prewarm_demo.py

echo
echo "== 2/3 start app =="
./run.sh || { echo "run.sh returned non-zero; continuing to smoke anyway"; }

echo
echo "== 3/3 smoke demo paths =="
"$PY" - "$BASE" <<'PY'
import json, sys, urllib.request

base = sys.argv[1]
def get(path):
    return json.loads(urllib.request.urlopen(base + path, timeout=180).read())
def post(path, payload):
    req = urllib.request.Request(base + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=180).read())

sc = json.load(open("data/demo/scenarios_demo.json"))
print("health:", get("/api/health")["status"])
anchor = get("/api/losses/bpc")["validation_anchor"]
print(f"BPC anchor: {anchor['loss_gwh_table']} GWh ({anchor['loss_pct_table']}%) in {anchor['year']}")
for key, s in sc["e1_scenarios"].items():
    sol = post("/api/e1/optimize", s["payload"]).get("solution", {})
    print(f"E1 {key}: total_annual_screen_cost_usd={sol.get('total_annual_screen_cost_usd'):,.0f}"
          f" | imports_avoided_mwh={sol.get('imports_avoided_mwh'):,.0f}"
          f" | solar_mw={sol.get('solar_mw')} | bess_mwh={sol.get('bess_mwh')}")
print("E2 system study:", post("/api/e2/system-benchmark", sc["e2_system_study"]).get("mode"))
print("E2 reconciliation status:", post("/api/e2/loss-reconciliation",
      {"modelled_loss_gwh": None, "model_scope": "transmission"}).get("status"))
model = get("/api/engines/loss-reconciliation")
print("Model transmission loss bracket (GWh/y):", model["reconciliation"]["modelled_transmission_only_gwh_range"])
e3 = get("/api/e3/criticality?limit=20")
print(f"E3: watchlist={len(e3.get('watchlist', []))} articulation_points={len(e3.get('articulation_points', []))}")
vb = sc["village_demand_benchmark"]
e4 = post("/api/e4/villagefit", {
    "village_id": sc["demo_village"],
    "use_live_nasa": True, "use_live_gep": False,  # NASA from prewarmed cache; GEP upstream is blocked
    "annual_kwh_per_household": vb["annual_kwh_per_household"],
    "peak_kw_per_household": vb["peak_kw_per_household"],
    "evening_energy_share_pct": vb["evening_energy_share_pct"],
})
sizing = e4.get("sizing", {})
print(f"E4 {e4.get('village', {}).get('name')}: pv_mw={sizing.get('solar_pv_mw_screen')}"
      f" bess_mwh={sizing.get('bess_mwh_screen')} status={e4.get('status')}")
print()
print("Demo URL:", f"{base}/?demo=1")
PY

if [[ "${OPEN:-0}" == "1" ]]; then
  xdg-open "$BASE/?demo=1" >/dev/null 2>&1 || true
fi
