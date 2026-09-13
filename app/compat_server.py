"""Dependency-free compatibility runtime for GridIQ.

Used only if the FastAPI environment cannot be installed. It preserves the same
browser/API contract so a newer Python release or missing compiler never blocks
the demo. FastAPI remains the preferred runtime.
"""
from __future__ import annotations

import json
import mimetypes
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from app.logic import (CACHE, audit_payload, baseline_payload, benchmark_transfer_study, benchmark_multi_injection_study, catalog_payload, cache_read, cache_write, census_districts_payload, district_access_context_payload, electrical_benchmarks_payload, enrich_power_geojson, evidence_manifest_payload, geojson_evidence_summary, neus_payload, overpass_to_geojson, plant_reference_payload, scenario_payload, storage_benchmarks_payload)
from engines.e1_opt import capacity_expansion_screen, spatialize_e1_plan
from engines.e3_criticality import structural_criticality_payload
from engines.e4_siting import villagefit_screen
from engines.e2_flow.reconciliation import loss_reconciliation_payload
from engines.e2_flow.loss_reconciliation import loss_reconciliation as e2_cross_check
from engines.payloads import (agriculture_payload, agriculture_district_payload, biogas_benchmarks_payload, bpc_grid_public_payload, bpc_losses_payload, community_benchmarks_payload, gep_reference_payload, renewable_benchmarks_payload, rural_electrification_payload, sapp_transfer_limits_payload)
from engines.supply import historical_supply_metrics_payload

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self' https://unpkg.com https://cdn.jsdelivr.net 'unsafe-inline'; "
        "style-src 'self' https://unpkg.com 'unsafe-inline'; img-src 'self' data: https://*.tile.openstreetmap.org; "
        "connect-src 'self' https://overpass-api.de https://power.larc.nasa.gov https://api.worldpop.org https://energydata.info https://storage.googleapis.com; font-src 'self' data:; "
        "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    ),
}


def _json_request(url: str, *, data: bytes | None = None, timeout: int = 45) -> dict:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "GridIQ-Botswana/1.7"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


