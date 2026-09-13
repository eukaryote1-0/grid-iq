import unittest

from app.logic import (
    baseline_payload,
    catalog_payload,
    census_districts_payload,
    geojson_evidence_summary,
    neus_payload,
    scenario_payload,
    storage_benchmarks_payload,
    validate_scenario,
)


class LogicTests(unittest.TestCase):
    def test_catalog_selected_sources(self):
        payload = catalog_payload()
        self.assertGreaterEqual(payload["count"], 12)
        ids = {x["id"] for x in payload["datasets"]}
        self.assertIn("osm_power", ids)
        self.assertIn("stats_electricity", ids)
        self.assertIn("battery_benchmark", ids)

    def test_official_baseline(self):
        b = baseline_payload()
        self.assertFalse(b["metadata"]["synthetic"])
        self.assertEqual(b["q1_2026"]["generation_mix_pct"]["coal"], 90.8)
        self.assertEqual(b["q1_2026"]["generation_mix_pct"]["solar"], 9.1)
        self.assertEqual(b["sapp_capacity"]["current_peak_demand_mw"], 610)
        self.assertEqual(len(b["quarterly"]), 41)

    def test_storage_benchmarks_are_labelled(self):
        b = storage_benchmarks_payload()
        self.assertFalse(b["metadata"]["synthetic"])
        self.assertEqual(b["utility_scale_bess_2024"]["global_total_installed_cost_usd_per_kwh"], 192)
        self.assertEqual(b["utility_scale_bess_2024"]["round_trip_efficiency_pct_nrel_atb"], 85)


    def test_neus_is_official_and_non_synthetic(self):
        n = neus_payload()
        self.assertFalse(n["synthetic"])
        self.assertEqual(n["national_access"]["grid_connection_pct"], 73.9)
        self.assertEqual(len(n["grid_connection_by_district"]), 26)
        rural = next(x for x in n["reasons_not_connected_by_locality"] if x["locality"] == "Rural Villages")
        self.assertEqual(rural["far_from_lines"], 51311)

    def test_census_district_population_is_official(self):
        c = census_districts_payload()
        self.assertFalse(c["synthetic"])
        self.assertEqual(c["total_population"], 2359609)
        self.assertEqual(len(c["districts"]), 28)
        kw = next(x for x in c["districts"] if x["district"] == "Kweneng East")
        self.assertEqual(kw["population"], 330220)


    def test_district_access_context_is_derived_not_synthetic(self):
        from app.logic import district_access_context_payload
        d = district_access_context_payload()
        self.assertFalse(d["synthetic"])
        self.assertEqual(len(d["records"]), 28)
        self.assertEqual(d["unmatched_census_districts"], ["Southern", "Delta", "CKGR"])
        kw = next(x for x in d["records"] if x["census_district"] == "Kweneng West")
        self.assertEqual(kw["household_grid_connection_pct"], 38.2)
        self.assertGreater(kw["population_weighted_access_gap_index"], 0)
        self.assertIn("NOT counts", d["transformation"]["interpretation"])

    def test_scenario_is_evidence_bounded_not_hourly_synthetic(self):
        result = scenario_payload({"storage_mw": 100, "storage_mwh": 400})
        self.assertNotIn("rows", result)
        self.assertEqual(result["meta"]["not"], "hourly dispatch, capacity adequacy study, power flow or OPF")
        self.assertEqual(result["summary"]["current_peak_capacity_gap_mw"], 151.0)
        self.assertEqual(result["summary"]["storage_duration_hours"], 4.0)
        self.assertFalse(result["gates"]["can_calculate_imports_avoided"])

    def test_validation(self):
        with self.assertRaises(ValueError):
            validate_scenario({"storage_mwh": -1})

    def test_osm_topology_summary(self):
        fc = {
            "type": "FeatureCollection",
            "features": [
                {"type":"Feature","geometry":{"type":"LineString","coordinates":[[25,-24],[25.1,-24],[25.2,-24]]},"properties":{"power":"line","voltage":"132000"}},
                {"type":"Feature","geometry":{"type":"LineString","coordinates":[[25.1,-24],[25.1,-23.9]]},"properties":{"power":"line","voltage":"220000"}},
                {"type":"Feature","geometry":{"type":"Point","coordinates":[25.1,-24]},"properties":{"power":"substation"}},
            ],
        }
        s = geojson_evidence_summary(fc)
        self.assertEqual(s["line_features"], 2)
        self.assertEqual(s["asset_features"], 1)
        self.assertGreater(s["mapped_line_length_km"], 0)
        self.assertEqual(s["topology"]["junctions_degree_3_plus"], 1)
        self.assertGreaterEqual(s["topology"]["connected_components"], 1)


