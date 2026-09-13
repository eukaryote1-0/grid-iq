from __future__ import annotations

import csv
import io
import json
import re
import time
from urllib.parse import urljoin
from datetime import date, timedelta
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from engines.e1_opt import (
    capacity_expansion_screen,
    representative_day_capacity_expansion_screen,
    spatialize_e1_plan,
)
from engines.e2_flow.reconciliation import loss_reconciliation_payload
from engines.e3_criticality import structural_criticality_payload
from engines.e4_siting import villagefit_screen
from engines.payloads import (
    agriculture_district_payload,
    agriculture_payload,
    biogas_benchmarks_payload,
    biomass_residue_benchmarks_payload,
    bpc_grid_public_payload,
    bpc_losses_payload,
    community_benchmarks_payload,
    gep_reference_payload,
    load_profile_benchmarks_payload,
    renewable_benchmarks_payload,
    rural_electrification_payload,
    sapp_transfer_limits_payload,
    transformer_benchmarks_payload,
)
from engines.supply import historical_supply_metrics_payload

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
    benchmark_multi_injection_study,
    overpass_to_geojson,
    neus_payload,
    plant_reference_payload,
    scenario_payload,
    storage_benchmarks_payload,
)
from .engines_router import router as engines_router

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"

app = FastAPI(title="GridIQ Botswana", version="1.7.0")
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
        "connect-src 'self' https://overpass-api.de https://power.larc.nasa.gov https://api.worldpop.org https://energydata.info https://storage.googleapis.com; font-src 'self' data:; "
        "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    )
    return response


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "gridiq", "version": "1.7.0", "runtime": "fastapi"}


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


@app.get("/api/supply/metrics")
def supply_metrics():
    return historical_supply_metrics_payload()


@app.get("/api/losses/bpc")
def bpc_losses():
    return bpc_losses_payload()


@app.get("/api/rural")
def rural_electrification():
    return rural_electrification_payload()


@app.get("/api/agriculture")
def agriculture():
    return agriculture_payload()


@app.get("/api/agriculture/district-2015")
def agriculture_district_2015():
    return agriculture_district_payload()


@app.get("/api/biogas-benchmarks")
def biogas_benchmarks():
    return biogas_benchmarks_payload()


@app.get("/api/bpc/grid-public")
def bpc_grid_public():
    return bpc_grid_public_payload()


@app.get("/api/gep/reference")
def gep_reference():
    return gep_reference_payload()


@app.get("/api/benchmarks/transformers")
def transformer_benchmarks():
    return transformer_benchmarks_payload()


@app.get("/api/benchmarks/load-profile-sources")
def load_profile_benchmarks():
    return load_profile_benchmarks_payload()


@app.get("/api/benchmarks/biomass-residues")
def biomass_residue_benchmarks():
    return biomass_residue_benchmarks_payload()


@app.get("/api/benchmarks/gap-resolution")
def benchmark_gap_resolution():
    return json.loads((ROOT / "data" / "benchmarks" / "gap_resolution.json").read_text(encoding="utf-8"))


@app.get("/api/gis/boundaries-benchmark")
async def benchmark_boundaries(level: int = Query(1, ge=0, le=2)):
    """Open benchmark administrative geometry, never relabelled as Statistics Botswana geometry."""
    if level not in {0,1,2}:
        raise HTTPException(status_code=422, detail="level must be 0, 1 or 2")
    key=f"boundary_benchmark_adm{level}.json"
    cached=cache_read(key, 30*24*3600)
    if cached:
        return cached
    url=f"https://storage.googleapis.com/location-grid-gis-layers/bwa_admin{level}.geojson"
    try:
        async with httpx.AsyncClient(timeout=35, headers={"User-Agent":"GridIQ-Botswana/1.7"}) as client:
            r=await client.get(url); r.raise_for_status(); body=r.json()
        out={"geojson":body,"meta":{"source":"Location Grid Project / public Botswana administrative layer","source_url":url,"evidence_class":"external_open_geometry_benchmark","warning":"This is a non-authoritative spatial substitute for display/spatial joins. It must not be relabelled as the Statistics Botswana official sub-district shapefile."}}
        cache_write(key,out); return out
    except Exception as exc:
        stale=CACHE/key
        if stale.exists():
            out=json.loads(stale.read_text(encoding="utf-8")); out.setdefault("meta",{})["cache"]="stale"; out["meta"]["refresh_error"]=str(exc); return out
        raise HTTPException(status_code=503,detail=f"Benchmark boundary layer unavailable: {exc}")


