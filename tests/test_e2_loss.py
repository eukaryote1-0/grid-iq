import pytest

from engines.e2_flow.loss_reconciliation import loss_reconciliation


@pytest.fixture(scope="module")
def result():
    return loss_reconciliation()


def test_engine_runs_and_is_bracketed(result):
    assert result["engine"] == "e2_flow.loss_reconciliation"
    assert result["supported"] is True
    for case in ("conservative", "reference", "high_capacity"):
        res = result["results_by_case"][case]
        assert res["supported"] is True
        assert res["approx_loss_at_average_load_mw"] > 0
        # Transmission-only screen must not exceed the whole-system T&D figure.
        assert 0 < res["loss_pct_of_average_demand"] < result["reconciliation"]["bpc_2023_td_pct"]
        assert res["annualised_gwh_low"] < res["annualised_gwh_high"]


def test_reconciliation_targets_are_present(result):
    rec = result["reconciliation"]
    assert rec["bpc_2023_td_gwh"] == 642.0
    assert rec["bpc_2023_td_pct"] == 14.51
    assert rec["afrec_2023_gwh"] == 630.0
    assert rec["afrec_2023_pct"] == 13.8


def test_evidence_boundaries_are_declared(result):
    classes = result["evidence_classes"]
    for key in ("observed", "derived", "benchmark", "assumed", "unknown"):
        assert key in classes
    assert "benchmark" in result["not"].lower()
    assert "opF".lower() in result["not"].lower()


def test_loss_is_concentrated_by_voltage(result):
    by_voltage = result["results_by_case"]["reference"]["loss_by_voltage_mw"]
    assert by_voltage, "expected losses broken down by voltage"
    assert all(v >= 0 for v in by_voltage.values())


def test_small_fixture_direct_solve():
    """Direct solver sanity: a 3-bus line must produce a finite positive loss."""
    pytest.importorskip("scipy")
    from engines.e2_flow.loss_reconciliation import _solve_direct

    edges = [
        {"from": 0, "to": 1, "length_km": 100.0, "voltage_kv": 220, "name": "A-B"},
        {"from": 1, "to": 2, "length_km": 100.0, "voltage_kv": 220, "name": "B-C"},
    ]
    r_per_km = [0.042, 0.042]
    x_per_km = [0.275, 0.275]
    flow, loss, iterations, residual = _solve_direct(edges, r_per_km, x_per_km, 100.0, m=2, slack=0, total_demand_mw=100.0, load_nodes=[2])
    assert len(flow) == 2
    assert sum(loss) > 0
    assert all(l == l for l in loss)  # not NaN
