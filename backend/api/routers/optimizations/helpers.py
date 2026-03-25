"""
Optimization Router — Helper functions.

Provides interval normalization and parameter value generation
utilities used across the optimization sub-routers.
"""

# mypy: disable-error-code="arg-type, assignment, var-annotated, return-value, union-attr, operator, attr-defined, misc, dict-item"

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.api.routers.optimizations.models import ParamRangeSpec

logger = logging.getLogger(__name__)


def _normalize_interval(interval: str) -> str:
    """
    Normalize interval format for database queries.

    Converts frontend-friendly formats to Bybit API/DB format:
    - '30m' -> '30'
    - '1h' -> '60'
    - '4h' -> '240'
    - '1d' -> 'D'
    - '1w' -> 'W'
    """
    interval = interval.lower().strip()
    if interval.endswith("m"):
        return interval[:-1]  # "30m" -> "30"
    elif interval.endswith("h"):
        hours = int(interval[:-1])
        return str(hours * 60)  # "1h" -> "60", "4h" -> "240"
    elif interval in ("d", "1d", "day"):
        return "D"
    elif interval in ("w", "1w", "week"):
        return "W"
    return interval


def generate_param_values(spec: "ParamRangeSpec") -> list[Any]:
    """
    Generate parameter values from a ParamRangeSpec.

    Supports:
    - Negative values (low=-50, high=50)
    - Fractional steps (step=0.01, step=0.001)
    - High precision (precision=4 for 0.0001)
    - Integer and float types

    Args:
        spec: Parameter range specification

    Returns:
        List of parameter values
    """
    if spec.values:
        return spec.values

    if spec.low is None or spec.high is None:
        return []

    # Determine default step based on type
    step = spec.step if spec.step is not None else (1.0 if spec.type == "int" else 0.01)

    # Determine precision for rounding
    if spec.precision is not None:
        precision = spec.precision
    else:
        # Auto-detect precision from step
        if step >= 1:
            precision = 0
        else:
            # Count decimal places in step
            step_str = f"{step:.10f}".rstrip("0")
            precision = len(step_str.split(".")[-1]) if "." in step_str else 0

    values = []
    val = spec.low

    # Handle both positive and negative ranges
    # Including cases where low > high (should not happen, but handle gracefully)
    if spec.low <= spec.high:
        while val <= spec.high + step * 0.001:  # Small epsilon for float comparison
            if spec.type == "int":
                values.append(round(val))
            else:
                # Round to specified precision
                rounded_val = round(val, precision) if precision > 0 else round(val)
                values.append(rounded_val)
            val += step

            # Safety limit: max 10000 values
            if len(values) >= 10000:
                logger.warning(
                    f"Parameter range truncated to 10000 values (low={spec.low}, high={spec.high}, step={step})"
                )
                break

    # Remove duplicates while preserving order (important for int type)
    seen = set()
    unique_values = []
    for v in values:
        if v not in seen:
            seen.add(v)
            unique_values.append(v)

    return unique_values