if __name__ == "__main__":
    unittest.main()

class EngineeringBenchmarkTests(unittest.TestCase):
    def _fixture(self):
        # Test-only deterministic graph. It is not shipped as product evidence.
        return {
            "type": "FeatureCollection",
            "features": [
                {"type":"Feature","id":"l1","geometry":{"type":"LineString","coordinates":[[25.0,-24.0],[25.1,-24.0]]},"properties":{"power":"line","voltage":"220000","circuits":"1","name":"A-B"}},
                {"type":"Feature","id":"l2","geometry":{"type":"LineString","coordinates":[[25.1,-24.0],[25.2,-24.0]]},"properties":{"power":"line","voltage":"220000","circuits":"1","name":"B-C"}},
                {"type":"Feature","id":"l3","geometry":{"type":"LineString","coordinates":[[25.0,-24.0],[25.2,-24.0]]},"properties":{"power":"line","voltage":"220000","circuits":"1","name":"A-C"}},
            ],
        }

    def test_electrical_benchmark_library_is_explicitly_non_bpc(self):
        from app.logic import electrical_benchmarks_payload
        b = electrical_benchmarks_payload()
        self.assertEqual(b["base_mva"], 100)
        self.assertAlmostEqual(b["security_factor_s_max_pu"], 0.7)
        self.assertIn("220", b["voltage_classes"])
        self.assertIn("never observed bpc", b["purpose"].lower())

    def test_line_enrichment_preserves_observed_and_labels_benchmark(self):
        from app.logic import enrich_power_geojson
        e = enrich_power_geojson(self._fixture(), case="reference")
        row = e["features"][0]["properties"]
        self.assertEqual(row["voltage"], "220000")
        self.assertGreater(row["derived_length_km"], 0)
        self.assertGreater(row["benchmark"]["benchmark_x_total_ohm"], 0)
        self.assertGreater(row["benchmark"]["benchmark_secure_mva"], 0)
        self.assertEqual(row["benchmark"]["case"], "reference")
        self.assertIn("benchmark", row["benchmark"]["warning"].lower())

    def test_connected_dc_transfer_returns_evidence_bounded_result(self):
        from app.logic import benchmark_transfer_study
        r = benchmark_transfer_study(
            self._fixture(), voltage_kv=220, case="reference", transfer_mw=100,
            source_lat=-24.0, source_lon=25.0, sink_lat=-24.0, sink_lon=25.2,
        )
        self.assertTrue(r["supported"])
        self.assertEqual(r["mode"], "benchmark_dc_transfer")
        self.assertEqual(len(r["flows"]), 3)
        self.assertGreater(r["summary"]["max_benchmark_utilization_pct"], 0)
        self.assertIn("not", r["meta"])
        self.assertIn("measured", r["meta"]["not"])

    def test_disconnected_dc_transfer_refuses_to_fabricate_connection(self):
        from app.logic import benchmark_transfer_study
        fc = self._fixture()
        fc["features"].append({"type":"Feature","id":"l4","geometry":{"type":"LineString","coordinates":[[27.0,-22.0],[27.1,-22.0]]},"properties":{"power":"line","voltage":"220000"}})
        r = benchmark_transfer_study(
            fc, voltage_kv=220, case="reference", transfer_mw=50,
            source_lat=-24.0, source_lon=25.0, sink_lat=-22.0, sink_lon=27.1,
        )
        self.assertFalse(r["supported"])
        self.assertIn("different mapped OSM components", r["reason"])

    def test_multi_injection_dc_benchmark_balances_and_solves(self):
        from app.logic import benchmark_multi_injection_study
        r = benchmark_multi_injection_study(
            self._fixture(), voltage_kv=220, case="reference",
            injections=[
                {"name":"source","lat":-24.0,"lon":25.0,"mw":100},
                {"name":"load-a","lat":-24.0,"lon":25.1,"mw":-60},
                {"name":"load-b","lat":-24.0,"lon":25.2,"mw":-40},
            ],
        )
        self.assertTrue(r["supported"])
        self.assertEqual(r["mode"], "benchmark_dc_multi_injection")
        self.assertEqual(len(r["mapped_injections"]), 3)
        self.assertGreater(r["summary"]["max_benchmark_utilization_pct"], 0)

    def test_multi_injection_refuses_unbalanced_case(self):
        from app.logic import benchmark_multi_injection_study
        with self.assertRaises(ValueError):
            benchmark_multi_injection_study(
                self._fixture(), voltage_kv=220, case="reference",
                injections=[
                    {"name":"source","lat":-24.0,"lon":25.0,"mw":100},
                    {"name":"load","lat":-24.0,"lon":25.2,"mw":-90},
                ],
            )

    def test_audit_is_gate_derived_and_separates_public_product_from_bpc_validation(self):
        from app.logic import audit_payload
        a = audit_payload()
        self.assertEqual(a["scores"]["open_data_governance"], 10.0)
        self.assertEqual(a["scores"]["benchmark_engineering_capability"], 10.0)
        self.assertEqual(a["scores"]["bpc_operational_validation"], 0.0)
        self.assertGreaterEqual(a["scores"]["public_data_planning_product"], 9.0)
        self.assertLess(a["scores"]["whole_solution"], 9.0)


