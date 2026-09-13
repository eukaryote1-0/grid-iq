from __future__ import annotations

import json
import time
from datetime import date, timedelta
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .logic import (
    CACHE,
    audit_payload,
    baseline_payload,
    cache_read,
    cache_write,
    catalog_payload,
    census_districts_payload,
    district_access_context_payload,
    electrical_benchmarks_payload,
    enrich_power_geojson,
    evidence_manifest_payload,
    geojson_evidence_summary,
    benchmark_transfer_study,
    overpass_to_geojson,
    neus_payload,
    plant_reference_payload,
    scenario_payload,
    storage_benchmarks_payload,
)
from .engines_router import router as engines_router

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"

app = FastAPI(title="GridIQ Botswana", version="1.4.0")
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.mount("/static", StaticFiles(directory=WEB), name="static")
app.include_router(engines_router)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self' https://unpkg.com https://cdn.jsdelivr.net 'unsafe-inline'; "
        "style-src 'self' https://unpkg.com 'unsafe-inline'; img-src 'self' data: https://*.tile.openstreetmap.org; "
        "connect-src 'self' https://overpass-api.de https://power.larc.nasa.gov https://api.worldpop.org; font-src 'self' data:; "
        "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    )
    return response


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "gridiq", "version": "1.4.0", "runtime": "fastapi"}


@app.get("/api/catalog")
def catalog():
    return catalog_payload()


@app.get("/api/baseline")
def baseline():
    return baseline_payload()


@app.get("/api/storage-benchmarks")
def storage_benchmarks():
    return storage_benchmarks_payload()


@app.get("/api/plants/reference")
def plant_reference():
    return plant_reference_payload()


@app.get("/api/neus")
def neus():
    return neus_payload()


@app.get("/api/census/districts")
def census_districts():
    return census_districts_payload()


@app.get("/api/demand/district-context")
def district_access_context():
    return district_access_context_payload()


@app.get("/api/osm/power")
async def osm_power(refresh: bool = False):
    cached = None if refresh else cache_read("osm_power.json", 6 * 3600)
    if cached:
        cached.setdefault("meta", {})["cache"] = "hit"
        if "evidence_summary" not in cached["meta"]:
            cached["meta"]["evidence_summary"] = geojson_evidence_summary(cached["data"])
        return cached

    q = '''[out:json][timeout:50];(way["power"~"line|minor_line"](-26.95,19.8,-17.7,29.5);nwr["power"="substation"](-26.95,19.8,-17.7,29.5);nwr["power"~"plant|generator"](-26.95,19.8,-17.7,29.5););out center geom tags;'''
    try:
        async with httpx.AsyncClient(timeout=60, headers={"User-Agent": "GridIQ-Botswana/1.4"}) as client:
            r = await client.post("https://overpass-api.de/api/interpreter", content=q)
            r.raise_for_status()
        fc = overpass_to_geojson(r.json())
        result = {
            "data": fc,
            "meta": {
                "source": "OpenStreetMap via Overpass API",
                "fetched_at": time.time(),
                "cache": "miss",
                "evidence_summary": geojson_evidence_summary(fc),
                "warning": "Mapped public infrastructure only. Ratings, impedance, loading and asset condition are not inferred.",
            },
        }
        cache_write("osm_power.json", result)
        return result
    except Exception as exc:
        stale = CACHE / "osm_power.json"
        if stale.exists():
            result = json.loads(stale.read_text(encoding="utf-8"))
            result.setdefault("meta", {})["cache"] = "stale"
            result["meta"]["evidence_summary"] = geojson_evidence_summary(result["data"])
            result["meta"]["warning"] = result["meta"].get("warning", "") + " Live refresh failed; serving stale cached result."
            return result
        raise HTTPException(status_code=503, detail=f"Live OSM power overlay unavailable: {exc}")


@app.get("/api/nasa/power")
async def nasa_power(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    days: int = Query(14, ge=3, le=60),
):
    # Cache per rounded site and requested horizon; these are source responses, not generated data.
    key = f"nasa_{lat:.4f}_{lon:.4f}_{days}.json".replace("-", "m").replace(".", "p")
    cached = cache_read(key, 12 * 3600)
    if cached:
        cached.setdefault("meta", {})["cache"] = "hit"
        return cached

    end = date.today() - timedelta(days=2)
    start = end - timedelta(days=days - 1)
    url = "https://power.larc.nasa.gov/api/temporal/daily/point"
    params = {
        "parameters": "ALLSKY_SFC_SW_DWN,T2M,WS10M",
        "community": "RE",
        "longitude": lon,
        "latitude": lat,
        "start": start.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
        "format": "JSON",
    }
    try:
        async with httpx.AsyncClient(timeout=35, headers={"User-Agent": "GridIQ-Botswana/1.4"}) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
        data = r.json()
        p = data.get("properties", {}).get("parameter", {})
        dates = sorted(set().union(*(x.keys() for x in p.values()))) if p else []
        rows = [
            {
                "date": d,
                "ghi": p.get("ALLSKY_SFC_SW_DWN", {}).get(d),
                "temp_c": p.get("T2M", {}).get(d),
                "wind_ms": p.get("WS10M", {}).get(d),
            }
            for d in dates
        ]
        result = {
            "rows": rows,
            "meta": {
                "source": "NASA POWER",
                "lat": lat,
                "lon": lon,
                "start": str(start),
                "end": str(end),
                "cache": "miss",
                "warning": "Planning-grade gridded meteorology; not a substitute for site measurement/bankability studies.",
            },
        }
        cache_write(key, result)
        return result
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"NASA POWER unavailable: {exc}")


