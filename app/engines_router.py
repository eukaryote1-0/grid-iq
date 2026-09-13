"""Engine API routes.

Only additive endpoints live here; the integration owner wires this router into
``app.main``. Each engine keeps its own evidence labels and 'not' boundaries.
"""
from __future__ import annotations

from fastapi import APIRouter

from engines.e2_flow.loss_reconciliation import loss_reconciliation

router = APIRouter(prefix="/api/engines", tags=["engines"])


@router.get("/loss-reconciliation")
def get_loss_reconciliation():
    """E2 — benchmark transmission I²R loss screen reconciled against BPC/AFREC."""
    return loss_reconciliation()
