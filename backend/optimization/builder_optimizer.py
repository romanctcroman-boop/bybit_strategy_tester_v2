"""
Builder Strategy Optimizer.

Enables optimization of visual node-based strategies from Strategy Builder.
Extracts optimizable parameters from graph blocks, clones graphs with modified params,
runs backtests via StrategyBuilderAdapter, and supports Grid Search + Optuna Bayesian.

Architecture:
    Strategy Builder Graph (blocks + connections)
        → extract_optimizable_params()  → discover param ranges
        → clone_graph_with_params()     → create modified graph
        → StrategyBuilderAdapter(graph) → generate signals
        → BacktestEngine.run()          → metrics
        → scoring + filtering           → ranked results
"""

from __future__ import annotations

import contextlib
import copy
import json
import logging
import math
import threading
import time
from itertools import product
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from optuna.samplers import BaseSampler
import pandas as pd

from backend.config.constants import COMMISSION_TV
from backend.optimization.early_pruning import should_prune_early
from backend.optimization.filters import passes_filters
from backend.optimization.graph_utils import MutableGraphUpdater
from backend.optimization.indicator_cache import IndicatorCache, _ohlcv_fingerprint
from backend.optimization.precompute import PrecomputedOHLCV
from backend.optimization.scoring import apply_pareto_scores, calculate_composite_score

logger = logging.getLogger(__name__)


_INTERVAL_BARS_PER_DAY: dict[str, float] = {
    "1": 1440.0,
    "3": 480.0,
    "5": 288.0,
    "15": 96.0,
    "30": 48.0,
    "60": 24.0,
    "120": 12.0,
    "240": 6.0,
    "360": 4.0,
    "720": 2.0,
    "D": 1.0,
    "W": 1.0 / 7.0,
    "M": 1.0 / 30.44,
}


def _bars_per_month(interval: str) -> int:
    """Approximate bars per calendar month for a given timeframe string."""
    bars_per_day = _INTERVAL_BARS_PER_DAY.get(str(interval), 48.0)
    return max(1, int(bars_per_day * 30.44))


def _log_info(msg: str) -> None:
    """Log to both module logger and uvicorn.error for guaranteed visibility."""
    logger.info(msg)
    uvi = logging.getLogger("uvicorn.error")
    if uvi.handlers:
        uvi.info(msg)


def _log_warning(msg: str, **kwargs) -> None:
    """Log warning to both module logger and uvicorn.error."""
    logger.warning(msg, **kwargs)
    uvi = logging.getLogger("uvicorn.error")
    if uvi.handlers:
        uvi.warning(msg, **kwargs)


# =============================================================================
# OPTIMIZATION PROGRESS TRACKING (file-based, shared across all uvicorn workers)
# =============================================================================
_progress_lock = threading.Lock()

# Progress stored in .run/optimizer_progress.json so all uvicorn workers share state
_PROGRESS_DIR = Path(__file__).parent.parent.parent / ".run"
_PROGRESS_FILE = _PROGRESS_DIR / "optimizer_progress.json"

# In-memory cache: written every trial, flushed to disk every _PROGRESS_FLUSH_INTERVAL trials.
# Reduces I/O bottleneck from O(n_trials) disk writes to O(n_trials / interval).
_progress_memory_cache: dict[str, Any] = {}
_progress_trial_counter: dict[str, int] = {}
_PROGRESS_FLUSH_INTERVAL = 5  # flush to disk every 5 trials

# =============================================================================
# OPTIMIZATION RESULTS STORAGE (in-memory, keyed by strategy_id)
# Used by fire-and-forget optimization endpoint to pass results to GET /results
# =============================================================================
_results_lock = threading.Lock()
_opt_results: dict[str, Any] = {}


def store_optimization_result(strategy_id: str, result: dict[str, Any]) -> None:
    """Store completed optimization result for retrieval via GET /optimize/results."""
    with _results_lock:
        _opt_results[strategy_id] = result


def get_optimization_result(strategy_id: str) -> dict[str, Any] | None:
    """Retrieve stored optimization result. Returns None if not ready."""
    with _results_lock:
        return _opt_results.get(strategy_id)


def clear_optimization_result(strategy_id: str) -> None:
    """Clear stored result after it has been consumed."""
    with _results_lock:
        _opt_results.pop(strategy_id, None)


