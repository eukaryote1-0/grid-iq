from __future__ import annotations

from typing import Any

from engines.payloads import (
    bpc_losses_payload,
)
def loss_reconciliation_payload(modelled_loss_gwh: float | None = None, model_scope: str = "transmission") -> dict[str, Any]:
    src = bpc_losses_payload()
    anchor = src["validation_anchor"]
    out: dict[str, Any] = {
        "anchor": anchor,
        "history": src["annual"],
        "cross_checks": src.get("report_cross_checks", []),
        "model_scope": model_scope,
        "modelled_loss_gwh": modelled_loss_gwh,
        "status": "model_result_not_supplied",
        "comparison": None,
        "scope_warning": src["metadata"]["scope_warning"],
        "source": src["metadata"]["primary_source"],
    }
    if modelled_loss_gwh is not None:
        if modelled_loss_gwh < 0:
            raise ValueError("modelled_loss_gwh must be non-negative")
        diff = modelled_loss_gwh - float(anchor["loss_gwh_table"])
        err = abs(diff) / float(anchor["loss_gwh_table"]) * 100.0
        out["status"] = "comparison_available_not_directly_equivalent" if model_scope == "transmission" else "comparison_available"
        out["comparison"] = {
            "difference_gwh": round(diff, 3),
            "absolute_error_pct_of_bpc_anchor": round(err, 2),
            "within_10pct_of_bpc_td_anchor": err <= 10.0,
            "interpretation": (
                "A transmission-only technical-loss model is not directly equivalent to BPC's combined T&D/system-loss accounting. "
                "Use the difference as a reconciliation diagnostic, not proof that the model is calibrated."
                if model_scope == "transmission" else
                "Comparison uses the supplied model scope. Confirm that accounting boundaries match before treating the error as calibration evidence."
            ),
        }
    return out