@app.get("/api/dre/reference")
def dre_reference():
    return json.loads((ROOT / "data" / "reference" / "dre_botswana_dataset.json").read_text(encoding="utf-8"))


@app.get("/api/dre/settlements")
async def dre_settlements(
    query: str = Query("", max_length=120),
    limit: int = Query(20, ge=1, le=100),
):
    """Search the World Bank DRE Atlas Botswana settlement clusters.

    This returns modelled settlement-planning evidence, not a BPC connection-status register.
    """
    rid = "42a50c1b-7920-4e2c-a465-e15f1f9d8711"
    q = query.strip().replace("'", "''")
    fields = 'geohash,lat,lon,village_name,admin_cgaz_1,admin_cgaz_2,population,num_buildings,main_road_access,dist_main_road_km,distance_to_existing_transmission_lines,distance_to_planned_transmission_lines,has_nightlight,pv_value,crop_types,ag_area,ag_value,ag_yield,num_connections,demand,demand_connection'
    where = f"WHERE lower(village_name) LIKE lower('%{q}%')" if q else ''
    sql = f'SELECT {fields} FROM "{rid}" {where} ORDER BY population DESC NULLS LAST LIMIT {int(limit)}'
    try:
        async with httpx.AsyncClient(timeout=35, headers={"User-Agent":"GridIQ-Botswana/1.7"}) as client:
            r=await client.get("https://energydata.info/en/api/3/action/datastore_search_sql",params={"sql":sql}); r.raise_for_status()
        body=r.json(); records=body.get("result",{}).get("records",[]) if body.get("success") else []
        return {"records":records,"count":len(records),"query":query,"meta":{"source":"World Bank Botswana DRE Atlas","resource_id":rid,"license":"CC BY 4.0","evidence_class":"modelled_open_settlement_planning_data","warning":"Settlement clusters and indicators are planning/modelled evidence, not a verified current BPC unconnected-village list."}}
    except Exception as exc:
        raise HTTPException(status_code=503,detail=f"DRE Atlas DataStore unavailable: {exc}")


@app.get("/api/dre/candidate-register")
async def dre_candidate_register(limit: int = Query(100, ge=10, le=500)):
    """Derived settlement-priority register from World Bank DRE indicators.

    This is intentionally not called an unconnected-village register. It ranks DRE
    settlement clusters using their own population, mapped transmission distance and
    night-light indicator so the absence of a current BPC connection register does not
    block planning screens.
    """
    rid="42a50c1b-7920-4e2c-a465-e15f1f9d8711"
    fields='geohash,lat,lon,village_name,admin_cgaz_1,admin_cgaz_2,population,distance_to_existing_transmission_lines,has_nightlight,pv_value,num_connections,demand,demand_connection'
    sql=f'SELECT {fields} FROM "{rid}" ORDER BY population DESC NULLS LAST LIMIT 500'
    try:
        async with httpx.AsyncClient(timeout=35,headers={"User-Agent":"GridIQ-Botswana/1.7"}) as client:
            r=await client.get("https://energydata.info/en/api/3/action/datastore_search_sql",params={"sql":sql}); r.raise_for_status()
        body=r.json(); rows=body.get("result",{}).get("records",[]) if body.get("success") else []
        def fnum(v):
            try: return float(v)
            except Exception: return None
        parsed=[]
        pops=[fnum(x.get("population")) for x in rows]; pops=[x for x in pops if x is not None and x>=0]
        dists=[fnum(x.get("distance_to_existing_transmission_lines")) for x in rows]; dists=[x for x in dists if x is not None and x>=0]
        pmax=max(pops) if pops else 1.0; dmax=max(dists) if dists else 1.0
        for x in rows:
            pop=fnum(x.get("population")); dist=fnum(x.get("distance_to_existing_transmission_lines"))
            nl=str(x.get("has_nightlight","")).strip().lower()
            no_light=nl in {"false","0","no","n","none",""}
            # Explainable screening score only, not connection probability.
            score=(0.45*((pop or 0)/pmax)+0.40*((dist or 0)/dmax)+0.15*(1.0 if no_light else 0.0))*100.0
            parsed.append({**x,"derived_priority_score":round(score,2),"derived_no_nightlight_flag":no_light})
        parsed.sort(key=lambda x:x["derived_priority_score"],reverse=True)
        return {"records":parsed[:limit],"count":min(limit,len(parsed)),"meta":{"source":"World Bank Botswana DRE Atlas","resource_id":rid,"evidence_class":"derived_from_modelled_open_settlement_indicators","formula":"45% population relative to retrieved candidates + 40% transmission-distance relative to retrieved candidates + 15% no-nightlight indicator","warning":"Priority score is not a BPC connection-status probability and does not assert that a settlement is unconnected."}}
    except Exception as exc:
        raise HTTPException(status_code=503,detail=f"DRE candidate register unavailable: {exc}")


