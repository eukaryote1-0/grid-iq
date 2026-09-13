from fastapi.testclient import TestClient

from app.main import app


def test_villages_endpoint_shape():
    client = TestClient(app)
    r = client.get("/api/villages?limit=5")
    assert r.status_code == 200
    body = r.json()
    assert len(body["villages"]) == 5
    assert body["total"] > 2000
    first = body["villages"][0]
    for key in ("id", "name", "lat", "lon", "district"):
        assert key in first


def test_villages_query_matches():
    client = TestClient(app)
    r = client.get("/api/villages?query=ukhwi")
    assert r.status_code == 200
    names = [v["name"].lower() for v in r.json()["villages"]]
    assert any("ukhwi" in n or "ukwi" in n for n in names)
    assert r.json()["count"] >= 1


def test_villages_include_verified_pilots():
    client = TestClient(app)
    rows = client.get("/api/villages?limit=3000").json()["villages"]
    pilots = [v for v in rows if v.get("verified_pilot")]
    assert pilots, "verified off-grid pilots must be flagged in the register"