def _read_progress_file() -> dict[str, Any]:
    """Read progress from shared JSON file (atomic read)."""
    try:
        if _PROGRESS_FILE.exists():
            return json.loads(_PROGRESS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _write_progress_file(data: dict[str, Any]) -> None:
    """Write progress to shared JSON file (atomic write via temp file)."""
    try:
        _PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
        tmp = _PROGRESS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        tmp.replace(_PROGRESS_FILE)
    except Exception:
        pass


#: Ordered list of optimization pipeline stages.  The UI uses this to
#: render a staged progress bar.  Stages added for hardening features
#: (2026-04-19) are only emitted when the corresponding feature is active.
OPTIMIZATION_STAGES: tuple[str, ...] = (
    "loading_data",  # market data fetch + sanity-check
    "preparing",  # warmup, param-spec merge, OOS split
    "searching",  # main trial loop (grid/random/Bayesian)
    "post_grid_refine",  # hardening: local ±pct grid around top-K
    "overfit_guards",  # hardening: annotate top-K with guard checks
    "finalizing",  # scoring, composite, context assembly
    "done",  # completed successfully
)


def update_optimization_progress(
    strategy_id: str,
    *,
    status: str = "running",
    tested: int = 0,
    total: int = 0,
    best_score: float = 0.0,
    results_found: int = 0,
    speed: float = 0.0,
    eta_seconds: int = 0,
    started_at: float | None = None,
    context: dict | None = None,
    stage: str | None = None,
) -> None:
    """Update progress for a running builder optimization.

    Writes to in-memory cache every call; flushes to disk every
    _PROGRESS_FLUSH_INTERVAL trials to reduce I/O bottleneck.
    Status transitions (running→completed/failed) always flush immediately.

    The ``stage`` argument lets callers tag the current pipeline phase
    (see :data:`OPTIMIZATION_STAGES`).  When omitted, the previously
    stored stage is preserved so per-trial updates don't clobber the
    stage set by the surrounding pipeline driver.  Transitions to a new
    stage always force an immediate flush so the UI sees the change
    without waiting for the trial-counter flush interval.
    """
    percent = round(tested * 100 / total, 1) if total > 0 else 0.0
    with _progress_lock:
        existing = _progress_memory_cache.get(strategy_id, {})
        # Preserve previously recorded stage across incremental updates;
        # only overwrite when a new stage is explicitly supplied.
        prev_stage = existing.get("stage", "")
        resolved_stage = stage if stage is not None else prev_stage
        stage_transitioned = bool(stage) and stage != prev_stage
        entry: dict = {
            "status": status,
            "stage": resolved_stage,
            "tested": tested,
            "total": total,
            "percent": percent,
            "best_score": best_score,
            "results_found": results_found,
            "speed": speed,
            "eta_seconds": eta_seconds,
            "started_at": started_at or existing.get("started_at") or time.time(),
            "updated_at": time.time(),
        }
        # Preserve context across incremental updates — only set when explicitly provided
        if context is not None:
            entry["optimization_context"] = context
        elif "optimization_context" in existing:
            entry["optimization_context"] = existing["optimization_context"]

        _progress_memory_cache[strategy_id] = entry

        # Flush to disk:
        #   - always on terminal states (completed/failed/stopped)
        #   - always on first call for a new strategy_id (creates the disk entry)
        #   - always on stage transition (so UI reflects pipeline phase immediately)
        #   - otherwise every N trials (reduces I/O bottleneck)
        terminal = status in ("completed", "failed", "stopped")
        _progress_trial_counter[strategy_id] = _progress_trial_counter.get(strategy_id, 0) + 1
        is_first = _progress_trial_counter[strategy_id] == 1
        should_flush = (
            terminal
            or is_first
            or stage_transitioned
            or (_progress_trial_counter[strategy_id] % _PROGRESS_FLUSH_INTERVAL == 0)
        )
        if should_flush:
            disk_data = _read_progress_file()
            disk_data[strategy_id] = entry
            _write_progress_file(disk_data)


def get_optimization_progress(strategy_id: str) -> dict[str, Any]:
    """Get current progress for a strategy optimization.

    Reads from in-memory cache first (fastest path for in-process polling).
    Falls back to disk for cross-worker reads (e.g. second uvicorn worker).
    """
    with _progress_lock:
        if strategy_id in _progress_memory_cache:
            return _progress_memory_cache[strategy_id].copy()
        data = _read_progress_file()
        return data.get(strategy_id, {"status": "idle"}).copy()


def clear_optimization_progress(strategy_id: str) -> None:
    """Clear progress entry after optimization completes (memory + disk)."""
    with _progress_lock:
        _progress_memory_cache.pop(strategy_id, None)
        _progress_trial_counter.pop(strategy_id, None)
        data = _read_progress_file()
        data.pop(strategy_id, None)
        _write_progress_file(data)


# =============================================================================
# SCORE COMPRESSION HELPER
# =============================================================================

# Metrics where log1p compression is applied to the raw composite score before
# storing in trial results and before OOS comparison.  Must stay in sync with
# the objective function inside run_builder_optuna_search.
# NOTE: "pareto_balance" is NOT in this set — after the 2026-04-19 rewrite its
# formula already applies sign-preserving log1p internally (see
# scoring.calculate_composite_score). Adding it here would double-compress.
_LOG_SCALE_METRICS: frozenset[str] = frozenset(
    {
        "profit_factor",
        "calmar_ratio",
        "recovery_factor",
        "sharpe_ratio",
        "sortino_ratio",
    }
)


def _compress_score(score: float, metric: str) -> float:
    """Apply log1p compression for ratio/multiplicative metrics.

    sign(x) × log1p(|x|) maps [−∞,+∞] monotonically with compression so the
    surrogate model learns from compressed score differences (profit_factor 10
    vs 2 is not "5× better" in practical terms).

    Used consistently in *both* the IS objective and OOS comparison so that
    is_score and oos_score are always on the same scale.
    """
    if metric in _LOG_SCALE_METRICS and score != 0.0:
        return math.copysign(math.log1p(abs(score)), score)
    return score


# =============================================================================
# P0-2: OOS (OUT-OF-SAMPLE) VALIDATION SPLIT
# =============================================================================


def split_ohlcv_is_oos(
    ohlcv: pd.DataFrame,
    oos_ratio: float = 0.2,
    oos_min_bars: int = 200,
    warmup_bars: int = 200,
) -> tuple[pd.DataFrame, pd.DataFrame | None, dict]:
    """
    Split OHLCV into In-Sample (IS) and Out-of-Sample (OOS) segments.

    The OOS segment is always the LAST oos_ratio fraction of the data.
    IS segment is everything before OOS.

    The OOS segment gets an additional ``warmup_bars`` prepended from the IS tail
    so that indicator warm-up (Wilder RSI, Supertrend) is available for OOS
    signal generation. These warm-up bars are sliced off before OOS backtest
    (via warmup_cutoff in config_params), preserving the "sealed OOS" invariant.

    Args:
        ohlcv: Full OHLCV DataFrame with DatetimeIndex.
        oos_ratio: Fraction of bars to reserve for OOS (default 0.2 = 20%).
        oos_min_bars: If OOS segment would have fewer bars, return None for OOS
                      (OOS validation skipped, IS = full dataset).
        warmup_bars: Extra bars prepended to OOS for indicator warm-up.

    Returns:
        Tuple of:
            - is_ohlcv: IS DataFrame (used for optimization)
            - oos_ohlcv: OOS DataFrame with warmup prepended, or None if too short
            - split_info: Dict with split metadata for response/logging
    """
    n = len(ohlcv)
    n_oos = max(int(n * oos_ratio), 1)
    n_is = n - n_oos

    if n_oos < oos_min_bars:
        return (
            ohlcv,
            None,
            {
                "oos_skipped": True,
                "reason": f"OOS segment too short: {n_oos} bars < oos_min_bars={oos_min_bars}",
                "n_total": n,
                "n_is": n,
                "n_oos": 0,
            },
        )

    is_ohlcv = ohlcv.iloc[:n_is]

    # OOS with warmup prepended (for indicator convergence)
    warmup_start = max(0, n_is - warmup_bars)
    oos_with_warmup = ohlcv.iloc[warmup_start:]
    oos_cutoff_ts = ohlcv.index[n_is]  # first bar of actual OOS

    split_info = {
        "oos_skipped": False,
        "n_total": n,
        "n_is": n_is,
        "n_oos": n_oos,
        "n_oos_warmup": n_is - warmup_start,
        "is_start": str(ohlcv.index[0]),
        "is_end": str(ohlcv.index[n_is - 1]),
        "oos_start": str(oos_cutoff_ts),
        "oos_end": str(ohlcv.index[-1]),
        "oos_cutoff_ts": str(oos_cutoff_ts),
    }

    return is_ohlcv, oos_with_warmup, split_info


def run_oos_validation(
    top_results: list[dict[str, Any]],
    base_graph: dict[str, Any],
    oos_ohlcv: pd.DataFrame,
    config_params: dict[str, Any],
    oos_cutoff_ts: str,
    n_top: int = 5,
) -> list[dict[str, Any]]:
    """
    Re-run top-N IS results on OOS data and attach OOS metrics.

    Mutates top_results in-place: adds ``oos_*`` keys to each result dict.
    Results that fail OOS backtest get oos_score=None.

    Args:
        top_results: List of result dicts from IS optimization (sorted by IS score).
        base_graph: Base strategy graph.
        oos_ohlcv: OOS DataFrame (with warmup prepended).
        config_params: Backtest config params (IS version — will clone with OOS cutoff).
        oos_cutoff_ts: Timestamp string where actual OOS starts (warmup cutoff).
        n_top: How many top results to validate (default 5).

    Returns:
        top_results with OOS metrics attached.
    """
    oos_config = {**config_params, "warmup_cutoff": oos_cutoff_ts}

    from loguru import logger as _loguru_logger

    _loguru_logger.disable("backend.backtesting")
    _loguru_logger.disable("backend.core")
    try:
        _run_oos_validation_inner(top_results, base_graph, oos_ohlcv, oos_config, config_params, n_top)
    finally:
        _loguru_logger.enable("backend.backtesting")
        _loguru_logger.enable("backend.core")

    return top_results


def _run_oos_validation_inner(
    top_results: list[dict[str, Any]],
    base_graph: dict[str, Any],
    oos_ohlcv: pd.DataFrame,
    oos_config: dict[str, Any],
    config_params: dict[str, Any],
    n_top: int,
) -> None:
    for result in top_results[:n_top]:
        params = result.get("params", {})
        if not params:
            continue

        modified_graph = clone_graph_with_params(base_graph, params)
        oos_result = run_builder_backtest(modified_graph, oos_ohlcv, oos_config)

        if oos_result is None:
            result["oos_score"] = None
            result["oos_sharpe_ratio"] = None
            result["oos_total_return"] = None
            result["oos_max_drawdown"] = None
            result["oos_win_rate"] = None
            result["oos_total_trades"] = None
            result["oos_degradation_pct"] = None
            continue

        _oos_metric = config_params.get("optimize_metric", "sharpe_ratio")
        oos_score = _compress_score(
            calculate_composite_score(oos_result, _oos_metric),
            _oos_metric,
        )
        is_score = result.get("score", 0) or 0

        result["oos_score"] = oos_score
        result["oos_sharpe_ratio"] = oos_result.get("sharpe_ratio")
        result["oos_total_return"] = oos_result.get("total_return")
        result["oos_max_drawdown"] = oos_result.get("max_drawdown")
        result["oos_win_rate"] = oos_result.get("win_rate")
        result["oos_total_trades"] = oos_result.get("total_trades")

        # OOS degradation: how much worse OOS vs IS (in %)
        # Positive number = deterioration, negative = OOS better than IS
        if abs(is_score) > 1e-9:
            result["oos_degradation_pct"] = round((is_score - oos_score) / abs(is_score) * 100, 1)
        else:
            result["oos_degradation_pct"] = None


# =============================================================================
# PARAMETER EXTRACTION FROM GRAPH
# =============================================================================

# Default optimization ranges per indicator block type
DEFAULT_PARAM_RANGES: dict[str, dict[str, dict[str, Any]]] = {
    "rsi": {
        # period: extended to 100 — slow RSI (period 50-100) can outperform on higher TFs
        "period": {"type": "int", "low": 7, "high": 100, "step": 1, "default": 14},
        # Range filter bounds (long) — step=2 for fine coverage
        "long_rsi_more": {"type": "float", "low": 5, "high": 60, "step": 2, "default": 30},
        "long_rsi_less": {"type": "float", "low": 50, "high": 95, "step": 2, "default": 70},
        # Range filter bounds (short) — step=2 for fine coverage
        "short_rsi_less": {"type": "float", "low": 50, "high": 95, "step": 2, "default": 70},
        "short_rsi_more": {"type": "float", "low": 5, "high": 60, "step": 2, "default": 30},
        # Cross levels: wide range, fine step=1 — Bayesian optimizer explores efficiently
        "cross_long_level": {"type": "float", "low": 15, "high": 85, "step": 1, "default": 45},
        "cross_short_level": {"type": "float", "low": 15, "high": 85, "step": 1, "default": 55},
        # Cross memory
        "cross_memory_bars": {"type": "int", "low": 1, "high": 20, "step": 1, "default": 5},
        # Legacy (backward compatibility — only used when no new mode is enabled)
        "overbought": {"type": "int", "low": 55, "high": 90, "step": 1, "default": 70},
        "oversold": {"type": "int", "low": 10, "high": 45, "step": 1, "default": 30},
    },
    "macd": {
        "fast_period": {"type": "int", "low": 5, "high": 20, "step": 1, "default": 12},
        "slow_period": {"type": "int", "low": 15, "high": 50, "step": 1, "default": 26},
        "signal_period": {"type": "int", "low": 3, "high": 15, "step": 1, "default": 9},
        # Cross with Level (Zero Line)
        "macd_cross_zero_level": {"type": "float", "low": -100.0, "high": 100.0, "step": 1.0, "default": 0},
        # Signal Memory
        "signal_memory_bars": {"type": "int", "low": 1, "high": 20, "step": 1, "default": 5},
    },
    "ema": {
        "period": {"type": "int", "low": 3, "high": 200, "step": 1, "default": 20},
    },
    "sma": {
        "period": {"type": "int", "low": 3, "high": 200, "step": 1, "default": 50},
    },
    "bollinger": {
        "period": {"type": "int", "low": 5, "high": 50, "step": 1, "default": 20},
        "std_dev": {"type": "float", "low": 1.0, "high": 4.0, "step": 0.1, "default": 2.0},
    },
    "supertrend": {
        # period < 5 → ATR becomes noise-dominated (1–4 bars), direction
        # flips every bar → block emits pure noise. min=5 is the floor that
        # keeps ATR statistically meaningful on 15m+ timeframes.
        "period": {"type": "int", "low": 5, "high": 30, "step": 1, "default": 10},
        # multiplier > 6 → ATR-bands wider than typical bar range → direction
        # never flips → block disabled. Realistic range on liquid crypto.
        "multiplier": {"type": "float", "low": 0.5, "high": 6.0, "step": 0.25, "default": 3.0},
    },
    "stochastic": {
        "stoch_k_length": {"type": "int", "low": 3, "high": 30, "step": 1, "default": 14},
        "stoch_k_smoothing": {"type": "int", "low": 1, "high": 7, "step": 1, "default": 3},
        "stoch_d_smoothing": {"type": "int", "low": 1, "high": 7, "step": 1, "default": 3},
        "long_stoch_d_more": {"type": "int", "low": 1, "high": 40, "step": 1, "default": 20},
        "long_stoch_d_less": {"type": "int", "low": 20, "high": 60, "step": 1, "default": 40},
        "short_stoch_d_less": {"type": "int", "low": 50, "high": 99, "step": 1, "default": 80},
        "short_stoch_d_more": {"type": "int", "low": 40, "high": 90, "step": 1, "default": 60},
        "stoch_cross_level_long": {"type": "int", "low": 5, "high": 40, "step": 1, "default": 20},
        "stoch_cross_level_short": {"type": "int", "low": 60, "high": 95, "step": 1, "default": 80},
        "stoch_cross_memory_bars": {"type": "int", "low": 1, "high": 20, "step": 1, "default": 5},
        "stoch_kd_memory_bars": {"type": "int", "low": 1, "high": 20, "step": 1, "default": 5},
    },
    "cci": {
        "period": {"type": "int", "low": 10, "high": 30, "step": 1, "default": 20},
    },
    "atr": {
        "period": {"type": "int", "low": 7, "high": 21, "step": 1, "default": 14},
    },
    "adx": {
        "period": {"type": "int", "low": 7, "high": 21, "step": 1, "default": 14},
    },
    "williams_r": {
        "period": {"type": "int", "low": 7, "high": 21, "step": 1, "default": 14},
    },
    "static_sltp": {
        "stop_loss_percent": {"type": "float", "low": 0.5, "high": 20.0, "step": 0.25, "default": 2.0},
        "take_profit_percent": {"type": "float", "low": 0.5, "high": 20.0, "step": 0.25, "default": 2.0},
        "breakeven_activation_percent": {"type": "float", "low": 0.1, "high": 5.0, "step": 0.1, "default": 0.5},
        "new_breakeven_sl_percent": {"type": "float", "low": 0.01, "high": 0.5, "step": 0.01, "default": 0.1},
    },
    "trailing_stop_exit": {
        "activation_percent": {"type": "float", "low": 0.5, "high": 3.0, "step": 0.25, "default": 1.0},
        "trailing_percent": {"type": "float", "low": 0.25, "high": 2.0, "step": 0.25, "default": 0.5},
    },
    # --- Extended indicator ranges ---
    "ichimoku": {
        "tenkan_period": {"type": "int", "low": 5, "high": 20, "step": 1, "default": 9},
        "kijun_period": {"type": "int", "low": 15, "high": 40, "step": 1, "default": 26},
        "senkou_b_period": {"type": "int", "low": 30, "high": 65, "step": 1, "default": 52},
    },
    "parabolic_sar": {
        "start": {"type": "float", "low": 0.01, "high": 0.05, "step": 0.005, "default": 0.02},
        "increment": {"type": "float", "low": 0.01, "high": 0.05, "step": 0.005, "default": 0.02},
        "max_value": {"type": "float", "low": 0.1, "high": 0.4, "step": 0.05, "default": 0.2},
    },
    "aroon": {
        "period": {"type": "int", "low": 10, "high": 50, "step": 5, "default": 25},
    },
    "qqe": {
        "rsi_period": {"type": "int", "low": 5, "high": 25, "step": 1, "default": 14},
        "qqe_factor": {"type": "float", "low": 2.0, "high": 6.0, "step": 0.5, "default": 4.238},
        "smoothing_period": {"type": "int", "low": 3, "high": 10, "step": 1, "default": 5},
        "qqe_signal_memory_bars": {"type": "int", "low": 1, "high": 20, "step": 1, "default": 5},
    },
    "keltner": {
        "ema_period": {"type": "int", "low": 10, "high": 40, "step": 5, "default": 20},
        "atr_period": {"type": "int", "low": 5, "high": 20, "step": 1, "default": 10},
        "multiplier": {"type": "float", "low": 1.0, "high": 4.0, "step": 0.5, "default": 2.0},
    },
    "donchian": {
        "period": {"type": "int", "low": 10, "high": 50, "step": 5, "default": 20},
    },
    "cmf": {
        "period": {"type": "int", "low": 10, "high": 30, "step": 5, "default": 20},
    },
    # --- DCA / Entry Refinement ---
    "dca": {
        "grid_size_percent": {"type": "int", "low": 5, "high": 30, "step": 1, "default": 15},
        "order_count": {"type": "int", "low": 3, "high": 15, "step": 1, "default": 5},
        "martingale_coefficient": {"type": "float", "low": 1.0, "high": 1.8, "step": 0.1, "default": 1.0},
        "log_steps_coefficient": {"type": "float", "low": 0.5, "high": 2.0, "step": 0.1, "default": 1.0},
        "first_order_offset": {"type": "float", "low": 0, "high": 5, "step": 0.5, "default": 0},
    },
    # --- Universal filter/indicator blocks ---
    "atr_volatility": {
        "atr_length1": {"type": "int", "low": 5, "high": 50, "step": 5, "default": 20},
        "atr_length2": {"type": "int", "low": 50, "high": 200, "step": 10, "default": 100},
        "atr_diff_percent": {"type": "float", "low": 0, "high": 50, "step": 5, "default": 10},
    },
    "volume_filter": {
        "vol_length1": {"type": "int", "low": 5, "high": 50, "step": 5, "default": 20},
        "vol_length2": {"type": "int", "low": 50, "high": 200, "step": 10, "default": 100},
        "vol_diff_percent": {"type": "float", "low": 0, "high": 50, "step": 5, "default": 10},
    },
    "highest_lowest_bar": {
        "hl_lookback_bars": {"type": "int", "low": 5, "high": 50, "step": 5, "default": 10},
        "hl_price_percent": {"type": "float", "low": 0, "high": 5, "step": 0.5, "default": 0},
        "hl_atr_percent": {"type": "float", "low": 0, "high": 10, "step": 1, "default": 0},
        "atr_hl_length": {"type": "int", "low": 10, "high": 100, "step": 10, "default": 50},
    },
    "two_mas": {
        "ma1_length": {"type": "int", "low": 10, "high": 100, "step": 5, "default": 50},
        "ma2_length": {"type": "int", "low": 50, "high": 200, "step": 10, "default": 100},
        "ma_cross_memory_bars": {"type": "int", "low": 1, "high": 20, "step": 1, "default": 5},
    },
    "accumulation_areas": {
        "backtracking_interval": {"type": "int", "low": 10, "high": 100, "step": 5, "default": 30},
        "min_bars_to_execute": {"type": "int", "low": 2, "high": 20, "step": 1, "default": 5},
    },
    "keltner_bollinger": {
        "keltner_length": {"type": "int", "low": 5, "high": 50, "step": 5, "default": 14},
        "keltner_mult": {"type": "float", "low": 0.5, "high": 5.0, "step": 0.5, "default": 1.5},
        "bb_length": {"type": "int", "low": 10, "high": 50, "step": 5, "default": 20},
        "bb_deviation": {"type": "float", "low": 1.0, "high": 4.0, "step": 0.5, "default": 2.0},
    },
    "rvi_filter": {
        "rvi_length": {"type": "int", "low": 5, "high": 30, "step": 1, "default": 10},
        "rvi_ma_length": {"type": "int", "low": 1, "high": 10, "step": 1, "default": 2},
        "rvi_long_more": {"type": "float", "low": -50, "high": 30, "step": 5, "default": 1},
        "rvi_long_less": {"type": "float", "low": 20, "high": 80, "step": 5, "default": 50},
        "rvi_short_less": {"type": "float", "low": 50, "high": 100, "step": 5, "default": 100},
        "rvi_short_more": {"type": "float", "low": 20, "high": 80, "step": 5, "default": 50},
    },
    "mfi_filter": {
        "mfi_length": {"type": "int", "low": 5, "high": 30, "step": 1, "default": 14},
        "mfi_long_more": {"type": "float", "low": 0, "high": 40, "step": 5, "default": 1},
        "mfi_long_less": {"type": "float", "low": 20, "high": 80, "step": 5, "default": 60},
        "mfi_short_less": {"type": "float", "low": 60, "high": 100, "step": 5, "default": 100},
        "mfi_short_more": {"type": "float", "low": 20, "high": 80, "step": 5, "default": 50},
    },
    "cci_filter": {
        "cci_length": {"type": "int", "low": 5, "high": 30, "step": 1, "default": 14},
        "cci_long_more": {"type": "float", "low": -400, "high": 0, "step": 50, "default": -400},
        "cci_long_less": {"type": "float", "low": 0, "high": 400, "step": 50, "default": 400},
        "cci_short_less": {"type": "float", "low": 0, "high": 400, "step": 50, "default": 400},
        "cci_short_more": {"type": "float", "low": -400, "high": 200, "step": 50, "default": 10},
    },
    "momentum_filter": {
        "momentum_length": {"type": "int", "low": 5, "high": 30, "step": 1, "default": 14},
        "momentum_long_more": {"type": "float", "low": -200, "high": 0, "step": 10, "default": -100},
        "momentum_long_less": {"type": "float", "low": 0, "high": 100, "step": 10, "default": 10},
        "momentum_short_less": {"type": "float", "low": 0, "high": 200, "step": 10, "default": 95},
        "momentum_short_more": {"type": "float", "low": -100, "high": 50, "step": 10, "default": -30},
    },
    "divergence": {
        "pivot_interval": {"type": "int", "low": 3, "high": 20, "step": 1, "default": 9},
        "rsi_period": {"type": "int", "low": 5, "high": 30, "step": 1, "default": 14},
        "stoch_length": {"type": "int", "low": 5, "high": 30, "step": 1, "default": 14},
        "momentum_length": {"type": "int", "low": 5, "high": 20, "step": 1, "default": 10},
        "cmf_period": {"type": "int", "low": 10, "high": 40, "step": 5, "default": 21},
        "mfi_length": {"type": "int", "low": 5, "high": 30, "step": 1, "default": 14},
        "keep_diver_signal_memory_bars": {"type": "int", "low": 1, "high": 20, "step": 1, "default": 5},
    },
    # --- Filter ranges ---
    "rsi_filter": {
        "rsi_period": {"type": "int", "low": 5, "high": 30, "step": 1, "default": 14},
    },
    "supertrend_filter": {
        "atr_period": {"type": "int", "low": 5, "high": 20, "step": 1, "default": 10},
        "atr_multiplier": {"type": "float", "low": 1.0, "high": 5.0, "step": 0.5, "default": 3.0},
    },
    "macd_filter": {
        "macd_fast_length": {"type": "int", "low": 8, "high": 16, "step": 1, "default": 12},
        "macd_slow_length": {"type": "int", "low": 20, "high": 30, "step": 1, "default": 26},
        "macd_signal_smoothing": {"type": "int", "low": 6, "high": 12, "step": 1, "default": 9},
    },
    "stochastic_filter": {
        "stoch_k_length": {"type": "int", "low": 5, "high": 21, "step": 1, "default": 14},
        "stoch_k_smoothing": {"type": "int", "low": 1, "high": 5, "step": 1, "default": 3},
        "stoch_d_smoothing": {"type": "int", "low": 1, "high": 5, "step": 1, "default": 3},
    },
    "two_ma_filter": {
        "ma1_length": {"type": "int", "low": 10, "high": 100, "step": 5, "default": 50},
        "ma2_length": {"type": "int", "low": 50, "high": 200, "step": 10, "default": 100},
    },
    "qqe_filter": {
        "qqe_rsi_length": {"type": "int", "low": 5, "high": 25, "step": 1, "default": 14},
        "qqe_rsi_smoothing": {"type": "int", "low": 3, "high": 10, "step": 1, "default": 5},
        "qqe_delta_multiplier": {"type": "float", "low": 2.0, "high": 8.0, "step": 0.5, "default": 5.1},
    },
    # --- Exit ranges ---
    "atr_exit": {
        "atr_sl_period": {"type": "int", "low": 50, "high": 200, "step": 10, "default": 140},
        "atr_sl_multiplier": {"type": "float", "low": 1.0, "high": 8.0, "step": 0.5, "default": 4.0},
        "atr_tp_period": {"type": "int", "low": 50, "high": 200, "step": 10, "default": 140},
        "atr_tp_multiplier": {"type": "float", "low": 1.0, "high": 8.0, "step": 0.5, "default": 4.0},
    },
    "multi_tp_exit": {
        "tp1_percent": {"type": "float", "low": 0.5, "high": 3.0, "step": 0.25, "default": 1.0},
        "tp2_percent": {"type": "float", "low": 1.0, "high": 5.0, "step": 0.5, "default": 2.0},
        "tp3_percent": {"type": "float", "low": 2.0, "high": 10.0, "step": 0.5, "default": 3.0},
        "tp1_close_percent": {"type": "int", "low": 20, "high": 50, "step": 5, "default": 33},
        "tp2_close_percent": {"type": "int", "low": 20, "high": 50, "step": 5, "default": 33},
        "tp3_close_percent": {"type": "int", "low": 20, "high": 50, "step": 5, "default": 34},
    },
    # --- Close-by-Indicator exit ranges ---
    "close_by_time": {
        "bars_since_entry": {"type": "int", "low": 3, "high": 50, "step": 1, "default": 10},
        # min_profit_percent extended to 25: must be >= take_profit_percent + 2 to avoid
        # premature time-exit before TP fires. Wide range needed for large TP configs.
        "min_profit_percent": {"type": "float", "low": 0, "high": 25, "step": 0.5, "default": 0},
    },
    "close_channel": {
        "keltner_length": {"type": "int", "low": 5, "high": 50, "step": 5, "default": 14},
        "keltner_mult": {"type": "float", "low": 0.5, "high": 5.0, "step": 0.5, "default": 1.5},
        "bb_length": {"type": "int", "low": 10, "high": 50, "step": 5, "default": 20},
        "bb_deviation": {"type": "float", "low": 1.0, "high": 4.0, "step": 0.5, "default": 2.0},
    },
    "close_ma_cross": {
        "ma1_length": {"type": "int", "low": 5, "high": 30, "step": 1, "default": 10},
        "ma2_length": {"type": "int", "low": 15, "high": 60, "step": 5, "default": 30},
        "min_profit_percent": {"type": "float", "low": 0, "high": 5, "step": 0.5, "default": 1},
    },
    "close_rsi": {
        "rsi_close_length": {"type": "int", "low": 5, "high": 30, "step": 1, "default": 14},
        "rsi_long_more": {"type": "float", "low": 60, "high": 85, "step": 5, "default": 70},
        "rsi_long_less": {"type": "float", "low": 90, "high": 100, "step": 5, "default": 100},
        "rsi_short_less": {"type": "float", "low": 15, "high": 40, "step": 5, "default": 30},
        "rsi_short_more": {"type": "float", "low": 0, "high": 10, "step": 1, "default": 1},
        "rsi_cross_long_level": {"type": "float", "low": 60, "high": 85, "step": 5, "default": 70},
        "rsi_cross_short_level": {"type": "float", "low": 15, "high": 40, "step": 5, "default": 30},
    },
    "close_stochastic": {
        "stoch_close_k_length": {"type": "int", "low": 5, "high": 30, "step": 1, "default": 14},
        "stoch_close_k_smoothing": {"type": "int", "low": 1, "high": 5, "step": 1, "default": 3},
        "stoch_close_d_smoothing": {"type": "int", "low": 1, "high": 5, "step": 1, "default": 3},
        "stoch_long_more": {"type": "float", "low": 70, "high": 90, "step": 5, "default": 80},
        "stoch_long_less": {"type": "float", "low": 90, "high": 100, "step": 5, "default": 100},
        "stoch_short_less": {"type": "float", "low": 10, "high": 30, "step": 5, "default": 20},
        "stoch_short_more": {"type": "float", "low": 0, "high": 10, "step": 1, "default": 1},
        "stoch_cross_long_level": {"type": "float", "low": 70, "high": 90, "step": 5, "default": 80},
        "stoch_cross_short_level": {"type": "float", "low": 10, "high": 30, "step": 5, "default": 20},
    },
    "close_psar": {
        "psar_start": {"type": "float", "low": 0.01, "high": 0.05, "step": 0.005, "default": 0.02},
        "psar_increment": {"type": "float", "low": 0.01, "high": 0.05, "step": 0.005, "default": 0.02},
        "psar_maximum": {"type": "float", "low": 0.1, "high": 0.4, "step": 0.05, "default": 0.2},
        "psar_close_nth_bar": {"type": "int", "low": 1, "high": 10, "step": 1, "default": 1},
    },
    "chandelier_exit": {
        "atr_period": {"type": "int", "low": 10, "high": 30, "step": 1, "default": 22},
        "atr_multiplier": {"type": "float", "low": 1.5, "high": 5.0, "step": 0.5, "default": 3.0},
    },
    "break_even_exit": {
        "activation_profit_percent": {"type": "float", "low": 0.5, "high": 3.0, "step": 0.25, "default": 1.0},
        "move_to_profit_percent": {"type": "float", "low": 0.0, "high": 0.5, "step": 0.05, "default": 0.1},
    },
    # --- MA variants (missing from original set) ---
    "wma": {
        "period": {"type": "int", "low": 5, "high": 50, "step": 1, "default": 20},
    },
    "dema": {
        "period": {"type": "int", "low": 5, "high": 50, "step": 1, "default": 20},
    },
    "tema": {
        "period": {"type": "int", "low": 5, "high": 50, "step": 1, "default": 20},
    },
    "hull_ma": {
        "period": {"type": "int", "low": 5, "high": 50, "step": 1, "default": 20},
    },
    # --- Oscillator variants ---
    "stoch_rsi": {
        "rsi_period": {"type": "int", "low": 5, "high": 25, "step": 1, "default": 14},
        "stoch_period": {"type": "int", "low": 5, "high": 25, "step": 1, "default": 14},
        "k_smooth": {"type": "int", "low": 1, "high": 5, "step": 1, "default": 3},
        "d_smooth": {"type": "int", "low": 1, "high": 5, "step": 1, "default": 3},
        "stoch_rsi_cross_level_long": {"type": "float", "low": 10, "high": 30, "step": 5, "default": 20},
        "stoch_rsi_cross_level_short": {"type": "float", "low": 70, "high": 90, "step": 5, "default": 80},
    },
    "roc": {
        "period": {"type": "int", "low": 5, "high": 30, "step": 1, "default": 14},
    },
    "cmo": {
        "period": {"type": "int", "low": 5, "high": 30, "step": 1, "default": 14},
    },
    "rvi": {
        "period": {"type": "int", "low": 5, "high": 20, "step": 1, "default": 10},
    },
    "mfi": {
        "period": {"type": "int", "low": 5, "high": 30, "step": 1, "default": 14},
    },
}


def extract_optimizable_params(graph: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Extract all optimizable parameters from a strategy graph.

    Scans blocks for indicator/exit types and returns parameter specs
    with default ranges based on block type.

    Args:
        graph: Strategy graph dict with 'blocks' key.

    Returns:
        List of parameter specs, each containing:
            - block_id: ID of the block
            - block_type: Type of the block (rsi, macd, etc.)
            - block_name: Display name of the block
            - param_key: Parameter name within the block
            - param_path: Full path "blockId.paramKey" for graph modification
            - type: "int" or "float"
            - low: Minimum value
            - high: Maximum value
            - step: Step size
            - default: Default value
            - current_value: Currently set value in the graph
    """
    blocks = graph.get("blocks", [])
    params = []

    # Build set of block IDs that participate in at least one connection.
    # Disconnected blocks have no effect on backtest results — optimizing their
    # params wastes Optuna trial budget and introduces noise into the surrogate model.
    connections = graph.get("connections", [])
    _connected_block_ids: set[str] = set()
    for _conn in connections:
        _src = _conn.get("source") or {}
        _tgt = _conn.get("target") or {}
        _raw_sid = _src.get("blockId") if isinstance(_src, dict) else None
        _raw_sid = _raw_sid or _conn.get("source_block_id", "")
        _raw_tid = _tgt.get("blockId") if isinstance(_tgt, dict) else None
        _raw_tid = _raw_tid or _conn.get("target_block_id", "")
        # Guard: source/target_block_id may be a nested dict if frontend sends {blockId, portId}
        _sid = _raw_sid.get("blockId", "") if isinstance(_raw_sid, dict) else (_raw_sid or "")
        _tid = _raw_tid.get("blockId", "") if isinstance(_raw_tid, dict) else (_raw_tid or "")
        if isinstance(_sid, str) and _sid:
            _connected_block_ids.add(_sid)
        if isinstance(_tid, str) and _tid:
            _connected_block_ids.add(_tid)

    for block in blocks:
        block_id = block.get("id", "")
        block_type = block.get("type", "")
        block_name = block.get("name", block_type)
        block_params = block.get("params") or block.get("config") or {}

        # Skip blocks that have no connections — their params don't affect backtest results.
        # Exception: strategy node itself (type=="strategy") is the sink, not a source — always skip.
        # Only skip disconnected non-strategy blocks (strategy type has no params to optimize anyway).
        if block_type != "strategy" and _connected_block_ids and block_id not in _connected_block_ids:
            logger.debug(
                f"[OptExtract] Skipping disconnected block '{block_id}' (type='{block_type}') "
                f"— not in any connection, params have no effect on backtest"
            )
            continue

        # User-provided optimization overrides from the UI (block.optimizationParams)
        user_opt_params: dict[str, dict[str, Any]] = block.get("optimizationParams") or {}

        # Track params the user EXPLICITLY disabled so DEFAULT_PARAM_RANGES doesn't re-add them.
        # Without this set, a param with {enabled: False} would be removed from user_opt_params
        # but then re-included from DEFAULT_PARAM_RANGES with default ranges.
        user_explicitly_disabled: set[str] = set()

        # Validate user-provided optimizationParams format
        if user_opt_params:
            _validated: dict[str, dict[str, Any]] = {}
            for pk, pv in user_opt_params.items():
                if not isinstance(pv, dict):
                    logger.warning(
                        f"[OptExtract] Invalid optimizationParams format for block '{block_id}' "
                        f"param '{pk}': expected dict with {{low, high, step}}, got {type(pv).__name__}. Skipping."
                    )
                    continue

                # Normalize frontend format: frontend stores {min, max, step, enabled}
                # backend expects {low, high, step, enabled}
                if "low" not in pv and "min" in pv:
                    pv = {**pv, "low": pv["min"]}
                if "high" not in pv and "max" in pv:
                    pv = {**pv, "high": pv["max"]}

                required_keys = {"low", "high"}
                if not required_keys.issubset(pv.keys()):
                    logger.warning(
                        f"[OptExtract] optimizationParams for block '{block_id}' param '{pk}' "
                        f"missing required keys {required_keys - pv.keys()}. Skipping."
                    )
                    continue

                # Skip if explicitly disabled — record it so DEFAULT_PARAM_RANGES won't re-add it
                if not pv.get("enabled", True):
                    user_explicitly_disabled.add(pk)
                    continue

                if pv["low"] > pv["high"]:
                    logger.warning(
                        f"[OptExtract] optimizationParams for block '{block_id}' param '{pk}': "
                        f"low ({pv['low']}) > high ({pv['high']}). Swapping."
                    )
                    pv["low"], pv["high"] = pv["high"], pv["low"]
                _validated[pk] = pv
            user_opt_params = _validated

        # Check if this block type has known optimizable params
        type_ranges = DEFAULT_PARAM_RANGES.get(block_type, {})
        if not type_ranges and not user_opt_params:
            continue

        # Track which param_keys have been added so we don't duplicate
        added_param_keys: set[str] = set()

        for param_key, range_spec in type_ranges.items():
            current_value = block_params.get(param_key, range_spec["default"])

            # If the user explicitly DISABLED this param, never include it from defaults
            if param_key in user_explicitly_disabled:
                continue

            # If the user explicitly enabled this param in optimizationParams,
            # always include it — skip mode-flag checks (user knows what they want).
            user_explicitly_enabled = param_key in user_opt_params

            # Skip RSI params for disabled modes to avoid wasted optimization iterations
            # — UNLESS the user explicitly marked this param as enabled in optimizationParams
            if block_type == "rsi" and not user_explicitly_enabled:
                if param_key in ("long_rsi_more", "long_rsi_less") and not block_params.get("use_long_range", False):
                    continue
                if param_key in ("short_rsi_less", "short_rsi_more") and not block_params.get("use_short_range", False):
                    continue
                if param_key in ("cross_long_level", "cross_short_level") and not block_params.get(
                    "use_cross_level", False
                ):
                    continue
                if param_key == "cross_memory_bars" and not block_params.get("use_cross_memory", False):
                    continue
                # Skip legacy overbought/oversold if new modes are active
                has_new_mode = (
                    block_params.get("use_long_range", False)
                    or block_params.get("use_short_range", False)
                    or block_params.get("use_cross_level", False)
                )
                if param_key in ("overbought", "oversold") and has_new_mode:
                    continue

            # Skip MACD params for disabled modes — UNLESS user explicitly enabled
            if block_type == "macd" and not user_explicitly_enabled:
                if param_key == "macd_cross_zero_level" and not block_params.get("use_macd_cross_zero", False):
                    continue
                if param_key == "signal_memory_bars" and block_params.get("disable_signal_memory", False):
                    continue
                # Skip signal_memory_bars if no signal mode is enabled
                has_signal_mode = block_params.get("use_macd_cross_zero", False) or block_params.get(
                    "use_macd_cross_signal", False
                )
                if param_key == "signal_memory_bars" and not has_signal_mode:
                    continue

            # Skip static_sltp breakeven params if breakeven is not activated — UNLESS user explicitly enabled
            if (
                block_type == "static_sltp"
                and not user_explicitly_enabled
                and param_key in ("breakeven_activation_percent", "new_breakeven_sl_percent")
                and not block_params.get("activate_breakeven", False)
            ):
                continue

            # Merge user-provided optimizationParams over defaults
            user_override = user_opt_params.get(param_key, {})
            effective_low = user_override.get("low", range_spec["low"])
            effective_high = user_override.get("high", range_spec["high"])
            effective_step = user_override.get("step", range_spec["step"])
            effective_type = user_override.get("type", range_spec["type"])

            # Normalize step for int params: frontend may store float step (e.g. 0.1)
            # which would produce step=0 after int() conversion → range() crash
            step_was_clamped = False
            original_step = effective_step
            if effective_type == "int" and float(effective_step) < 1:
                logger.warning(
                    f"[OptExtract] Block '{block_id}' param '{param_key}': "
                    f"type=int but step={effective_step} < 1 — clamping to 1"
                )
                effective_step = 1
                step_was_clamped = True

            params.append(
                {
                    "block_id": block_id,
                    "block_type": block_type,
                    "block_name": block_name,
                    "param_key": param_key,
                    "param_path": f"{block_id}.{param_key}",
                    "type": effective_type,
                    "low": effective_low,
                    "high": effective_high,
                    "step": effective_step,
                    "default": range_spec["default"],
                    "current_value": current_value,
                    # Recommended ranges (backend defaults) — preserved even when
                    # user overrides `low`/`high`. Frontend can compare current
                    # range to recommended and highlight degenerate user ranges
                    # (e.g. supertrend.multiplier user=1..40 vs recommended=0.5..6).
                    "recommended_low": range_spec["low"],
                    "recommended_high": range_spec["high"],
                    # Carry clamping info so callers can surface warnings to the user
                    "step_clamped": step_was_clamped,
                    "original_step": original_step if step_was_clamped else effective_step,
                }
            )
            added_param_keys.add(param_key)

        # Second pass: include any user_opt_params keys that were NOT in type_ranges.
        # This handles custom/extra params the user enabled that have no DEFAULT_PARAM_RANGES
        # entry for this block type (rare, but valid).
        for param_key, user_override in user_opt_params.items():
            if param_key in added_param_keys:
                continue  # already added above
            current_value = block_params.get(param_key, user_override.get("low", 0))
            second_pass_type = user_override.get("type", "float")
            second_pass_step = user_override.get("step", 1)
            # Normalize step for int params (same guard as first pass)
            if second_pass_type == "int" and float(second_pass_step) < 1:
                logger.warning(
                    f"[OptExtract] Block '{block_id}' param '{param_key}' (extra): "
                    f"type=int but step={second_pass_step} < 1 — clamping to 1"
                )
                second_pass_step = 1
            params.append(
                {
                    "block_id": block_id,
                    "block_type": block_type,
                    "block_name": block_name,
                    "param_key": param_key,
                    "param_path": f"{block_id}.{param_key}",
                    "type": second_pass_type,
                    "low": user_override["low"],
                    "high": user_override["high"],
                    "step": second_pass_step,
                    "default": current_value,
                    "current_value": current_value,
                }
            )
            logger.debug(
                f"[OptExtract] Added user-enabled param '{block_id}.{param_key}' "
                f"(not in DEFAULT_PARAM_RANGES for block_type='{block_type}')"
            )

    return params


# =============================================================================
# GRAPH CLONING WITH PARAMETER SUBSTITUTION
# =============================================================================


def clone_graph_with_params(
    base_graph: dict[str, Any],
    param_overrides: dict[str, Any],
) -> dict[str, Any]:
    """
    Deep-clone a strategy graph and apply parameter overrides.

    Args:
        base_graph: Original strategy graph.
        param_overrides: Dict mapping param_path ("blockId.paramKey") to new value.

    Returns:
        Modified copy of the graph with updated block parameters.
    """
    graph = copy.deepcopy(base_graph)
    blocks = graph.get("blocks", [])

    # Build block lookup by ID
    block_map = {b["id"]: b for b in blocks}

    for param_path, value in param_overrides.items():
        parts = param_path.split(".", 1)
        if len(parts) != 2:
            logger.warning(f"Invalid param_path: {param_path}")
            continue

        block_id, param_key = parts
        block = block_map.get(block_id)
        if not block:
            logger.warning(f"Block {block_id} not found in graph")
            continue

        # Ensure params dict exists (handle both 'params' and 'config' keys)
        params_key = "params" if "params" in block else "config"
        if params_key not in block or block[params_key] is None:
            block[params_key] = {}
        block[params_key][param_key] = value

        # Auto-enable mode flags when optimizing mode-gated RSI params.
        # Each param maps to the exact mode flag that gates it.
        # Cross + range can coexist: "RSI crosses level AND is within range".
        if block.get("type") == "rsi":
            rsi_p = block[params_key]
            if param_key in ("cross_long_level", "cross_short_level"):
                rsi_p["use_cross_level"] = True
            elif param_key == "cross_memory_bars":
                rsi_p["use_cross_memory"] = True
            elif param_key in ("long_rsi_more", "long_rsi_less"):
                rsi_p["use_long_range"] = True
            elif param_key in ("short_rsi_more", "short_rsi_less"):
                rsi_p["use_short_range"] = True

        # Auto-enable mode flags for MACD
        if block.get("type") == "macd":
            if param_key == "macd_cross_zero_level":
                block[params_key]["use_macd_cross_zero"] = True
            elif param_key == "signal_memory_bars":
                block[params_key]["disable_signal_memory"] = False

    return graph


# =============================================================================
# PARAMETER COMBINATION GENERATION FOR BUILDER STRATEGIES
# =============================================================================


def generate_builder_param_combinations(
    param_specs: list[dict[str, Any]],
    custom_ranges: list[dict[str, Any]] | None = None,
    search_method: str = "grid",
    max_iterations: int = 0,
    random_seed: int | None = None,
) -> tuple[Any, int, bool]:
    """
    Generate parameter combinations for builder strategy optimization.

    For grid search returns a **lazy iterator** (itertools.product-based) so that
    arbitrarily large grids are fully explored without materialising them all in
    memory at once.  run_builder_grid_search consumes it chunk-by-chunk.

    For random search a materialized list is returned (bounded by max_iterations).

    Args:
        param_specs: List of optimizable params from extract_optimizable_params().
        custom_ranges: User-defined ranges overriding defaults. Each dict has:
                       - param_path: "blockId.paramKey"
                       - low, high, step (optional overrides)
                       - enabled: bool (whether to optimize this param)
        search_method: "grid" or "random".
        max_iterations: Max combos for random search (0 = no limit).
        random_seed: Seed for reproducibility (random search only).

    Returns:
        Tuple of (combos_or_iterator, total_count, was_capped).
        was_capped is always False for grid search (full exhaustive sweep).
    """
    import random as rng_module

    # Merge custom ranges with defaults
    active_specs = _merge_ranges(param_specs, custom_ranges)

    if not active_specs:
        logger.warning("No active parameters to optimize")
        return [{}], 1, False

    # Build per-param value lists
    param_paths: list[str] = []
    value_ranges: list[list] = []

    for spec in active_specs:
        param_paths.append(spec["param_path"])
        low = spec["low"]
        high = spec["high"]
        step = spec["step"]

        if spec["type"] == "int":
            values = list(range(int(low), int(high) + 1, int(step)))
        else:
            values = list(np.arange(float(low), float(high) + float(step) / 2, float(step)))
            values = [round(v, 4) for v in values]

        value_ranges.append(values)

    # Exact total — computed without materialising the product
    total_combinations = 1
    for vr in value_ranges:
        total_combinations *= len(vr)

    # ── Random search: bounded materialised list ─────────────────────────────
    if search_method == "random" and max_iterations > 0:
        n_sample = min(max_iterations, total_combinations)
        if n_sample >= total_combinations:
            # Small enough — full grid, no sampling
            all_combos: list[dict[str, Any]] = [
                dict(zip(param_paths, combo, strict=False)) for combo in product(*value_ranges)
            ]
        else:
            # Lazy reservoir-sample without materialising the full product
            if random_seed is not None:
                rng_module.seed(random_seed)
            sizes = [len(vr) for vr in value_ranges]
            seen: set[tuple[int, ...]] = set()
            sampled: list[tuple] = []
            max_attempts = n_sample * 20
            attempts = 0
            while len(sampled) < n_sample and attempts < max_attempts:
                attempts += 1
                idx = tuple(rng_module.randrange(s) for s in sizes)
                if idx not in seen:
                    seen.add(idx)
                    sampled.append(tuple(vr[i] for vr, i in zip(value_ranges, idx, strict=False)))
            all_combos = [dict(zip(param_paths, combo, strict=False)) for combo in sampled]
        logger.info(f"🎲 Builder Random Search: {len(all_combos):,} of {total_combinations:,}")
        was_capped = len(all_combos) < total_combinations
        return all_combos, total_combinations, was_capped

    # ── Grid search: interleaved round-robin iterator ────────────────────────
    # Problem with plain product(*shuffled_ranges): with 78M combos and 7500
    # iterations budget, product exhausts ALL combos for period[0] before ever
    # visiting period[1].  Under timeout you'd only see a single "period" value.
    #
    # Solution — interleaved (round-robin) sweep:
    #   • Treat param_0 (e.g. "period") as the "outer" axis.
    #   • For each value of param_0, produce one random combo of the remaining
    #     params, cycling through all param_0 values repeatedly.
    #   • This guarantees every distinct value of param_0 appears within the
    #     first len(param_0_values) iterations — no matter when we time out.
    #   • Full exhaustive coverage is still achieved when given enough time:
    #     we track which "inner" combos have been yielded for each param_0 value
    #     and continue until the full grid is done.
    #
    # Memory: O(1) — only the current combo is held in memory.
    logger.info(f"🔢 Builder Grid Search: {total_combinations:,} combinations (interleaved round-robin, seed=42)")

    import random as _rng

    def _interleaved_grid_iter() -> Any:
        rng = _rng.Random(42)  # isolated instance — never affects global state

        if len(value_ranges) == 1:
            # Trivial: single parameter, just yield in shuffled order
            vals = value_ranges[0][:]
            rng.shuffle(vals)
            for v in vals:
                yield {param_paths[0]: v}
            return

        # Outer axis = param_0 (typically the slowest-varying, e.g. "period")
        outer_vals = value_ranges[0][:]
        rng.shuffle(outer_vals)

        inner_ranges = value_ranges[1:]
        inner_paths = param_paths[1:]

        # Pre-shuffle each inner range once for consistent ordering
        shuffled_inner = [v[:] for v in inner_ranges]
        for v in shuffled_inner:
            rng.shuffle(v)

        # For each outer value, keep a separate shuffled iterator over inner combos
        # so that across rounds we don't repeat combos.
        # We build inner combos lazily: outer index → list of remaining inner combos.
        # To stay O(1) in memory we generate them on demand using an index counter.
        inner_total = 1
        for v in inner_ranges:
            inner_total *= len(v)

        # Generate inner combo by linear index (no materialisation)
        inner_sizes = [len(v) for v in shuffled_inner]

        def _inner_combo(linear_idx: int) -> dict:
            """Decode linear index into an inner param combo."""
            combo = {}
            idx = linear_idx
            for path, vals, size in zip(inner_paths, shuffled_inner, inner_sizes, strict=False):
                combo[path] = vals[idx % size]
                idx //= size
            return combo

        # We permute the linear indices for each outer value so that the inner
        # combos are visited in a different random order per outer value — this
        # avoids patterns where the same TP/SL pair always appears first.
        # Memory-efficient: use per-outer seeds instead of materialising full permutations.
        # Each outer[oi] gets seed = 42 + oi, so it's reproducible but independent.
        # We build a lazy Fisher-Yates mapping: track swaps on-the-fly with a dict.
        outer_seeds = [42 + i for i in range(len(outer_vals))]

        def _lazy_perm_index(seed: int, total: int, round_idx: int) -> int:
            """
            Compute the round_idx-th element of a Fisher-Yates shuffle of range(total)
            seeded with `seed`, without materialising the full permutation.

            Uses a dict to remember previous swaps — memory O(round_idx), not O(total).
            """
            # We cache built permutation state per outer value in _perm_cache
            # keyed by seed. Each entry is (rng_state, swaps_dict, next_round).
            if seed not in _perm_cache:
                r = _rng.Random(seed)
                _perm_cache[seed] = (r, {}, 0)  # rng, swaps dict, rounds_done

            r, swaps, rounds_done = _perm_cache[seed]

            # Advance the permutation from rounds_done to round_idx (inclusive)
            while rounds_done <= round_idx:
                i = total - 1 - rounds_done
                j = r.randint(0, i)
                # Swap positions i and j in the virtual array
                vi = swaps.get(i, i)
                vj = swaps.get(j, j)
                swaps[i] = vj
                swaps[j] = vi
                rounds_done += 1

            _perm_cache[seed] = (r, swaps, rounds_done)
            # The value at position round_idx was settled after rounds_done = round_idx+1
            return swaps.get(round_idx, round_idx)

        _perm_cache: dict = {}

        # Round-robin: one inner combo per outer value per round
        # round k → yield outer_vals[0] + inner k-th, outer_vals[1] + inner k-th, …
        for inner_round in range(inner_total):
            for oi, outer_v in enumerate(outer_vals):
                inner_idx = _lazy_perm_index(outer_seeds[oi], inner_total, inner_round)
                inner_combo = _inner_combo(inner_idx)
                yield {param_paths[0]: outer_v, **inner_combo}

    # was_capped=False — grid is always exhaustive
    return _interleaved_grid_iter(), total_combinations, False


def _merge_ranges(
    param_specs: list[dict[str, Any]],
    custom_ranges: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """
    Merge default param specs with user-defined custom ranges.

    Custom ranges can override low/high/step and enable/disable params.

    Matching strategy (in priority order):
    1. Exact param_path match: "block_1772832197062_q10k0.period" == "block_1772832197062_q10k0.period"
    2. Suffix param_key match: custom "rsi_0.period" → param_key="period", matches any spec with param_key="period"
       (when UI sends short-form IDs like "rsi_0" instead of real block IDs)
    """
    if not custom_ranges:
        # Use all defaults as-is
        return param_specs

    # Build lookup by exact param_path
    custom_map: dict[str, dict[str, Any]] = {cr["param_path"]: cr for cr in custom_ranges}

    # Also build fallback lookup by param_key suffix (e.g. "rsi_0.period" → param_key="period")
    # Key: param_key string, Value: list of custom range dicts with that key
    custom_by_key: dict[str, list[dict[str, Any]]] = {}
    for cr in custom_ranges:
        param_path = cr["param_path"]
        dot_idx = param_path.rfind(".")
        param_key = param_path[dot_idx + 1 :] if dot_idx >= 0 else param_path
        custom_by_key.setdefault(param_key, []).append(cr)

    active = []
    for spec in param_specs:
        path = spec["param_path"]
        param_key = spec.get("param_key", path.split(".")[-1])

        # 1. Exact match
        custom = custom_map.get(path)

        # 2. Fallback: match by param_key if exactly one custom range has that key
        if custom is None:
            candidates = custom_by_key.get(param_key, [])
            if len(candidates) == 1:
                custom = candidates[0]
                logger.debug(
                    f"_merge_ranges: fuzzy match '{path}' → '{custom['param_path']}' via param_key='{param_key}'"
                )

        if custom is not None:
            # User explicitly configured this param
            if not custom.get("enabled", True):
                continue  # User disabled this param

            # Override ranges
            merged = {**spec}
            if "low" in custom:
                merged["low"] = custom["low"]
            if "high" in custom:
                merged["high"] = custom["high"]
            if "step" in custom:
                merged["step"] = custom["step"]
            active.append(merged)
        # else: param not in custom_ranges → skip (user only wants to optimize selected params)

    return active


# =============================================================================
# SINGLE BACKTEST WITH BUILDER ADAPTER
# =============================================================================


def run_builder_backtest(
    graph: dict[str, Any],
    ohlcv: pd.DataFrame,
    config_params: dict[str, Any],
    indicator_cache: IndicatorCache | None = None,
) -> dict[str, Any] | None:
    """
    Run a single backtest using StrategyBuilderAdapter.

    Mirrors the normal backtest flow (router.py) so that DCA, SL/TP, close_by_time
    and other block-level configurations are properly applied during optimization.

    Args:
        graph: Strategy graph (already cloned with modified params).
        ohlcv: OHLCV DataFrame.
        config_params: Dict with symbol, interval, initial_capital, leverage,
                       commission, direction, stop_loss, take_profit, etc.
        indicator_cache: Optional IndicatorCache shared across optimization trials.
                         Pass None (default) for standalone backtests.

    Returns:
        Result dict with metrics, or None on failure.
    """
    from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

    try:
        adapter = StrategyBuilderAdapter(graph, indicator_cache=indicator_cache)

        # ── Extract block-level configs (mirrors router.py normal backtest) ──
        block_dca_config = adapter.extract_dca_config()
        has_dca_blocks = adapter.has_dca_blocks()

        dca_enabled = has_dca_blocks or block_dca_config.get("dca_enabled", False)

        # Extract SL/TP / breakeven / close_by_time from blocks
        block_stop_loss: float | None = config_params.get("stop_loss_pct")
        block_take_profit: float | None = config_params.get("take_profit_pct")
        if block_stop_loss:
            block_stop_loss = block_stop_loss / 100.0
        if block_take_profit:
            block_take_profit = block_take_profit / 100.0
        block_breakeven_enabled = False
        block_breakeven_activation_pct = 0.005
        block_breakeven_offset = 0.0
        block_close_only_in_profit = False
        block_sl_type = "average_price"
        block_max_bars_in_trade = 0
        # close_by_time: profit_only requires FallbackEngineV4 (extra_data path).
        # NumbaEngineV2 doesn't read extra_data, so profit_only would be silently ignored.
        block_close_by_time_profit_only = False

        for block in graph.get("blocks", []):
            block_type = block.get("type", "")
            block_params = block.get("params") or block.get("config") or {}
            if block_type == "close_by_time":
                bars_val = block_params.get("bars_since_entry", block_params.get("bars", 0))
                block_max_bars_in_trade = int(bars_val) if bars_val else 0
                block_close_by_time_profit_only = bool(block_params.get("profit_only", False))
            elif block_type == "static_sltp":
                if block_stop_loss is None:
                    sl_val = block_params.get("stop_loss_percent", 1.5)
                    block_stop_loss = sl_val / 100.0
                if block_take_profit is None:
                    tp_val = block_params.get("take_profit_percent", 1.5)
                    block_take_profit = tp_val / 100.0
                block_breakeven_enabled = block_params.get("activate_breakeven", False)
                if block_breakeven_enabled:
                    block_breakeven_activation_pct = block_params.get("breakeven_activation_percent", 0.5) / 100.0
                    block_breakeven_offset = block_params.get("new_breakeven_sl_percent", 0.1) / 100.0
                block_close_only_in_profit = block_params.get("close_only_in_profit", False)
                block_sl_type = block_params.get("sl_type", "average_price")
            elif block_type == "tp_percent" and block_take_profit is None:
                block_take_profit = block_params.get("take_profit_percent", 3.0) / 100.0
            elif block_type == "sl_percent" and block_stop_loss is None:
                block_stop_loss = block_params.get("stop_loss_percent", 1.5) / 100.0

        direction_str = config_params.get("direction", "both")

        # Sync DCA direction to strategy direction
        final_dca_config = block_dca_config.copy()
        final_dca_config["dca_enabled"] = dca_enabled
        if final_dca_config.get("dca_direction", "both") == "both" and direction_str in ("long", "short"):
            final_dca_config["dca_direction"] = direction_str

        # ── Route to DCA engine if DCA blocks are present ──────────────────
        if dca_enabled:
            from backend.backtesting.engines.dca_engine import DCAEngine
            from backend.backtesting.models import BacktestConfig, StrategyType

            config = BacktestConfig(
                symbol=config_params.get("symbol", "BTCUSDT"),
                interval=config_params.get("interval", "15"),
                start_date="2025-01-01",
                end_date="2026-01-01",
                strategy_type=StrategyType.CUSTOM,
                strategy_params={
                    "close_conditions": final_dca_config.get("close_conditions", {}),
                    "indent_order": final_dca_config.get("indent_order", {}),
                },
                initial_capital=config_params.get("initial_capital", 10000.0),
                position_size=config_params.get("position_size", 1.0),
                leverage=config_params.get("leverage", 10),
                direction=direction_str,
                stop_loss=block_stop_loss if block_stop_loss else None,
                take_profit=block_take_profit if block_take_profit else None,
                commission_value=config_params.get("commission", COMMISSION_TV),
                taker_fee=config_params.get("commission", COMMISSION_TV),
                maker_fee=config_params.get("commission", COMMISSION_TV),
                # DCA fields from block config
                dca_enabled=True,
                dca_direction=final_dca_config.get("dca_direction", "both"),
                dca_order_count=final_dca_config.get("dca_order_count", 5),
                dca_grid_size_percent=final_dca_config.get("dca_grid_size_percent", 10.0),
                dca_martingale_coef=final_dca_config.get("dca_martingale_coef", 1.0),
                dca_martingale_mode=final_dca_config.get("dca_martingale_mode", "multiply_each"),
                dca_log_step_enabled=final_dca_config.get("dca_log_step_enabled", False),
                dca_log_step_coef=final_dca_config.get("dca_log_step_coef", 1.1),
                dca_safety_close_enabled=final_dca_config.get("dca_safety_close_enabled", True),
                dca_drawdown_threshold=final_dca_config.get("dca_drawdown_threshold", 30.0),
                dca_multi_tp_enabled=final_dca_config.get("dca_multi_tp_enabled", False),
                # DCA multi-TP levels from block config
                dca_tp1_percent=final_dca_config.get("dca_tp1_percent", 0.5),
                dca_tp1_close_percent=final_dca_config.get("dca_tp1_close_percent", 25.0),
                dca_tp2_percent=final_dca_config.get("dca_tp2_percent", 1.0),
                dca_tp2_close_percent=final_dca_config.get("dca_tp2_close_percent", 25.0),
                dca_tp3_percent=final_dca_config.get("dca_tp3_percent", 2.0),
                dca_tp3_close_percent=final_dca_config.get("dca_tp3_close_percent", 25.0),
                dca_tp4_percent=final_dca_config.get("dca_tp4_percent", 3.0),
                dca_tp4_close_percent=final_dca_config.get("dca_tp4_close_percent", 25.0),
                # Breakeven
                breakeven_enabled=block_breakeven_enabled,
                breakeven_activation_pct=block_breakeven_activation_pct,
                breakeven_offset=block_breakeven_offset,
                sl_type=block_sl_type,
                # Close by time
                max_bars_in_trade=block_max_bars_in_trade,
                close_only_in_profit=block_close_only_in_profit,
                pyramiding=config_params.get("pyramiding", 1),
                no_trade_days=config_params.get("no_trade_days", ()),
            )

            engine = DCAEngine()
            bt_result = engine.run_from_config(config, ohlcv, custom_strategy=adapter)

            if bt_result is None:
                return None

            # Extract metrics from BacktestResult (DCA engine returns BacktestResult)
            metrics = getattr(bt_result, "metrics", None) or getattr(bt_result, "performance", None)
            if metrics is None:
                return None

            def _safe(v: Any, default: float = 0.0) -> float:
                return float(v) if v is not None else default

            win_rate = _safe(getattr(metrics, "win_rate", 0))
            if win_rate <= 1.0:
                win_rate *= 100.0

            return {
                "total_return": _safe(getattr(metrics, "total_return", 0)),
                "sharpe_ratio": _safe(getattr(metrics, "sharpe_ratio", 0)),
                "sharpe_method": str(getattr(metrics, "sharpe_method", "fallback") or "fallback"),
                "sharpe_samples": int(getattr(metrics, "sharpe_samples", 0) or 0),
                "max_drawdown": _safe(getattr(metrics, "max_drawdown", 0)),
                "win_rate": win_rate,
                "total_trades": int(getattr(metrics, "total_trades", 0) or 0),
                "profit_factor": _safe(getattr(metrics, "profit_factor", 0)),
                "winning_trades": int(getattr(metrics, "winning_trades", 0) or 0),
                "losing_trades": int(getattr(metrics, "losing_trades", 0) or 0),
                "net_profit": _safe(getattr(metrics, "net_profit", 0)),
                "net_profit_pct": _safe(getattr(metrics, "total_return", 0)),
                "gross_profit": _safe(getattr(metrics, "gross_profit", 0)),
                "gross_loss": _safe(getattr(metrics, "gross_loss", 0)),
                "avg_win": _safe(getattr(metrics, "avg_win", 0)),
                "avg_loss": _safe(getattr(metrics, "avg_loss", 0)),
                # % aliases for unit-toggle constraints
                "avg_win_pct": _safe(getattr(metrics, "avg_win", 0)),
                "avg_loss_pct": _safe(getattr(metrics, "avg_loss", 0)),
                "largest_win": _safe(getattr(metrics, "largest_win", 0)),
                "largest_loss": _safe(getattr(metrics, "largest_loss", 0)),
                "recovery_factor": _safe(getattr(metrics, "recovery_factor", 0)),
                "expectancy": _safe(getattr(metrics, "expectancy", 0)),
                "expectancy_pct": _safe(getattr(metrics, "expectancy_pct", 0)),
                "sortino_ratio": _safe(getattr(metrics, "sortino_ratio", 0)),
                "calmar_ratio": _safe(getattr(metrics, "calmar_ratio", 0)),
                "max_drawdown_value": _safe(getattr(metrics, "max_drawdown_usdt", 0)),
                "long_trades": int(getattr(metrics, "long_trades", 0) or 0),
                "short_trades": int(getattr(metrics, "short_trades", 0) or 0),
            }

        # ── Non-DCA path: use fast numba engine with BacktestInput ──────────
        signals = adapter.generate_signals(ohlcv)

        # ── Warmup cutoff: slice to [start_date:] before backtest ────────────
        # When ohlcv includes pre-period warmup bars (e.g. start_date - 45d) for
        # indicator convergence, generate signals on the full warmup dataset so
        # Wilder RSI is stable, then trim both ohlcv and signal Series to the actual
        # backtest window.  Matches API router behaviour: signals computed on warmup
        # data, backtest engine runs only on [start_date, end_date].
        _warmup_cutoff_raw = config_params.get("warmup_cutoff")
        if _warmup_cutoff_raw is not None:
            import pandas as _pd_wm

            _cutoff = _pd_wm.Timestamp(_warmup_cutoff_raw)
            # Align timezone with ohlcv index
            if ohlcv.index.tz is not None:
                _cutoff = (
                    _cutoff.tz_localize(ohlcv.index.tz)
                    if _cutoff.tzinfo is None
                    else _cutoff.tz_convert(ohlcv.index.tz)
                )
            elif _cutoff.tzinfo is not None:
                _cutoff = _cutoff.tz_localize(None)
            _wmask = ohlcv.index >= _cutoff
            _n_warmup_dropped = int((~_wmask).sum())
            if _n_warmup_dropped > 0:
                ohlcv = ohlcv.loc[_wmask]
                signals.entries = signals.entries.loc[_wmask]
                signals.exits = signals.exits.loc[_wmask]
                if signals.short_entries is not None:
                    signals.short_entries = signals.short_entries.loc[_wmask]
                if signals.short_exits is not None:
                    signals.short_exits = signals.short_exits.loc[_wmask]

        # Convert SignalResult to numpy arrays
        long_entries = np.asarray(signals.entries.values, dtype=bool)
        long_exits = np.asarray(signals.exits.values, dtype=bool)
        short_entries = (
            np.asarray(signals.short_entries.values, dtype=bool)
            if signals.short_entries is not None
            else np.zeros(len(ohlcv), dtype=bool)
        )
        short_exits = (
            np.asarray(signals.short_exits.values, dtype=bool)
            if signals.short_exits is not None
            else np.zeros(len(ohlcv), dtype=bool)
        )

        from backend.optimization.utils import build_backtest_input, extract_metrics_from_output, parse_trade_direction

        trade_direction = parse_trade_direction(direction_str)

        bt_input = build_backtest_input(
            candles=ohlcv,
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            request_params=config_params,
            trade_direction=trade_direction,
            stop_loss_pct=(block_stop_loss * 100.0) if block_stop_loss else 0.0,
            take_profit_pct=(block_take_profit * 100.0) if block_take_profit else 0.0,
            max_bars_in_trade=block_max_bars_in_trade,
        )

        # When close_by_time has profit_only=True, extra_data is required for parity.
        # NumbaEngineV2 doesn't read extra_data → silently ignores profit_only condition.
        # Fall back to FallbackEngineV4 via BacktestEngine which DOES handle extra_data.
        # OPTIMIZATION EXCEPTION: when engine_type=="numba" (default in optimization loops),
        # skip the FallbackEngineV4 path — profit_only is silently ignored by NumbaEngineV2
        # but this is acceptable for optimization (ranking stays correct, speed 1000×).
        _use_numba_for_opt = config_params.get("engine_type", "numba") == "numba"
        if block_close_by_time_profit_only and not _use_numba_for_opt:
            from backend.backtesting.engine import BacktestEngine
            from backend.backtesting.models import BacktestConfig, StrategyType

            # Wrap already-computed (warmup-trimmed) signals so BacktestEngine doesn't
            # re-run adapter.generate_signals() on the trimmed OHLCV without warmup bars.
            # signals.extra_data carries time_exit_profit_only / time_exit_min_profit
            # which FallbackEngineV4 reads to enforce the profit-only close condition.
            _cached_signals = signals

            class _PrecomputedStrategy:
                def generate_signals(self, data):
                    return _cached_signals

            _v4_config = BacktestConfig(
                symbol=config_params.get("symbol", "BTCUSDT"),
                interval=config_params.get("interval", "15"),
                start_date=ohlcv.index[0],  # ohlcv already trimmed to actual window
                end_date=ohlcv.index[-1],
                strategy_type=StrategyType.CUSTOM,
                strategy_params={},
                initial_capital=config_params.get("initial_capital", 10000.0),
                position_size=config_params.get("position_size", 1.0),
                leverage=config_params.get("leverage", 1),
                direction=direction_str,
                stop_loss=block_stop_loss if block_stop_loss else None,
                take_profit=block_take_profit if block_take_profit else None,
                commission_value=config_params.get("commission", COMMISSION_TV),
                taker_fee=config_params.get("commission", COMMISSION_TV),
                maker_fee=config_params.get("commission", COMMISSION_TV),
                breakeven_enabled=block_breakeven_enabled,
                breakeven_activation_pct=block_breakeven_activation_pct,
                breakeven_offset=block_breakeven_offset,
                sl_type=block_sl_type,
                max_bars_in_trade=block_max_bars_in_trade,
                close_only_in_profit=block_close_only_in_profit,
                use_bar_magnifier=False,  # prevents 200k 1m-bar IntrabarEngine load per trial
                pyramiding=config_params.get("pyramiding", 1),
                no_trade_days=config_params.get("no_trade_days", ()),
            )
            _v4_engine = BacktestEngine()
            _v4_result = _v4_engine.run(_v4_config, ohlcv, custom_strategy=_PrecomputedStrategy())
            if _v4_result is None:
                return None
            _m = _v4_result.metrics
            if _m is None:
                return None

            def _safe_v4(v: Any, default: float = 0.0) -> float:
                return float(v) if v is not None else default

            win_rate_v4 = _safe_v4(getattr(_m, "win_rate", 0))
            if win_rate_v4 <= 1.0:
                win_rate_v4 *= 100.0
            # PerformanceMetrics.total_return is a FRACTION (engine.py line 457: no *100)
            # extract_metrics_from_output() expects PERCENT — multiply by 100 for parity
            _v4_total_return_pct = _safe_v4(getattr(_m, "total_return", 0)) * 100
            return {
                "total_return": _v4_total_return_pct,
                "sharpe_ratio": _safe_v4(getattr(_m, "sharpe_ratio", 0)),
                "sharpe_method": str(getattr(_m, "sharpe_method", "fallback") or "fallback"),
                "sharpe_samples": int(getattr(_m, "sharpe_samples", 0) or 0),
                "max_drawdown": _safe_v4(getattr(_m, "max_drawdown", 0)),
                "win_rate": win_rate_v4,
                "total_trades": int(getattr(_m, "total_trades", 0) or 0),
                "profit_factor": _safe_v4(getattr(_m, "profit_factor", 0)),
                "winning_trades": int(getattr(_m, "winning_trades", 0) or 0),
                "losing_trades": int(getattr(_m, "losing_trades", 0) or 0),
                "net_profit": _safe_v4(getattr(_m, "net_profit", 0)),
                "net_profit_pct": _v4_total_return_pct,
                "gross_profit": _safe_v4(getattr(_m, "gross_profit", 0)),
                "gross_loss": _safe_v4(getattr(_m, "gross_loss", 0)),
                "avg_win": _safe_v4(getattr(_m, "avg_win", 0)),
                "avg_loss": _safe_v4(getattr(_m, "avg_loss", 0)),
                "avg_win_pct": _safe_v4(getattr(_m, "avg_win", 0)),
                "avg_loss_pct": _safe_v4(getattr(_m, "avg_loss", 0)),
                "largest_win": _safe_v4(getattr(_m, "largest_win", 0)),
                "largest_loss": _safe_v4(getattr(_m, "largest_loss", 0)),
                "recovery_factor": _safe_v4(getattr(_m, "recovery_factor", 0)),
                "expectancy": _safe_v4(getattr(_m, "expectancy", 0)),
                "expectancy_pct": _safe_v4(getattr(_m, "expectancy_pct", 0)),
                "sortino_ratio": _safe_v4(getattr(_m, "sortino_ratio", 0)),
                "calmar_ratio": _safe_v4(getattr(_m, "calmar_ratio", 0)),
                "max_drawdown_value": _safe_v4(getattr(_m, "max_drawdown_value", 0)),
                "long_trades": int(getattr(_m, "long_trades", 0) or 0),
                "short_trades": int(getattr(_m, "short_trades", 0) or 0),
            }

        from backend.backtesting.engine_selector import get_engine

        engine_type = config_params.get("engine_type", "numba")
        engine = get_engine(engine_type=engine_type)

        bt_output = engine.run(bt_input)

        if not bt_output.is_valid:
            return None

        result = extract_metrics_from_output(bt_output, win_rate_as_pct=True)
        return result

    except Exception as e:
        logger.warning(f"Builder backtest failed: {e}", exc_info=True)
        return None


# =============================================================================
# GRID SEARCH FOR BUILDER STRATEGIES
# =============================================================================


def _is_rsi_threshold_only_optimization(
    param_combinations: list[dict[str, Any]],
    base_graph: dict[str, Any],
) -> tuple[bool, str | None]:
    """Check if optimization only varies RSI threshold params (not period).

    When only RSI thresholds change, we can pre-compute the RSI series once
    and quickly re-evaluate threshold conditions for each combination,
    avoiding the full signal generation pipeline (~10-50x speedup).

    Returns:
        (is_threshold_only, rsi_block_id) tuple
    """
    if not param_combinations:
        return False, None

    # Collect all param_keys being optimized and their block IDs
    sample = param_combinations[0]
    rsi_block_id = None
    threshold_params = {
        "cross_long_level",
        "cross_short_level",
        "long_rsi_more",
        "long_rsi_less",
        "short_rsi_more",
        "short_rsi_less",
        "overbought",
        "oversold",
        "cross_memory_bars",
    }

    for param_path in sample:
        parts = param_path.split(".", 1)
        if len(parts) != 2:
            return False, None
        block_id, param_key = parts

        # Allow static_sltp block params (SL/TP) — handled in fast path per combo
        block = None
        for b in base_graph.get("blocks", []):
            if b.get("id") == block_id:
                block = b
                break
        if not block:
            return False, None

        block_type = block.get("type", "")

        # static_sltp params are allowed alongside RSI threshold params
        if block_type == "static_sltp":
            sltp_allowed = {"stop_loss_percent", "take_profit_percent"}
            if param_key not in sltp_allowed:
                return False, None
            continue  # Don't require RSI block for SL/TP params

        if block_type != "rsi":
            return False, None

        # Check that param is a threshold (not period)
        # NOTE: 'period' IS now allowed — the fast path handles it by re-computing RSI per period.
        rsi_allowed_params = threshold_params | {"period"}
        if param_key not in rsi_allowed_params:
            return False, None

        if rsi_block_id is None:
            rsi_block_id = block_id
        elif rsi_block_id != block_id:
            return False, None  # Multiple RSI blocks — not supported for fast path

    # ── Topology checks: fast path can only handle simple signal chains ────────
    # The fast path pre-computes RSI signals and applies only two_mas filter masks.
    # If the graph has AND blocks in the entry chain or non-two_mas filter blocks,
    # the fast path would silently ignore them → wrong signals → parity failure.
    connections = base_graph.get("connections", [])
    blocks_by_id: dict[str, dict] = {b.get("id", ""): b for b in base_graph.get("blocks", [])}

    # Find strategy node ID (main collector)
    strategy_block_id: str | None = None
    for b in base_graph.get("blocks", []):
        if b.get("type") == "strategy" or b.get("isMain"):
            strategy_block_id = b.get("id")
            break
    if not strategy_block_id:
        strategy_block_id = "main_strategy"

    for conn in connections:
        src = conn.get("source", {})
        tgt = conn.get("target", {})
        tgt_block_id = tgt.get("blockId", "")
        tgt_port = tgt.get("portId", "")
        src_block_id = src.get("blockId", "")

        if tgt_block_id != strategy_block_id:
            continue

        if tgt_port in ("entry_long", "entry", "entry_short"):
            # Fast path requires RSI to connect DIRECTLY to entry ports.
            # If anything else (e.g. AND block) connects here, fall back.
            if rsi_block_id and src_block_id != rsi_block_id:
                return False, None
            src_block = blocks_by_id.get(src_block_id, {})
            if src_block.get("type") in ("and", "or", "condition", "filter"):
                return False, None

        elif tgt_port in ("filter_long", "confirm_long", "filter_short", "confirm_short"):
            # Fast path only pre-computes two_mas filter masks; other block types
            # (adx, supertrend, ema, sma, etc.) are silently skipped → fall back.
            src_block = blocks_by_id.get(src_block_id, {})
            if src_block.get("type", "") != "two_mas":
                return False, None

    return True, rsi_block_id


def _run_fast_rsi_threshold_optimization(
    base_graph: dict[str, Any],
    ohlcv: pd.DataFrame,
    param_combinations: list[dict[str, Any]],
    config_params: dict[str, Any],
    rsi_block_id: str,
    optimize_metric: str = "sharpe_ratio",
    weights: dict[str, float] | None = None,
    max_results: int = 20,
    early_stopping: bool = False,
    early_stopping_patience: int = 20,
    timeout_seconds: int = 3600,
    strategy_id: str = "",
) -> dict[str, Any]:
    """Fast-path RSI threshold optimization.

    Pre-computes the RSI series once, then quickly evaluates different
    threshold combinations without re-running the full signal pipeline.
    Falls back to standard path on any error.
    """
    start_time = time.time()
    results: list[dict[str, Any]] = []
    all_results: list[dict[str, Any]] = []
    best_score = float("-inf")
    no_improvement_count = 0
    total = len(param_combinations)
    tested = 0

    # Initialize progress
    if strategy_id:
        update_optimization_progress(
            strategy_id, status="running", tested=0, total=total, started_at=start_time, stage="searching"
        )
    # Get the RSI block's base params
    rsi_block = None
    for block in base_graph.get("blocks", []):
        if block.get("id") == rsi_block_id:
            rsi_block = block
            break

    if not rsi_block:
        logger.warning("Fast RSI optimization: RSI block not found, falling back to standard path")
        raise ValueError("RSI block not found")

    base_params = rsi_block.get("params") or rsi_block.get("config") or {}
    _base_period = int(base_params.get("period", 14))

    # Pre-compute RSI for each unique period in the combo set (avoids full pipeline per combo)
    close = ohlcv["close"].astype(float).values
    gain_arr = np.where(np.diff(close, prepend=close[0]) > 0, np.diff(close, prepend=close[0]), 0.0)
    loss_arr = np.where(np.diff(close, prepend=close[0]) < 0, -np.diff(close, prepend=close[0]), 0.0)

    def _compute_rsi_for_period(p: int) -> tuple:
        """Compute Wilder RSI series for a given period."""
        alpha = 1.0 / p
        ag = np.zeros(len(close))
        al = np.zeros(len(close))
        ag[p] = np.mean(gain_arr[1 : p + 1])
        al[p] = np.mean(loss_arr[1 : p + 1])
        for j in range(p + 1, len(close)):
            ag[j] = ag[j - 1] * (1 - alpha) + gain_arr[j] * alpha
            al[j] = al[j - 1] * (1 - alpha) + loss_arr[j] * alpha
        rs = np.divide(ag, al, out=np.zeros_like(ag), where=al != 0)
        vals = 100.0 - 100.0 / (1.0 + rs)
        vals[:p] = np.nan
        s = pd.Series(vals, index=ohlcv.index)
        return s, s.shift(1)

    # Pre-compute RSI for all unique periods in the combo list
    _rsi_cache: dict[int, tuple] = {}
    for _combo in param_combinations:
        for _path, _val in _combo.items():
            if _path.endswith(".period"):
                _p = int(_val)
                if _p not in _rsi_cache:
                    _rsi_cache[_p] = _compute_rsi_for_period(_p)
    # Always include base period
    if _base_period not in _rsi_cache:
        _rsi_cache[_base_period] = _compute_rsi_for_period(_base_period)

    # Default RSI (base period) — will be overridden per-combo if period is swept
    rsi, rsi_prev = _rsi_cache[_base_period]

    _log_info(
        f"⚡ Fast RSI threshold optimization: pre-computed RSI for {len(_rsi_cache)} "
        f"period(s) {sorted(_rsi_cache.keys())} over {len(ohlcv)} bars"
    )

    # Pre-extract DCA config and other block-level configs from the BASE graph
    # (these don't change across RSI threshold combos)
    from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

    base_adapter = StrategyBuilderAdapter(base_graph)
    block_dca_config = base_adapter.extract_dca_config()
    has_dca_blocks = base_adapter.has_dca_blocks()
    dca_enabled = has_dca_blocks or block_dca_config.get("dca_enabled", False)

    # Extract SL/TP / close_by_time from base graph (unchanged across combos)
    block_stop_loss: float | None = config_params.get("stop_loss_pct")
    block_take_profit: float | None = config_params.get("take_profit_pct")
    if block_stop_loss:
        block_stop_loss = block_stop_loss / 100.0
    if block_take_profit:
        block_take_profit = block_take_profit / 100.0
    block_breakeven_enabled = False
    block_breakeven_activation_pct = 0.005
    block_breakeven_offset = 0.0
    block_close_only_in_profit = False
    block_sl_type = "average_price"
    block_max_bars_in_trade = 0

    for block in base_graph.get("blocks", []):
        block_type = block.get("type", "")
        bp = block.get("params") or block.get("config") or {}
        if block_type == "close_by_time":
            bars_val = bp.get("bars_since_entry", bp.get("bars", 0))
            block_max_bars_in_trade = int(bars_val) if bars_val else 0
        elif block_type == "static_sltp":
            if block_stop_loss is None:
                block_stop_loss = bp.get("stop_loss_percent", 1.5) / 100.0
            if block_take_profit is None:
                block_take_profit = bp.get("take_profit_percent", 1.5) / 100.0
            block_breakeven_enabled = bp.get("activate_breakeven", False)
            if block_breakeven_enabled:
                block_breakeven_activation_pct = bp.get("breakeven_activation_percent", 0.5) / 100.0
                block_breakeven_offset = bp.get("new_breakeven_sl_percent", 0.1) / 100.0
            block_close_only_in_profit = bp.get("close_only_in_profit", False)
            block_sl_type = bp.get("sl_type", "average_price")
        elif block_type == "tp_percent" and block_take_profit is None:
            block_take_profit = bp.get("take_profit_percent", 3.0) / 100.0
        elif block_type == "sl_percent" and block_stop_loss is None:
            block_stop_loss = bp.get("stop_loss_percent", 1.5) / 100.0

    direction_str = config_params.get("direction", "both")

    # Sync DCA direction
    final_dca_config = block_dca_config.copy()
    final_dca_config["dca_enabled"] = dca_enabled
    if final_dca_config.get("dca_direction", "both") == "both" and direction_str in ("long", "short"):
        final_dca_config["dca_direction"] = direction_str

    def _compute_two_mas_filter_mask(ohlcv_df: pd.DataFrame, blk_params: dict, src_port: str) -> np.ndarray | None:
        """Compute EMA/MA filter boolean mask from a two_mas block directly (no adapter needed)."""
        try:
            ma1_len = int(blk_params.get("ma1_length", 50))
            ma2_len = int(blk_params.get("ma2_length", 100))
            ma1_type = str(blk_params.get("ma1_smoothing", "SMA")).upper()
            ma2_type = str(blk_params.get("ma2_smoothing", "EMA")).upper()
            ma1_src = str(blk_params.get("ma1_source", "close"))
            ma2_src = str(blk_params.get("ma2_source", "close"))

            src1 = ohlcv_df[ma1_src] if ma1_src in ohlcv_df.columns else ohlcv_df["close"]
            src2 = ohlcv_df[ma2_src] if ma2_src in ohlcv_df.columns else ohlcv_df["close"]

            def _ma(series: pd.Series, length: int, ma_type: str) -> pd.Series:
                if ma_type == "EMA":
                    return series.ewm(span=length, adjust=False).mean()
                elif ma_type == "WMA":
                    weights = np.arange(1, length + 1)
                    return series.rolling(length).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)
                else:  # SMA default
                    return series.rolling(length).mean()

            ma1 = _ma(src1, ma1_len, ma1_type)
            ma2 = _ma(src2, ma2_len, ma2_type)
            close = ohlcv_df["close"]

            long_signal = pd.Series(True, index=ohlcv_df.index)
            short_signal = pd.Series(True, index=ohlcv_df.index)

            if blk_params.get("use_ma_cross", False):
                ma1_prev = ma1.shift(1)
                ma2_prev = ma2.shift(1)
                long_signal = (ma1 > ma2) & (ma1_prev <= ma2_prev)
                short_signal = (ma1 < ma2) & (ma1_prev >= ma2_prev)
            elif blk_params.get("use_ma1_filter", False):
                above = close > ma1
                opposite = blk_params.get("opposite_ma1_filter", False)
                if opposite:
                    long_signal = ~above
                    short_signal = above
                else:
                    long_signal = above
                    short_signal = ~above

            if src_port in ("long", "long_filter"):
                sig = long_signal
            elif src_port in ("short", "short_filter"):
                sig = short_signal
            else:
                sig = long_signal

            return np.asarray(sig.fillna(False).values, dtype=bool)
        except Exception as _e:
            _log_warning(f"_compute_two_mas_filter_mask failed: {_e}")
            return None

    # ── Pre-compute filter signals (EMA/indicator AND-filters) ───────────────
    # These don't change across RSI threshold combos, so compute once and reuse.
    _ema_long_filter: np.ndarray | None = None
    _ema_short_filter: np.ndarray | None = None
    _has_non_dca_filter = False
    if not dca_enabled:
        try:
            _connections = base_graph.get("connections", [])
            _filter_long_sigs: list[np.ndarray] = []
            _filter_short_sigs: list[np.ndarray] = []
            # Find connections that go to filter_long / filter_short ports
            for _conn in _connections:
                _tgt_port = _conn.get("target", {}).get("portId", "")
                _src_block_id = _conn.get("source", {}).get("blockId", "")
                if _tgt_port in ("filter_long", "confirm_long"):
                    # Find the source block
                    for _blk in base_graph.get("blocks", []):
                        if _blk.get("id") == _src_block_id:
                            _blk_type = _blk.get("type", "")
                            _blk_params = _blk.get("params") or _blk.get("config") or {}
                            if _blk_type == "two_mas":
                                _src_port = _conn.get("source", {}).get("portId", "long")
                                _sig = _compute_two_mas_filter_mask(ohlcv, _blk_params, _src_port)
                                if _sig is not None:
                                    _filter_long_sigs.append(_sig)
                elif _tgt_port in ("filter_short", "confirm_short"):
                    for _blk in base_graph.get("blocks", []):
                        if _blk.get("id") == _src_block_id:
                            _blk_type = _blk.get("type", "")
                            _blk_params = _blk.get("params") or _blk.get("config") or {}
                            if _blk_type == "two_mas":
                                _src_port = _conn.get("source", {}).get("portId", "short")
                                _sig = _compute_two_mas_filter_mask(ohlcv, _blk_params, _src_port)
                                if _sig is not None:
                                    _filter_short_sigs.append(_sig)

            if _filter_long_sigs:
                _ema_long_filter = _filter_long_sigs[0]
                for _f in _filter_long_sigs[1:]:
                    _ema_long_filter = _ema_long_filter & _f
                _has_non_dca_filter = True
                _log_info(f"⚡ Fast RSI path: pre-computed long filter mask ({_ema_long_filter.sum()} True bars)")
            if _filter_short_sigs:
                _ema_short_filter = _filter_short_sigs[0]
                for _f in _filter_short_sigs[1:]:
                    _ema_short_filter = _ema_short_filter & _f
                _has_non_dca_filter = True
                _log_info(f"⚡ Fast RSI path: pre-computed short filter mask ({_ema_short_filter.sum()} True bars)")
        except Exception as _e:
            _log_warning(f"Fast RSI path: filter pre-computation failed ({_e}), filters will be skipped")
            _ema_long_filter = None
            _ema_short_filter = None

    # ── Determine if SL/TP is being swept across combos ──────────────────────
    # When static_sltp params appear in overrides, extract per-combo instead of using base values.
    _sltp_block_ids: set[str] = {b["id"] for b in base_graph.get("blocks", []) if b.get("type") == "static_sltp"}
    _sample_combo = param_combinations[0] if param_combinations else {}
    _sltp_in_overrides = any(k.split(".")[0] in _sltp_block_ids for k in _sample_combo)
    if _sltp_in_overrides:
        _log_info("⚡ Fast RSI path: SL/TP params detected in combos — will extract per-combo")

    if dca_enabled:
        _fast_rsi_dca_close_cache = _precompute_dca_close_cache(final_dca_config, config_params, ohlcv)
        if _fast_rsi_dca_close_cache is not None:
            _log_info("⚡ Fast RSI path: DCA close-condition indicator cache pre-computed")

    # ── Warmup cutoff: trim all pre-computed series to [start_date:] ─────────
    # RSI cache and filter masks were computed on the full warmup ohlcv so
    # Wilder RSI converges before start_date. Now slice everything to the actual
    # backtest window so the engine runs only on [start_date, end_date].
    _warmup_cutoff_frp = config_params.get("warmup_cutoff")
    if _warmup_cutoff_frp is not None:
        import pandas as _pd_frp

        _cutoff_frp = _pd_frp.Timestamp(_warmup_cutoff_frp)
        if ohlcv.index.tz is not None:
            _cutoff_frp = (
                _cutoff_frp.tz_localize(ohlcv.index.tz)
                if _cutoff_frp.tzinfo is None
                else _cutoff_frp.tz_convert(ohlcv.index.tz)
            )
        elif _cutoff_frp.tzinfo is not None:
            _cutoff_frp = _cutoff_frp.tz_localize(None)
        _wmask_frp = ohlcv.index >= _cutoff_frp
        _n_warmup_frp = int((~_wmask_frp).sum())
        if _n_warmup_frp > 0:
            ohlcv = ohlcv.loc[_wmask_frp]
            # Slice RSI cache Series (same index as original ohlcv)
            for _fp_key in list(_rsi_cache.keys()):
                _fs, _fsp = _rsi_cache[_fp_key]
                _rsi_cache[_fp_key] = (_fs.loc[_wmask_frp], _fsp.loc[_wmask_frp])
            rsi, rsi_prev = _rsi_cache.get(_base_period, next(iter(_rsi_cache.values())))
            # Slice numpy filter masks
            if _ema_long_filter is not None:
                _ema_long_filter = _ema_long_filter[_n_warmup_frp:]
            if _ema_short_filter is not None:
                _ema_short_filter = _ema_short_filter[_n_warmup_frp:]
            _log_info(f"⚡ Fast RSI path: trimmed {_n_warmup_frp} warmup bars → {len(ohlcv)} bars for backtest")

    # ── Pre-init engine and imports outside the hot loop ─────────────────────
    # Importing inside the loop adds ~0.1-1ms per combo. Pre-init here.
    if not dca_enabled:
        from backend.backtesting.engine_selector import get_engine as _get_engine
        from backend.backtesting.interfaces import BacktestInput
        from backend.optimization.utils import extract_metrics_from_output, parse_trade_direction

        _bt_engine = _get_engine(engine_type="numba")
        _trade_direction = parse_trade_direction(direction_str)
        # Pre-allocate zero arrays (same size, reused every combo)
        _n = len(ohlcv)
        _long_exits = np.zeros(_n, dtype=bool)
        _short_exits = np.zeros(_n, dtype=bool)
        _log_info(f"⚡ Fast RSI path: engine pre-initialized ({type(_bt_engine).__name__}), {_n} bars")

    # Log to console every ~5%; update progress store every combo (for real-time UI feedback).
    # Fast RSI path may run 100s of combos/s — cap progress store updates at 50ms intervals.
    log_interval = max(1, total // 20)
    _last_progress_update = 0.0

    for i, overrides in enumerate(param_combinations):
        elapsed = time.time() - start_time
        if elapsed > timeout_seconds:
            logger.info(f"⏱️ Fast RSI optimization timeout after {elapsed:.0f}s at combo {i}/{total}")
            break

        tested += 1

        # Fast signal generation from pre-computed RSI
        merged_params = {**base_params}
        for param_path, value in overrides.items():
            _bid_tmp, _pkey_tmp = param_path.split(".", 1)
            if _bid_tmp not in _sltp_block_ids:
                merged_params[_pkey_tmp] = value

        # Pick RSI series for the combo's period (cached above)
        _combo_period = int(merged_params.get("period", _base_period))
        if _combo_period in _rsi_cache:
            rsi, rsi_prev = _rsi_cache[_combo_period]
        else:
            rsi, rsi_prev = _rsi_cache[_base_period]

        # Auto-enable mode flags when optimizing mode-gated RSI params —
        # mirrors clone_graph_with_params logic (line ~617) so that
        # e.g. optimizing cross_long_level activates use_cross_level=True
        # even if the base block has it disabled.
        # Also skip SL/TP keys so they don't pollute merged_params (not RSI params)
        for param_path in overrides:
            block_id_p, param_key = param_path.split(".", 1)
            if block_id_p in _sltp_block_ids:
                continue  # SL/TP params handled separately below
            if param_key in ("cross_long_level", "cross_short_level"):
                merged_params["use_cross_level"] = True
            elif param_key == "cross_memory_bars":
                merged_params["use_cross_memory"] = True
            elif param_key in ("long_rsi_more", "long_rsi_less"):
                merged_params["use_long_range"] = True
            elif param_key in ("short_rsi_more", "short_rsi_less"):
                merged_params["use_short_range"] = True

        # Extract per-combo SL/TP (when static_sltp params are being swept)
        _combo_sl = block_stop_loss
        _combo_tp = block_take_profit
        if _sltp_in_overrides:
            for param_path, value in overrides.items():
                _bid, _pkey = param_path.split(".", 1)
                if _bid in _sltp_block_ids:
                    if _pkey == "stop_loss_percent":
                        _combo_sl = float(value) / 100.0
                    elif _pkey == "take_profit_percent":
                        _combo_tp = float(value) / 100.0

        # Compute signals using pre-computed RSI
        signals = _fast_rsi_signals(
            rsi=rsi,
            rsi_prev=rsi_prev,
            params=merged_params,
            direction=direction_str,
        )

        # Apply pre-computed EMA/indicator AND-filter masks (fast path replacement for adapter pipeline)
        if _ema_long_filter is not None:
            long_mask = signals > 0
            long_mask &= _ema_long_filter
            signals[signals > 0] = 0
            signals[long_mask] = 1
        if _ema_short_filter is not None:
            short_mask = signals < 0
            short_mask &= _ema_short_filter
            signals[signals < 0] = 0
            signals[short_mask] = -1

        long_signal_count = int(np.sum(signals > 0))
        short_signal_count = int(np.sum(signals < 0))

        # Update progress store at most every 50ms (before potential early-continue)
        now = time.time()
        if strategy_id and (now - _last_progress_update) >= 0.05:
            _last_progress_update = now
            elapsed_now = now - start_time
            speed_now = round(tested / max(elapsed_now, 0.001), 1)
            eta_now = int((total - tested) / speed_now) if speed_now > 0 else 0
            update_optimization_progress(
                strategy_id,
                status="running",
                tested=tested,
                total=total,
                best_score=best_score if best_score != float("-inf") else 0.0,
                results_found=len(results),
                speed=speed_now,
                eta_seconds=eta_now,
                started_at=start_time,
            )

        # Log to console every 5%
        if tested > 0 and tested % log_interval == 0:
            elapsed_now = time.time() - start_time
            speed_now = round(tested / max(elapsed_now, 0.001), 1)
            eta_now = int((total - tested) / speed_now) if speed_now > 0 else 0
            pct = tested * 100 // total if total > 0 else 0
            logger.info(
                f"📊 Fast RSI optimization progress: {tested}/{total} ({pct}%) "
                f"speed={speed_now} combos/s, ETA={eta_now}s, results={len(results)}"
            )

        # Fast skip: no signals → no trades
        if long_signal_count == 0 and short_signal_count == 0:
            continue

        # Run DCA engine with pre-computed signals
        if dca_enabled:
            result = _run_dca_with_signals(
                signals=signals,
                ohlcv=ohlcv,
                config_params=config_params,
                final_dca_config=final_dca_config,
                direction_str=direction_str,
                block_stop_loss=_combo_sl,
                block_take_profit=_combo_tp,
                block_breakeven_enabled=block_breakeven_enabled,
                block_breakeven_activation_pct=block_breakeven_activation_pct,
                block_breakeven_offset=block_breakeven_offset,
                block_close_only_in_profit=block_close_only_in_profit,
                block_sl_type=block_sl_type,
                block_max_bars_in_trade=block_max_bars_in_trade,
                close_indicator_cache=_fast_rsi_dca_close_cache,
            )
        else:
            # Fast path: directly run engine with pre-computed filtered signals.
            # Engine and imports are pre-initialized before the loop for speed.
            try:
                long_entries = (signals > 0).astype(bool)
                short_entries = (signals < 0).astype(bool)

                bt_input = BacktestInput(
                    candles=ohlcv,
                    candles_1m=None,
                    long_entries=long_entries,
                    long_exits=_long_exits,
                    short_entries=short_entries,
                    short_exits=_short_exits,
                    symbol=config_params.get("symbol", "BTCUSDT"),
                    interval=config_params.get("interval", "15"),
                    initial_capital=config_params.get("initial_capital", 10000.0),
                    position_size=config_params.get("position_size", 1.0),
                    use_fixed_amount=False,
                    fixed_amount=0.0,
                    leverage=config_params.get("leverage", 10),
                    stop_loss=_combo_sl if _combo_sl else 0.0,
                    take_profit=_combo_tp if _combo_tp else 0.0,
                    direction=_trade_direction,
                    taker_fee=config_params.get("commission", COMMISSION_TV),
                    maker_fee=config_params.get("commission", COMMISSION_TV),
                    slippage=config_params.get("slippage", 0.0),
                    use_bar_magnifier=False,
                    max_drawdown_limit=0.0,
                    pyramiding=config_params.get("pyramiding", 1),
                    max_bars_in_trade=block_max_bars_in_trade,
                    market_regime_enabled=False,
                    market_regime_filter="not_volatile",
                    market_regime_lookback=50,
                )

                bt_output = _bt_engine.run(bt_input)
                if not bt_output.is_valid:
                    result = None
                else:
                    result = extract_metrics_from_output(bt_output, win_rate_as_pct=True)
            except Exception as _fast_err:
                _log_warning(f"Fast non-DCA path failed ({_fast_err}), using standard backtest")
                modified_graph = clone_graph_with_params(base_graph, overrides)
                result = run_builder_backtest(modified_graph, ohlcv, config_params)

        # Update progress store at most every 50ms to avoid lock contention at high speed
        now = time.time()
        if strategy_id and (now - _last_progress_update) >= 0.05:
            _last_progress_update = now
            elapsed_now = now - start_time
            speed_now = round(tested / max(elapsed_now, 0.001), 1)
            eta_now = int((total - tested) / speed_now) if speed_now > 0 else 0
            update_optimization_progress(
                strategy_id,
                status="running",
                tested=tested,
                total=total,
                best_score=best_score if best_score != float("-inf") else 0.0,
                results_found=len(results),
                speed=speed_now,
                eta_seconds=eta_now,
                started_at=start_time,
            )

        # Log to console every 5%
        if tested > 0 and tested % log_interval == 0:
            elapsed_now = time.time() - start_time
            speed_now = round(tested / max(elapsed_now, 0.001), 1)
            eta_now = int((total - tested) / speed_now) if speed_now > 0 else 0
            pct = tested * 100 // total if total > 0 else 0
            logger.info(
                f"📊 Fast RSI optimization progress: {tested}/{total} ({pct}%) "
                f"speed={speed_now} combos/s, ETA={eta_now}s, results={len(results)}"
            )

        if result is None:
            continue

        score = calculate_composite_score(result, optimize_metric, weights)
        entry = {"params": overrides, "score": score, **result}
        all_results.append(entry)

        if not passes_filters(result, config_params):
            continue

        results.append(entry)

        if score > best_score:
            best_score = score
            no_improvement_count = 0
        else:
            no_improvement_count += 1

        if early_stopping and no_improvement_count >= early_stopping_patience:
            logger.info(f"⏹️ Fast RSI early stopping at combo {i}/{total}")
            break

    # Pareto post-processing: re-score all candidates by NP/DD balance before final sort
    if optimize_metric == "pareto_balance":
        apply_pareto_scores(all_results)
        apply_pareto_scores(results)

    results.sort(key=lambda r: r["score"], reverse=True)
    top_results = results[:max_results]

    # Fallback: all results were filtered out — return best unfiltered with a warning flag
    fallback_used = False
    if not top_results and all_results:
        _min_trades_fb = config_params.get("min_trades") or 1
        _constraints_fb = config_params.get("constraints") or []
        logger.warning(
            f"⚠️ Fast RSI: all {len(all_results)} results filtered out "
            f"(min_trades={_min_trades_fb}, constraints={len(_constraints_fb)}). "
            "Returning best unfiltered results."
        )
        # Apply a soft min-trades guard to avoid showing garbage 1-2 trade combos
        _fb_candidates = [r for r in all_results if r.get("total_trades", 0) >= max(_min_trades_fb, 3)]
        if not _fb_candidates:
            _fb_candidates = all_results
        _fb_candidates.sort(key=lambda r: r["score"], reverse=True)
        top_results = _fb_candidates[:max_results]
        fallback_used = True

    execution_time = time.time() - start_time
    speed = round(tested / max(execution_time, 0.001), 1)

    logger.info(
        f"⚡ Fast RSI optimization complete: {tested}/{total} tested in {execution_time:.1f}s "
        f"({speed} combos/s), {len(results)} results found"
    )

    timed_out = time.time() - start_time >= timeout_seconds

    # Mark progress as completed
    if strategy_id:
        update_optimization_progress(
            strategy_id,
            status="completed" if not timed_out else "partial",
            tested=tested,
            total=total,
            best_score=top_results[0]["score"] if top_results else 0.0,
            results_found=len(results),
            speed=speed,
            eta_seconds=0,
            started_at=start_time,
        )

    return {
        "status": "completed" if not timed_out else "partial",
        "total_combinations": total,
        "tested_combinations": tested,
        "results_passing_filters": len(results),
        "results_found": len(results),
        "top_results": top_results,
        "best_params": top_results[0]["params"] if top_results else {},
        "best_score": top_results[0]["score"] if top_results else 0.0,
        "best_metrics": {k: v for k, v in top_results[0].items() if k not in ("params", "score")}
        if top_results
        else {},
        "execution_time_seconds": round(execution_time, 2),
        "speed_combinations_per_sec": speed,
        "early_stopped": early_stopping and no_improvement_count >= early_stopping_patience,
        "fallback_used": fallback_used,
        "no_positive_results": bool(top_results and top_results[0].get("score", 0) < 0),
        "optimize_metric": optimize_metric,
    }


def _fast_rsi_signals(
    rsi: pd.Series,
    rsi_prev: pd.Series,
    params: dict[str, Any],
    direction: str = "both",
) -> np.ndarray:
    """Generate RSI signals using pre-computed RSI series.

    This is the fast-path signal generator that avoids the full
    StrategyBuilderAdapter pipeline. Only evaluates threshold conditions.
    """
    n = len(rsi)
    signals = np.zeros(n)

    use_long_range = params.get("use_long_range", False)
    use_short_range = params.get("use_short_range", False)
    use_cross_level = params.get("use_cross_level", False)

    # Range conditions
    if use_long_range:
        long_more = float(params.get("long_rsi_more", 0))
        long_less = float(params.get("long_rsi_less", 50))
        if long_more > long_less:
            long_more, long_less = long_less, long_more
        long_range = (rsi >= long_more) & (rsi <= long_less)
    else:
        long_range = pd.Series(True, index=rsi.index)

    if use_short_range:
        short_less = float(params.get("short_rsi_less", 100))
        short_more = float(params.get("short_rsi_more", 50))
        if short_more > short_less:
            short_more, short_less = short_less, short_more
        short_range = (rsi <= short_less) & (rsi >= short_more)
    else:
        short_range = pd.Series(True, index=rsi.index)

    # Cross conditions
    if use_cross_level:
        cross_long_level = float(params.get("cross_long_level", 29))
        cross_short_level = float(params.get("cross_short_level", 55))
        cross_long = (rsi_prev < cross_long_level) & (rsi >= cross_long_level)
        cross_short = (rsi_prev > cross_short_level) & (rsi <= cross_short_level)

        # Apply cross memory if enabled
        if params.get("use_cross_memory", False):
            memory_bars = int(params.get("cross_memory_bars", 5))
            cross_long = _apply_memory(cross_long, memory_bars)
            cross_short = _apply_memory(cross_short, memory_bars)

        long_cross = cross_long
        short_cross = cross_short
    else:
        long_cross = pd.Series(True, index=rsi.index)
        short_cross = pd.Series(True, index=rsi.index)

    # Combine conditions (matching indicator_handlers.py logic)
    if use_long_range and use_cross_level:
        _cross_l = float(params.get("cross_long_level", 29))
        _long_more = float(params.get("long_rsi_more", 0))
        if _cross_l < _long_more:
            # Conflict resolution: also fire when RSI crosses UP through long_rsi_more
            cross_into_range = (rsi_prev < _long_more) & (rsi >= _long_more)
            long_signal = (long_cross | cross_into_range) & long_range
        else:
            long_signal = long_cross & long_range
    elif use_long_range:
        long_signal = long_range
    else:
        long_signal = long_cross

    if use_short_range and use_cross_level:
        _cross_s = float(params.get("cross_short_level", 55))
        _short_less = float(params.get("short_rsi_less", 100))
        if _cross_s > _short_less:
            cross_into_range_s = (rsi_prev > _short_less) & (rsi <= _short_less)
            short_signal = (short_cross | cross_into_range_s) & short_range
        else:
            short_signal = short_cross & short_range
    elif use_short_range:
        short_signal = short_range
    else:
        short_signal = short_cross

    # Legacy overbought/oversold
    overbought = float(params.get("overbought", 0))
    oversold = float(params.get("oversold", 0))
    if overbought > 0 and oversold > 0 and not use_long_range and not use_short_range and not use_cross_level:
        long_signal = (rsi <= oversold).fillna(False)
        short_signal = (rsi >= overbought).fillna(False)

    # Apply direction filter
    long_arr = long_signal.fillna(False).values.astype(bool)
    short_arr = short_signal.fillna(False).values.astype(bool)

    if direction in ("long", "both"):
        signals[long_arr] = 1
    if direction in ("short", "both"):
        # Only set short where long isn't already set
        short_mask = short_arr & (signals == 0)
        signals[short_mask] = -1

    return signals


def _apply_memory(signal: pd.Series, memory_bars: int) -> pd.Series:
    """Apply signal memory: keep signal True for N bars after it fires."""
    result = signal.copy()
    counter = 0
    for i in range(len(result)):
        if signal.iloc[i]:
            counter = memory_bars
            result.iloc[i] = True
        elif counter > 0:
            counter -= 1
            result.iloc[i] = True
        else:
            result.iloc[i] = False
    return result


def _precompute_dca_close_cache(
    final_dca_config: dict[str, Any],
    config_params: dict[str, Any],
    ohlcv: pd.DataFrame,
) -> dict | None:
    """Pre-compute DCA close-condition indicator caches for the given OHLCV.

    Called ONCE before the optimization loop when DCA is enabled and the
    close_conditions parameters are static (don't change across trials).
    Returns a cache dict suitable for injection into each DCAEngine via
    ``_inject_close_indicator_cache``.  Returns None on error.
    """
    from backend.backtesting.engines.dca_engine import DCAEngine
    from backend.backtesting.models import BacktestConfig, StrategyType

    try:
        config = BacktestConfig(
            symbol=config_params.get("symbol", "BTCUSDT"),
            interval=config_params.get("interval", "15"),
            start_date="2025-01-01",
            end_date="2026-01-01",
            strategy_type=StrategyType.CUSTOM,
            strategy_params={
                "close_conditions": final_dca_config.get("close_conditions", {}),
                "indent_order": final_dca_config.get("indent_order", {}),
            },
            initial_capital=config_params.get("initial_capital", 10000.0),
            commission_value=config_params.get("commission", COMMISSION_TV),
            taker_fee=config_params.get("commission", COMMISSION_TV),
            maker_fee=config_params.get("commission", COMMISSION_TV),
            dca_enabled=True,
        )
        engine = DCAEngine()
        engine._configure_from_config(config)
        engine._precompute_close_condition_indicators(ohlcv)
        cache = engine._extract_close_indicator_cache()
        logger.debug("⚡ DCA close-condition indicator cache built (will be reused for all trials)")
        return cache
    except Exception as e:
        logger.warning(f"Failed to pre-compute DCA close-condition cache: {e}")
        return None


def _is_dca_sltp_only_optimization(
    param_combinations: list[dict[str, Any]],
    base_graph: dict[str, Any],
) -> tuple[bool, list[str]]:
    """
    Detect if optimization only varies static_sltp block params (stop_loss_percent /
    take_profit_percent) while keeping RSI / other indicator params constant.

    When True, the Numba DCA batch path can pre-compute entry signals ONCE and
    sweep all (sl, tp) combinations in parallel without re-running the adapter.

    Returns:
        (is_sltp_only, sltp_block_ids)
    """
    if not param_combinations:
        return False, []

    # Collect all param paths that vary across combinations
    varying: set[str] = set()
    if len(param_combinations) > 1:
        first = param_combinations[0]
        for combo in param_combinations[1:]:
            for k, v in combo.items():
                if k in first and first[k] != v:
                    varying.add(k)
            for k in first:
                if k not in combo:
                    varying.add(k)
    else:
        varying = set(param_combinations[0].keys())

    # All varying paths must be from static_sltp blocks only
    sltp_block_ids: list[str] = []
    blocks = base_graph.get("blocks", [])
    for b in blocks:
        if b.get("type") == "static_sltp":
            sltp_block_ids.append(b["id"])

    if not sltp_block_ids:
        return False, []

    for path in varying:
        if "." not in path:
            return False, sltp_block_ids
        block_id, _ = path.split(".", 1)
        if block_id not in sltp_block_ids:
            # Non-SLTP param varies → mixed case. Return the SLTP ids so
            # caller can activate the mixed batch path.
            return False, sltp_block_ids

    return bool(varying), sltp_block_ids


def _run_dca_sltp_batch_numba(
    base_graph: dict[str, Any],
    ohlcv: pd.DataFrame,
    param_combinations: list[dict[str, Any]],
    config_params: dict[str, Any],
    final_dca_config: dict[str, Any],
    direction_str: str,
    sltp_block_ids: list[str],
) -> list[dict[str, Any] | None]:
    """
    Fast DCA optimization path: pre-compute entry signals ONCE, then batch-simulate
    all (sl, tp) combinations via Numba prange (parallel).

    Returns list of result dicts aligned with param_combinations (None on failure).
    """
    from backend.backtesting.numba_dca_engine import run_dca_batch_numba
    from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

    n = len(param_combinations)
    if n == 0:
        return []

    try:
        # Generate entry signals once using the base graph (no SL/TP in signals)
        adapter = StrategyBuilderAdapter(base_graph)
        signal_result = adapter.generate_signals(ohlcv)
        if signal_result is None:
            return [None] * n

        entries = signal_result.entries if signal_result.entries is not None else None
        short_entries = signal_result.short_entries

        # Build int8 signal array: +1 long, -1 short, 0 none
        n_bars = len(ohlcv)
        signals_int = np.zeros(n_bars, dtype=np.int8)
        if entries is not None:
            signals_int[entries.to_numpy(dtype=bool)] = 1
        if short_entries is not None:
            signals_int[short_entries.to_numpy(dtype=bool)] -= 1

        # Extract (sl, tp) arrays for each combo
        sl_arr = np.empty(n, dtype=np.float64)
        tp_arr = np.empty(n, dtype=np.float64)
        default_sl = 0.03
        default_tp = 0.06
        for i, combo in enumerate(param_combinations):
            sl_val = default_sl
            tp_val = default_tp
            for path, val in combo.items():
                _, param_key = path.split(".", 1)
                if param_key == "stop_loss_percent":
                    sl_val = float(val) / 100.0
                elif param_key == "take_profit_percent":
                    tp_val = float(val) / 100.0
            sl_arr[i] = sl_val
            tp_arr[i] = tp_val

        # DCA config scalars
        direction_int = 0 if direction_str == "long" else (1 if direction_str == "short" else 2)
        order_count = int(final_dca_config.get("dca_order_count", 5))
        grid_size_pct = float(final_dca_config.get("dca_grid_size_percent", 10.0))
        martingale_coef = float(final_dca_config.get("dca_martingale_coef", 1.3))
        initial_capital = float(config_params.get("initial_capital", 10000.0))
        leverage = float(config_params.get("leverage", 1.0))
        taker_fee = float(config_params.get("commission", COMMISSION_TV))

        # Extract close_by_time, breakeven, and safety_close from base graph (for parity with V4)
        _sltp_max_bars = 0
        _sltp_min_profit_pct = 0.0
        _sltp_be_activation = 0.0
        _sltp_be_offset = 0.0
        _sltp_safety_close = int(bool(final_dca_config.get("dca_safety_close_enabled", True)))
        _sltp_safety_threshold = float(final_dca_config.get("dca_drawdown_threshold", 30.0))
        for _blk in base_graph.get("blocks", []):
            _bt = _blk.get("type", "")
            _bp = _blk.get("params") or _blk.get("config") or {}
            if _bt == "close_by_time":
                _sltp_max_bars = int(_bp.get("bars_since_entry", _bp.get("bars", 0)) or 0)
                _sltp_min_profit_pct = float(_bp.get("min_profit_percent", 0.0)) / 100.0
            elif _bt == "static_sltp" and _bp.get("activate_breakeven", False):
                _sltp_be_activation = float(_bp.get("breakeven_activation_percent", 0.5)) / 100.0
                _sltp_be_offset = float(_bp.get("new_breakeven_sl_percent", 0.1)) / 100.0

        # Run Numba batch
        batch = run_dca_batch_numba(
            close=ohlcv["close"].to_numpy(dtype=np.float64),
            high=ohlcv["high"].to_numpy(dtype=np.float64),
            low=ohlcv["low"].to_numpy(dtype=np.float64),
            entry_signals=signals_int,
            sl_pct_arr=sl_arr,
            tp_pct_arr=tp_arr,
            direction=direction_int,
            order_count=order_count,
            grid_size_pct=grid_size_pct,
            martingale_coef=martingale_coef,
            initial_capital=initial_capital,
            position_size_frac=1.0,
            leverage=leverage,
            taker_fee=taker_fee,
            max_bars_in_trade=_sltp_max_bars,
            min_profit_close_pct=_sltp_min_profit_pct,
            breakeven_activation_pct=_sltp_be_activation,
            breakeven_offset_pct=_sltp_be_offset,
            safety_close_enabled=_sltp_safety_close,
            safety_close_threshold_pct=_sltp_safety_threshold,
            bars_per_month=_bars_per_month(str(config_params.get("interval", "30"))),
        )

        results: list[dict[str, Any] | None] = []
        for i in range(n):
            nt = int(batch["n_trades"][i])
            if nt == 0:
                results.append(None)
                continue
            _np = float(batch["net_profit"][i])
            _dd = float(batch["max_drawdown"][i])  # fraction 0-1
            _wr = float(batch["win_rate"][i])  # fraction 0-1
            _pf = float(batch["profit_factor"][i])
            # calmar = total_return% / max_drawdown% (analytically derivable from batch)
            _calmar = (_np / initial_capital * 100.0) / (_dd * 100.0) if _dd > 0 else 0.0
            # payoff = avg_win / avg_loss = profit_factor * (1 - win_rate) / win_rate
            _payoff = _pf * (1.0 - _wr) / _wr if _wr > 0 else 0.0
            results.append(
                {
                    "net_profit": _np,
                    "net_profit_pct": _np / initial_capital * 100.0,
                    "total_return": _np / initial_capital * 100.0,
                    "max_drawdown": _dd * 100.0,
                    "win_rate": _wr * 100.0,
                    "sharpe_ratio": float(batch["sharpe"][i]),
                    "profit_factor": _pf,
                    "total_trades": nt,
                    "n_trades": nt,
                    "sortino_ratio": float(batch["sortino"][i]),
                    "calmar_ratio": float(np.clip(_calmar, -1e6, 1e6)),
                    "payoff_ratio": float(np.clip(_payoff, 0.0, 1e6)),
                    # expectancy / avg_win / avg_loss not available from Numba batch
                    "expectancy": 0.0,
                    "expectancy_pct": 0.0,
                    "avg_win": 0.0,
                    "avg_win_pct": 0.0,
                    "avg_loss": 0.0,
                    "avg_loss_pct": 0.0,
                }
            )
        logger.info(f"⚡ Numba DCA batch: {n} combos done in parallel")
        return results

    except Exception as exc:
        logger.warning(f"Numba DCA batch failed, falling back to Python path: {exc}")
        return [None] * n  # caller will fall back to standard loop


def _run_dca_mixed_batch_numba(
    base_graph: dict[str, Any],
    ohlcv: pd.DataFrame,
    param_combinations: list[dict[str, Any]],
    config_params: dict[str, Any],
    final_dca_config: dict[str, Any],
    direction_str: str,
    sltp_block_ids: list[str],
    progress_callback: Any = None,
) -> list[dict[str, Any] | None]:
    """
    Nested DCA batch: handles mixed RSI+SLTP optimization (e.g. DCA-RSI-6 with
    31×26×21×18 = 304,668 combos).

    Algorithm:
        1. Split each combo into indicator params (RSI, etc.) and SLTP params.
        2. Group all combos by their indicator params → N_indicator unique groups.
        3. For each group:
              a. Clone base_graph with indicator params applied.
              b. Generate entry signals ONCE via StrategyBuilderAdapter.
              c. Collect all SLTP (sl, tp) variants for this group.
              d. Run run_dca_batch_numba() over the SLTP sub-batch.
              e. Store results back in original order.

    Speedup for DCA-RSI-6 (806 indicator groups × 378 SLTP each):
        Standard:  304,668 × ~0.4s ≈ 5h 17m
        This path: 806 × 0.1s (signals) + 806 × 0.002s (Numba) ≈ 83s  (~230× faster)

    Returns list of result dicts aligned with param_combinations (None on failure).
    """
    from backend.backtesting.numba_dca_engine import run_dca_batch_numba
    from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

    n = len(param_combinations)
    if n == 0:
        return []

    try:
        # ── Step 1: Split paths into SLTP vs indicator ──────────────────────────
        sltp_id_set = set(sltp_block_ids)

        def _is_sltp_path(path: str) -> bool:
            block_id = path.split(".", 1)[0]
            return block_id in sltp_id_set

        # ── Step 2: Group combos by indicator params ────────────────────────────
        # Key: frozenset of (indicator_path, value) tuples → comparable/hashable
        group_key_to_indices: dict[tuple, list[int]] = {}
        for i, combo in enumerate(param_combinations):
            ind_key = tuple(sorted((k, v) for k, v in combo.items() if not _is_sltp_path(k)))
            group_key_to_indices.setdefault(ind_key, []).append(i)

        n_groups = len(group_key_to_indices)
        _log_info(f"⚡ Mixed DCA batch: {n} combos → {n_groups} indicator groups × ~{n // max(n_groups, 1)} SLTP each")

        # ── Shared arrays for the whole OHLCV ───────────────────────────────────
        close_np = ohlcv["close"].to_numpy(dtype=np.float64)
        high_np = ohlcv["high"].to_numpy(dtype=np.float64)
        low_np = ohlcv["low"].to_numpy(dtype=np.float64)

        # DCA engine scalars (same for all groups)
        direction_int = 0 if direction_str == "long" else (1 if direction_str == "short" else 2)
        order_count = int(final_dca_config.get("dca_order_count", 5))
        grid_size_pct = float(final_dca_config.get("dca_grid_size_percent", 10.0))
        martingale = float(final_dca_config.get("dca_martingale_coef", 1.3))
        capital = float(config_params.get("initial_capital", 10000.0))
        leverage = float(config_params.get("leverage", 1.0))
        taker_fee = float(config_params.get("commission", COMMISSION_TV))

        # Extract close_by_time, breakeven, and safety_close from base_graph (parity with V4)
        _mx_max_bars = 0
        _mx_min_profit_pct = 0.0
        _mx_be_activation = 0.0
        _mx_be_offset = 0.0
        _mx_safety_close = int(bool(final_dca_config.get("dca_safety_close_enabled", True)))
        _mx_safety_threshold = float(final_dca_config.get("dca_drawdown_threshold", 30.0))
        for _blk in base_graph.get("blocks", []):
            _bt = _blk.get("type", "")
            _bp = _blk.get("params") or _blk.get("config") or {}
            if _bt == "close_by_time":
                _mx_max_bars = int(_bp.get("bars_since_entry", _bp.get("bars", 0)) or 0)
                _mx_min_profit_pct = float(_bp.get("min_profit_percent", 0.0)) / 100.0
            elif _bt == "static_sltp" and _bp.get("activate_breakeven", False):
                _mx_be_activation = float(_bp.get("breakeven_activation_percent", 0.5)) / 100.0
                _mx_be_offset = float(_bp.get("new_breakeven_sl_percent", 0.1)) / 100.0

        results: list[dict[str, Any] | None] = [None] * n
        _groups_no_signals = 0
        _groups_sig_error = 0
        _groups_ok = 0

        # ── Step 3: Process each indicator group ────────────────────────────────
        for group_idx, (ind_key, indices) in enumerate(group_key_to_indices.items()):
            indicator_overrides = dict(ind_key)

            # 3a. Clone graph with indicator params
            ind_graph = clone_graph_with_params(base_graph, indicator_overrides)

            # 3b. Generate signals once for this indicator combo
            try:
                adapter = StrategyBuilderAdapter(ind_graph)
                sig = adapter.generate_signals(ohlcv)
            except Exception as _sig_exc:
                logger.debug(f"Mixed batch: signal gen failed for group {group_idx}: {_sig_exc}")
                _groups_sig_error += 1
                continue  # leave results[i] = None for these combos

            if sig is None:
                _groups_no_signals += 1
                continue

            n_bars = len(ohlcv)
            signals_int = np.zeros(n_bars, dtype=np.int8)
            if sig.entries is not None:
                signals_int[sig.entries.to_numpy(dtype=bool)] = 1
            if sig.short_entries is not None:
                signals_int[sig.short_entries.to_numpy(dtype=bool)] -= 1

            n_long_signals = int((signals_int > 0).sum())
            n_short_signals = int((signals_int < 0).sum())
            if n_long_signals == 0 and n_short_signals == 0:
                _groups_no_signals += 1
                continue  # no signals → all SLTP combos for this group will have 0 trades
            _groups_ok += 1

            # Log first-group signal counts for debugging
            if group_idx == 0:
                logger.debug(
                    f"Mixed DCA group 0 signals: long={n_long_signals}, short={n_short_signals}, "
                    f"direction='{direction_str}' (int={direction_int}), ohlcv_bars={n_bars}, "
                    f"indicator_overrides={indicator_overrides}"
                )

            # 3c. Collect SLTP (sl%, tp%) for all combos in this group
            m = len(indices)
            sl_arr = np.empty(m, dtype=np.float64)
            tp_arr = np.empty(m, dtype=np.float64)
            default_sl, default_tp = 0.03, 0.06
            for j, idx in enumerate(indices):
                sl_val, tp_val = default_sl, default_tp
                for path, val in param_combinations[idx].items():
                    if _is_sltp_path(path):
                        _, pk = path.split(".", 1)
                        if pk == "stop_loss_percent":
                            sl_val = float(val) / 100.0
                        elif pk == "take_profit_percent":
                            tp_val = float(val) / 100.0
                sl_arr[j] = sl_val
                tp_arr[j] = tp_val

            # 3d. Numba batch over SLTP sub-batch.
            # Apply DCA structural params from this group's indicator_overrides
            # (e.g. order_count, grid_size_percent, martingale_coefficient may be optimized).
            _group_order_count = order_count
            _group_grid_size_pct = grid_size_pct
            _group_martingale = martingale
            for _path, _val in indicator_overrides.items():
                if "." in _path:
                    _, _pk = _path.split(".", 1)
                    if _pk == "order_count":
                        _group_order_count = int(_val)
                    elif _pk in ("grid_size_percent", "grid_size_pct"):
                        _group_grid_size_pct = float(_val)
                    elif _pk in ("martingale_coefficient", "martingale_coef"):
                        _group_martingale = float(_val)

            batch = run_dca_batch_numba(
                close=close_np,
                high=high_np,
                low=low_np,
                entry_signals=signals_int,
                sl_pct_arr=sl_arr,
                tp_pct_arr=tp_arr,
                direction=direction_int,
                order_count=_group_order_count,
                grid_size_pct=_group_grid_size_pct,
                martingale_coef=_group_martingale,
                initial_capital=capital,
                position_size_frac=1.0,
                leverage=leverage,
                taker_fee=taker_fee,
                max_bars_in_trade=_mx_max_bars,
                min_profit_close_pct=_mx_min_profit_pct,
                breakeven_activation_pct=_mx_be_activation,
                breakeven_offset_pct=_mx_be_offset,
                safety_close_enabled=_mx_safety_close,
                safety_close_threshold_pct=_mx_safety_threshold,
                bars_per_month=_bars_per_month(str(config_params.get("interval", "30"))),
            )

            # 3e. Map results back to original indices
            for j, idx in enumerate(indices):
                nt = int(batch["n_trades"][j])
                if nt == 0:
                    continue
                _np = float(batch["net_profit"][j])
                _dd = float(batch["max_drawdown"][j])  # fraction 0-1
                _wr = float(batch["win_rate"][j])  # fraction 0-1
                _pf = float(batch["profit_factor"][j])
                _calmar = (_np / capital * 100.0) / (_dd * 100.0) if _dd > 0 else 0.0
                _payoff = _pf * (1.0 - _wr) / _wr if _wr > 0 else 0.0
                results[idx] = {
                    "net_profit": _np,
                    "net_profit_pct": _np / capital * 100.0,
                    "total_return": _np / capital * 100.0,
                    "max_drawdown": _dd * 100.0,
                    "win_rate": _wr * 100.0,
                    "sharpe_ratio": float(batch["sharpe"][j]),
                    "profit_factor": _pf,
                    "total_trades": nt,
                    "n_trades": nt,
                    "sortino_ratio": float(batch["sortino"][j]),
                    "calmar_ratio": float(np.clip(_calmar, -1e6, 1e6)),
                    "payoff_ratio": float(np.clip(_payoff, 0.0, 1e6)),
                    "expectancy": 0.0,
                    "expectancy_pct": 0.0,
                    "avg_win": 0.0,
                    "avg_win_pct": 0.0,
                    "avg_loss": 0.0,
                    "avg_loss_pct": 0.0,
                }

            # Update progress after each indicator group (called by caller via callback)
            if progress_callback is not None:
                try:
                    combos_done = sum(len(v) for k, v in list(group_key_to_indices.items())[: group_idx + 1])
                    progress_callback(combos_done, n)
                except Exception:
                    pass

        non_none = sum(1 for r in results if r is not None)
        logger.info(
            f"⚡ Mixed DCA batch complete: {n} combos, {n_groups} groups — "
            f"ok={_groups_ok}, no_signals={_groups_no_signals}, errors={_groups_sig_error}, "
            f"results_with_trades={non_none}"
        )
        if non_none == 0:
            _diag = f"groups_ok={_groups_ok}, groups_no_signals={_groups_no_signals}, groups_error={_groups_sig_error}"
            if _groups_no_signals == n_groups:
                logger.warning(
                    f"⚠️ Mixed DCA batch: ALL {n_groups} indicator groups produced 0 entry signals. "
                    f"Cause: RSI/indicator params in optimization range never trigger signals. "
                    f"Check oversold/overbought ranges — e.g. oversold=5 means RSI must drop below 5 to enter. "
                    f"Direction: '{direction_str}', bars={len(ohlcv)}. {_diag}"
                )
            elif _groups_sig_error == n_groups:
                logger.warning(
                    f"⚠️ Mixed DCA batch: ALL {n_groups} groups failed signal generation (exception). "
                    f"Check StrategyBuilderAdapter for errors with these param ranges. {_diag}"
                )
            else:
                logger.warning(
                    f"⚠️ Mixed DCA batch: 0 trades from {n} combinations. "
                    f"Direction: '{direction_str}' (int={direction_int}), "
                    f"order_count={order_count}, grid_size={grid_size_pct}%. {_diag}"
                )
        return results

    except Exception as exc:
        logger.warning(f"Mixed DCA batch failed, falling back to Python path: {exc}")
        return [None] * n


def _run_dca_with_signals(
    signals: np.ndarray,
    ohlcv: pd.DataFrame,
    config_params: dict[str, Any],
    final_dca_config: dict[str, Any],
    direction_str: str,
    block_stop_loss: float | None,
    block_take_profit: float | None,
    block_breakeven_enabled: bool,
    block_breakeven_activation_pct: float,
    block_breakeven_offset: float,
    block_close_only_in_profit: bool,
    block_sl_type: str,
    block_max_bars_in_trade: int,
    close_indicator_cache: dict | None = None,
) -> dict[str, Any] | None:
    """Run DCA engine with pre-computed signals (bypasses adapter signal generation)."""
    from backend.backtesting.engines.dca_engine import DCAEngine
    from backend.backtesting.models import BacktestConfig, StrategyType

    try:
        config = BacktestConfig(
            symbol=config_params.get("symbol", "BTCUSDT"),
            interval=config_params.get("interval", "15"),
            start_date="2025-01-01",
            end_date="2026-01-01",
            strategy_type=StrategyType.CUSTOM,
            strategy_params={
                "close_conditions": final_dca_config.get("close_conditions", {}),
                "indent_order": final_dca_config.get("indent_order", {}),
            },
            initial_capital=config_params.get("initial_capital", 10000.0),
            position_size=config_params.get("position_size", 1.0),
            leverage=config_params.get("leverage", 1),
            direction=direction_str,
            stop_loss=block_stop_loss if block_stop_loss else None,
            take_profit=block_take_profit if block_take_profit else None,
            commission_value=config_params.get("commission", COMMISSION_TV),
            taker_fee=config_params.get("commission", COMMISSION_TV),
            maker_fee=config_params.get("commission", COMMISSION_TV),
            dca_enabled=True,
            dca_direction=final_dca_config.get("dca_direction", "both"),
            dca_order_count=final_dca_config.get("dca_order_count", 5),
            dca_grid_size_percent=final_dca_config.get("dca_grid_size_percent", 10.0),
            dca_martingale_coef=final_dca_config.get("dca_martingale_coef", 1.0),
            dca_martingale_mode=final_dca_config.get("dca_martingale_mode", "multiply_each"),
            dca_log_step_enabled=final_dca_config.get("dca_log_step_enabled", False),
            dca_log_step_coef=final_dca_config.get("dca_log_step_coef", 1.1),
            dca_safety_close_enabled=final_dca_config.get("dca_safety_close_enabled", True),
            dca_drawdown_threshold=final_dca_config.get("dca_drawdown_threshold", 30.0),
            dca_multi_tp_enabled=final_dca_config.get("dca_multi_tp_enabled", False),
            dca_tp1_percent=final_dca_config.get("dca_tp1_percent", 0.5),
            dca_tp1_close_percent=final_dca_config.get("dca_tp1_close_percent", 25.0),
            dca_tp2_percent=final_dca_config.get("dca_tp2_percent", 1.0),
            dca_tp2_close_percent=final_dca_config.get("dca_tp2_close_percent", 25.0),
            dca_tp3_percent=final_dca_config.get("dca_tp3_percent", 2.0),
            dca_tp3_close_percent=final_dca_config.get("dca_tp3_close_percent", 25.0),
            dca_tp4_percent=final_dca_config.get("dca_tp4_percent", 3.0),
            dca_tp4_close_percent=final_dca_config.get("dca_tp4_close_percent", 25.0),
            breakeven_enabled=block_breakeven_enabled,
            breakeven_activation_pct=block_breakeven_activation_pct,
            breakeven_offset=block_breakeven_offset,
            sl_type=block_sl_type,
            max_bars_in_trade=block_max_bars_in_trade,
            close_only_in_profit=block_close_only_in_profit,
        )

        engine = DCAEngine()
        # Inject pre-computed close-condition indicator cache (avoids recalculating
        # RSI/Stoch/MA/BB/Keltner/PSAR for every trial when OHLCV is unchanged)
        if close_indicator_cache is not None:
            engine._inject_close_indicator_cache(close_indicator_cache)
        # Inject pre-computed signals directly (bypass _generate_signals_from_config)
        engine._precomputed_signals = signals
        bt_result = engine.run_from_config(config, ohlcv, custom_strategy=None)

        if bt_result is None:
            return None

        metrics = getattr(bt_result, "metrics", None) or getattr(bt_result, "performance", None)
        if metrics is None:
            return None

        def _safe(v: Any, default: float = 0.0) -> float:
            return float(v) if v is not None else default

        win_rate = _safe(getattr(metrics, "win_rate", 0))
        if win_rate <= 1.0:
            win_rate *= 100.0

        return {
            "total_return": _safe(getattr(metrics, "total_return", 0)),
            "sharpe_ratio": _safe(getattr(metrics, "sharpe_ratio", 0)),
            "sharpe_method": str(getattr(metrics, "sharpe_method", "fallback") or "fallback"),
            "sharpe_samples": int(getattr(metrics, "sharpe_samples", 0) or 0),
            "max_drawdown": _safe(getattr(metrics, "max_drawdown", 0)),
            "win_rate": win_rate,
            "total_trades": int(getattr(metrics, "total_trades", 0) or 0),
            "profit_factor": _safe(getattr(metrics, "profit_factor", 0)),
            "winning_trades": int(getattr(metrics, "winning_trades", 0) or 0),
            "losing_trades": int(getattr(metrics, "losing_trades", 0) or 0),
            "net_profit": _safe(getattr(metrics, "net_profit", 0)),
            "net_profit_pct": _safe(getattr(metrics, "total_return", 0)),
            "avg_trade": _safe(getattr(metrics, "avg_trade", 0)),
            "avg_win": _safe(getattr(metrics, "avg_win", 0)),
            "avg_loss": _safe(getattr(metrics, "avg_loss", 0)),
            # % aliases for unit-toggle constraints
            "avg_win_pct": _safe(getattr(metrics, "avg_win", 0)),
            "avg_loss_pct": _safe(getattr(metrics, "avg_loss", 0)),
            "expectancy": _safe(getattr(metrics, "expectancy", 0)),
            "expectancy_pct": _safe(getattr(metrics, "expectancy_pct", 0)),
            "sortino_ratio": _safe(getattr(metrics, "sortino_ratio", 0)),
            "calmar_ratio": _safe(getattr(metrics, "calmar_ratio", 0)),
            "payoff_ratio": _safe(getattr(metrics, "payoff_ratio", 0)),
        }
    except Exception as e:
        logger.debug(f"DCA with pre-computed signals failed: {e}")
        return None


def build_infeasibility_checker(base_graph: dict[str, Any]):
    """Pre-compute base block params once and return a fast per-combo checker.

    Call this ONCE before the optimization loop. The returned function is O(n_overrides)
    per combo — much faster than rebuilding block_params from the full graph each time.

    Returns a callable: checker(overrides) -> bool  (True = skip this combo)
    """
    # Extract base params for RSI blocks only (the only ones we check)
    rsi_blocks: list[tuple[str, dict[str, Any]]] = []
    for block in base_graph.get("blocks", []):
        if block.get("type") == "rsi":
            bid = block.get("id", "")
            bp = dict(block.get("params") or block.get("config") or {})
            rsi_blocks.append((bid, bp))

    if not rsi_blocks:
        # No RSI blocks → nothing to filter → always feasible
        return lambda overrides: False

    def _checker(overrides: dict[str, Any]) -> bool:
        for bid, base_bp in rsi_blocks:
            # Start from base values, apply any overrides for this block
            bp = base_bp  # shared reference — DO NOT mutate
            prefix = bid + "."
            # Collect overrides for this block only
            block_overrides = {k[len(prefix) :]: v for k, v in overrides.items() if k.startswith(prefix)}

            if not block_overrides:
                # No overrides for this block → use base values directly
                pass
            else:
                # Merge: create a combined view (avoid full copy when possible)
                bp = {**base_bp, **block_overrides}

            use_cross = bp.get("use_cross_level", False)
            use_long_range = bp.get("use_long_range", False)
            use_short_range = bp.get("use_short_range", False)

            # RSI(1) is degenerate: always jumps to 0 or 100 → no cross signals
            period = float(bp.get("period", 14))
            if period <= 1:
                return True  # infeasible

            if use_cross and use_long_range:
                # NOTE: cross_long_level < long_rsi_more is NOT infeasible.
                # oscillators.py has a conflict-resolution path that fires an "extended
                # cross" signal when RSI enters the range from below (at long_rsi_more).
                # Only prune the degenerate edge where cross level equals range floor
                # and no bar movement could produce a signal.
                # Nothing to prune here — both regions are explored by the optimizer.
                pass

            if use_cross and use_short_range:
                cross_short = float(bp.get("cross_short_level", 55))
                short_less = float(bp.get("short_rsi_less", 100))
                if cross_short >= short_less:
                    return True  # infeasible: cross at or above range ceiling → 0 signals

        return False

    return _checker


def combo_is_infeasible(overrides: dict[str, Any], base_graph: dict[str, Any]) -> bool:
    """Single-call wrapper around build_infeasibility_checker.

    For the optimization loop use build_infeasibility_checker() once and reuse
    the returned checker — this avoids rebuilding base_block_params every call.
    """
    return build_infeasibility_checker(base_graph)(overrides)


def _reeval_top_accurate(
    top_results: list[dict[str, Any]],
    base_graph: dict[str, Any],
    ohlcv: pd.DataFrame,
    config_params: dict[str, Any],
    optimize_metric: str,
    weights: dict[str, float] | None,
) -> list[dict[str, Any]]:
    """Variant A: re-evaluate top-N results with FallbackEngineV4 for optimizer-backtester parity.

    NumbaEngineV2 (used during optimization trials for speed) silently ignores extra_data,
    so profit_only / min_profit conditions in Close-by-Time are not enforced.
    FallbackEngineV4 handles extra_data correctly — matching what the manual Backtest button produces.
    """
    from backend.optimization.scoring import calculate_composite_score

    reeval_config = {**config_params, "engine_type": "fallback"}
    accurate: list[dict[str, Any]] = []
    for r in top_results:
        modified_graph = clone_graph_with_params(base_graph, r["params"])
        acc = run_builder_backtest(modified_graph, ohlcv, reeval_config)
        if acc is not None:
            score_raw = calculate_composite_score(acc, optimize_metric, weights or {})
            score = _compress_score(score_raw, optimize_metric)
            accurate.append({**r, **acc, "score_raw": score_raw, "score": score})
    if not accurate:
        return top_results
    accurate.sort(key=lambda x: x["score"], reverse=True)
    return accurate


def run_builder_grid_search(
    base_graph: dict[str, Any],
    ohlcv: pd.DataFrame,
    param_combinations: Any,  # list[dict] | Iterator[dict] — lazy grid iterator supported
    config_params: dict[str, Any],
    optimize_metric: str = "sharpe_ratio",
    weights: dict[str, float] | None = None,
    max_results: int = 20,
    early_stopping: bool = False,
    early_stopping_patience: int = 20,
    timeout_seconds: int = 3600,
    strategy_id: str = "",
    total_combinations: int = 0,  # pre-computed total; 0 → derive from list length
) -> dict[str, Any]:
    """
    Run grid search optimization for a builder strategy.

    ``param_combinations`` can be either a materialized list **or** a lazy
    iterator produced by ``generate_builder_param_combinations``.  Using an
    iterator keeps memory usage O(1) regardless of grid size, enabling
    exhaustive search over millions of combinations.

    Fast-paths (RSI-threshold-only, Numba DCA batch) require a materialized
    list; when an iterator is supplied those paths are attempted only if the
    total is small enough to materialise safely (≤ 2 000 000).

    Args:
        base_graph: Base strategy graph to clone.
        ohlcv: OHLCV DataFrame.
        param_combinations: List or lazy iterator of param-override dicts.
        config_params: Backtest config params.
        optimize_metric: Metric to optimize.
        weights: Metric weights for composite scoring.
        max_results: Max results to return.
        early_stopping: Enable early stopping.
        early_stopping_patience: Patience for early stopping.
        timeout_seconds: Total timeout.
        strategy_id: Strategy ID for progress tracking.
        total_combinations: Exact total count (provided by caller to avoid
            materialisation; derived from list length when 0).

    Returns:
        Dict with optimization results.
    """
    # ── Normalise to iterator + known total ──────────────────────────────────
    # If caller passed a list we can len() it and still use fast-paths.
    # If caller passed a generator we consume it lazily.
    _is_list = isinstance(param_combinations, list)
    total = (total_combinations or len(param_combinations)) if _is_list else total_combinations

    # ── Materialise generator when small enough for fast path ─────────────────
    # Grid search returns a lazy iterator to save memory on huge grids.
    # For ≤ 2M combos, materialising into a list is safe (~100MB RAM worst case)
    # and REQUIRED to enable the fast RSI threshold path.
    FAST_PATH_MATERIALISE_CAP = 2_000_000
    if not _is_list and total and total <= FAST_PATH_MATERIALISE_CAP:
        _log_info(f"⚡ Materialising {total:,} combos for fast-path eligibility check...")
        param_combinations = list(param_combinations)
        _is_list = True

    _log_info(f"🔍 Builder grid search: {total:,} combinations, metric={optimize_metric}, timeout={timeout_seconds}s")

    # Quick DCA check — RSI threshold fast path is incompatible with DCA graphs.
    # DCA strategies use the mixed batch path (below); skip RSI threshold path for them.
    _has_dca_blocks_early = any(b.get("type") in ("dca", "grid_orders") for b in base_graph.get("blocks", []))

    # ── Fast path: RSI threshold-only ────────────────────────────────────────
    # Only feasible when we have a materialized list (needs random access) AND
    # the grid is small enough to hold in memory AND no DCA blocks present.
    if _is_list and total <= FAST_PATH_MATERIALISE_CAP and not _has_dca_blocks_early:
        is_rsi_threshold, rsi_block_id = _is_rsi_threshold_only_optimization(param_combinations, base_graph)
        if is_rsi_threshold and rsi_block_id:
            _log_info(f"⚡ Using fast RSI threshold optimization path for block {rsi_block_id}")
            try:
                return _run_fast_rsi_threshold_optimization(
                    base_graph=base_graph,
                    ohlcv=ohlcv,
                    param_combinations=param_combinations,
                    config_params=config_params,
                    rsi_block_id=rsi_block_id,
                    optimize_metric=optimize_metric,
                    weights=weights,
                    max_results=max_results,
                    early_stopping=early_stopping,
                    early_stopping_patience=early_stopping_patience,
                    timeout_seconds=timeout_seconds,
                    strategy_id=strategy_id,
                )
            except Exception as e:
                _log_warning(f"Fast RSI path failed, falling back to standard: {e}", exc_info=True)

    # Standard path
    _log_info(f"📉 Falling through to STANDARD path for {total:,} combinations")
    start_time = time.time()
    results: list[dict[str, Any]] = []
    all_results: list[dict[str, Any]] = []  # All results before filtering (fallback)
    best_score = float("-inf")
    no_improvement_count = 0
    tested = 0
    skipped_infeasible = 0  # combos skipped by pre-filter (logical conflicts, e.g. RSI cross < range)

    # Build infeasibility checker ONCE — avoids rebuilding base block params on every combo
    _infeasibility_checker = build_infeasibility_checker(base_graph)

    # Initialize progress for standard path
    if strategy_id:
        update_optimization_progress(
            strategy_id, status="running", tested=0, total=total, started_at=start_time, stage="searching"
        )

    # Log to console every ~5% to avoid spam; but update progress store after EVERY combo
    # so the frontend polling sees real-time progress (critical for slow DCA backtests).
    log_interval = max(1, total // 20)

    # ── DCA pre-computation (close-condition indicators) ────────────────────
    # When DCA is enabled, _precompute_close_condition_indicators() recomputes
    # RSI/Stoch/MA/BB/Keltner/PSAR for every trial even though OHLCV is constant.
    # Pre-compute once here and inject into each DCAEngine via cache injection.
    _std_dca_enabled = False
    _std_dca_final_config: dict[str, Any] = {}
    _std_dca_close_cache: dict | None = None
    _std_block_stop_loss: float | None = config_params.get("stop_loss_pct")
    _std_block_take_profit: float | None = config_params.get("take_profit_pct")
    if _std_block_stop_loss:
        _std_block_stop_loss = _std_block_stop_loss / 100.0
    if _std_block_take_profit:
        _std_block_take_profit = _std_block_take_profit / 100.0
    _std_block_breakeven_enabled = False
    _std_block_breakeven_activation_pct = 0.005
    _std_block_breakeven_offset = 0.0
    _std_block_close_only_in_profit = False
    _std_block_sl_type = "average_price"
    _std_block_max_bars_in_trade = 0

    try:
        from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter as _SBA

        _probe_adapter = _SBA(base_graph)
        _probe_dca_config = _probe_adapter.extract_dca_config()
        _std_dca_enabled = _probe_adapter.has_dca_blocks() or _probe_dca_config.get("dca_enabled", False)

        if _std_dca_enabled:
            _direction_str = config_params.get("direction", "both")
            _std_dca_final_config = _probe_dca_config.copy()
            _std_dca_final_config["dca_enabled"] = True
            if _std_dca_final_config.get("dca_direction", "both") == "both" and _direction_str in ("long", "short"):
                _std_dca_final_config["dca_direction"] = _direction_str

            # Extract SL/TP/close_by_time from base graph (static across all trials)
            for block in base_graph.get("blocks", []):
                btype = block.get("type", "")
                bp = block.get("params") or block.get("config") or {}
                if btype == "close_by_time":
                    bars_val = bp.get("bars_since_entry", bp.get("bars", 0))
                    _std_block_max_bars_in_trade = int(bars_val) if bars_val else 0
                elif btype == "static_sltp":
                    if _std_block_stop_loss is None:
                        _std_block_stop_loss = bp.get("stop_loss_percent", 1.5) / 100.0
                    if _std_block_take_profit is None:
                        _std_block_take_profit = bp.get("take_profit_percent", 1.5) / 100.0
                    _std_block_breakeven_enabled = bp.get("activate_breakeven", False)
                    if _std_block_breakeven_enabled:
                        _std_block_breakeven_activation_pct = bp.get("breakeven_activation_percent", 0.5) / 100.0
                        _std_block_breakeven_offset = bp.get("new_breakeven_sl_percent", 0.1) / 100.0
                    _std_block_close_only_in_profit = bp.get("close_only_in_profit", False)
                    _std_block_sl_type = bp.get("sl_type", "average_price")
                elif btype == "tp_percent" and _std_block_take_profit is None:
                    _std_block_take_profit = bp.get("take_profit_percent", 3.0) / 100.0
                elif btype == "sl_percent" and _std_block_stop_loss is None:
                    _std_block_stop_loss = bp.get("stop_loss_percent", 1.5) / 100.0

            # Pre-compute close-condition indicator cache once for all trials
            _std_dca_close_cache = _precompute_dca_close_cache(_std_dca_final_config, config_params, ohlcv)
            if _std_dca_close_cache is not None:
                _log_info("⚡ DCA close-condition indicators pre-computed (shared across all trials)")
    except Exception as _e:
        logger.debug(f"DCA pre-computation probe failed, using standard path: {_e}")
        _std_dca_enabled = False
        _std_dca_close_cache = None
    # ────────────────────────────────────────────────────────────────────────

    # ── Numba DCA batch fast path ────────────────────────────────────────────
    # When DCA is enabled AND only static_sltp params vary, we can pre-compute
    # entry signals once and batch-simulate all (sl, tp) combos in parallel via
    # Numba prange — 20-40x faster than per-trial DCAEngine calls.
    #
    # Both Numba batch paths require a materialised list.  When param_combinations
    # is a lazy iterator (large grid) we materialise it here — the DCA batch paths
    # are extremely fast (Numba prange) so even millions of combos are fine in RAM
    # because each dict is tiny (~5 keys × 8 bytes).
    if _std_dca_enabled:
        if not _is_list:
            # Materialise the iterator for DCA batch inspection
            param_combinations = list(param_combinations)
            _is_list = True
            if not total:
                total = len(param_combinations)

        is_sltp_only, _sltp_block_ids = _is_dca_sltp_only_optimization(param_combinations, base_graph)
        if is_sltp_only and _sltp_block_ids:
            _log_info(f"⚡ Using Numba DCA batch path ({total} SL/TP combos, parallel prange)")
            try:
                _numba_results = _run_dca_sltp_batch_numba(
                    base_graph=base_graph,
                    ohlcv=ohlcv,
                    param_combinations=param_combinations,
                    config_params=config_params,
                    final_dca_config=_std_dca_final_config,
                    direction_str=config_params.get("direction", "both"),
                    sltp_block_ids=_sltp_block_ids,
                )
                # Build output structure matching standard path
                _nb_results_out: list[dict[str, Any]] = []
                _nb_all_out: list[dict[str, Any]] = []
                for _ci, (_res, _combo) in enumerate(zip(_numba_results, param_combinations, strict=False)):
                    if _res is None:
                        continue
                    _score = calculate_composite_score(_res, optimize_metric, weights)
                    _entry = {"params": _combo, "score": _score, **_res}
                    _nb_all_out.append(_entry)
                    if passes_filters(_res, config_params):
                        _nb_results_out.append(_entry)

                _nb_results_out.sort(key=lambda r: r["score"], reverse=True)
                if not _nb_results_out:
                    _nb_all_out.sort(key=lambda r: r["score"], reverse=True)
                    _nb_results_out = _nb_all_out
                _nb_top = _nb_results_out[:max_results]
                _nb_elapsed = time.time() - start_time
                return {
                    "status": "completed",
                    "method": "grid_numba_dca",
                    "total_combinations": total,
                    "tested_combinations": len(_numba_results),
                    "results_passing_filters": len(_nb_results_out),
                    "results_found": len(_nb_top),
                    "top_results": _nb_top,
                    "best_params": _nb_top[0]["params"] if _nb_top else {},
                    "best_score": _nb_top[0]["score"] if _nb_top else 0.0,
                    "best_metrics": {k: v for k, v in _nb_top[0].items() if k not in ("params", "score")}
                    if _nb_top
                    else {},
                    "execution_time_seconds": round(_nb_elapsed, 2),
                    "speed_combinations_per_sec": int(len(_numba_results) / max(_nb_elapsed, 0.001)),
                    "early_stopped": False,
                    "optimize_metric": optimize_metric,
                    "numba_accelerated": True,
                }
            except Exception as _nb_exc:
                _log_warning(f"Numba DCA batch failed, falling back to standard loop: {_nb_exc}")

        # ── Mixed Numba DCA batch fast path ──────────────────────────────────
        # When DCA is enabled AND params include BOTH indicator (RSI/etc.) and
        # SLTP variations, group by indicator combos and Numba-batch SLTP per group.
        # For DCA-RSI-6: 806 RSI groups × 378 SLTP = 304,668 total — ~230× faster.
        elif _sltp_block_ids:
            _log_info(f"⚡ Using Mixed DCA batch path ({total} combos, Numba prange per indicator group)")
            try:
                # Update progress: Numba batch is running (progress will jump to 100% on completion)
                if strategy_id:
                    update_optimization_progress(
                        strategy_id,
                        status="running",
                        tested=0,
                        total=total,
                        best_score=0.0,
                        results_found=0,
                        speed=0,
                        eta_seconds=0,
                        started_at=start_time,
                    )

                # Build progress callback for mixed batch — updates UI per indicator group
                _mx_start = start_time

                def _mixed_progress_cb(done: int, total_c: int) -> None:
                    _now = time.time()
                    _elapsed = max(_now - _mx_start, 0.001)
                    _spd = int(done / _elapsed)
                    _eta = int((total_c - done) / max(_spd, 1))
                    update_optimization_progress(
                        strategy_id,
                        status="running",
                        tested=done,
                        total=total_c,
                        best_score=0.0,
                        results_found=0,
                        speed=_spd,
                        eta_seconds=_eta,
                        started_at=_mx_start,
                    )

                _mixed_results = _run_dca_mixed_batch_numba(
                    base_graph=base_graph,
                    ohlcv=ohlcv,
                    param_combinations=param_combinations,
                    config_params=config_params,
                    final_dca_config=_std_dca_final_config,
                    direction_str=config_params.get("direction", "both"),
                    sltp_block_ids=_sltp_block_ids,
                    progress_callback=_mixed_progress_cb if strategy_id else None,
                )
                _mx_results_out: list[dict[str, Any]] = []
                _mx_all_out: list[dict[str, Any]] = []
                for _ci, (_res, _combo) in enumerate(zip(_mixed_results, param_combinations, strict=False)):
                    if _res is None:
                        continue
                    _score = calculate_composite_score(_res, optimize_metric, weights)
                    _entry = {"params": _combo, "score": _score, **_res}
                    _mx_all_out.append(_entry)
                    if passes_filters(_res, config_params):
                        _mx_results_out.append(_entry)

                _mx_results_out.sort(key=lambda r: r["score"], reverse=True)
                _mx_passing_count = len(_mx_results_out)  # count before fallback
                if not _mx_results_out:
                    _mx_all_out.sort(key=lambda r: r["score"], reverse=True)
                    _mx_results_out = _mx_all_out
                _mx_top = _mx_results_out[:max_results]
                _mx_elapsed = time.time() - start_time
                _mx_tested = sum(1 for r in _mixed_results if r is not None)

                # ── Detect features with minor Numba approximation (implemented but slight diff) ──
                # safety_close, close_by_time, breakeven are all implemented now.
                # Remaining ~4% trade count gap is from avg_entry formula (fee-deducted coins vs V4).
                _approximations: list[str] = []
                for _blk in base_graph.get("blocks", []):
                    _bt = _blk.get("type", "")
                    _bp = _blk.get("params") or _blk.get("config") or {}
                    if _bt == "static_sltp" and _bp.get("activate_breakeven", False):
                        _approximations.append("breakeven_approx")  # <4% trade diff vs V4
                    if _bt == "close_by_time":
                        _approximations.append("close_by_time_approx")  # implemented, minor diff

                # ── Post-validate top-N via full V4 DCA engine ────────────────
                # Numba ~96% parity with V4; re-score top candidates through
                # run_builder_backtest() for exact final metrics.
                _V4_VALIDATE_N = min(5, len(_mx_top))
                _validated_top: list[dict[str, Any]] = []
                if _approximations and _mx_top:
                    _log_info(f"🔍 Post-validating top {_V4_VALIDATE_N} via V4 DCA (approximations: {_approximations})")
                    for _cand in _mx_top[:_V4_VALIDATE_N]:
                        _v4_graph = clone_graph_with_params(base_graph, _cand["params"])
                        _v4_res = run_builder_backtest(_v4_graph, ohlcv, config_params)
                        if _v4_res is not None:
                            _v4_score = calculate_composite_score(_v4_res, optimize_metric, weights)
                            _validated_top.append({"params": _cand["params"], "score": _v4_score, **_v4_res})
                        else:
                            _validated_top.append(_cand)  # keep Numba result if V4 fails
                    _validated_top.sort(key=lambda r: r["score"], reverse=True)
                    # Merge: validated first, then remaining Numba results
                    _remaining = list(_mx_top[_V4_VALIDATE_N:])
                    _mx_top = _validated_top + _remaining
                    _log_info(f"✅ V4 post-validation complete for {len(_validated_top)} results")

                # Update progress file to "completed" so frontend polling sees final state
                if strategy_id:
                    update_optimization_progress(
                        strategy_id,
                        status="completed",
                        tested=_mx_tested,
                        total=total,
                        best_score=_mx_top[0]["score"] if _mx_top else 0.0,
                        results_found=len(_mx_top),
                        speed=round(_mx_tested / max(_mx_elapsed, 0.001), 1),
                        eta_seconds=0,
                        started_at=start_time,
                    )

                return {
                    "status": "completed",
                    "method": "grid_numba_dca_mixed",
                    "total_combinations": total,
                    "tested_combinations": _mx_tested,
                    "results_passing_filters": _mx_passing_count,
                    "results_found": len(_mx_top),
                    "top_results": _mx_top,
                    "best_params": _mx_top[0]["params"] if _mx_top else {},
                    "best_score": _mx_top[0]["score"] if _mx_top else 0.0,
                    "best_metrics": {k: v for k, v in _mx_top[0].items() if k not in ("params", "score")}
                    if _mx_top
                    else {},
                    "execution_time_seconds": round(_mx_elapsed, 2),
                    "speed_combinations_per_sec": round(_mx_tested / max(_mx_elapsed, 0.001), 1),
                    "early_stopped": False,
                    "optimize_metric": optimize_metric,
                    "numba_accelerated": True,
                    "approximations": _approximations,
                    "top_validated_by_v4": len(_validated_top) if _approximations else 0,
                }
            except Exception as _mx_exc:
                _log_warning(f"Mixed DCA batch failed, falling back to standard loop: {_mx_exc}")
    # ────────────────────────────────────────────────────────────────────────

    for i, overrides in enumerate(param_combinations):
        # Timeout check
        elapsed = time.time() - start_time
        if elapsed > timeout_seconds:
            _log_info(f"⏱️ Builder optimization timeout after {elapsed:.0f}s at combo {i}/{total}")
            break

        # Pre-filter: skip combos with known logical conflicts (e.g. RSI cross < range floor)
        # _infeasibility_checker is built once before the loop — O(n_overrides) per combo.
        if _infeasibility_checker(overrides):
            skipped_infeasible += 1
            continue

        # Clone graph and apply param overrides
        modified_graph = clone_graph_with_params(base_graph, overrides)

        # DCA fast path: generate signals via modified adapter, run DCA with cached indicators
        if _std_dca_enabled and _std_dca_close_cache is not None:
            try:
                from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter as _SBA2

                _trial_adapter = _SBA2(modified_graph)
                _trial_signals_raw = _trial_adapter.generate_signals(ohlcv)
                import numpy as _np

                _long = _np.asarray(_trial_signals_raw.entries.values, dtype=bool)
                _short = (
                    _np.asarray(_trial_signals_raw.short_entries.values, dtype=bool)
                    if _trial_signals_raw.short_entries is not None
                    else _np.zeros(len(ohlcv), dtype=bool)
                )
                _dir = config_params.get("direction", "both")
                _signals = _np.zeros(len(ohlcv), dtype=float)
                if _dir in ("long", "both"):
                    _signals[_long] = 1
                if _dir in ("short", "both"):
                    _short_only = _short & ~_long
                    _signals[_short_only] = -1

                # Skip no-signal combos early (same fast-skip as fast RSI path)
                if int(_np.sum(_signals > 0)) == 0 and int(_np.sum(_signals < 0)) == 0:
                    tested += 1
                    # Still update progress
                    if strategy_id:
                        _elapsed_now = time.time() - start_time
                        _spd = int(tested / max(_elapsed_now, 0.001))
                        _eta = int((total - tested) / max(_spd, 1))
                        update_optimization_progress(
                            strategy_id,
                            status="running",
                            tested=tested,
                            total=total,
                            best_score=best_score if best_score != float("-inf") else 0.0,
                            results_found=len(results),
                            speed=_spd,
                            eta_seconds=_eta,
                            started_at=start_time,
                        )
                    continue

                # Override base-graph SL/TP/close_by_time if this combo varies those params
                _trial_sl = _std_block_stop_loss
                _trial_tp = _std_block_take_profit
                _trial_max_bars = _std_block_max_bars_in_trade
                for _ovr_path, _ovr_val in overrides.items():
                    if "." in _ovr_path:
                        _, _ovr_pk = _ovr_path.split(".", 1)
                        if _ovr_pk == "stop_loss_percent":
                            _trial_sl = float(_ovr_val) / 100.0
                        elif _ovr_pk == "take_profit_percent":
                            _trial_tp = float(_ovr_val) / 100.0
                        elif _ovr_pk in ("bars_since_entry", "bars"):
                            _trial_max_bars = int(_ovr_val)

                result = _run_dca_with_signals(
                    signals=_signals,
                    ohlcv=ohlcv,
                    config_params=config_params,
                    final_dca_config=_std_dca_final_config,
                    direction_str=_dir,
                    block_stop_loss=_trial_sl,
                    block_take_profit=_trial_tp,
                    block_breakeven_enabled=_std_block_breakeven_enabled,
                    block_breakeven_activation_pct=_std_block_breakeven_activation_pct,
                    block_breakeven_offset=_std_block_breakeven_offset,
                    block_close_only_in_profit=_std_block_close_only_in_profit,
                    block_sl_type=_std_block_sl_type,
                    block_max_bars_in_trade=_trial_max_bars,
                    close_indicator_cache=_std_dca_close_cache,
                )
            except Exception as _trial_e:
                logger.debug(f"DCA fast trial {i} failed, falling back: {_trial_e}")
                result = run_builder_backtest(modified_graph, ohlcv, config_params)
        else:
            # Standard (non-DCA or cache-miss) path
            result = run_builder_backtest(modified_graph, ohlcv, config_params)
        tested += 1

        # Update progress after EVERY backtest — this is the primary real-time signal
        # for the frontend. DCA backtests take 2-5s each, so this is cheap overhead.
        if strategy_id:
            elapsed_now = time.time() - start_time
            speed = round(tested / max(elapsed_now, 0.001), 1)
            eta = int((total - tested) / speed) if speed > 0 else 0
            update_optimization_progress(
                strategy_id,
                status="running",
                tested=tested,
                total=total,
                best_score=best_score if best_score != float("-inf") else 0.0,
                results_found=len(results),
                speed=speed,
                eta_seconds=eta,
                started_at=start_time,
            )

        # Log to console every 5% to avoid log spam
        if tested > 0 and tested % log_interval == 0:
            elapsed_now = time.time() - start_time
            speed = round(tested / max(elapsed_now, 0.001), 1)
            eta = int((total - tested) / speed) if speed > 0 else 0
            pct = tested * 100 // total if total > 0 else 0
            _log_info(
                f"📊 Builder optimization progress: {tested}/{total} ({pct}%) "
                f"speed={speed} combos/s, ETA={eta}s, results={len(results)}"
            )

        if result is None:
            continue

        # Skip zero-trade results early — they're worthless for optimization
        if int(result.get("total_trades", 0)) == 0:
            continue

        # Calculate score
        score = calculate_composite_score(result, optimize_metric, weights)

        # Build result entry
        entry = {
            "params": overrides,
            "score": score,
            **result,
        }

        # Always keep in all_results for fallback display
        all_results.append(entry)

        # Apply filters — only filtered results go into ranked results
        if not passes_filters(result, config_params):
            continue

        results.append(entry)

        # Early stopping
        if score > best_score:
            best_score = score
            no_improvement_count = 0
        else:
            no_improvement_count += 1

        if early_stopping and no_improvement_count >= early_stopping_patience:
            logger.info(f"⏹️ Builder early stopping at combo {i}/{total} (patience={early_stopping_patience})")
            break

    # Pareto post-processing: re-score all candidates by NP/DD balance before final sort
    if optimize_metric == "pareto_balance":
        apply_pareto_scores(all_results)
        apply_pareto_scores(results)

    # Sort results
    results.sort(key=lambda r: r["score"], reverse=True)
    top_results = results[:max_results]

    # Fallback: if all results were filtered out, return top N unfiltered results
    # This happens when constraints, min_trades, or other filters reject all combos
    fallback_used = False
    if not top_results and all_results:
        _min_trades_gs = config_params.get("min_trades") or 1
        _constraints_gs = config_params.get("constraints") or []
        logger.warning(
            f"⚠️ All {len(all_results)} results filtered out "
            f"(min_trades={_min_trades_gs}, constraints={len(_constraints_gs)}). "
            "Returning best unfiltered results."
        )
        # Soft min-trades guard: avoid garbage 1-2 trade combos in fallback
        _fb_candidates_gs = [r for r in all_results if r.get("total_trades", 0) >= max(_min_trades_gs, 3)]
        if not _fb_candidates_gs:
            _fb_candidates_gs = all_results
        _fb_candidates_gs.sort(key=lambda r: r["score"], reverse=True)
        top_results = _fb_candidates_gs[:max_results]
        fallback_used = True

    # Variant A: re-evaluate top results with FallbackEngineV4 for metric parity
    if top_results:
        top_results = _reeval_top_accurate(top_results, base_graph, ohlcv, config_params, optimize_metric, weights)
    # Re-apply cross-result pareto normalisation after reeval resets individual scores.
    if optimize_metric == "pareto_balance" and top_results:
        apply_pareto_scores(top_results)

    # Detect if best result has negative score for the optimize metric
    no_positive_results = bool(top_results and top_results[0].get("score", 0) < 0)

    execution_time = time.time() - start_time
    speed = round(tested / max(execution_time, 0.001), 1)
    timed_out = tested < total

    logger.info(
        f"{'⏱️' if timed_out else '✅'} Builder optimization {'partial' if timed_out else 'complete'}: "
        f"{tested}/{total} tested in {execution_time:.1f}s ({speed} combos/s), {len(results)} results"
        + (f", {skipped_infeasible} skipped (infeasible)" if skipped_infeasible else "")
    )

    # Mark progress as completed
    if strategy_id:
        update_optimization_progress(
            strategy_id,
            status="completed" if not timed_out else "partial",
            tested=tested,
            total=total,
            best_score=top_results[0]["score"] if top_results else 0.0,
            results_found=len(results),
            speed=speed,
            eta_seconds=0,
            started_at=start_time,
        )

    return {
        "status": "partial" if timed_out else "completed",
        "total_combinations": total,
        "tested_combinations": tested,
        "skipped_infeasible": skipped_infeasible,
        "results_passing_filters": len(results),
        "results_found": len(results),
        "top_results": top_results,
        "best_params": top_results[0]["params"] if top_results else {},
        "best_score": top_results[0]["score"] if top_results else 0.0,
        "best_metrics": {k: v for k, v in top_results[0].items() if k not in ("params", "score")}
        if top_results
        else {},
        "execution_time_seconds": round(execution_time, 2),
        "speed_combinations_per_sec": speed,
        "early_stopped": early_stopping and no_improvement_count >= early_stopping_patience,
        "fallback_used": fallback_used,
        "no_positive_results": no_positive_results,
        "optimize_metric": optimize_metric,
    }


# =============================================================================
# CROSS-BLOCK CONSTRAINT CLAMPING (shared by objective AND re-run)
# =============================================================================


def _apply_cross_block_constraints(
    overrides: dict[str, Any],
    param_specs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Apply cross-block constraints to parameter overrides.

    Ensures structural consistency:
    - MACD: fast_period < slow_period
    - SL/TP: TP >= SL * 1.5 ONLY when no close_by_time block present
      (strategies with close_by_time use time-exit as primary; TP < SL is valid)
    - breakeven: activation < TP (clamped to 70% of TP)
    - NOTE: min_profit >= TP + 2.0% removed — inverts close_by_time semantics
      (min_profit < TP lets CBT close profitable trades before TP fires)

    CRITICAL: Must be called in BOTH the objective function AND the re-run
    top-N path.  trial.params stores values from suggest_*() BEFORE clamping,
    so re-run with raw trial.params would produce a different backtest than
    the original trial.

    Args:
        overrides: Dict mapping param_path to value (modified in-place).
        param_specs: List of optimizable param specs.

    Returns:
        The same overrides dict (modified in-place) for convenience.
    """
    # ── MACD fast < slow constraint ─────────────────────────────────────────
    for path in list(overrides.keys()):
        if path.endswith("fast_period"):
            slow_path = path[: -len("fast_period")] + "slow_period"
            if slow_path in overrides:
                fast_val = int(overrides[path])
                slow_val = int(overrides[slow_path])
                if slow_val <= fast_val:
                    overrides[slow_path] = fast_val + 1

    # ── SL/TP/close_by_time/breakeven constraints ───────────────────────────
    _tp_path: str | None = None
    _sl_path: str | None = None
    _be_path: str | None = None
    _has_close_by_time = any(s.get("block_type") == "close_by_time" for s in param_specs)
    for _spec in param_specs:
        _btype = _spec.get("block_type", "")
        if _btype == "static_sltp":
            if _spec.get("param_key") == "take_profit_percent":
                _tp_path = _spec["param_path"]
            elif _spec.get("param_key") == "stop_loss_percent":
                _sl_path = _spec["param_path"]
            elif _spec.get("param_key") == "breakeven_activation_percent":
                _be_path = _spec["param_path"]

    # TP >= SL * 1.5 (minimum risk/reward ratio).
    # Skipped when close_by_time block is present — those strategies use time-exit
    # as the primary exit mechanism and TP < SL is a valid design (quick profit + wide SL).
    if _tp_path and _sl_path and _tp_path in overrides and _sl_path in overrides and not _has_close_by_time:
        _tp_val_rr = float(overrides[_tp_path])
        _sl_val_rr = float(overrides[_sl_path])
        _min_tp = round(_sl_val_rr * 1.5, 2)
        if _tp_val_rr < _min_tp:
            overrides[_tp_path] = _min_tp

    # breakeven_activation < TP (clamped to 70% of TP) — always valid.
    if _tp_path and _be_path and _tp_path in overrides and _be_path in overrides:
        _tp_val = float(overrides[_tp_path])
        _be_val = float(overrides[_be_path])
        if _be_val >= _tp_val:
            overrides[_be_path] = round(_tp_val * 0.7, 2)

    # ── Supertrend anti-degeneracy: multiplier clamp only ───────────────
    # multiplier > 10 makes ATR-bands wider than typical bar range →
    # direction never flips → block becomes inert signal source.
    #
    # NOTE: period-clamp (period<5 → 5) was tried and caused TPE hangs —
    # when TPE suggests period values 1..4 all getting clamped to 5, the
    # surrogate sees flat response across that axis → covariance matrix
    # becomes rank-deficient on `period` dimension → scipy Cholesky fails
    # → native C thread hangs uninterruptibly. Period-degeneracy is real
    # but must be handled at the UI range layer, not via silent clamp.
    for _spec in param_specs:
        if _spec.get("block_type") != "supertrend":
            continue
        _pk = _spec.get("param_key")
        _path = _spec["param_path"]
        if _path not in overrides:
            continue
        if _pk == "multiplier" and float(overrides[_path]) > 10.0:
            overrides[_path] = 10.0

    return overrides


# =============================================================================
# OPTUNA BAYESIAN SEARCH FOR BUILDER STRATEGIES
# =============================================================================


def run_builder_optuna_search(
    base_graph: dict[str, Any],
    ohlcv: pd.DataFrame,
    param_specs: list[dict[str, Any]],
    config_params: dict[str, Any],
    optimize_metric: str = "sharpe_ratio",
    weights: dict[str, float] | None = None,
    n_trials: int | None = None,
    sampler_type: str = "tpe",
    top_n: int = 10,
    timeout_seconds: int = 3600,
    n_jobs: int = 1,
    strategy_id: str | None = None,
    warm_start_trials: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Run Optuna Bayesian optimization for a builder strategy.

    Args:
        base_graph: Base strategy graph.
        ohlcv: OHLCV DataFrame.
        param_specs: Active param specs with ranges.
        config_params: Backtest config params.
        optimize_metric: Metric to maximize.
        weights: Metric weights for composite scoring.
        n_trials: Max Optuna trials. ``None`` (default) = unlimited — stop only
            when ``timeout_seconds`` is reached. This is the correct mode for
            large parameter spaces (10^6–10^9 combos): Bayesian sampling explores
            intelligently without enumerating.
        sampler_type: "tpe", "random", "cmaes" (BIPOP restart via OptunaHub), "gp", or "auto" (Optuna 4.6+).
        top_n: Number of top results to re-run for full metrics.
        timeout_seconds: Wall-clock budget. Optimizer stops when this expires.
        n_jobs: Number of parallel workers (default 1). Values > 1 enable
            multi-threaded Optuna trials. Capped at os.cpu_count().
        strategy_id: Optional strategy ID for progress tracking.
        warm_start_trials: Optional list of previous best results (each with "params" dict)
            to enqueue before optimization starts. Improves initial coverage ~30% (meta-learning).

    Returns:
        Dict with optimization results.
    """
    try:
        import optuna
        from optuna.pruners import HyperbandPruner, MedianPruner
        from optuna.samplers import CmaEsSampler, RandomSampler, TPESampler

        try:
            from optuna.samplers import QMCSampler  # Optuna ≥ 3.0
        except ImportError:
            QMCSampler = None  # type: ignore[assignment,misc]

        try:
            from optuna.samplers import GPSampler  # Optuna ≥ 3.6 native GP
        except ImportError:
            GPSampler = None  # type: ignore[assignment,misc]

        # P1-3: AutoSampler (Optuna ≥ 4.6) — automatic sampler selection
        try:
            from optuna.samplers import AutoSampler  # type: ignore[attr-defined]
        except ImportError:
            AutoSampler = None  # type: ignore[assignment,misc]

        # P0-1: OptunaHub RestartCmaEsSampler with BIPOP restart strategy
        # Replaces deprecated restart_strategy="ipop" in CmaEsSampler (Optuna 4.4.0+)
        RestartCmaEsSampler = None
        try:
            import optunahub as _optunahub

            _restart_cmaes_module = _optunahub.load_module("samplers/restart_cmaes")
            RestartCmaEsSampler = _restart_cmaes_module.RestartCmaEsSampler
        except Exception:
            RestartCmaEsSampler = None  # fallback to standard CmaEsSampler
    except ImportError:
        logger.error("Optuna not installed. Install with: pip install optuna")
        return {
            "status": "error",
            "error": "Optuna not installed",
            "total_combinations": 0,
            "tested_combinations": 0,
            "top_results": [],
            "best_params": {},
            "best_score": 0.0,
            "best_metrics": {},
            "execution_time_seconds": 0.0,
        }

    import os

    start_time = time.time()

    # Number of optimizable parameters — used to compute adaptive startup budgets.
    _n_params = len(param_specs)

    # P2: Auto-detect optimal n_jobs when set to 1 (default)
    # Use min(4, cpu_count) for strategies with > 5 params (benefit outweighs overhead)
    _cpu_count = os.cpu_count() or 1
    # Windows: multiprocessing uses spawn() — conflicts with Uvicorn's event loop.
    # Optuna n_jobs > 1 spawns new processes that re-import the module and
    # try to re-bind the same port → server crash. Force single-threaded on Windows.
    import sys as _sys

    if _sys.platform == "win32":
        if n_jobs > 1:
            logger.info(
                f"P2: Windows detected — forcing n_jobs=1 (spawn-based multiprocessing "
                f"conflicts with Uvicorn; requested n_jobs={n_jobs})"
            )
        n_jobs = 1
    elif n_jobs <= 1 and _n_params >= 5 and _cpu_count >= 2:
        n_jobs = min(4, _cpu_count)
        logger.info(f"P2: Auto-enabled parallel trials: n_jobs={n_jobs} (params={_n_params}, CPUs={_cpu_count})")

    # Clamp n_jobs to available CPUs
    effective_n_jobs = max(1, min(n_jobs, _cpu_count))

    # P2-MEM: Memory-aware n_jobs capping — prevent OOM crashes on large datasets.
    # Each parallel trial holds: OHLCV copy (~8 cols × 8B × N rows), engine state,
    # indicator buffers (~3× OHLCV), signal arrays, and trade objects.
    # Empirical estimate: ~500 bytes/candle per trial (conservative upper bound).
    _n_candles = len(ohlcv)
    _BYTES_PER_CANDLE_PER_TRIAL = 500
    _est_mem_per_trial_mb = (_n_candles * _BYTES_PER_CANDLE_PER_TRIAL) / (1024 * 1024)
    try:
        import psutil

        _avail_mb = psutil.virtual_memory().available / (1024 * 1024)
        # Reserve 30% of available RAM for OS + uvicorn + other services
        _usable_mb = _avail_mb * 0.7
        _max_jobs_by_mem = max(1, int(_usable_mb / max(_est_mem_per_trial_mb, 1)))
        if _max_jobs_by_mem < effective_n_jobs:
            logger.warning(
                f"P2-MEM: Reducing n_jobs {effective_n_jobs}→{_max_jobs_by_mem} "
                f"(avail={_avail_mb:.0f}MB, est/trial={_est_mem_per_trial_mb:.0f}MB, "
                f"candles={_n_candles})"
            )
            effective_n_jobs = _max_jobs_by_mem
    except ImportError:
        # psutil not available — use heuristic: >30K candles → reduce to max 2 jobs
        if _n_candles > 30_000 and effective_n_jobs > 2:
            logger.warning(
                f"P2-MEM: Capping n_jobs {effective_n_jobs}→2 (no psutil, candles={_n_candles} > 30K threshold)"
            )
            effective_n_jobs = 2

    if effective_n_jobs > 1:
        logger.info(
            f"Optuna parallel search: n_jobs={effective_n_jobs} "
            f"(CPUs={_cpu_count}, candles={_n_candles}, "
            f"est_mem/trial={_est_mem_per_trial_mb:.1f}MB)"
        )

    # Store all results (before min_trades filter) for fallback display.
    # Protected by a lock when n_jobs > 1 (multiple threads write concurrently).
    all_trial_results: list[dict[str, Any]] = []
    _results_lock = threading.Lock()

    # ── Native constraint function for Optuna's constrained BO ───────────────
    # Constraint values ≤ 0 = feasible; > 0 = violated.
    # Stored in trial.user_attrs["constraint"] by the objective function,
    # read back here by Optuna's sampler after each trial completes.
    # This replaces the old penalty (-1000) approach: the surrogate model now
    # trains on the true objective landscape, and feasibility is handled
    # separately — exactly how constrained Bayesian optimization should work.
    def _constraints_func(trial: optuna.Trial) -> list[float]:
        return trial.user_attrs.get("constraint", [0.0])

    # Choose sampler
    sampler: BaseSampler
    if sampler_type == "auto" and AutoSampler is not None:
        # P1-3: Optuna 4.6 AutoSampler — automatically selects GPSampler/NSGAIISampler/TPESampler
        # based on study characteristics (n_trials, multi-objective, param types).
        sampler = AutoSampler(seed=42)  # type: ignore[assignment]
        logger.info("Using Optuna 4.6 AutoSampler (automatic sampler selection)")
    elif sampler_type == "auto":
        # Fallback for Optuna < 4.6 — pick a sampler based on dimensionality
        # using sampler_factory.prefer_for_high_dim (TPE for ≤ 20 dims, CMA-ES above).
        from backend.optimization.sampler_factory import prefer_for_high_dim

        _fallback = prefer_for_high_dim(_n_params)
        logger.warning(
            "AutoSampler not available (requires Optuna ≥ 4.6); sampler_factory.prefer_for_high_dim(D=%d) → %s",
            _n_params,
            _fallback,
        )
        sampler_type = _fallback  # will fall through to the matching block below

    if sampler_type == "random":
        sampler = RandomSampler(seed=42)
    elif sampler_type == "cmaes":
        # CMA-ES: startup = max(4×n_params, 20) capped at n_trials//4.
        # Use QMC for startup phase when available — covers the search space
        # more uniformly than pure random (Sobol low-discrepancy sequence).
        # with_margin=True makes CMA-ES treat integer params as rounded Gaussians
        # instead of hard-clipping, which reduces boundary pileup.
        _cmaes_startup = max(_n_params * 4, 20)
        if n_trials is not None:
            _cmaes_startup = min(_cmaes_startup, max(n_trials // 4, 10))
        _cmaes_seed_sampler: BaseSampler | None = None
        if QMCSampler is not None:
            try:
                _cmaes_seed_sampler = QMCSampler(qmc_type="sobol", seed=42)
            except Exception:
                _cmaes_seed_sampler = None

        if RestartCmaEsSampler is not None:
            # P0-1: OptunaHub RestartCmaEsSampler with BIPOP strategy (Hansen 2009).
            # BIPOP adaptively chooses between large population (global search) and
            # small population (local refinement) — outperforms IPOP on 15/24 BBOB functions.
            # NOTE: RestartCmaEsSampler does NOT support constraints_func or with_margin —
            # constraints are handled via penalty in the objective function instead.
            _restart_cmaes_kwargs: dict[str, Any] = {
                "seed": 42,
                "n_startup_trials": _cmaes_startup,
                "restart_strategy": "bipop",
            }
            if _cmaes_seed_sampler is not None:
                _restart_cmaes_kwargs["independent_sampler"] = _cmaes_seed_sampler
            sampler = RestartCmaEsSampler(**_restart_cmaes_kwargs)  # type: ignore[assignment]
            logger.info("CMA-ES sampler: BIPOP restart via OptunaHub RestartCmaEsSampler")
        else:
            # Fallback: standard CmaEsSampler without restart (deprecated restart_strategy removed)
            # NOTE: CmaEsSampler does NOT support constraints_func; with_margin=True is experimental.
            _cmaes_kwargs: dict[str, Any] = {
                "seed": 42,
                "n_startup_trials": _cmaes_startup,
            }
            if _cmaes_seed_sampler is not None:
                _cmaes_kwargs["independent_sampler"] = _cmaes_seed_sampler
            try:
                sampler = CmaEsSampler(with_margin=True, **_cmaes_kwargs)  # type: ignore[assignment]
            except TypeError:
                sampler = CmaEsSampler(**_cmaes_kwargs)  # type: ignore[assignment]
            logger.warning("OptunaHub not available — CMA-ES without restart (install: pip install optunahub cmaes)")
    elif sampler_type == "gp" and GPSampler is not None:
        # Gaussian Process sampler — best sample efficiency for < 200 trials.
        # Fits a GP (Matérn 5/2 kernel with ARD) to the objective landscape,
        # optimizes Expected Improvement acquisition function.
        # Outperforms TPE when n_trials < 200; similar quality at larger budgets.
        # QMC Sobol for independent/startup sampling gives uniform initial coverage.
        _gp_startup = max(_n_params * 2, 10)
        if n_trials is not None:
            _gp_startup = min(_gp_startup, max(n_trials // 5, 5))
        _gp_ind_sampler: BaseSampler | None = None
        if QMCSampler is not None:
            try:
                _gp_ind_sampler = QMCSampler(qmc_type="sobol", seed=42)
            except Exception:
                _gp_ind_sampler = None
        _gp_kwargs: dict[str, Any] = {
            "seed": 42,
            "n_startup_trials": _gp_startup,
            "constraints_func": _constraints_func,
        }
        if _gp_ind_sampler is not None:
            _gp_kwargs["independent_sampler"] = _gp_ind_sampler
        try:
            sampler = GPSampler(**_gp_kwargs)  # type: ignore[assignment]
        except TypeError:
            # Older Optuna build — remove unsupported kwargs
            _gp_kwargs.pop("constraints_func", None)
            _gp_kwargs.pop("independent_sampler", None)
            sampler = GPSampler(**_gp_kwargs)  # type: ignore[assignment]
    else:
        # TPE (default): startup = max(4×n_params, 20) capped at n_trials//4.
        # Fixed formula was min(10, n_trials//3) which always returned 10 —
        # far too few for multivariate mode to learn parameter correlations.
        # multivariate=True fits a joint distribution over all params instead
        # of independent marginals, critical when params interact (e.g. fast/slow period).
        # QMC Sobol seed_sampler replaces random startup for better initial coverage.
        _tpe_startup = max(_n_params * 4, 20)
        if n_trials is not None:
            _tpe_startup = min(_tpe_startup, max(n_trials // 4, 10))
        _tpe_seed_sampler: BaseSampler | None = None
        if QMCSampler is not None:
            try:
                _tpe_seed_sampler = QMCSampler(qmc_type="sobol", seed=42)
            except Exception:
                _tpe_seed_sampler = None
        _tpe_kwargs: dict[str, Any] = {
            "seed": 42,
            "n_startup_trials": _tpe_startup,
            "multivariate": True,
            "group": True,  # group correlated params (e.g. MACD fast/slow/signal)
            "constraints_func": _constraints_func,
            # constant_liar: when n_jobs > 1, in-flight (running) trials are
            # treated as if they returned the worst-known score. Without this,
            # parallel workers all sample the same "promising" point and waste
            # 50-80 % of the budget on duplicates. Harmless for n_jobs == 1.
            "constant_liar": effective_n_jobs > 1,
        }
        if _tpe_seed_sampler is not None:
            _tpe_kwargs["seed_sampler"] = _tpe_seed_sampler
        # seed_sampler supported in Optuna ≥ 3.0; group + constant_liar in ≥ 3.1 — degrade gracefully
        try:
            sampler = TPESampler(**_tpe_kwargs)  # type: ignore[assignment]
        except TypeError:
            _tpe_kwargs.pop("seed_sampler", None)
            _tpe_kwargs.pop("group", None)
            _tpe_kwargs.pop("constant_liar", None)
            sampler = TPESampler(**_tpe_kwargs)  # type: ignore[assignment]

    # Suppress Optuna logging
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    # ── Suppress verbose DEBUG logging during optimizer runs ─────────────────
    # The backtesting adapter and indicator handlers emit per-bar DEBUG lines for
    # every trial (12+ lines/trial × 3000 trials = 36k+ lines). This slows I/O
    # significantly. Use loguru.logger.disable() during the run, re-enable after.
    # loguru.disable(name) suppresses all messages from modules whose __name__
    # starts with `name`, so a single prefix disables the entire backtesting subtree.
    from loguru import logger as _loguru_logger

    _quiet_prefix = "backend.backtesting"
    _loguru_logger.disable(_quiet_prefix)

    # Optuna's default in-memory storage is thread-safe for n_jobs > 1.
    # No external storage backend needed.
    # Pruner choice: HyperbandPruner is preferred for long backtests because it
    # uses successive halving to allocate compute, but it requires a meaningful
    # ``max_resource``. For our single-step objective (one report() per trial)
    # we keep MedianPruner — falling back to it preserves identical behaviour
    # when callers don't opt into multi-step reporting. HyperbandPruner is wired
    # up so future walk-forward objectives (which report per-fold) gain its
    # benefits automatically.
    _use_hyperband = bool(config_params.get("use_hyperband_pruner", False))
    if _use_hyperband:
        _pruner: optuna.pruners.BasePruner = HyperbandPruner(
            min_resource=1,
            reduction_factor=3,
        )
        logger.info("Using HyperbandPruner (min_resource=1, reduction_factor=3)")
    else:
        # n_startup_trials must exceed TPE's multivariate-fit requirement.
        # Otherwise: MedianPruner starts pruning at trial 11; TPE tries to build a
        # 10-dim Cholesky-factorised covariance with <5 COMPLETE trials → rank-deficient
        # matrix → scipy.linalg.cholesky on Windows enters uninterruptible native C loop
        # → `threading.Thread.join(_TRIAL_TIMEOUT_S)` doesn't help (C-thread ignores it).
        # Rule of thumb: pruner_startup >= max(30, n_params * 3) to guarantee enough
        # feasible samples for TPE's surrogate before pruning kicks in.
        _pruner_startup = max(30, _n_params * 3)
        _pruner = MedianPruner(n_startup_trials=_pruner_startup, n_warmup_steps=0)

    study = optuna.create_study(
        direction="maximize",
        sampler=sampler,
        pruner=_pruner,
        study_name=f"builder_opt_{int(time.time())}",
    )

    # Warm-start: enqueue best params from a previous optimization run.
    # These will be evaluated first, giving the surrogate model good seed points.
    # Using enqueue_trial() (not add_trial()) so they go through the objective function
    # and produce real constraint values for the current dataset.
    if warm_start_trials:
        _enqueued = 0
        for _wt in warm_start_trials[:10]:  # cap at 10 warm-start points
            _wt_params = _wt.get("params", {})
            if not _wt_params:
                continue
            # Only enqueue if ALL param keys match the current param_specs
            _valid_keys = {spec["param_path"] for spec in param_specs}
            if all(k in _valid_keys for k in _wt_params):
                study.enqueue_trial(_wt_params, user_attrs={"warm_start": True})
                _enqueued += 1
        if _enqueued:
            logger.info(f"Warm-start: enqueued {_enqueued} trials from previous optimization run")

    # ── P0-P3: Performance optimization setup ──────────────────────────────
    # P0: Indicator cache — shared across trials (thread-safe)
    _indicator_cache = IndicatorCache(max_size=1024)

    # P1: Mutable graph updater — one per thread for n_jobs > 1
    # (stored in thread-local for safety)
    import threading as _opt_threading

    _graph_updater_local = _opt_threading.local()

    def _get_graph_updater() -> MutableGraphUpdater:
        """Get or create thread-local MutableGraphUpdater."""
        if not hasattr(_graph_updater_local, "updater"):
            _graph_updater_local.updater = MutableGraphUpdater(base_graph)
        return _graph_updater_local.updater

    # P3: Precompute OHLCV arrays once
    _precomputed = PrecomputedOHLCV(ohlcv)
    _ohlcv_fp = _ohlcv_fingerprint(ohlcv)

    # Track best score for P4 early pruning
    _best_score_so_far: list[float] = [float("-inf")]
    _best_score_lock = _opt_threading.Lock()

    def objective(trial: optuna.Trial) -> float:
        """Optuna objective function for builder strategy."""
        # Suggest parameters
        overrides: dict[str, Any] = {}
        for spec in param_specs:
            path = spec["param_path"]
            if spec["type"] == "int":
                int_step = max(1, int(spec["step"]))  # guard: float step (e.g. 0.1) → 0 breaks range()
                val: int | float = trial.suggest_int(path, int(spec["low"]), int(spec["high"]), step=int_step)
                overrides[path] = val
            else:
                val = trial.suggest_float(path, float(spec["low"]), float(spec["high"]), step=float(spec["step"]))
                overrides[path] = val

        # Enforce fast_period < slow_period for MACD blocks + cross-block
        # constraints (TP/SL/breakeven/close_by_time). Centralised so the same
        # clamping is applied both here AND in the re-run top-N path.
        _apply_cross_block_constraints(overrides, param_specs)

        # P1: Use MutableGraphUpdater instead of deepcopy per trial
        _updater = _get_graph_updater()
        modified_graph = _updater.apply(overrides)

        _TRIAL_TIMEOUT_S = 120  # abort any trial that blocks longer than 2 minutes
        _res: list[Any] = [None]
        _exc: list[BaseException | None] = [None]

        def _run_trial() -> None:
            try:
                _res[0] = run_builder_backtest(modified_graph, ohlcv, config_params, indicator_cache=_indicator_cache)
            except BaseException as _e:
                _exc[0] = _e

        _t = threading.Thread(target=_run_trial, daemon=True)
        _t.start()
        _t.join(timeout=_TRIAL_TIMEOUT_S)

        # P1: Restore graph state after trial (before any early return)
        _updater.restore()

        if _t.is_alive():
            logger.warning(
                "Trial %d timed out after %ds — pruning",
                trial.number,
                _TRIAL_TIMEOUT_S,
            )
            raise optuna.TrialPruned()
        if _exc[0] is not None:
            raise _exc[0]
        result = _res[0]

        # P4: Early pruning for structurally broken trials.
        # Return a severe penalty score instead of TrialPruned() so the trial
        # counts as COMPLETE (preserves tested_combinations semantics) but
        # is ranked last and filtered out by passes_filters().
        with _best_score_lock:
            _current_best = _best_score_so_far[0]
            _n_tested_so_far = len(all_trial_results)
        if should_prune_early(result, config_params, _current_best, _n_tested_so_far):
            _penalty_score = -1e6
            with _results_lock:
                all_trial_results.append(
                    {
                        "params": dict(overrides),
                        "score": _penalty_score,
                        "_trial_number": trial.number,
                        **(result or {}),
                    }
                )
            return _penalty_score

        # Always store result before applying min_trades filter (for fallback).
        # Lock protects the shared list when multiple threads write concurrently.
        score_raw = calculate_composite_score(result, optimize_metric, weights)

        # Guard against pathological metric values (NaN/inf) that would corrupt
        # Optuna's surrogate model (TPE/CMA-ES degrade on non-finite values).
        if not math.isfinite(score_raw):
            raise optuna.TrialPruned()
        # Clamp to prevent extreme outliers from warping the surrogate model.
        score_raw = max(-1e6, min(1e6, score_raw))

        # Log-scale compression via module-level _compress_score (same function
        # used in run_oos_validation so IS and OOS scores are always comparable).
        score_raw = _compress_score(score_raw, optimize_metric)

        # Report intermediate value so MedianPruner can track step-0 scores.
        # For single-step objectives the pruning check happens after the backtest;
        # it doesn't skip computation for *this* trial, but it prunes future trials
        # that clearly underperform the running median.
        trial.report(score_raw, step=0)
        if trial.should_prune():
            raise optuna.TrialPruned()

        with _results_lock:
            all_trial_results.append(
                {"params": dict(overrides), "score": score_raw, "_trial_number": trial.number, **result}
            )
            _n_tested = len(all_trial_results)

        # P4: Update best score for early pruning (thread-safe)
        with _best_score_lock:
            if score_raw > _best_score_so_far[0]:
                _best_score_so_far[0] = score_raw

        # Update progress for frontend polling (every trial)
        if strategy_id:
            _best = max((r["score"] for r in all_trial_results), default=0.0)
            _elapsed = time.time() - start_time
            _speed = round(_n_tested / max(_elapsed, 1), 1)
            _remaining = (n_trials - _n_tested) if n_trials else 0
            _eta = int(_remaining / _speed) if _speed > 0 else 0
            update_optimization_progress(
                strategy_id,
                status="running",
                tested=_n_tested,
                total=n_trials or 0,
                best_score=_best,
                results_found=_n_tested,
                speed=_speed,
                eta_seconds=_eta,
                started_at=start_time,
            )

        # Compute constraint violations and store for Optuna's constrained sampler.
        # Each value > 0 means the constraint is violated; ≤ 0 means satisfied.
        # Constraints are passed via trial.user_attrs so constraints_func can read them.
        # Violations of each filter:
        #   min_trades:          min_trades - total_trades  (>0 if too few trades)
        #   max_drawdown_limit:  drawdown_pct - limit_pct   (>0 if drawdown too large)
        #   min_profit_factor:   min_pf - profit_factor     (>0 if PF too low)
        #   min_win_rate:        min_wr - win_rate_fraction  (>0 if WR too low)
        _violations: list[float] = []
        _min_t = config_params.get("min_trades")
        if _min_t:
            _violations.append(float(_min_t) - float(result.get("total_trades", 0) or 0))
        _max_dd = config_params.get("max_drawdown_limit")
        if _max_dd is not None:
            _violations.append(float(abs(result.get("max_drawdown", 0) or 0)) - float(_max_dd) * 100.0)
        _min_pf = config_params.get("min_profit_factor")
        if _min_pf is not None:
            _violations.append(float(_min_pf) - float(result.get("profit_factor", 0) or 0))
        _min_wr = config_params.get("min_win_rate")
        if _min_wr is not None:
            _violations.append(float(_min_wr) - float(result.get("win_rate", 0) or 0) / 100.0)

        # Dynamic constraints from EvaluationCriteriaPanel (grid/random apply these via
        # passes_filters; Bayesian path must wire them into Optuna's constraint mechanism
        # so the surrogate model also learns to avoid infeasible regions).
        # Convention: violation > 0 → constraint violated; ≤ 0 → satisfied.
        _dyn_constraints = config_params.get("constraints") or []
        for _c in _dyn_constraints:
            _m = _c.get("metric")
            _op = _c.get("operator")
            _thr = _c.get("value")
            if not (_m and _op and _thr is not None):
                continue
            _metric_key = "total_trades" if _m == "min_trades" else _m
            _raw = result.get(_metric_key)
            try:
                _val = float(_raw) if _raw is not None else 0.0
                if not math.isfinite(_val):
                    _val = 0.0
            except (TypeError, ValueError):
                _val = 0.0
            # For drawdown, use absolute value
            if _m in ("max_drawdown", "avg_drawdown") and _val < 0:
                _val = abs(_val)
            try:
                _thr_f = float(_thr)
                if _op == "<=":
                    _violations.append(_val - _thr_f)  # >0 if value exceeds threshold
                elif _op == ">=":
                    _violations.append(_thr_f - _val)  # >0 if value below threshold
                elif _op == "<":
                    _violations.append(_val - _thr_f + 1e-9)
                elif _op == ">":
                    _violations.append(_thr_f - _val + 1e-9)
            except (TypeError, ValueError):
                pass

        trial.set_user_attr("constraint", _violations if _violations else [0.0])

        # With native constrained BO, return the true score for ALL trials.
        # The constraints_func marks infeasible trials; the sampler deprioritises them
        # while still learning from the objective landscape — better than a large penalty
        # that warps the surrogate model with artificial values.
        return score_raw

    # Run optimization
    # Emit explicit stage transition so the UI switches from "Preparing" to
    # "Searching" at the moment the main trial loop begins.
    if strategy_id:
        update_optimization_progress(
            strategy_id,
            status="running",
            tested=0,
            total=n_trials or 0,
            started_at=start_time,
            stage="searching",
        )
    try:
        study.optimize(
            objective,
            n_trials=n_trials,
            timeout=timeout_seconds,
            show_progress_bar=False,
            n_jobs=effective_n_jobs,
            # Catch all trial-level exceptions (e.g. ImportError from missing torch when
            # GPSampler tries to use the Gaussian Process kernel, or any other transient
            # error in a single trial).  Failed trials are logged by Optuna as FAIL-state
            # and excluded from completed_trials below — the optimization continues normally.
            catch=(Exception,),
        )
    finally:
        # Re-enable backend.backtesting logging after optimization
        _loguru_logger.enable(_quiet_prefix)

    # Collect top-N trials — only those that passed filters (native constraint feasibility)
    completed_trials = [
        t
        for t in study.trials
        if t.state == optuna.trial.TrialState.COMPLETE and t.value is not None and t.value > float("-inf")
    ]
    # Filter by native constraint feasibility (constraints stored in user_attrs by objective).
    # A trial is feasible if ALL constraint values are ≤ 0.
    # Falls back to old passes_filters() check for backward compatibility with trials that
    # have no "constraint" user attr (e.g. from warm-started trials added via add_trial).

    def _trial_is_feasible(t: optuna.trial.FrozenTrial) -> bool:
        user_c = t.user_attrs.get("constraint")
        if user_c is not None:
            return all(c <= 0.0 for c in user_c)
        # Fallback: no constraint attr → check via passes_filters on stored result
        _r = next((r for r in all_trial_results if r.get("_trial_number") == t.number), None)
        if _r is not None:
            return passes_filters(_r, config_params)
        return True  # no data → assume feasible (conservative)

    passing_trials = [t for t in completed_trials if _trial_is_feasible(t)]
    passing_trials.sort(key=lambda t: t.value if t.value is not None else 0.0, reverse=True)
    # Deduplicate by param combination — TPE may re-sample the same point multiple times,
    # especially in small search spaces. Keep only the first (highest-score) occurrence.
    _seen_param_keys: set[str] = set()
    deduped_passing: list = []
    for _t in passing_trials:
        _key = str(sorted(_t.params.items()))
        if _key not in _seen_param_keys:
            _seen_param_keys.add(_key)
            deduped_passing.append(_t)
    top_trials = deduped_passing[:top_n]

    # Re-run top-N with FallbackEngineV4 for accurate metrics (Variant A parity fix).
    # NumbaEngineV2 ignores extra_data → profit_only/min_profit in Close-by-Time silently dropped.
    # Using fallback engine here ensures results match what the manual Backtest button produces.
    # Emit "finalizing" stage so the UI progress bar doesn't appear stuck during the
    # ~20 s FallbackEngineV4 re-evaluation pass (previously the bar stalled at the
    # last "searching" tested=N value, looking like a hang).
    if strategy_id and top_trials:
        update_optimization_progress(
            strategy_id,
            status="running",
            tested=0,
            total=len(top_trials),
            stage="finalizing",
        )
    _reeval_config = {**config_params, "engine_type": "fallback"}
    _loguru_logger.disable(_quiet_prefix)
    _loguru_logger.disable("backend.core")
    top_results: list[dict[str, Any]] = []
    try:
        for _reeval_idx, trial in enumerate(top_trials, start=1):
            # CRITICAL: trial.params stores PRE-constraint values from suggest_*().
            # Must re-apply the same cross-block constraints that the objective used,
            # otherwise the re-run backtest uses different params than the original trial.
            overrides = dict(trial.params)  # copy to avoid mutating Optuna internals
            _apply_cross_block_constraints(overrides, param_specs)
            modified_graph = clone_graph_with_params(base_graph, overrides)
            result = run_builder_backtest(modified_graph, ohlcv, _reeval_config)

            if result is not None:
                score_raw = calculate_composite_score(result, optimize_metric, weights)
                # Compress so re-run scores match objective scores and OOS
                # validation compares like-for-like (both compressed).
                score = _compress_score(score_raw, optimize_metric)
                top_results.append(
                    {
                        "params": overrides,
                        "score": score,
                        "score_raw": score_raw,
                        "trial_number": trial.number,
                        **result,
                    }
                )
            # Tick progress so UI knows finalizing is advancing, not stalled.
            if strategy_id and top_trials:
                update_optimization_progress(
                    strategy_id,
                    status="running",
                    tested=_reeval_idx,
                    total=len(top_trials),
                    stage="finalizing",
                )
    finally:
        _loguru_logger.enable(_quiet_prefix)
        _loguru_logger.enable("backend.core")

    # Sort by score
    top_results.sort(key=lambda r: r["score"], reverse=True)

    # Pareto post-processing: re-score top results by NP/DD balance (mirrors grid/random paths)
    if optimize_metric == "pareto_balance" and top_results:
        apply_pareto_scores(top_results)

    # ── P1-1: GT-Score post-processing (optional, opt-in via config_params) ──
    if config_params.get("run_gt_score", False) and top_results:
        from backend.optimization.scoring import calculate_gt_score

        gt_n = min(config_params.get("gt_score_top_n", 5), len(top_results))
        gt_neighbors = config_params.get("gt_score_neighbors", 20)
        gt_epsilon = config_params.get("gt_score_epsilon", 0.05)

        logger.info(f"GT-Score: evaluating {gt_n} top results × {gt_neighbors} neighbors each")

        _loguru_logger.disable(_quiet_prefix)
        _loguru_logger.disable("backend.core")
        try:
            for _gt_result in top_results[:gt_n]:

                def _bt_fn(params, _graph=base_graph, _ohlcv=ohlcv, _cfg=config_params):
                    modified = clone_graph_with_params(_graph, params)
                    r = run_builder_backtest(modified, _ohlcv, _cfg)
                    if r is None:
                        return None
                    return calculate_composite_score(r, optimize_metric, weights)

                gt_info = calculate_gt_score(
                    base_params=_gt_result["params"],
                    param_specs=param_specs,
                    run_backtest_fn=_bt_fn,
                    n_neighbors=gt_neighbors,
                    epsilon=gt_epsilon,
                )
                _gt_result.update(gt_info)
        finally:
            _loguru_logger.enable(_quiet_prefix)
            _loguru_logger.enable("backend.core")
        logger.debug(f"GT-Score done for {gt_n} results")

    # ── P1-2: fANOVA parameter importance (post-optimization analytics) ──
    param_importance: dict[str, float] = {}
    param_importance_low: list[str] = []
    if len(completed_trials) >= 30:
        try:
            # Try fast fANOVA first, then default Optuna evaluator (version-agnostic).
            # FanovaImportanceEvaluator was removed/moved in Optuna 4.x; the default
            # evaluator (PedANOVA / MeanDecreaseImpurity) is always available.
            _evaluator = None
            try:
                from optuna_fast_fanova import FanovaImportanceEvaluator as _FanovaEval

                _evaluator = _FanovaEval(seed=42)
            except ImportError:
                try:
                    from optuna.importance import FanovaImportanceEvaluator as _FanovaEval

                    _evaluator = _FanovaEval(seed=42)
                except (ImportError, AttributeError):
                    pass  # Use default evaluator below

            importance_result = optuna.importance.get_param_importances(
                study,
                evaluator=_evaluator,  # None → Optuna default (always works)
                params=None,
            )
            param_importance = {k: round(float(v), 4) for k, v in importance_result.items()}
            logger.info(f"Param importance: {param_importance}")

            # Tag low-importance params (<5%) — candidates for fixing in next optimization
            param_importance_low = [p for p, imp in param_importance.items() if imp < 0.05]
            if param_importance_low:
                logger.info(f"Low-importance params (consider fixing): {param_importance_low}")

        except Exception as _fanova_err:
            logger.warning(f"Param importance failed (non-critical): {_fanova_err}")

    # ── P2-1: CSCV validation (optional, opt-in via config_params) ──
    cscv_result: dict = {}
    if config_params.get("run_cscv", False) and len(top_results) >= 2:
        try:
            from backend.optimization.cscv import cscv_validation

            def _cscv_backtest_fn(params, sub_ohlcv, _graph=base_graph, _cfg=config_params):
                modified = clone_graph_with_params(_graph, params)
                r = run_builder_backtest(modified, sub_ohlcv, _cfg)
                if r is None:
                    return None
                return calculate_composite_score(r, optimize_metric, weights)

            cscv_result = cscv_validation(
                strategies=top_results[:10],
                ohlcv=ohlcv,
                run_backtest_fn=_cscv_backtest_fn,
                n_splits=config_params.get("cscv_n_splits", 16),
            )
            logger.info(f"CSCV result: PBO={cscv_result.get('pbo')}, {cscv_result.get('pbo_interpretation')}")
        except Exception as _cscv_err:
            logger.warning(f"CSCV validation failed (non-critical): {_cscv_err}")

    # ── P2-3: Deflated Sharpe Ratio (selection bias correction) ──
    dsr_value = None
    best_sr = top_results[0].get("sharpe_ratio") if top_results else None
    if best_sr is not None and completed_trials:
        try:
            from backend.optimization.scoring import deflated_sharpe_ratio

            dsr_value = deflated_sharpe_ratio(
                sharpe_ratio=float(best_sr),
                n_trials=len(completed_trials),
                n_observations=len(ohlcv),
            )
            if dsr_value is not None and not math.isnan(dsr_value) and dsr_value < 0.1:
                logger.warning(
                    f"⚠️ DSR={dsr_value:.3f}: best Sharpe may not be statistically significant "
                    f"(tested {len(completed_trials)} combinations on {len(ohlcv)} bars). "
                    f"Consider longer history or fewer trials."
                )
        except Exception as _dsr_err:
            logger.debug(f"DSR calculation failed (non-critical): {_dsr_err}")

    # Fallback: if min_trades filter pruned all results, use all_trial_results instead.
    # Tag fallback results with a warning so callers (builder_workflow) know the
    # constraint was violated and can decide whether to apply the params.
    fallback_used = False
    _min_trades_req = config_params.get("min_trades", 0)
    if not top_results and all_trial_results:
        logger.warning(
            f"⚠️ Optuna: all {len(completed_trials)} completed trials were filtered out "
            f"(min_trades={_min_trades_req}). Strategy may be structurally unable to generate "
            f"enough signals. Falling back to best {min(top_n, len(all_trial_results))} unfiltered results."
        )
        all_trial_results.sort(key=lambda r: r["score"], reverse=True)
        top_results = all_trial_results[:top_n]
        # Tag each result so callers know the min_trades constraint was not met
        for _r in top_results:
            _r["_below_min_trades"] = True
            _r["_min_trades_required"] = _min_trades_req
        fallback_used = True

    # Detect if best result is negative for the optimize metric
    no_positive_results = False
    if top_results:
        best_score = top_results[0].get("score", 0)
        if best_score < 0:
            no_positive_results = True

    execution_time = time.time() - start_time

    # Mark optimization as completed in progress store
    if strategy_id:
        _final_best = top_results[0]["score"] if top_results else 0.0
        update_optimization_progress(
            strategy_id,
            status="completed",
            tested=len(completed_trials),
            total=n_trials or len(completed_trials),
            best_score=_final_best,
            results_found=len(top_results),
            speed=0,
            eta_seconds=0,
        )

    return {
        "status": "completed",
        "method": "optuna",
        "sampler": sampler_type,
        "total_combinations": n_trials,
        "tested_combinations": len(completed_trials),  # all COMPLETE trials (including penalized)
        "results_passing_filters": len(passing_trials),
        "results_found": len(top_results),
        "top_results": top_results,
        "best_params": top_results[0]["params"] if top_results else {},
        "best_score": top_results[0]["score"] if top_results else 0.0,
        "best_metrics": {k: v for k, v in top_results[0].items() if k not in ("params", "score", "trial_number")}
        if top_results
        else {},
        "execution_time_seconds": round(execution_time, 2),
        "speed_combinations_per_sec": int(len(completed_trials) / max(execution_time, 0.001)),
        "early_stopped": False,
        "fallback_used": fallback_used,
        "no_positive_results": no_positive_results,
        "optimize_metric": optimize_metric,
        # P1-2: fANOVA parameter importance
        "param_importance": param_importance,
        "param_importance_low": param_importance_low,
        # P2-3: Deflated Sharpe Ratio
        "deflated_sharpe_ratio": dsr_value,
        "dsr_warning": dsr_value is not None and not math.isnan(dsr_value) and dsr_value < 0.1,
        # P2-1: CSCV
        "cscv": cscv_result if cscv_result else None,
        # Performance optimization stats (P0-P4)
        "indicator_cache_stats": _indicator_cache.stats,
    }


# =============================================================================
# P2-2: MULTI-OBJECTIVE ANTI-OVERFIT OPTIMIZATION (NSGA-II)
# =============================================================================


def run_builder_optuna_multi_objective(
    base_graph: dict[str, Any],
    is_ohlcv: pd.DataFrame,
    oos_ohlcv: pd.DataFrame,
    oos_cutoff_ts: str,
    param_specs: list[dict[str, Any]],
    config_params: dict[str, Any],
    optimize_metric: str = "sharpe_ratio",
    weights: dict[str, float] | None = None,
    n_trials: int | None = 200,
    top_n: int = 10,
    timeout_seconds: int = 3600,
    strategy_id: str | None = None,
) -> dict[str, Any]:
    """
    Multi-objective Bayesian optimization: maximize OOS score + minimize IS/OOS gap.

    Uses NSGA-II (Non-dominated Sorting Genetic Algorithm) which is the
    standard for multi-objective optimization. Results form a Pareto front
    of strategies that are simultaneously good AND not overfitted.

    Objectives:
        f1 = oos_score (maximize) — performance on held-out data
        f2 = -(is_score - oos_score) (maximize = minimize gap) — generalization

    Requires OOS split to be performed externally (sealed OOS invariant).

    Args:
        base_graph: Base strategy graph.
        is_ohlcv: In-sample OHLCV (optimization target).
        oos_ohlcv: Out-of-sample OHLCV with warmup prepended.
        oos_cutoff_ts: Timestamp where actual OOS starts (warmup cutoff).
        param_specs: Parameter specs with ranges.
        config_params: Backtest config params.
        optimize_metric: Metric to maximize.
        weights: Metric weights for composite scoring.
        n_trials: Max Optuna trials.
        top_n: Number of top results to return.
        timeout_seconds: Wall-clock budget.
        strategy_id: Optional strategy ID for progress tracking.

    Returns:
        Dict with Pareto-front results sorted by OOS score.
    """
    import optuna

    try:
        from optuna.samplers import NSGAIISampler
    except ImportError:
        from optuna.samplers import TPESampler as NSGAIISampler  # type: ignore[assignment]

    start_time = time.time()

    # Suppress verbose logging during optimization
    from loguru import logger as _loguru_logger

    _loguru_logger.disable("backend.backtesting")

    # OOS config: add warmup_cutoff so engine trims warmup bars
    oos_config = {**config_params, "warmup_cutoff": oos_cutoff_ts}

    optuna.logging.set_verbosity(optuna.logging.WARNING)

    n_params = len(param_specs)
    sampler = NSGAIISampler(
        seed=42,
        population_size=max(50, n_params * 5),
        mutation_prob=None,  # auto
        crossover_prob=0.9,
        swapping_prob=0.5,
    )

    study = optuna.create_study(
        directions=["maximize", "maximize"],  # f1=oos_score, f2=-(is-oos gap)
        sampler=sampler,
    )

    all_trial_results: list[dict[str, Any]] = []

    def objective(trial: optuna.Trial) -> tuple[float, float]:
        params: dict[str, Any] = {}
        for spec in param_specs:
            path = spec["param_path"]
            if spec["type"] == "int":
                params[path] = trial.suggest_int(
                    path,
                    int(spec["low"]),
                    int(spec["high"]),
                    step=max(1, int(spec.get("step", 1))),
                )
            else:
                params[path] = trial.suggest_float(
                    path,
                    float(spec["low"]),
                    float(spec["high"]),
                    step=float(spec.get("step")) if spec.get("step") else None,
                )

        # IS backtest
        is_graph = clone_graph_with_params(base_graph, params)
        is_result = run_builder_backtest(is_graph, is_ohlcv, config_params)
        if is_result is None:
            return float("-inf"), float("-inf")

        # IS gate: compute IS score early and skip OOS for clearly poor trials.
        # Multi-objective Optuna doesn't support pruners, so we implement early
        # exit manually — saves ~50% compute when IS is obviously bad.
        is_score = calculate_composite_score(is_result, optimize_metric, weights)
        if not math.isfinite(is_score) or is_score < -1.0:
            return float("-inf"), float("-inf")

        # OOS backtest (only reached when IS is promising)
        oos_graph = clone_graph_with_params(base_graph, params)
        oos_result = run_builder_backtest(oos_graph, oos_ohlcv, oos_config)
        if oos_result is None:
            return float("-inf"), float("-inf")

        oos_score = calculate_composite_score(oos_result, optimize_metric, weights)

        # f2: minimize IS/OOS gap → maximize negative gap
        gap_penalty = -(is_score - oos_score)

        trial.set_user_attr("is_score", is_score)
        trial.set_user_attr("oos_score", oos_score)
        all_trial_results.append(
            {
                "params": params,
                "is_score": is_score,
                "oos_score": oos_score,
                "_trial_number": trial.number,
            }
        )

        return oos_score, gap_penalty

    # Emit stage transition for multi-objective path
    if strategy_id:
        update_optimization_progress(
            strategy_id,
            status="running",
            tested=0,
            total=n_trials or 0,
            started_at=start_time,
            stage="searching",
        )
    try:
        study.optimize(
            objective,
            n_trials=n_trials,
            timeout=timeout_seconds,
            show_progress_bar=False,
            catch=(Exception,),
        )
    finally:
        _loguru_logger.enable("backend.backtesting")

    # Extract Pareto-front trials
    pareto_trials = study.best_trials  # Optuna returns non-dominated trials
    pareto_results: list[dict[str, Any]] = []
    for trial in pareto_trials:
        if trial.values is None:
            continue
        oos_score_val, gap_penalty_val = trial.values
        result_dict: dict[str, Any] = {
            "params": trial.params,
            "oos_score": oos_score_val,
            "is_score": trial.user_attrs.get("is_score", 0),
            "gap_penalty": gap_penalty_val,
            "score": oos_score_val,  # primary sort key = OOS performance
            "oos_degradation_pct": None,
        }
        is_s = result_dict["is_score"]
        if abs(is_s) > 1e-9:
            result_dict["oos_degradation_pct"] = round((is_s - oos_score_val) / abs(is_s) * 100, 1)
        pareto_results.append(result_dict)

    # Sort Pareto front by OOS score (primary) then gap (secondary)
    pareto_results.sort(key=lambda r: (r["oos_score"], r["gap_penalty"]), reverse=True)
    top_results = pareto_results[:top_n]

    execution_time = time.time() - start_time
    completed = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]

    return {
        "status": "completed",
        "method": "optuna_multi_objective",
        "sampler": "nsga2",
        "total_combinations": n_trials,
        "tested_combinations": len(completed),
        "pareto_front_size": len(pareto_trials),
        "top_results": top_results,
        "best_params": top_results[0]["params"] if top_results else {},
        "best_score": top_results[0]["oos_score"] if top_results else 0.0,
        "best_metrics": {k: v for k, v in top_results[0].items() if k not in ("params", "score")}
        if top_results
        else {},
        "execution_time_seconds": round(execution_time, 2),
    }


# =============================================================================
# WALK-FORWARD OPTIMIZATION FOR BUILDER STRATEGIES
# =============================================================================

logger_wf = logging.getLogger(__name__)


def run_builder_walk_forward(
    base_graph: dict[str, Any],
    ohlcv: pd.DataFrame,
    param_specs: list[dict[str, Any]],
    config_params: dict[str, Any],
    optimize_metric: str = "sharpe_ratio",
    weights: dict[str, float] | None = None,
    n_splits: int = 5,
    train_ratio: float = 0.7,
    gap_periods: int = 0,
    inner_method: str = "grid",
    max_iterations: int = 200,
    n_trials: int = 50,
    sampler_type: str = "tpe",
    max_results: int = 20,
    timeout_seconds: int = 3600,
) -> dict[str, Any]:
    """
    Walk-Forward Optimization for Builder strategies.

    Splits OHLCV data into n_splits rolling windows. For each window:
      - Optimizes parameters on the train portion (IS) using Grid or Bayesian
      - Validates best params on the out-of-sample (OOS) portion
    Returns aggregate robustness metrics and per-window results.

    Args:
        base_graph: Strategy graph.
        ohlcv: Full OHLCV DataFrame (sorted ascending).
        param_specs: Optimizable params from extract_optimizable_params().
        config_params: Backtest config (symbol, capital, commission, etc.).
        optimize_metric: Metric to optimise on IS (e.g. 'sharpe_ratio').
        weights: Composite scoring weights.
        n_splits: Number of WF windows.
        train_ratio: Fraction of each window used for IS optimisation.
        gap_periods: Bars to skip between IS and OOS (avoid look-ahead).
        inner_method: 'grid' or 'bayesian' for IS optimisation.
        max_iterations: Max combos for Grid/Random IS search.
        n_trials: Max Optuna trials per window (Bayesian mode).
        sampler_type: Optuna sampler ('tpe', 'random').
        max_results: Top results to keep across all windows.
        timeout_seconds: Total wall-clock timeout.

    Returns:
        Dict with keys: status, windows (list), aggregate_metrics, top_results,
        best_params, recommended_params, overfit_score, execution_time_seconds.
    """
    start_time = time.time()

    total_bars = len(ohlcv)
    if total_bars < n_splits * 30:
        raise ValueError(
            f"Not enough data for {n_splits} walk-forward splits ({total_bars} bars, need at least {n_splits * 30})"
        )

    window_size = total_bars // n_splits
    train_size = int(window_size * train_ratio)
    test_size = window_size - train_size - gap_periods

    if test_size < 10:
        raise ValueError(
            f"OOS window too small ({test_size} bars). Reduce n_splits, increase train_ratio, or use more data."
        )

    logger_wf.info(
        f"[WF] Starting Walk-Forward: {n_splits} splits, "
        f"window={window_size} bars, IS={train_size}, OOS={test_size}, method={inner_method}"
    )

    windows: list[dict[str, Any]] = []
    all_best_params: list[dict[str, Any]] = []
    oos_results_all: list[dict[str, Any]] = []

    for split_idx in range(n_splits):
        elapsed = time.time() - start_time
        if elapsed > timeout_seconds:
            logger_wf.info(f"[WF] Timeout after {elapsed:.0f}s at window {split_idx}/{n_splits}")
            break

        # Slice IS and OOS
        is_start = split_idx * window_size
        is_end = is_start + train_size
        oos_start = is_end + gap_periods
        oos_end = min(oos_start + test_size, total_bars)

        ohlcv_is = ohlcv.iloc[is_start:is_end].copy()

        # Prepend warmup bars to OOS slice so indicators (e.g. SMA-200, RSI-14)
        # are properly initialised before the OOS period begins.  Without warmup
        # the first ~max_period bars of OOS would have NaN indicators → no signals
        # → artificially low OOS metrics (data leakage via missing indicator state).
        # We take bars from the IS period (pre-gap), which are already "seen" by
        # the optimised params — this does NOT leak future price data into IS fitting.
        _WF_WARMUP_BARS = 200
        oos_warmup_start = max(0, oos_start - _WF_WARMUP_BARS)
        ohlcv_oos = ohlcv.iloc[oos_warmup_start:oos_end].copy()

        if len(ohlcv_is) < 20 or len(ohlcv_oos) < 10:
            logger_wf.warning(f"[WF] Window {split_idx + 1}: insufficient data, skipping")
            continue

        window_timeout = max(30, int((timeout_seconds - elapsed) / max(1, n_splits - split_idx)))

        # --- IS optimisation ---
        try:
            if inner_method == "bayesian":
                is_result = run_builder_optuna_search(
                    base_graph=base_graph,
                    ohlcv=ohlcv_is,
                    param_specs=param_specs,
                    config_params=config_params,
                    optimize_metric=optimize_metric,
                    weights=weights,
                    n_trials=n_trials,
                    sampler_type=sampler_type,
                    top_n=1,
                    timeout_seconds=window_timeout,
                )
            else:
                combos, _total, _capped = generate_builder_param_combinations(
                    param_specs=param_specs,
                    custom_ranges=None,
                    search_method="random" if inner_method == "random" else "grid",
                    max_iterations=max_iterations,
                )
                is_result = run_builder_grid_search(
                    base_graph=base_graph,
                    ohlcv=ohlcv_is,
                    param_combinations=combos,
                    config_params=config_params,
                    optimize_metric=optimize_metric,
                    weights=weights,
                    max_results=1,
                    timeout_seconds=window_timeout,
                )
        except Exception as e:
            logger_wf.warning(f"[WF] Window {split_idx + 1} IS optimisation failed: {e}")
            continue

        best_params = is_result.get("best_params") or {}
        best_is_metrics = is_result.get("best_metrics") or {}
        is_score = is_result.get("best_score", 0.0)

        if not best_params:
            logger_wf.warning(f"[WF] Window {split_idx + 1}: no best params found, skipping")
            continue

        # --- OOS validation ---
        modified_graph = clone_graph_with_params(base_graph, best_params)
        oos_metrics = run_builder_backtest(modified_graph, ohlcv_oos, config_params)
        oos_score = calculate_composite_score(oos_metrics, optimize_metric, weights) if oos_metrics else 0.0

        # Degradation: how much worse is OOS vs IS
        is_ret = best_is_metrics.get("total_return", 0.0) or 0.0
        oos_ret = (oos_metrics or {}).get("total_return", 0.0) or 0.0
        is_sharpe = best_is_metrics.get("sharpe_ratio", 0.0) or 0.0
        oos_sharpe = (oos_metrics or {}).get("sharpe_ratio", 0.0) or 0.0
        return_degradation = (oos_ret / is_ret - 1.0) if is_ret != 0 else 0.0
        sharpe_degradation = (oos_sharpe / is_sharpe - 1.0) if is_sharpe != 0 else 0.0

        is_ts = ohlcv_is.index[0] if hasattr(ohlcv_is.index, "__getitem__") else None
        is_te = ohlcv_is.index[-1] if hasattr(ohlcv_is.index, "__getitem__") else None
        oos_ts = ohlcv_oos.index[0] if hasattr(ohlcv_oos.index, "__getitem__") else None
        oos_te = ohlcv_oos.index[-1] if hasattr(ohlcv_oos.index, "__getitem__") else None

        window_result = {
            "window_id": split_idx + 1,
            "train_period": {
                "start": str(is_ts) if is_ts is not None else None,
                "end": str(is_te) if is_te is not None else None,
                "bars": len(ohlcv_is),
            },
            "test_period": {
                "start": str(oos_ts) if oos_ts is not None else None,
                "end": str(oos_te) if oos_te is not None else None,
                "bars": len(ohlcv_oos),
            },
            "best_params": best_params,
            "is_score": round(is_score, 4),
            "oos_score": round(oos_score, 4),
            "is_metrics": {
                "return_pct": round(is_ret, 2),
                "sharpe": round(is_sharpe, 3),
                "max_drawdown_pct": round(best_is_metrics.get("max_drawdown", 0.0) or 0.0, 2),
                "trades": best_is_metrics.get("total_trades", 0) or 0,
            },
            "oos_metrics": {
                "return_pct": round(oos_ret, 2),
                "sharpe": round(oos_sharpe, 3),
                "max_drawdown_pct": round((oos_metrics or {}).get("max_drawdown", 0.0) or 0.0, 2),
                "trades": (oos_metrics or {}).get("total_trades", 0) or 0,
            },
            "degradation": {
                "return_pct": round(return_degradation * 100, 2),
                "sharpe_pct": round(sharpe_degradation * 100, 2),
            },
        }
        windows.append(window_result)
        all_best_params.append(best_params)

        if oos_metrics:
            oos_results_all.append({"params": best_params, "score": oos_score, **oos_metrics})

    # --- Aggregate metrics ---
    n_windows = len(windows)
    if n_windows == 0:
        raise ValueError("Walk-Forward: no windows completed successfully")

    avg_is_sharpe = sum(w["is_metrics"]["sharpe"] for w in windows) / n_windows
    avg_oos_sharpe = sum(w["oos_metrics"]["sharpe"] for w in windows) / n_windows
    avg_is_ret = sum(w["is_metrics"]["return_pct"] for w in windows) / n_windows
    avg_oos_ret = sum(w["oos_metrics"]["return_pct"] for w in windows) / n_windows
    consistency_ratio = sum(1 for w in windows if w["oos_metrics"]["return_pct"] > 0) / n_windows

    # Overfitting score: 0 = no overfit, 1 = severe
    overfit_score = max(0.0, min(1.0, 1.0 - avg_oos_sharpe / avg_is_sharpe)) if avg_is_sharpe > 0 else 0.5

    # Parameter stability: fraction of params that match the most-common value
    param_stability = 1.0
    if all_best_params:
        all_keys = set().union(*all_best_params)
        stabilities = []
        for k in all_keys:
            vals = [str(p.get(k)) for p in all_best_params if k in p]
            if vals:
                most_common_count = max(vals.count(v) for v in set(vals))
                stabilities.append(most_common_count / len(vals))
        param_stability = sum(stabilities) / len(stabilities) if stabilities else 1.0

    # Recommended params: most common best params across windows
    recommended_params: dict[str, Any] = {}
    if all_best_params:
        all_keys = set().union(*all_best_params)
        for k in all_keys:
            vals = [p[k] for p in all_best_params if k in p]
            if vals:
                # Most frequent value
                recommended_params[k] = max(set(map(str, vals)), key=lambda v: [str(x) for x in vals].count(v))
                # Try to cast back to numeric
                try:
                    recommended_params[k] = int(recommended_params[k])
                except (ValueError, TypeError):
                    with contextlib.suppress(ValueError, TypeError):
                        recommended_params[k] = float(recommended_params[k])

    confidence = (
        "high"
        if consistency_ratio >= 0.7 and overfit_score < 0.3
        else "medium"
        if consistency_ratio >= 0.5 and overfit_score < 0.6
        else "low"
    )

    # Pareto post-processing: re-score OOS results by NP/DD balance (mirrors grid/Bayesian paths)
    if optimize_metric == "pareto_balance" and oos_results_all:
        apply_pareto_scores(oos_results_all)

    # Sort OOS results for top_results
    oos_results_all.sort(key=lambda r: r["score"], reverse=True)
    top_results = oos_results_all[:max_results]

    execution_time = time.time() - start_time
    logger_wf.info(
        f"[WF] Completed: {n_windows} windows, "
        f"avg OOS sharpe={avg_oos_sharpe:.3f}, overfit={overfit_score:.2f}, "
        f"confidence={confidence}, time={execution_time:.1f}s"
    )

    return {
        "status": "completed",
        "method": "walk_forward",
        "n_splits": n_splits,
        "train_ratio": train_ratio,
        "windows_completed": n_windows,
        "windows": windows,
        "aggregate_metrics": {
            "train": {
                "avg_return_pct": round(avg_is_ret, 2),
                "avg_sharpe": round(avg_is_sharpe, 3),
            },
            "test": {
                "avg_return_pct": round(avg_oos_ret, 2),
                "avg_sharpe": round(avg_oos_sharpe, 3),
            },
        },
        "robustness": {
            "consistency_ratio_pct": round(consistency_ratio * 100, 2),
            "parameter_stability_pct": round(param_stability * 100, 2),
            "overfit_score": round(overfit_score, 3),
        },
        "recommendation": {
            "params": recommended_params,
            "confidence": confidence,
        },
        "total_combinations": n_splits,
        "tested_combinations": n_windows,
        "results_found": len(oos_results_all),
        "top_results": top_results,
        "best_params": recommended_params,
        "best_score": round(avg_oos_sharpe, 4),
        "best_metrics": {},
        "execution_time_seconds": round(execution_time, 2),
        "speed_combinations_per_sec": int(n_windows / max(execution_time, 0.001)),
        "early_stopped": False,
    }