@app.get("/api/dre/point")
async def dre_point(lat: float=Query(...,ge=-90,le=90), lon: float=Query(...,ge=-180,le=180)):
    rid="42a50c1b-7920-4e2c-a465-e15f1f9d8711"
    fields='geohash,lat,lon,village_name,admin_cgaz_1,admin_cgaz_2,population,num_buildings,main_road_access,dist_main_road_km,distance_to_existing_transmission_lines,distance_to_planned_transmission_lines,has_nightlight,pv_value,crop_types,ag_area,ag_value,ag_yield,num_connections,demand,demand_connection'
    sql=(f'SELECT {fields} FROM "{rid}" ORDER BY POWER(CAST(lat AS double precision)-({float(lat)}),2)+POWER(CAST(lon AS double precision)-({float(lon)}),2) LIMIT 1')
    try:
        async with httpx.AsyncClient(timeout=35,headers={"User-Agent":"GridIQ-Botswana/1.7"}) as client:
            r=await client.get("https://energydata.info/en/api/3/action/datastore_search_sql",params={"sql":sql});r.raise_for_status()
        body=r.json(); rec=body.get("result",{}).get("records",[]) if body.get("success") else []
        if not rec: raise RuntimeError("DRE DataStore returned no settlement")
        return {"record":rec[0],"query":{"lat":lat,"lon":lon},"meta":{"source":"World Bank Botswana DRE Atlas","resource_id":rid,"license":"CC BY 4.0","evidence_class":"modelled_open_settlement_planning_data","warning":"Nearest modelled settlement cluster, not a BPC connection-status determination."}}
    except Exception as exc:
        raise HTTPException(status_code=503,detail=f"DRE Atlas DataStore unavailable: {exc}")


@app.get("/api/gep/point")
async def gep_point(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
):
    """Nearest World Bank GEP Climate-model input cell to an explicit point.

    GEP is public/modelled planning data. Values returned here are never relabelled as
    BPC measurements. The query is bounded to Botswana and cached.
    """
    key = f"gep_{lat:.4f}_{lon:.4f}.json".replace("-", "m").replace(".", "p")
    cached = cache_read(key, 14 * 24 * 3600)
    if cached:
        cached.setdefault("meta", {})["cache"] = "hit"
        return cached
    rid = "3d6620fa-f9b7-46b3-b886-18b4072c38a8"
    # CKAN DataStore SQL: nearest cell by squared geographic distance.
    sql = (
        f'SELECT * FROM "{rid}" '
        f'ORDER BY POWER(CAST("X_deg" AS double precision)-({float(lon)}),2) + '
        f'POWER(CAST("Y_deg" AS double precision)-({float(lat)}),2) LIMIT 1'
    )
    try:
        async with httpx.AsyncClient(timeout=35, headers={"User-Agent": "GridIQ-Botswana/1.7"}) as client:
            r = await client.get("https://energydata.info/en/api/3/action/datastore_search_sql", params={"sql": sql})
            r.raise_for_status()
        body = r.json()
        records = body.get("result", {}).get("records", []) if body.get("success") else []
        if not records:
            raise RuntimeError("GEP DataStore returned no record")
        record = records[0]
        out = {
            "record": record,
            "query": {"lat": lat, "lon": lon},
            "meta": {
                "source": "World Bank Global Electrification Platform (Botswana) - Climate Energy Modeling Parameters",
                "resource_id": rid,
                "license": "CC BY 4.0",
                "evidence_class": "modelled_open_planning_input",
                "cache": "miss",
                "warning": "GEP is a least-cost electrification planning dataset derived from public inputs. It is not measured BPC demand, line capacity, or site-bankability evidence.",
            },
        }
        cache_write(key, out)
        return out
    except Exception as exc:
        stale = CACHE / key
        if stale.exists():
            out = json.loads(stale.read_text(encoding="utf-8")); out.setdefault("meta", {})["cache"] = "stale"; return out
        raise HTTPException(status_code=503, detail=f"World Bank GEP DataStore unavailable: {exc}")


