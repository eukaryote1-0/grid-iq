import os
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


def test_load_json_is_memory_cached_and_mtime_invalidated():
    from app.logic import _load_json

    path = ROOT / "data" / "benchmarks" / "storage_benchmarks.json"
    first = _load_json(path)
    second = _load_json(path)
    assert first is second, "second load must come from the in-process cache"
    st = path.stat()
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))
    third = _load_json(path)
    assert third is not first, "mtime change must invalidate the cached object"
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))


def test_static_assets_are_browser_cacheable_and_api_is_not():
    from app.main import app

    client = TestClient(app)
    static = client.get("/static/js/app.bundle.js")
    assert static.status_code == 200
    assert "max-age" in static.headers.get("cache-control", "")
    api = client.get("/api/baseline")
    assert api.status_code == 200
    assert api.headers.get("cache-control") == "no-store"


def test_large_api_responses_are_gzipped():
    from app.main import app

    client = TestClient(app)
    r = client.get("/api/catalog", headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200
    assert r.headers.get("content-encoding") == "gzip"


def test_tile_proxy_serves_from_local_cache(tmp_path=None):
    from app.main import app

    tile = ROOT / "data" / "cache" / "tiles" / "5" / "17" / "17.png"
    tile.parent.mkdir(parents=True, exist_ok=True)
    tile.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 32)
    client = TestClient(app)
    r = client.get("/tiles/5/17/17.png")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert "max-age" in r.headers.get("cache-control", "")


def test_upstream_breaker_trips_and_resets():
    from app.main import _mark_upstream, _upstream_blocked

    _mark_upstream("gep", True)
    assert _upstream_blocked("gep") is False
    _mark_upstream("gep", False)
    assert _upstream_blocked("gep") is True
    _mark_upstream("gep", True)
    assert _upstream_blocked("gep") is False
