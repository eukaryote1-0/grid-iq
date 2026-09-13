"""Local, bounded OpenStreetMap tile cache.

Serves /tiles/{z}/{x}/{y}.png from data/cache/tiles; on a miss it fetches the
tile once, stores it, and returns it. After the demo prewarm, map pans and zooms
touch no upstream at all.

Attribution remains with OpenStreetMap; the prewarm script is throttled and
bounded to respect the tile usage policy.
"""
from __future__ import annotations

import os
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, Response

ROOT = Path(__file__).resolve().parents[1]
TILES = ROOT / "data" / "cache" / "tiles"
UPSTREAMS = (
    "https://a.tile.openstreetmap.org",
    "https://b.tile.openstreetmap.org",
    "https://c.tile.openstreetmap.org",
)
TILE_HEADERS = {"Cache-Control": "public, max-age=2592000, immutable"}

router = APIRouter(tags=["tiles"])


@router.get("/tiles/{z}/{x}/{y}.png")
async def tile(z: int, x: int, y: int):
    if not (0 <= z <= 19 and 0 <= x < (1 << z) and 0 <= y < (1 << z)):
        raise HTTPException(status_code=400, detail="invalid tile coordinates")
    path = TILES / str(z) / str(x) / f"{y}.png"
    if path.exists():
        return Response(path.read_bytes(), media_type="image/png", headers=TILE_HEADERS)

    data: bytes | None = None
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(12, connect=4),
        headers={"User-Agent": "GridIQ-Botswana/1.8 (bounded demo tile cache)"},
    ) as client:
        for host in UPSTREAMS:
            try:
                r = await client.get(f"{host}/{z}/{x}/{y}.png")
                if r.status_code == 200 and r.content:
                    data = r.content
                    break
            except Exception:
                continue
    if data is None:
        raise HTTPException(status_code=404, detail="tile unavailable")

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)
    return Response(data, media_type="image/png", headers=TILE_HEADERS)