@app.get("/api/renewable-benchmarks")
def renewable_benchmarks():
    return renewable_benchmarks_payload()


@app.get("/api/community-benchmarks")
def community_benchmarks():
    return community_benchmarks_payload()


@app.get("/api/sapp/transfer-limits")
def sapp_transfer_limits():
    return sapp_transfer_limits_payload()


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
        async with httpx.AsyncClient(timeout=60, headers={"User-Agent": "GridIQ-Botswana/1.7"}) as client:
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
        async with httpx.AsyncClient(timeout=35, headers={"User-Agent": "GridIQ-Botswana/1.7"}) as client:
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



def _parse_hour_from_timestamp(value: str) -> int | None:
    text = (value or "").strip()
    if not text:
        return None
    m = re.search(r"(?:^|[ T])(\d{1,2}):(\d{2})(?::\d{2})?\s*(AM|PM)?", text, re.I)
    if not m:
        return None
    hour = int(m.group(1)); ap = (m.group(3) or "").upper()
    if ap == "PM" and hour != 12:
        hour += 12
    if ap == "AM" and hour == 12:
        hour = 0
    return hour if 0 <= hour <= 23 else None


def _to_float(value) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if text in {"", "-", "--", "NA", "N/A", "null", "None"}:
        return None
    try:
        v = float(text)
        return v if math.isfinite(v) else None
    except Exception:
        return None


async def _eskom_hourly_shape() -> dict:
    key = "eskom_hourly_shape.json"
    cached = cache_read(key, 6 * 3600)
    if cached:
        cached.setdefault("meta", {})["cache"] = "hit"
        return cached
    page = "https://www.eskom.co.za/dataportal/demand-side/system-hourly-demand-and-available-capacity/"
    try:
        async with httpx.AsyncClient(timeout=35, follow_redirects=True, headers={"User-Agent":"GridIQ-Botswana/1.6"}) as client:
            page_resp = await client.get(page)
            page_resp.raise_for_status()
            html = page_resp.text
            hrefs = re.findall(r"href=[\"']([^\"']+\.csv(?:\?[^\"']*)?)[\"']", html, re.I)
            hrefs = sorted(hrefs, key=lambda x: ("system_hourly_demand" not in x.lower(), x))
            if not hrefs:
                raise RuntimeError("Eskom page exposed no CSV download link")
            csv_url = urljoin(page, hrefs[0])
            rr = await client.get(csv_url)
            rr.raise_for_status()
            text = rr.text
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
        if not rows:
            raise RuntimeError("Eskom CSV contained no rows")
        cols = list(rows[0].keys())
        time_col = next((c for c in cols if c and "date time hour beginning" in c.lower()), None)
        if time_col is None:
            time_col = next((c for c in cols if c and "time" in c.lower() and "date" in c.lower()), None)
        demand_col = None
        for pref in ("rsa contracted demand", "residual demand"):
            demand_col = next((c for c in cols if c and c.strip().lower() == pref), None)
            if demand_col:
                break
        if demand_col is None:
            demand_col = next((c for c in cols if c and "demand" in c.lower() and "forecast" not in c.lower()), None)
        if not time_col or not demand_col:
            raise RuntimeError(f"Could not identify timestamp/demand columns. Columns={cols[:20]}")
        buckets = {h: [] for h in range(24)}
        for row in rows:
            h = _parse_hour_from_timestamp(row.get(time_col, ""))
            v = _to_float(row.get(demand_col))
            if h is not None and v is not None and v > 0:
                buckets[h].append(v)
        means = [sum(buckets[h]) / len(buckets[h]) if buckets[h] else None for h in range(24)]
        if any(v is None for v in means):
            raise RuntimeError("Eskom CSV did not provide complete 24-hour coverage")
        peak = max(means)
        shape = [float(v) / peak for v in means]
        out = {
            "shape_pu_peak": [round(v, 6) for v in shape],
            "mean_mw_source": [round(float(v), 3) for v in means],
            "source_rows": len(rows),
            "series_column": demand_col,
            "meta": {
                "source": "Eskom Data Portal",
                "page_url": page,
                "csv_url": csv_url,
                "evidence_class": "regional_official_hourly_demand_benchmark",
                "cache": "miss",
                "warning": "South African system demand shape only. GridIQ discards the South African magnitude and scales the normalized shape to published Botswana anchors; it is not measured Botswana demand."
            }
        }
        cache_write(key, out)
        return out
    except Exception as exc:
        stale = CACHE / key
        if stale.exists():
            out = json.loads(stale.read_text(encoding="utf-8"))
            out.setdefault("meta", {})["cache"] = "stale"
            out["meta"]["refresh_error"] = str(exc)
            return out
        raise HTTPException(status_code=503, detail=f"Eskom hourly benchmark unavailable: {exc}")


