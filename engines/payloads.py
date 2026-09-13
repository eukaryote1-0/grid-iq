from __future__ import annotations

from typing import Any

from app.logic import (
    DATA, _load_json,
)
def bpc_losses_payload() -> dict[str, Any]:
    return _load_json(DATA / "official" / "bpc_system_losses.json")



def rural_electrification_payload() -> dict[str, Any]:
    return _load_json(DATA / "official" / "rural_electrification.json")



def agriculture_payload() -> dict[str, Any]:
    return _load_json(DATA / "official" / "agriculture_2025.json")



def agriculture_district_payload() -> dict[str, Any]:
    return _load_json(DATA / "official" / "agriculture_district_2015.json")



def biogas_benchmarks_payload() -> dict[str, Any]:
    return _load_json(DATA / "benchmarks" / "biogas_benchmarks.json")



def sapp_transfer_limits_payload() -> dict[str, Any]:
    return _load_json(DATA / "official" / "sapp_transfer_limits.json")



def renewable_benchmarks_payload() -> dict[str, Any]:
    return _load_json(DATA / "benchmarks" / "renewable_costs.json")



def community_benchmarks_payload() -> dict[str, Any]:
    return _load_json(DATA / "benchmarks" / "community_costs.json")



def bpc_grid_public_payload() -> dict[str, Any]:
    return _load_json(DATA / "official" / "bpc_grid_public_snapshot.json")



def gep_reference_payload() -> dict[str, Any]:
    return _load_json(DATA / "reference" / "gep_botswana_dataset.json")



def transformer_benchmarks_payload() -> dict[str, Any]:
    return _load_json(DATA / "benchmarks" / "transformer_benchmarks.json")



def load_profile_benchmarks_payload() -> dict[str, Any]:
    return _load_json(DATA / "benchmarks" / "load_profile_benchmarks.json")



def biomass_residue_benchmarks_payload() -> dict[str, Any]:
    return _load_json(DATA / "benchmarks" / "biomass_residue_benchmarks.json")