class Handler(BaseHTTPRequestHandler):
    server_version = "GridIQCompat/1.7"

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}", flush=True)

    def _headers(self, status=200, content_type="application/json; charset=utf-8", length=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        if length is not None:
            self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        for k, v in SECURITY_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()

    def _json(self, payload, status=200):
        body = json.dumps(payload).encode()
        self._headers(status, length=len(body))
        self.wfile.write(body)

    def _error(self, status, detail):
        self._json({"detail": detail}, status)

    def _static(self, rel: str):
        target = (WEB / rel).resolve()
        if WEB.resolve() not in target.parents and target != WEB.resolve():
            return self._error(403, "Forbidden")
        if not target.is_file():
            return self._error(404, "Not found")
        body = target.read_bytes()
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self._headers(200, ctype, len(body))
        self.wfile.write(body)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        path = u.path
        qs = urllib.parse.parse_qs(u.query)
        if path == "/":
            return self._static("index.html")
        if path.startswith("/static/"):
            return self._static(path.removeprefix("/static/"))
        if path == "/api/health":
            return self._json({"status": "ok", "service": "gridiq", "version": "1.7.0", "runtime": "compat-stdlib"})
        if path == "/api/catalog":
            return self._json(catalog_payload())
        if path == "/api/baseline":
            return self._json(baseline_payload())
        if path == "/api/storage-benchmarks":
            return self._json(storage_benchmarks_payload())
        if path == "/api/plants/reference":
            return self._json(plant_reference_payload())
        if path == "/api/neus":
            return self._json(neus_payload())
        if path == "/api/census/districts":
            return self._json(census_districts_payload())
        if path == "/api/demand/district-context":
            return self._json(district_access_context_payload())
        if path == "/api/supply/metrics":
            return self._json(historical_supply_metrics_payload())
        if path == "/api/losses/bpc":
            return self._json(bpc_losses_payload())
        if path == "/api/rural":
            return self._json(rural_electrification_payload())
        if path == "/api/agriculture":
            return self._json(agriculture_payload())
        if path == "/api/agriculture/district-2015":
            return self._json(agriculture_district_payload())
        if path == "/api/biogas-benchmarks":
            return self._json(biogas_benchmarks_payload())
        if path == "/api/benchmarks/gap-resolution":
            return self._json(json.loads((ROOT / "data" / "benchmarks" / "gap_resolution.json").read_text(encoding="utf-8")))
        if path == "/api/gis/boundaries-benchmark":
            try:
                level=int(qs.get("level",[1])[0])
                if level not in (0,1,2): raise ValueError
            except Exception:
                return self._error(422,"level must be 0, 1 or 2")
            key=f"boundary_benchmark_adm{level}.json"; cached=cache_read(key,30*24*3600)
            if cached: return self._json(cached)
            url=f"https://storage.googleapis.com/location-grid-gis-layers/bwa_admin{level}.geojson"
            try:
                req=urllib.request.Request(url,headers={"User-Agent":"GridIQ-Botswana/1.7"})
                with urllib.request.urlopen(req,timeout=35) as r: body=json.loads(r.read().decode("utf-8"))
                out={"geojson":body,"meta":{"source":"Location Grid Project / public Botswana administrative layer","source_url":url,"evidence_class":"external_open_geometry_benchmark","warning":"Non-authoritative substitute for display/spatial joins; not Statistics Botswana official geometry."}}
                cache_write(key,out); return self._json(out)
            except Exception as exc:
                return self._error(503,f"Benchmark boundary layer unavailable: {exc}")
        if path == "/api/bpc/grid-public":
            return self._json(bpc_grid_public_payload())
        if path == "/api/gep/reference":
            return self._json(gep_reference_payload())
        if path == "/api/dre/reference":
            return self._json(json.loads((ROOT / "data" / "reference" / "dre_botswana_dataset.json").read_text(encoding="utf-8")))
        if path == "/api/dre/settlements":
            query=qs.get("query",[""])[0].strip().replace("'","''"); limit=max(1,min(100,int(qs.get("limit",[20])[0])))
            rid="42a50c1b-7920-4e2c-a465-e15f1f9d8711"; fields='geohash,lat,lon,village_name,admin_cgaz_1,admin_cgaz_2,population,num_buildings,main_road_access,dist_main_road_km,distance_to_existing_transmission_lines,distance_to_planned_transmission_lines,has_nightlight,pv_value,crop_types,ag_area,ag_value,ag_yield,num_connections,demand,demand_connection'
            where=f"WHERE lower(village_name) LIKE lower('%{query}%')" if query else ""; sql=f'SELECT {fields} FROM "{rid}" {where} ORDER BY population DESC NULLS LAST LIMIT {limit}'
            try:
                body=_json_request("https://energydata.info/en/api/3/action/datastore_search_sql?"+urllib.parse.urlencode({"sql":sql}),timeout=35); rec=body.get("result",{}).get("records",[]) if body.get("success") else []
                return self._json({"records":rec,"count":len(rec),"query":query,"meta":{"source":"World Bank Botswana DRE Atlas","resource_id":rid,"license":"CC BY 4.0","evidence_class":"modelled_open_settlement_planning_data","warning":"Settlement clusters and indicators are planning/modelled evidence, not a verified current BPC unconnected-village list."}})
            except Exception as exc: return self._error(503,f"DRE Atlas DataStore unavailable: {exc}")
        if path == "/api/dre/candidate-register":
            limit=max(10,min(500,int(qs.get("limit",[100])[0]))); rid="42a50c1b-7920-4e2c-a465-e15f1f9d8711"
            fields='geohash,lat,lon,village_name,admin_cgaz_1,admin_cgaz_2,population,distance_to_existing_transmission_lines,has_nightlight,pv_value,num_connections,demand,demand_connection'
            sql=f'SELECT {fields} FROM "{rid}" ORDER BY population DESC NULLS LAST LIMIT 500'
            try:
                body=_json_request("https://energydata.info/en/api/3/action/datastore_search_sql?"+urllib.parse.urlencode({"sql":sql}),timeout=35); rows=body.get("result",{}).get("records",[]) if body.get("success") else []
                def fnum(v):
                    try: return float(v)
                    except Exception: return None
                pops=[fnum(x.get("population")) for x in rows]; pops=[x for x in pops if x is not None and x>=0]; pmax=max(pops) if pops else 1.0
                dists=[fnum(x.get("distance_to_existing_transmission_lines")) for x in rows]; dists=[x for x in dists if x is not None and x>=0]; dmax=max(dists) if dists else 1.0
                parsed=[]
                for x in rows:
                    pop=fnum(x.get("population")); dist=fnum(x.get("distance_to_existing_transmission_lines")); nl=str(x.get("has_nightlight","")).strip().lower(); no_light=nl in {"false","0","no","n","none",""}
                    score=(0.45*((pop or 0)/pmax)+0.40*((dist or 0)/dmax)+0.15*(1.0 if no_light else 0.0))*100.0
                    parsed.append({**x,"derived_priority_score":round(score,2),"derived_no_nightlight_flag":no_light})
                parsed.sort(key=lambda x:x["derived_priority_score"],reverse=True)
                return self._json({"records":parsed[:limit],"count":min(limit,len(parsed)),"meta":{"source":"World Bank Botswana DRE Atlas","evidence_class":"derived_from_modelled_open_settlement_indicators","warning":"Priority score is not BPC connection-status truth."}})
            except Exception as exc:
                return self._error(503,f"DRE candidate register unavailable: {exc}")
        if path == "/api/gep/point":
            try:
                lat=float(qs.get("lat",[None])[0]); lon=float(qs.get("lon",[None])[0])
                if not (-90<=lat<=90 and -180<=lon<=180): raise ValueError
            except (TypeError,ValueError):
                return self._error(422,"Valid lat/lon are required")
            key=f"gep_{lat:.4f}_{lon:.4f}.json".replace("-","m").replace(".","p")
            cached=cache_read(key,14*24*3600)
            if cached:
                cached.setdefault("meta",{})["cache"]="hit"; return self._json(cached)
            rid="3d6620fa-f9b7-46b3-b886-18b4072c38a8"
            sql=(f'SELECT * FROM "{rid}" ORDER BY POWER(CAST("X_deg" AS double precision)-({lon}),2) + POWER(CAST("Y_deg" AS double precision)-({lat}),2) LIMIT 1')
            url="https://energydata.info/en/api/3/action/datastore_search_sql?"+urllib.parse.urlencode({"sql":sql})
            try:
                body=_json_request(url,timeout=35); records=body.get("result",{}).get("records",[]) if body.get("success") else []
                if not records: raise RuntimeError("GEP DataStore returned no record")
                out={"record":records[0],"query":{"lat":lat,"lon":lon},"meta":{"source":"World Bank Global Electrification Platform (Botswana) - Climate Energy Modeling Parameters","resource_id":rid,"license":"CC BY 4.0","evidence_class":"modelled_open_planning_input","cache":"miss","warning":"GEP is a least-cost electrification planning dataset derived from public inputs. It is not measured BPC demand, line capacity, or site-bankability evidence."}}
                cache_write(key,out); return self._json(out)
            except Exception as exc:
                return self._error(503,f"World Bank GEP DataStore unavailable: {exc}")
        if path == "/api/renewable-benchmarks":
            return self._json(renewable_benchmarks_payload())
        if path == "/api/community-benchmarks":
            return self._json(community_benchmarks_payload())
        if path == "/api/sapp/transfer-limits":
            return self._json(sapp_transfer_limits_payload())
        if path == "/api/engineering/benchmarks":
            return self._json(electrical_benchmarks_payload())
        if path == "/api/evidence/manifest":
            return self._json(evidence_manifest_payload())
        if path == "/api/audit":
            return self._json(audit_payload())
        if path == "/api/engines/loss-reconciliation":
            return self._json(e2_cross_check())
        if path == "/api/engineering/enriched-network":
            case = qs.get("case", ["reference"])[0]
            cached = cache_read("osm_power.json", 365 * 24 * 3600)
            if not cached:
                return self._error(409, "Load the OSM power layer first so GridIQ has observed geometry to enrich.")
            try:
                return self._json(enrich_power_geojson(cached["data"], case))
            except ValueError as exc:
                return self._error(422, str(exc))
        if path == "/api/e3/criticality":
            cached = cache_read("osm_power.json", 365 * 24 * 3600)
            if not cached:
                return self._error(409, "Load the OSM power layer first so E3 has observed mapped topology to analyse.")
            try:
                vraw = qs.get("voltage_kv", [None])[0]
                voltage = int(vraw) if vraw not in (None, "", "null") else None
                limit = int(qs.get("limit", [30])[0])
                return self._json(structural_criticality_payload(cached["data"], voltage_kv=voltage, limit=limit))
            except ValueError as exc:
                return self._error(422, str(exc))
        if path == "/api/worldpop/population":
            try:
                lat = float(qs.get("lat", [None])[0]); lon = float(qs.get("lon", [None])[0])
                radius_km = float(qs.get("radius_km", [10])[0]); year = int(qs.get("year", [2025])[0])
                if not (-90 <= lat <= 90 and -180 <= lon <= 180 and 1 <= radius_km <= 30 and 2015 <= year <= 2030):
                    raise ValueError
            except (TypeError, ValueError):
                return self._error(422, "Valid lat/lon, radius_km=1..30 and year=2015..2030 are required")
            key = f"worldpop_{lat:.4f}_{lon:.4f}_{radius_km:.1f}_{year}.json".replace("-", "m").replace(".", "p")
            cached = cache_read(key, 7 * 24 * 3600)
            if cached:
                cached.setdefault("meta", {})["cache"] = "hit"
                return self._json(cached)
            import math
            coords=[]
            for i in range(33):
                a=2*math.pi*i/32; dlat=radius_km*math.sin(a)/111.32; dlon=radius_km*math.cos(a)/max(1e-6,111.32*math.cos(math.radians(lat)))
                coords.append([lon+dlon,lat+dlat])
            body=json.dumps({"geojson":{"type":"Polygon","coordinates":[coords]},"year":year,"resolution":"1km"}).encode()
            try:
                req=urllib.request.Request("https://api.worldpop.org/v2/population",data=body,headers={"User-Agent":"GridIQ-Botswana/1.7","Content-Type":"application/json"})
                with urllib.request.urlopen(req,timeout=35) as r:
                    task=json.loads(r.read().decode())
                task_id=task.get("task_id")
                if not task_id: raise RuntimeError("WorldPop did not return a task id")
                result=None
                for _ in range(20):
                    time.sleep(.8)
                    result=_json_request(f"https://api.worldpop.org/v2/tasks/{task_id}",timeout=20)
                    if result.get("status") in {"success","failure"}: break
                if not result or result.get("status")!="success": raise RuntimeError((result or {}).get("error") or "WorldPop task timed out")
                out={"total_population":result.get("result",{}).get("total_population"),"lat":lat,"lon":lon,"radius_km":radius_km,"year":year,"meta":{"source":"WorldPop API v2","resolution":"1km","cache":"miss","evidence_class":"modelled_population_dataset","warning":"Population is a spatial demand driver, not measured electrical load."}}
                cache_write(key,out); return self._json(out)
            except Exception as exc:
                stale=CACHE/key
                if stale.exists():
                    out=json.loads(stale.read_text()); out.setdefault("meta",{})["cache"]="stale"; return self._json(out)
                return self._error(503,f"WorldPop unavailable: {exc}")
        if path == "/api/osm/power":
            refresh = qs.get("refresh", ["false"])[0].lower() in {"1", "true", "yes"}
            cached = None if refresh else cache_read("osm_power.json", 6 * 3600)
            if cached:
                cached.setdefault("meta", {})["cache"] = "hit"
                cached["meta"]["evidence_summary"] = geojson_evidence_summary(cached["data"])
                return self._json(cached)
            q = '''[out:json][timeout:50];(way["power"~"line|minor_line"](-26.95,19.8,-17.7,29.5);nwr["power"="substation"](-26.95,19.8,-17.7,29.5);nwr["power"~"plant|generator"](-26.95,19.8,-17.7,29.5););out center geom tags;'''
            try:
                raw = _json_request("https://overpass-api.de/api/interpreter", data=q.encode(), timeout=60)
                fc = overpass_to_geojson(raw)
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
                return self._json(result)
            except Exception as exc:
                stale = CACHE / "osm_power.json"
                if stale.exists():
                    result = json.loads(stale.read_text())
                    result.setdefault("meta", {})["cache"] = "stale"
                    result["meta"]["evidence_summary"] = geojson_evidence_summary(result["data"])
                    result["meta"]["warning"] = result["meta"].get("warning", "") + " Live refresh failed; serving stale cached result."
                    return self._json(result)
                return self._error(503, f"Live OSM power overlay unavailable: {exc}")
        if path == "/api/nasa/power":
            try:
                lat = float(qs.get("lat", [None])[0])
                lon = float(qs.get("lon", [None])[0])
                days = int(qs.get("days", [14])[0])
                if not -90 <= lat <= 90 or not -180 <= lon <= 180 or not 3 <= days <= 60:
                    raise ValueError("lat/lon/days out of range")
            except (TypeError, ValueError):
                return self._error(422, "Valid lat, lon and days=3..60 are required")
            end = date.today() - timedelta(days=2)
            start = end - timedelta(days=days - 1)
            params = urllib.parse.urlencode({
                "parameters": "ALLSKY_SFC_SW_DWN,T2M,WS10M",
                "community": "RE",
                "longitude": lon,
                "latitude": lat,
                "start": start.strftime("%Y%m%d"),
                "end": end.strftime("%Y%m%d"),
                "format": "JSON",
            })
            try:
                data = _json_request(f"https://power.larc.nasa.gov/api/temporal/daily/point?{params}", timeout=35)
                p = data.get("properties", {}).get("parameter", {})
                dates = sorted(set().union(*(x.keys() for x in p.values()))) if p else []
                rows = [{"date": d, "ghi": p.get("ALLSKY_SFC_SW_DWN", {}).get(d), "temp_c": p.get("T2M", {}).get(d), "wind_ms": p.get("WS10M", {}).get(d)} for d in dates]
                return self._json({"rows": rows, "meta": {"source": "NASA POWER", "lat": lat, "lon": lon, "start": str(start), "end": str(end), "warning": "Planning-grade gridded meteorology; not a substitute for site measurement/bankability studies."}})
            except Exception as exc:
                return self._error(503, f"NASA POWER unavailable: {exc}")
        return self._error(404, "Not found")

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        try:
            n = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(n) or b"{}")
            if path == "/api/scenario":
                return self._json(scenario_payload(payload))
            if path == "/api/e1/optimize":
                return self._json(capacity_expansion_screen(payload))
            if path == "/api/e1/site-screen":
                cached = cache_read("osm_power.json", 365 * 24 * 3600)
                base = capacity_expansion_screen({k:payload[k] for k in ("source_year","import_capacity_limit_mw","import_energy_price_usd_per_mwh","max_solar_mw","max_wind_mw","max_bess_mw","bess_duration_h","real_discount_rate") if k in payload})
                return self._json(spatialize_e1_plan(base, site_name=payload.get("site_name","Selected candidate"), lat=float(payload["lat"]), lon=float(payload["lon"]), osm_fc=cached["data"] if cached else None, grid_cost_case=payload.get("grid_cost_case","reference"), resource_evidence=payload.get("resource_evidence")))
            if path == "/api/e2/loss-reconciliation":
                return self._json(loss_reconciliation_payload(payload.get("modelled_loss_gwh"), payload.get("model_scope", "transmission")))
            if path == "/api/e4/villagefit":
                rural = rural_electrification_payload()
                custom = None
                custom_keys=("custom_name","custom_lat","custom_lon","custom_population")
                if any(payload.get(k) is not None for k in custom_keys):
                    if any(payload.get(k) is None for k in custom_keys): return self._error(422,"custom_name, custom_lat, custom_lon and custom_population must be supplied together")
                    custom={"id":"custom","name":payload["custom_name"],"population_2022":float(payload["custom_population"]),"lat":float(payload["custom_lat"]),"lon":float(payload["custom_lon"]),"source_status":"explicit settlement input"}
                    village=custom
                else:
                    village = next((v for v in rural["pilot_villages"] if v["id"] == payload.get("village_id","ukhwi")), None)
                    if not village: return self._error(422, "Unknown verified pilot village")
                cached = cache_read("osm_power.json", 365 * 24 * 3600)
                nasa_rows = None
                if payload.get("use_live_nasa", True):
                    try:
                        days = int(payload.get("nasa_days", 30)); end = date.today() - timedelta(days=2); start = end - timedelta(days=days-1)
                        params = urllib.parse.urlencode({"parameters":"ALLSKY_SFC_SW_DWN,T2M,WS10M","community":"RE","longitude":village["lon"],"latitude":village["lat"],"start":start.strftime("%Y%m%d"),"end":end.strftime("%Y%m%d"),"format":"JSON"})
                        data=_json_request(f"https://power.larc.nasa.gov/api/temporal/daily/point?{params}",timeout=35)
                        pp=data.get("properties",{}).get("parameter",{}); dates=sorted(set().union(*(x.keys() for x in pp.values()))) if pp else []
                        nasa_rows=[{"date":d,"ghi":pp.get("ALLSKY_SFC_SW_DWN",{}).get(d),"temp_c":pp.get("T2M",{}).get(d),"wind_ms":pp.get("WS10M",{}).get(d)} for d in dates]
                    except Exception:
                        nasa_rows=None
                gep_data=None
                if payload.get("use_live_gep", True):
                    try:
                        rid="3d6620fa-f9b7-46b3-b886-18b4072c38a8"; lat=float(village["lat"]); lon=float(village["lon"])
                        sql=(f'SELECT * FROM "{rid}" ORDER BY POWER(CAST("X_deg" AS double precision)-({lon}),2) + POWER(CAST("Y_deg" AS double precision)-({lat}),2) LIMIT 1')
                        body=_json_request("https://energydata.info/en/api/3/action/datastore_search_sql?"+urllib.parse.urlencode({"sql":sql}),timeout=35)
                        rec=body.get("result",{}).get("records",[]) if body.get("success") else []
                        if rec: gep_data={"record":rec[0],"query":{"lat":lat,"lon":lon},"meta":{"source":"World Bank GEP","evidence_class":"modelled_open_planning_input"}}
                    except Exception:
                        gep_data=None
                return self._json(villagefit_screen(payload.get("village_id","ukhwi"), osm_fc=cached["data"] if cached else None, nasa_rows=nasa_rows, grid_cost_case=payload.get("grid_cost_case","reference"), annual_kwh_per_household=payload.get("annual_kwh_per_household"), peak_kw_per_household=payload.get("peak_kw_per_household"), evening_energy_share_pct=payload.get("evening_energy_share_pct"), village_override=custom, gep_point=gep_data, collectable_cattle_manure_kg_per_day=payload.get("collectable_cattle_manure_kg_per_day"), biogas_yield_case=payload.get("biogas_yield_case","reference")))
            if path == "/api/e2/system-benchmark":
                cached = cache_read("osm_power.json", 365 * 24 * 3600)
                if not cached: return self._error(409,"Load the OSM power layer first so the benchmark system model has observed mapped geometry.")
                return self._json(benchmark_multi_injection_study(cached["data"],voltage_kv=int(payload.get("voltage_kv",220)),case=payload.get("case","reference"),injections=payload.get("injections",[])))
            if path == "/api/e1/representative-day":
                return self._error(503,"24-hour benchmark chronology requires the preferred FastAPI runtime in this release; annual E1 screening remains available in compatibility mode.")
            if path == "/api/engineering/transfer":
                cached = cache_read("osm_power.json", 365 * 24 * 3600)
                if not cached:
                    return self._error(409, "Load the OSM power layer first so GridIQ has observed geometry to analyse.")
                required = ["voltage_kv","case","transfer_mw","source_lat","source_lon","sink_lat","sink_lon"]
                if any(k not in payload for k in required):
                    return self._error(422, "Missing engineering transfer input")
                return self._json(benchmark_transfer_study(cached["data"], **{k: payload[k] for k in required}))
            return self._error(404, "Not found")
        except ValueError as exc:
            return self._error(422, str(exc))
        except Exception as exc:
            return self._error(500, f"Internal error: {type(exc).__name__}")


def main():
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    print(f"GridIQ compatibility runtime listening on http://{host}:{port}", flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