@app.get("/api/benchmarks/eskom-hourly-shape")
async def eskom_hourly_shape():
    return await _eskom_hourly_shape()


@app.get("/api/nasa/hourly-solar-shape")
async def nasa_hourly_solar_shape(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    days: int = Query(14, ge=7, le=31),
):
    key = f"nasa_hourly_shape_{lat:.4f}_{lon:.4f}_{days}.json".replace("-", "m").replace(".", "p")
    cached = cache_read(key, 12 * 3600)
    if cached:
        cached.setdefault("meta", {})["cache"] = "hit"
        return cached
    end = date.today() - timedelta(days=2)
    start = end - timedelta(days=days - 1)
    params = {
        "parameters": "ALLSKY_SFC_SW_DWN",
        "community": "RE",
        "longitude": lon,
        "latitude": lat,
        "start": start.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
        "format": "JSON",
    }
    try:
        async with httpx.AsyncClient(timeout=40, headers={"User-Agent":"GridIQ-Botswana/1.6"}) as client:
            r = await client.get("https://power.larc.nasa.gov/api/temporal/hourly/point", params=params)
            r.raise_for_status()
            data = r.json()
        vals = data.get("properties", {}).get("parameter", {}).get("ALLSKY_SFC_SW_DWN", {})
        buckets = {h: [] for h in range(24)}
        for k, v in vals.items():
            fv = _to_float(v)
            if fv is None or fv < 0:
                continue
            try:
                h = int(str(k)[-2:])
            except Exception:
                continue
            if 0 <= h <= 23:
                buckets[h].append(fv)
        means = [sum(buckets[h]) / len(buckets[h]) if buckets[h] else 0.0 for h in range(24)]
        m = max(means)
        if m <= 0:
            raise RuntimeError("NASA hourly series contains no usable solar radiation")
        temporal = [v / m for v in means]
        target_cf = float(renewable_benchmarks_payload()["botswana_resource_screening"]["solar_pvout_kwh_per_kwp_year"]) / 8760.0
        cf = temporal[:]
        for _ in range(4):
            avg = sum(cf) / 24.0
            if avg <= 0:
                break
            fac = target_cf / avg
            cf = [min(1.0, max(0.0, x * fac)) for x in cf]
        out = {
            "solar_cf_pu": [round(x, 6) for x in cf],
            "nasa_hourly_mean": [round(x, 4) for x in means],
            "meta": {
                "source": "NASA POWER hourly ALLSKY_SFC_SW_DWN + Botswana PVOUT benchmark calibration",
                "lat": lat,
                "lon": lon,
                "days": days,
                "target_annual_capacity_factor": round(target_cf, 6),
                "evidence_class": "derived_open_resource_benchmark",
                "cache": "miss",
                "warning": "Temporal shape comes from NASA gridded irradiance and annual mean is calibrated to a published Botswana PVOUT screening benchmark. It is not measured plant generation."
            }
        }
        cache_write(key, out)
        return out
    except Exception as exc:
        stale = CACHE / key
        if stale.exists():
            out = json.loads(stale.read_text(encoding="utf-8"))
            out.setdefault("meta", {})["cache"] = "stale"
            out["meta"]["refresh_error"] = str(exc)
            return out
        raise HTTPException(status_code=503, detail=f"NASA hourly solar benchmark unavailable: {exc}")


