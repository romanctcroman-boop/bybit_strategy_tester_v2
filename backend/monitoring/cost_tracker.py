"""
Cost Tracker - backward-compatibility shim.

The canonical implementation now lives in ``backend.agents.cost_tracker``.
This module re-exports the public API so that existing imports keep working.
"""

from backend.agents.cost_tracker import (
    COST_TABLE,
    CostRecord,
    CostSummary,
    CostTracker,
    get_cost_tracker,
    record_api_cost,
)

__all__ = [
    "COST_TABLE",
    "CostRecord",
    "CostSummary",
    "CostTracker",
    "get_cost_tracker",
    "record_api_cost",
]
