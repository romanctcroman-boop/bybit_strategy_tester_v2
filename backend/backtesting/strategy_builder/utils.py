"""
Shared utility functions for the Strategy Builder.

These helpers are used by both the adapter (adapter.py) and the
block executor (block_executor.py). Keeping them here avoids
circular imports.
"""

from __future__ import annotations

from typing import Any

from loguru import logger


def _param(params: dict, default: Any, *keys: str) -> Any:
    """Get param value trying keys in order (supports snake_case and camelCase from frontend)."""
    for k in keys:
        v = params.get(k)
        if v is not None:
            return v
    return default


def _clamp_period(val: Any, min_val: int = 1, max_val: int = 500) -> int:
    """Convert indicator period to a safe integer, clamped to [min_val, max_val].

    Protects against user-supplied values like 0, -5, or 999999 which would cause
    vectorbt/NumPy errors. Logs a warning when clamping is applied.

    Args:
        val: Raw parameter value (int, float, str, or None).
        min_val: Minimum allowed period (default 1).
        max_val: Maximum allowed period (default 500).

    Returns:
        Clamped integer period.
    """
    try:
        raw = int(val)
    except (TypeError, ValueError):
        logger.warning("_clamp_period: could not convert {!r} to int, using min_val={}", val, min_val)
        return min_val
    clamped = max(min_val, min(max_val, raw))
    if clamped != raw:
        logger.warning(
            "_clamp_period: period={} out of range [{}, {}], clamped to {}",
            raw,
            min_val,
            max_val,
            clamped,
        )
    return clamped