class RepresentativeE1Input(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    source_year: int = 2025
    peak_demand_mw: float = Field(610, ge=50, le=3000)
    import_capacity_limit_mw: float = Field(190, ge=0, le=2000)
    import_energy_price_usd_per_mwh: float = Field(100, ge=0, le=2000)
    max_solar_mw: float = Field(2500, ge=0, le=10000)
    max_bess_mw: float = Field(1000, ge=0, le=5000)
    bess_duration_h: float = Field(4, ge=1, le=12)
    real_discount_rate: float = Field(0.08, ge=0, le=0.30)
    nasa_days: int = Field(14, ge=7, le=31)


@app.post("/api/e1/representative-day")
async def e1_representative_day(inp: RepresentativeE1Input):
    demand = await _eskom_hourly_shape()
    solar = await nasa_hourly_solar_shape(inp.lat, inp.lon, inp.nasa_days)
    try:
        return representative_day_capacity_expansion_screen(
            inp.model_dump(),
            demand["shape_pu_peak"],
            solar["solar_cf_pu"],
            demand_source_meta=demand.get("meta"),
            solar_source_meta=solar.get("meta"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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


class OptimizeInput(BaseModel):
    source_year: int = 2025
    import_capacity_limit_mw: float = Field(190, ge=0, le=2000)
    import_energy_price_usd_per_mwh: float = Field(100, ge=0, le=2000)
    max_solar_mw: float = Field(2500, ge=0, le=10000)
    max_wind_mw: float = Field(0, ge=0, le=10000)
    max_bess_mw: float = Field(1000, ge=0, le=5000)
    bess_duration_h: float = Field(4, ge=1, le=12)
    real_discount_rate: float = Field(0.08, ge=0, le=0.30)


@app.post("/api/e1/optimize")
def e1_optimize(inp: OptimizeInput):
    try:
        return capacity_expansion_screen(inp.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class E1SpatialInput(BaseModel):
    site_name: str = Field("Selected candidate")
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    grid_cost_case: str = Field("reference")
    source_year: int = 2025
    import_capacity_limit_mw: float = Field(190, ge=0, le=2000)
    import_energy_price_usd_per_mwh: float = Field(100, ge=0, le=2000)
    max_solar_mw: float = Field(2500, ge=0, le=10000)
    max_wind_mw: float = Field(0, ge=0, le=10000)
    max_bess_mw: float = Field(1000, ge=0, le=5000)
    bess_duration_h: float = Field(4, ge=1, le=12)
    real_discount_rate: float = Field(0.08, ge=0, le=0.30)
    resource_evidence: dict | None = None


@app.post("/api/e1/site-screen")
def e1_site_screen(inp: E1SpatialInput):
    cached = cache_read("osm_power.json", 365 * 24 * 3600)
    d = inp.model_dump()
    e1_keys = {k:d[k] for k in ("source_year","import_capacity_limit_mw","import_energy_price_usd_per_mwh","max_solar_mw","max_wind_mw","max_bess_mw","bess_duration_h","real_discount_rate")}
    try:
        base = capacity_expansion_screen(e1_keys)
        return spatialize_e1_plan(
            base, site_name=inp.site_name, lat=inp.lat, lon=inp.lon,
            osm_fc=cached["data"] if cached else None, grid_cost_case=inp.grid_cost_case,
            resource_evidence=inp.resource_evidence,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class LossReconcileInput(BaseModel):
    modelled_loss_gwh: float | None = Field(None, ge=0)
    model_scope: str = Field("transmission")


@app.post("/api/e2/loss-reconciliation")
def e2_loss_reconciliation(inp: LossReconcileInput):
    return loss_reconciliation_payload(inp.modelled_loss_gwh, inp.model_scope)


@app.get("/api/e3/criticality")
def e3_criticality(voltage_kv: int | None = Query(None, ge=1, le=1000), limit: int = Query(30, ge=1, le=200)):
    cached = cache_read("osm_power.json", 365 * 24 * 3600)
    if not cached:
        raise HTTPException(status_code=409, detail="Load the OSM power layer first so E3 has observed mapped topology to analyse.")
    return structural_criticality_payload(cached["data"], voltage_kv=voltage_kv, limit=limit)


class VillageFitInput(BaseModel):
    village_id: str = "ukhwi"
    custom_name: str | None = None
    custom_lat: float | None = Field(None, ge=-90, le=90)
    custom_lon: float | None = Field(None, ge=-180, le=180)
    custom_population: float | None = Field(None, gt=0)
    grid_cost_case: str = Field("reference")
    annual_kwh_per_household: float | None = Field(None, gt=0)
    peak_kw_per_household: float | None = Field(None, gt=0)
    evening_energy_share_pct: float | None = Field(None, ge=0, le=100)
    use_live_nasa: bool = True
    use_live_gep: bool = True
    nasa_days: int = Field(30, ge=7, le=60)
    collectable_cattle_manure_kg_per_day: float | None = Field(None, gt=0)
    biogas_yield_case: str = Field("reference")


@app.post("/api/e4/villagefit")
async def e4_villagefit(inp: VillageFitInput):
    rural = rural_electrification_payload()
    custom = None
    if inp.custom_name is not None or inp.custom_lat is not None or inp.custom_lon is not None or inp.custom_population is not None:
        if None in (inp.custom_name, inp.custom_lat, inp.custom_lon, inp.custom_population):
            raise HTTPException(status_code=422, detail="custom_name, custom_lat, custom_lon and custom_population must be supplied together")
        custom = {"id":"custom","name":inp.custom_name,"population_2022":inp.custom_population,"lat":inp.custom_lat,"lon":inp.custom_lon,"source_status":"explicit settlement input"}
        village = custom
    else:
        village = next((v for v in rural["pilot_villages"] if v["id"] == inp.village_id), None)
        if not village:
            raise HTTPException(status_code=422, detail="Unknown verified pilot village")
    cached = cache_read("osm_power.json", 365 * 24 * 3600)
    nasa_rows = None
    nasa_meta = None
    if inp.use_live_nasa:
        try:
            nr = await nasa_power(lat=float(village["lat"]), lon=float(village["lon"]), days=inp.nasa_days)
            nasa_rows = nr.get("rows", [])
            nasa_meta = nr.get("meta")
        except HTTPException as exc:
            nasa_meta = {"status": "unavailable", "detail": str(exc.detail)}
    gep_data = None
    if inp.use_live_gep:
        try:
            gep_data = await gep_point(lat=float(village["lat"]), lon=float(village["lon"]))
        except HTTPException:
            gep_data = None
    try:
        out = villagefit_screen(
            inp.village_id,
            osm_fc=cached["data"] if cached else None,
            nasa_rows=nasa_rows,
            grid_cost_case=inp.grid_cost_case,
            annual_kwh_per_household=inp.annual_kwh_per_household,
            peak_kw_per_household=inp.peak_kw_per_household,
            evening_energy_share_pct=inp.evening_energy_share_pct,
            village_override=custom,
            gep_point=gep_data,
            collectable_cattle_manure_kg_per_day=inp.collectable_cattle_manure_kg_per_day,
            biogas_yield_case=inp.biogas_yield_case,
        )
        out["nasa_meta"] = nasa_meta
        return out
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class InjectionPoint(BaseModel):
    name: str | None = None
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    mw: float = Field(..., ge=-5000, le=5000)


class SystemBenchmarkInput(BaseModel):
    voltage_kv: int = Field(220)
    case: str = Field("reference")
    injections: list[InjectionPoint]


@app.post("/api/e2/system-benchmark")
def e2_system_benchmark(inp: SystemBenchmarkInput):
    cached = cache_read("osm_power.json", 365 * 24 * 3600)
    if not cached:
        raise HTTPException(status_code=409, detail="Load the OSM power layer first so the benchmark system model has observed mapped geometry.")
    try:
        return benchmark_multi_injection_study(cached["data"], voltage_kv=inp.voltage_kv, case=inp.case, injections=[x.model_dump() for x in inp.injections])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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
        async with httpx.AsyncClient(timeout=35, headers={"User-Agent": "GridIQ-Botswana/1.7"}) as client:
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
