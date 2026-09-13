import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "data" / "demo"


def test_demo_scenarios_validate():
    sc = json.loads((DEMO / "scenarios_demo.json").read_text(encoding="utf-8"))
    assert sc["demo_village"] in [v["id"] for v in json.loads(
        (ROOT / "data" / "official" / "rural_electrification.json").read_text(encoding="utf-8"))["pilot_villages"]]
    for key in ("A", "B"):
        payload = sc["e1_scenarios"][key]["payload"]
        assert payload["max_solar_mw"] > 0 and payload["bess_duration_h"] > 0
    net = sum(i["mw"] for i in sc["e2_system_study"]["injections"])
    assert abs(net) < 1e-6, "benchmark injections must balance"


def test_required_demo_fixtures_committed():
    villages = json.loads((ROOT / "data" / "official" / "rural_electrification.json").read_text(encoding="utf-8"))["pilot_villages"]
    for v in villages:
        lat, lon = float(v["lat"]), float(v["lon"])
        key = f"nasa_{lat:.4f}_{lon:.4f}_30.json".replace("-", "m").replace(".", "p")
        assert (DEMO / "cache" / key).exists(), f"missing NASA fixture for {v['name']}"


def test_prewarm_builds_osm_cache():
    import importlib.util

    spec = importlib.util.spec_from_file_location("prewarm_demo", ROOT / "scripts" / "prewarm_demo.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    payload = mod.build_osm_cache()
    features = payload["data"]["features"]
    assert len(features) > 1000
    assert any(f["geometry"]["type"] == "LineString" for f in features)
    assert any(f["geometry"]["type"] == "Point" for f in features)