@app.get("/api/engineering/benchmarks")
def engineering_benchmarks():
    return electrical_benchmarks_payload()


@app.get("/api/evidence/manifest")
def evidence_manifest():
    return evidence_manifest_payload()


@app.get("/api/audit")
def audit():
    return audit_payload()


@app.get("/api/engineering/enriched-network")
def engineering_enriched_network(case: str = Query("reference", pattern="^(conservative|reference|high_capacity)$")):
    cached = cache_read("osm_power.json", 365 * 24 * 3600)
    if not cached:
        raise HTTPException(status_code=409, detail="Load the OSM power layer first so GridIQ has observed geometry to enrich.")
    return enrich_power_geojson(cached["data"], case)


class TransferInput(BaseModel):
    voltage_kv: int = Field(220)
    case: str = Field("reference")
    transfer_mw: float = Field(100, ge=1, le=2000)
    source_lat: float = Field(..., ge=-90, le=90)
    source_lon: float = Field(..., ge=-180, le=180)
    sink_lat: float = Field(..., ge=-90, le=90)
    sink_lon: float = Field(..., ge=-180, le=180)


@app.post("/api/engineering/transfer")
def engineering_transfer(inp: TransferInput):
    cached = cache_read("osm_power.json", 365 * 24 * 3600)
    if not cached:
        raise HTTPException(status_code=409, detail="Load the OSM power layer first so GridIQ has observed geometry to analyse.")
    try:
        return benchmark_transfer_study(cached["data"], **inp.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/worldpop/population")
async def worldpop_population(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(10, ge=1, le=30),
    year: int = Query(2025, ge=2015, le=2030),
):
    key = f"worldpop_{lat:.4f}_{lon:.4f}_{radius_km:.1f}_{year}.json".replace("-", "m").replace(".", "p")
    cached = cache_read(key, 7 * 24 * 3600)
    if cached:
        cached.setdefault("meta", {})["cache"] = "hit"
        return cached
    # 32-vertex geodesic approximation of a radius around the selected point.
    import math
    coords = []
    for i in range(33):
        a = 2 * math.pi * i / 32
        dlat = radius_km * math.sin(a) / 111.32
        dlon = radius_km * math.cos(a) / max(1e-6, 111.32 * math.cos(math.radians(lat)))
        coords.append([lon + dlon, lat + dlat])
    payload = {"geojson": {"type": "Polygon", "coordinates": [coords]}, "year": year, "resolution": "1km"}
    try:
        async with httpx.AsyncClient(timeout=35, headers={"User-Agent": "GridIQ-Botswana/1.4"}) as client:
            submitted = await client.post("https://api.worldpop.org/v2/population", json=payload)
            submitted.raise_for_status()
            task_id = submitted.json().get("task_id")
            if not task_id:
                raise RuntimeError("WorldPop did not return a task id")
            result = None
            for _ in range(20):
                await __import__("asyncio").sleep(0.8)
                r = await client.get(f"https://api.worldpop.org/v2/tasks/{task_id}")
                r.raise_for_status()
                result = r.json()
                if result.get("status") in {"success", "failure"}:
                    break
            if not result or result.get("status") != "success":
                raise RuntimeError((result or {}).get("error") or "WorldPop task timed out")
        total = result.get("result", {}).get("total_population")
        out = {"total_population": total, "lat": lat, "lon": lon, "radius_km": radius_km, "year": year, "meta": {"source": "WorldPop API v2", "resolution": "1km", "cache": "miss", "evidence_class": "modelled_population_dataset", "warning": "Population is a spatial demand driver, not measured electrical load."}}
        cache_write(key, out)
        return out
    except Exception as exc:
        stale = CACHE / key
        if stale.exists():
            out = json.loads(stale.read_text(encoding="utf-8"))
            out.setdefault("meta", {})["cache"] = "stale"
            return out
        raise HTTPException(status_code=503, detail=f"WorldPop unavailable: {exc}")


class ScenarioInput(BaseModel):
    solar_build_mw: float = Field(0, ge=0, le=3000)
    storage_mw: float = Field(0, ge=0, le=2000)
    storage_mwh: float = Field(0, ge=0, le=12000)
    peak_demand_mw: float = Field(610, ge=50, le=3000)
    operating_capacity_mw: float = Field(459, ge=0, le=3000)
    reserve_requirement_mw: float = Field(88, ge=0, le=1000)
    roundtrip_efficiency: float = Field(0.85, ge=0.5, le=0.99)
    storage_cost_usd_per_kwh: float = Field(192, ge=50, le=2000)


@app.post("/api/scenario")
def scenario(inp: ScenarioInput):
    return scenario_payload(inp.model_dump())


@app.exception_handler(Exception)
async def unhandled(request, exc):
    return JSONResponse(status_code=500, content={"detail": "Internal error", "type": type(exc).__name__})
