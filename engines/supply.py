from __future__ import annotations

from typing import Any

from app.logic import (
    baseline_payload,
)
def historical_supply_metrics_payload() -> dict[str, Any]:
    base = baseline_payload()
    rows = base["quarterly"]
    enriched=[]
    for r in rows:
        total=float(r["generation_mwh"])+float(r["imports_mwh"])
        enriched.append({**r,"total_supply_mwh":round(total,1),"local_generation_share_pct":round(float(r["generation_mwh"])/total*100.0,2) if total else None})
    window=[r for r in enriched if 2018 <= int(str(r["period"])[:4]) <= 2022]
    wg=sum(float(r["generation_mwh"]) for r in window); wt=sum(float(r["total_supply_mwh"]) for r in window)
    lowest=min(enriched,key=lambda r:r["local_generation_share_pct"] if r["local_generation_share_pct"] is not None else 999)
    return {
        "quarterly":enriched,
        "five_year_2018_2022":{
            "local_generation_share_pct":round(wg/wt*100.0,2),
            "imports_share_pct":round((wt-wg)/wt*100.0,2),
            "method":"Sum Statistics Botswana quarterly local generation across 2018Q1-2022Q4 divided by total local generation + imports for the same quarters."
        },
        "lowest_quarter_local_share":lowest,
        "q1_2026":base["q1_2026"],
        "synthetic":False,
    }
