"""
Formatting helpers for the backtests router.

Pure utility functions for safe type conversion and building response payloads.
"""

import math as _math
from datetime import UTC, datetime
from typing import Any, cast

from backend.backtesting.models import EquityCurve


def _get_side_value(side: Any) -> str:
    """Safely extract side value from enum or return string representation."""
    if side is None:
        return "unknown"
    if hasattr(side, "value"):
        return str(side.value)
    return str(side)


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Safely convert SQLAlchemy Column or other value to float.
    Also replaces inf/nan with default to keep JSON serialization valid.
    """
    if val is None:
        return default
    try:
        f = float(val)
        return default if (_math.isnan(f) or _math.isinf(f)) else f
    except (TypeError, ValueError):
        return default


def _safe_int(val: Any, default: int = 0) -> int:
    """Safely convert SQLAlchemy Column or other value to int."""
    if val is None:
        return default
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _safe_str(val: Any, default: str = "") -> str:
    """Safely convert SQLAlchemy Column or other value to str."""
    if val is None:
        return default
    return str(val)


def _ensure_utc(dt: Any) -> datetime:
    """Ensure a datetime value is timezone-aware (UTC).

    Handles strings, naive datetimes, and already-aware datetimes.
    Prevents 'can't compare offset-naive and offset-aware datetimes' errors.
    """
    if dt is None:
        return datetime.now(UTC)
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
    if isinstance(dt, datetime) and dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return cast(datetime, dt)


def downsample_list(data: list, max_points: int = 500) -> list:
    """Evenly downsample a list to max_points, keeping first and last."""
    if not data or len(data) <= max_points:
        return data

    # Always include first and last points
    step = (len(data) - 1) / (max_points - 1)
    indices = [int(i * step) for i in range(max_points - 1)]
    indices.append(len(data) - 1)  # Ensure last point is included

    return [data[i] for i in indices]


def build_equity_curve_response(
    equity_curve: EquityCurve, trades: list | None = None, max_points: int = 800
) -> dict[str, Any] | None:
    """Build equity curve response with one point per trade exit.

    Returns equity value at the moment each trade closes.
    Number of points = number of trades (like TradingView).
    """
    if not equity_curve:
        return None

    timestamps = equity_curve.timestamps or []
    equity = equity_curve.equity or []
    drawdown = equity_curve.drawdown or []
    bh_equity = equity_curve.bh_equity or []
    bh_drawdown = equity_curve.bh_drawdown or []
    returns = equity_curve.returns or []
    runup = equity_curve.runup or []

    n = len(timestamps)
    if n == 0:
        return None

    # If no trades, return start and end points only
    if not trades or len(trades) == 0:
        return {
            "timestamps": [
                timestamps[0].isoformat() if hasattr(timestamps[0], "isoformat") else str(timestamps[0]),
                timestamps[-1].isoformat() if hasattr(timestamps[-1], "isoformat") else str(timestamps[-1]),
            ],
            "equity": [float(equity[0]), float(equity[-1])] if equity else [],
            "drawdown": [float(drawdown[0]), float(drawdown[-1])] if drawdown else [],
            "bh_equity": [float(bh_equity[0]), float(bh_equity[-1])] if bh_equity else [],
            "bh_drawdown": [float(bh_drawdown[0]), float(bh_drawdown[-1])] if bh_drawdown else [],
            "returns": [float(returns[0]), float(returns[-1])] if returns else [],
            "runup": [float(runup[0]), float(runup[-1])] if runup else [],
        }

    # Create timestamp -> index mapping for fast lookup (epoch-based, avoids TZ string fragility)
    def _to_epoch_ms(ts: Any) -> int | None:
        """Convert timestamp to epoch milliseconds for reliable matching."""
        if isinstance(ts, (int, float)):
            return int(ts)
        if hasattr(ts, "timestamp"):
            return int(ts.timestamp() * 1000)
        try:
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            return int(dt.timestamp() * 1000)
        except (ValueError, TypeError):
            return None

    ts_to_idx: dict[int, int] = {}
    for i, ts in enumerate(timestamps):
        epoch = _to_epoch_ms(ts)
        if epoch is not None:
            ts_to_idx[epoch] = i

    # Collect indices for trade EXIT times only (one point per closed trade)
    exit_indices = []
    for trade in trades:
        exit_time = trade.exit_time if hasattr(trade, "exit_time") else trade.get("exit_time")

        if exit_time:
            epoch = _to_epoch_ms(exit_time)
            if epoch is not None:
                idx = ts_to_idx.get(epoch)
                if idx is not None:
                    exit_indices.append(idx)

    # If we couldn't match any trades, fallback to first/last
    if not exit_indices:
        return {
            "timestamps": [
                timestamps[0].isoformat() if hasattr(timestamps[0], "isoformat") else str(timestamps[0]),
                timestamps[-1].isoformat() if hasattr(timestamps[-1], "isoformat") else str(timestamps[-1]),
            ],
            "equity": [float(equity[0]), float(equity[-1])] if equity else [],
            "drawdown": [float(drawdown[0]), float(drawdown[-1])] if drawdown else [],
            "bh_equity": [],
            "bh_drawdown": [],
            "returns": [float(returns[0]), float(returns[-1])] if returns else [],
            "runup": [float(runup[0]), float(runup[-1])] if runup else [],
        }

    # Sort indices chronologically
    indices = sorted(set(exit_indices))

    # Helper: sanitize float values to avoid JSON serialization errors with inf/nan
    def _fv(v: Any) -> float:
        try:
            f = float(v)
            return 0.0 if (_math.isnan(f) or _math.isinf(f)) else f
        except (TypeError, ValueError):
            return 0.0

    return {
        "timestamps": [
            timestamps[i].isoformat() if hasattr(timestamps[i], "isoformat") else str(timestamps[i])
            for i in indices
            if i < len(timestamps)
        ],
        "equity": [_fv(equity[i]) for i in indices if i < len(equity)],
        "drawdown": [_fv(drawdown[i]) for i in indices if i < len(drawdown)],
        "bh_equity": [_fv(bh_equity[i]) for i in indices if i < len(bh_equity)] if bh_equity else [],
        "bh_drawdown": [_fv(bh_drawdown[i]) for i in indices if i < len(bh_drawdown)] if bh_drawdown else [],
        "returns": [_fv(returns[i]) for i in indices if i < len(returns)] if returns else [],
        "runup": [_fv(runup[i]) for i in indices if i < len(runup)] if runup else [],
    }
