import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def test_committed_external_datasets_match_manifest():
    manifest = json.loads((ROOT / "data" / "manifests" / "external_datasets.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "generated"
    assert manifest["files"], "expected at least one committed external dataset"
    for entry in manifest["files"]:
        path = ROOT / entry["path"]
        assert path.exists(), f"missing committed dataset: {entry['path']}"
        assert sha256(path) == entry["sha256"], f"checksum mismatch: {entry['path']}"


def test_botswana_grid_is_usable_geojson():
    path = ROOT / "data" / "grid" / "botswana_grid.geojson"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["type"] == "FeatureCollection"
    assert len(payload["features"]) > 50
    voltages = {
        f["properties"].get("voltage_kV")
        for f in payload["features"]
        if f.get("properties", {}).get("voltage_kV")
    }
    assert {132, 220, 400} <= {int(v) for v in voltages}


def test_techno_economic_workbook_has_expected_sheets():
    import openpyxl

    path = ROOT / "data" / "benchmarks" / "botswana_techno_economic.xlsx"
    wb = openpyxl.load_workbook(path, read_only=True)
    for expected in ("Trans. and Dist.", "Cost of RE Power Plants ", "Elec. imp. & exp."):
        assert expected in wb.sheetnames
