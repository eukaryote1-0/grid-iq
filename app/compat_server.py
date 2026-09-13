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

from app.logic import (CACHE, audit_payload, baseline_payload, benchmark_transfer_study, catalog_payload, cache_read, cache_write, census_districts_payload, district_access_context_payload, electrical_benchmarks_payload, enrich_power_geojson, evidence_manifest_payload, geojson_evidence_summary, neus_payload, overpass_to_geojson, plant_reference_payload, scenario_payload, storage_benchmarks_payload)
from engines.e2_flow.loss_reconciliation import loss_reconciliation

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
        "connect-src 'self' https://overpass-api.de https://power.larc.nasa.gov https://api.worldpop.org; font-src 'self' data:; "
        "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    ),
}


def _json_request(url: str, *, data: bytes | None = None, timeout: int = 45) -> dict:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "GridIQ-Botswana/1.4"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


class Handler(BaseHTTPRequestHandler):
    server_version = "GridIQCompat/1.4"

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
            return self._json({"status": "ok", "service": "gridiq", "version": "1.4.0", "runtime": "compat-stdlib"})
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
        if path == "/api/engineering/benchmarks":
            return self._json(electrical_benchmarks_payload())
        if path == "/api/evidence/manifest":
            return self._json(evidence_manifest_payload())
        if path == "/api/audit":
            return self._json(audit_payload())
        if path == "/api/engines/loss-reconciliation":
            return self._json(loss_reconciliation())
        if path == "/api/engineering/enriched-network":
            case = qs.get("case", ["reference"])[0]
            cached = cache_read("osm_power.json", 365 * 24 * 3600)
            if not cached:
                return self._error(409, "Load the OSM power layer first so GridIQ has observed geometry to enrich.")
            try:
                return self._json(enrich_power_geojson(cached["data"], case))
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
                req=urllib.request.Request("https://api.worldpop.org/v2/population",data=body,headers={"User-Agent":"GridIQ-Botswana/1.4","Content-Type":"application/json"})
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