def test_representative_day_benchmark_engine_solves_with_test_shapes():
    from engines.e1_opt import representative_day_capacity_expansion_screen
    # Test-only deterministic fixtures; no fixture values are shipped as energy evidence.
    demand = [0.70,0.66,0.63,0.61,0.60,0.62,0.70,0.80,0.88,0.90,0.89,0.87,
              0.85,0.84,0.86,0.90,0.96,1.00,0.98,0.94,0.90,0.84,0.78,0.73]
    solar = [0,0,0,0,0,0.02,0.12,0.35,0.58,0.76,0.90,1.0,
             0.96,0.84,0.67,0.44,0.20,0.05,0,0,0,0,0,0]
    r = representative_day_capacity_expansion_screen(
        {"source_year":2025,"peak_demand_mw":610,"import_capacity_limit_mw":190,
         "import_energy_price_usd_per_mwh":100,"max_solar_mw":2500,"max_bess_mw":1000,
         "bess_duration_h":4,"real_discount_rate":0.08},
        demand, solar,
        demand_source_meta={"evidence_class":"test_fixture"},
        solar_source_meta={"evidence_class":"test_fixture"},
    )
    assert r["status"] == "solved"
    assert len(r["hourly"]) == 24
    assert r["solution"]["solar_build_mw"] >= 0
    assert "not measured BPC hourly dispatch" in r["evidence_boundary"]


def test_v17_audit_keeps_operational_validation_zero():
    from app.logic import audit_payload
    a = audit_payload()
    assert a["scores"]["public_data_planning_product"] == 9.5
    assert a["scores"]["bpc_operational_validation"] == 0.0
    assert a["scores"]["whole_solution"] == 8.0
    assert a["release_gates"]["benchmark_gap_register_present"] is True
