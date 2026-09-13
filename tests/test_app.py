import unittest

try:
    from fastapi.testclient import TestClient
    from app.main import app
except Exception:
    TestClient = None
    app = None


@unittest.skipIf(TestClient is None, "FastAPI runtime not installed")
class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = TestClient(app)

    def test_health(self):
        j = self.c.get("/api/health").json()
        self.assertEqual(j["status"], "ok")
        self.assertEqual(j["version"], "1.7.0")

    def test_catalog(self):
        j = self.c.get("/api/catalog").json()
        self.assertGreaterEqual(j["count"], 12)
        self.assertTrue(any(x["id"] == "stats_electricity" for x in j["datasets"]))

    def test_baseline(self):
        j = self.c.get("/api/baseline").json()
        self.assertEqual(j["q1_2026"]["local_generation_share_of_distribution_pct"], 80.4)
        self.assertEqual(j["grid"]["transmission_km_by_voltage"]["400_kv"], 1027.0)

    def test_benchmarks(self):
        j = self.c.get("/api/storage-benchmarks").json()
        self.assertEqual(j["utility_scale_bess_2024"]["round_trip_efficiency_pct_nrel_atb"], 85)

    def test_neus(self):
        j = self.c.get("/api/neus").json()
        self.assertEqual(j["national_access"]["grid_connection_pct"], 73.9)
        self.assertEqual(len(j["grid_connection_by_district"]), 26)

    def test_census_districts(self):
        j = self.c.get("/api/census/districts").json()
        self.assertEqual(j["total_population"], 2359609)
        self.assertEqual(len(j["districts"]), 28)


    def test_engineering_benchmark_endpoint(self):
        j = self.c.get("/api/engineering/benchmarks").json()
        self.assertEqual(j["base_mva"], 100)
        self.assertIn("220", j["voltage_classes"])

    def test_evidence_manifest_endpoint(self):
        j = self.c.get("/api/evidence/manifest").json()
        self.assertEqual(j["status"], "generated")
        self.assertGreaterEqual(len(j["files"]), 8)

    def test_audit_endpoint_is_not_hardcoded_to_nine(self):
        j = self.c.get("/api/audit").json()
        self.assertEqual(j["scores"]["open_data_governance"], 10.0)
        self.assertEqual(j["scores"]["benchmark_engineering_capability"], 10.0)
        self.assertEqual(j["scores"]["bpc_operational_validation"], 0.0)
        self.assertGreaterEqual(j["scores"]["public_data_planning_product"], 9.0)
        self.assertLess(j["scores"]["whole_solution"], 9.0)


    def test_district_access_context_endpoint(self):
        j = self.c.get("/api/demand/district-context").json()
        self.assertFalse(j["synthetic"])
        self.assertEqual(len(j["records"]), 28)
        self.assertIn("Southern", j["unmatched_census_districts"])


    def test_gap_resolution_register(self):
        j = self.c.get("/api/benchmarks/gap-resolution").json()
        self.assertGreaterEqual(len(j["gaps"]), 8)
        self.assertTrue(all("status" in x for x in j["gaps"]))
        self.assertFalse(j["metadata"]["synthetic"])

    def test_scenario(self):
        j = self.c.post("/api/scenario", json={"storage_mw": 100, "storage_mwh": 400}).json()
        self.assertNotIn("rows", j)
        self.assertEqual(j["summary"]["storage_duration_hours"], 4.0)
        self.assertFalse(j["gates"]["can_calculate_line_congestion"])


def test_frontend_uses_v14_bundle():
    if TestClient is None:
        return
    client = TestClient(app)
    html = client.get("/").text
    assert "/static/js/app.bundle.js?v=" in html
    assert 'type="module"' not in html
    assert "FRONTEND STARTUP DELAY" in html


def test_static_bundle_has_persistence_and_no_dummy_series():
    if TestClient is None:
        return
    client = TestClient(app)
    text = client.get("/static/js/app.bundle.js").text
    assert "localStorage" in text
    assert "resetDetachedMap" in text
    assert "no synthetic hourly" in text
    assert "dummyScenario" not in text
    assert "Math.exp" not in text
    assert "/api/neus" in text
    assert "/api/census/districts" in text
    assert "/api/demand/district-context" in text
    assert "/api/engineering/transfer" in text
    assert "/api/worldpop/population" in text
    assert "benchmark_engineering_capability" in text
    assert "data.osm" in text
