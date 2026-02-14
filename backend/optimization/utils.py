"""
Optimization Utilities.

BacktestInput builder (DRY), parameter combination generator,
train/test split, timeout/early-stopping helpers.
"""

from __future__ import annotations

import logging
import time
from itertools import product
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from backend.backtesting.interfaces import BacktestInput, TradeDirection

logger = logging.getLogger(__name__)


# =============================================================================
# BACKTEST INPUT BUILDER (eliminates 6x duplication)
# =============================================================================


def build_backtest_input(
    candles: pd.DataFrame,
    long_entries: np.ndarray,
    long_exits: np.ndarray,
    short_entries: np.ndarray,
    short_exits: np.ndarray,
    request_params: dict,
    trade_direction: TradeDirection,
    stop_loss_pct: float = 0.0,
    take_profit_pct: float = 0.0,
) -> BacktestInput:
    """
    Build BacktestInput from request params — single source of truth.

    Replaces 6 identical construction blocks throughout optimizations.py.

    Args:
        candles: OHLCV DataFrame.
        long_entries/exits, short_entries/exits: Signal arrays.
        request_params: Dict with symbol, interval, initial_capital, etc.
        trade_direction: TradeDirection enum.
        stop_loss_pct: Stop loss percent (e.g. 10.0 = 10%).
        take_profit_pct: Take profit percent (e.g. 1.5 = 1.5%).

    Returns:
        Configured BacktestInput instance.
    """
    from backend.backtesting.interfaces import BacktestInput

    # Position sizing: fixed amount or percentage
    use_fixed = request_params.get("use_fixed_amount", False)
    pos_size = 0.1 if use_fixed else 1.0

    return BacktestInput(
        candles=candles,
        candles_1m=None,  # Bar Magnifier off for optimization speed
        long_entries=long_entries,
        long_exits=long_exits,
        short_entries=short_entries,
        short_exits=short_exits,
        symbol=request_params["symbol"],
        interval=request_params["interval"],
        initial_capital=request_params["initial_capital"],
        position_size=pos_size,
        use_fixed_amount=use_fixed,
        fixed_amount=request_params.get("fixed_amount", 0.0),
        leverage=request_params["leverage"],
        stop_loss=stop_loss_pct / 100.0 if stop_loss_pct else 0.0,
        take_profit=take_profit_pct / 100.0 if take_profit_pct else 0.0,
        direction=trade_direction,
        taker_fee=request_params["commission"],
        maker_fee=request_params["commission"],
        slippage=0.0005,
        use_bar_magnifier=False,
        max_drawdown_limit=0.0,
        pyramiding=1,
        market_regime_enabled=request_params.get("market_regime_enabled", False),
        market_regime_filter=request_params.get("market_regime_filter", "not_volatile"),
        market_regime_lookback=request_params.get("market_regime_lookback", 50),
    )


# =============================================================================
# PARAMETER COMBINATION GENERATOR
# =============================================================================


def generate_param_combinations(
    request,
    search_method: str = "grid",
    max_iterations: int = 0,
    random_seed: int | None = None,
) -> tuple[list[tuple], int, list[str]]:
    """
    Generate parameter combinations from request ranges.

    Supports grid search (all combos) and random search (sampled subset).
    Universal — works with any strategy type's parameter ranges.

    Args:
        request: SyncOptimizationRequest with *_range fields.
        search_method: "grid" or "random".
        max_iterations: Max combos for random search (0 = 10% of total).
        random_seed: Seed for reproducibility.

    Returns:
        Tuple of (combinations_list, total_count_before_sampling, param_names).
        param_names tells the caller what each element in the tuple represents.
    """
    import random

    sl_range = request.stop_loss_range if request.stop_loss_range else [0]
    tp_range = request.take_profit_range if request.take_profit_range else [0]

    strategy_type = getattr(request, "strategy_type", "rsi").lower().strip()

    # Build strategy-specific param ranges + names
    strategy_ranges: list[list] = []
    param_names: list[str] = []

    if strategy_type == "rsi":
        strategy_ranges = [
            request.rsi_period_range,
            request.rsi_overbought_range,
            request.rsi_oversold_range,
        ]
        param_names = ["rsi_period", "rsi_overbought", "rsi_oversold"]

    elif strategy_type == "sma_crossover":
        strategy_ranges = [
            getattr(request, "sma_fast_period_range", None) or [10, 20],
            getattr(request, "sma_slow_period_range", None) or [50, 100],
        ]
        param_names = ["sma_fast_period", "sma_slow_period"]

    elif strategy_type == "ema_crossover":
        strategy_ranges = [
            getattr(request, "ema_fast_period_range", None) or [9, 12],
            getattr(request, "ema_slow_period_range", None) or [21, 26],
        ]
        param_names = ["ema_fast_period", "ema_slow_period"]

    elif strategy_type == "macd":
        strategy_ranges = [
            getattr(request, "macd_fast_period_range", None) or [12],
            getattr(request, "macd_slow_period_range", None) or [26],
            getattr(request, "macd_signal_period_range", None) or [9],
        ]
        param_names = ["macd_fast_period", "macd_slow_period", "macd_signal_period"]

    elif strategy_type == "bollinger_bands":
        strategy_ranges = [
            getattr(request, "bb_period_range", None) or [20],
            getattr(request, "bb_std_dev_range", None) or [2.0],
        ]
        param_names = ["bb_period", "bb_std_dev"]

    else:
        # Fallback: RSI ranges (backward compat)
        strategy_ranges = [
            request.rsi_period_range,
            request.rsi_overbought_range,
            request.rsi_oversold_range,
        ]
        param_names = ["rsi_period", "rsi_overbought", "rsi_oversold"]
        logger.warning(f"Unknown strategy_type '{strategy_type}', using RSI ranges as fallback")

    # Append SL/TP ranges
    param_names.extend(["stop_loss_pct", "take_profit_pct"])
    all_ranges = [*strategy_ranges, sl_range, tp_range]

    param_combinations = list(product(*all_ranges))
    total_before_sampling = len(param_combinations)

    if search_method == "random":
        if random_seed is not None:
            random.seed(random_seed)

        if max_iterations <= 0:
            max_iterations = max(10, total_before_sampling // 10)

        if max_iterations < total_before_sampling:
            param_combinations = random.sample(param_combinations, max_iterations)
            logger.info(f"🎲 Random Search: sampling {max_iterations} from {total_before_sampling}")
        else:
            logger.info(f"🎲 Random Search: all {total_before_sampling} combos (< max_iterations)")
    else:
        logger.info(f"🔢 Grid Search: {total_before_sampling} combinations")

    return param_combinations, total_before_sampling, param_names


def combo_to_params(combo: tuple, param_names: list[str]) -> dict:
    """
    Convert a parameter combination tuple to a named params dict.

    Args:
        combo: Tuple of parameter values from generate_param_combinations().
        param_names: List of param names from generate_param_combinations().

    Returns:
        Dict mapping param name to value, e.g. {"rsi_period": 14, ...}.
    """
    return dict(
        zip(param_names, combo, strict=False)
    )  # =============================================================================


# TRAIN/TEST SPLIT
# =============================================================================


def split_candles(candles: pd.DataFrame, train_split: float) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """
    Split candles into train and test sets.

    Args:
        candles: Full OHLCV DataFrame.
        train_split: Fraction for training (0.5-0.95). 1.0 = no split.

    Returns:
        (train_candles, test_candles_or_None)
    """
    if train_split >= 1.0 or train_split <= 0.0:
        return candles, None

    # Clamp to valid range
    train_split = max(0.5, min(0.95, train_split))

    split_idx = int(len(candles) * train_split)
    # Ensure at least 50 candles in each set
    split_idx = max(50, min(split_idx, len(candles) - 50))

    train = candles.iloc[:split_idx]
    test = candles.iloc[split_idx:]

    logger.info(f"📊 Train/Test split: {train_split:.0%} → train={len(train)} candles, test={len(test)} candles")

    return train, test


# =============================================================================
# TIMEOUT CHECKER
# =============================================================================


class TimeoutChecker:
    """
    Check if optimization has exceeded time limit.

    Usage:
        checker = TimeoutChecker(timeout_seconds=300)
        for combo in combinations:
            if checker.is_expired():
                break
            # ... run backtest
    """

    def __init__(self, timeout_seconds: int = 3600):
        self.timeout_seconds = timeout_seconds
        self.start_time = time.time()
        self._expired = False

    def is_expired(self) -> bool:
        """Check if timeout reached. Caches result after first expiry."""
        if self._expired:
            return True
        if self.timeout_seconds > 0 and (time.time() - self.start_time) > self.timeout_seconds:
            self._expired = True
            elapsed = time.time() - self.start_time
            logger.warning(f"⏰ Timeout reached: {elapsed:.0f}s > {self.timeout_seconds}s limit")
            return True
        return False

    @property
    def elapsed(self) -> float:
        """Seconds elapsed since start."""
        return time.time() - self.start_time


# =============================================================================
# EARLY STOPPING
# =============================================================================


class EarlyStopper:
    """
    Track best score and stop when no improvement for N iterations.

    Usage:
        stopper = EarlyStopper(patience=20, enabled=True)
        for combo in combinations:
            score = run_backtest(combo)
            if stopper.should_stop(score):
                break
    """

    def __init__(self, patience: int = 20, enabled: bool = False):
        self.patience = patience
        self.enabled = enabled
        self.best_score = float("-inf")
        self.iterations_without_improvement = 0
        self.total_iterations = 0
        self._stopped = False

    def should_stop(self, score: float) -> bool:
        """
        Check if optimization should stop.

        Args:
            score: Score from latest backtest.

        Returns:
            True if patience exhausted.
        """
        if not self.enabled:
            return False

        self.total_iterations += 1

        if score > self.best_score:
            self.best_score = score
            self.iterations_without_improvement = 0
        else:
            self.iterations_without_improvement += 1

        if self.iterations_without_improvement >= self.patience:
            self._stopped = True
            logger.info(
                f"🛑 Early stopping: no improvement for {self.patience} iterations "
                f"(best={self.best_score:.4f}, total={self.total_iterations})"
            )
            return True

        return False

    @property
    def stopped(self) -> bool:
        """Whether early stopping was triggered."""
        return self._stopped


# =============================================================================
# RESULT METRICS EXTRACTOR
# =============================================================================


def extract_metrics_from_output(bt_output, win_rate_as_pct: bool = True) -> dict[str, Any]:
    """
    Extract standardized metrics dict from BacktestOutput.

    Eliminates ~50-line manual dict construction repeated in multiple places.

    Args:
        bt_output: BacktestOutput from engine.run().
        win_rate_as_pct: If True, convert win_rate 0-1 to 0-100%.

    Returns:
        Dict with all standard metrics.
    """
    metrics = bt_output.metrics
    if not metrics:
        return {
            "total_return": 0,
            "sharpe_ratio": 0,
            "max_drawdown": 0,
            "win_rate": 0,
            "total_trades": 0,
            "profit_factor": 0,
        }

    win_rate = metrics.win_rate
    if win_rate_as_pct and win_rate is not None and win_rate <= 1.0:
        win_rate = win_rate * 100

    result = {
        "total_return": metrics.total_return or 0,
        "sharpe_ratio": metrics.sharpe_ratio or 0,
        "max_drawdown": metrics.max_drawdown or 0,
        "win_rate": win_rate or 0,
        "total_trades": metrics.total_trades or 0,
        "profit_factor": metrics.profit_factor or 0,
        "winning_trades": metrics.winning_trades or 0,
        "losing_trades": metrics.losing_trades or 0,
        "net_profit": metrics.net_profit or 0,
        "net_profit_pct": metrics.total_return or 0,
        "gross_profit": metrics.gross_profit or 0,
        "gross_loss": metrics.gross_loss or 0,
        "avg_win": metrics.avg_win or 0,
        "avg_loss": metrics.avg_loss or 0,
        "avg_win_value": metrics.avg_win or 0,
        "avg_loss_value": metrics.avg_loss or 0,
        "largest_win": metrics.largest_win or 0,
        "largest_loss": metrics.largest_loss or 0,
        "largest_win_value": metrics.largest_win or 0,
        "largest_loss_value": metrics.largest_loss or 0,
        "recovery_factor": metrics.recovery_factor or 0,
        "expectancy": metrics.expectancy or 0,
        "sortino_ratio": metrics.sortino_ratio or 0,
        "calmar_ratio": metrics.calmar_ratio or 0,
        "max_drawdown_value": 0,
        # Long/Short breakdown
        "long_trades": metrics.long_trades or 0,
        "long_winning_trades": getattr(metrics, "long_winning_trades", 0) or 0,
        "long_losing_trades": getattr(metrics, "long_losing_trades", 0) or 0,
        "long_win_rate": (metrics.long_win_rate * 100 if win_rate_as_pct else metrics.long_win_rate)
        if metrics.long_win_rate
        else 0,
        "long_gross_profit": getattr(metrics, "long_gross_profit", 0) or 0,
        "long_gross_loss": getattr(metrics, "long_gross_loss", 0) or 0,
        "long_net_profit": metrics.long_profit or 0,
        "long_profit_factor": getattr(metrics, "long_profit_factor", 0) or 0,
        "long_avg_win": getattr(metrics, "long_avg_win", 0) or 0,
        "long_avg_loss": getattr(metrics, "long_avg_loss", 0) or 0,
        "short_trades": metrics.short_trades or 0,
        "short_winning_trades": getattr(metrics, "short_winning_trades", 0) or 0,
        "short_losing_trades": getattr(metrics, "short_losing_trades", 0) or 0,
        "short_win_rate": (metrics.short_win_rate * 100 if win_rate_as_pct else metrics.short_win_rate)
        if metrics.short_win_rate
        else 0,
        "short_gross_profit": getattr(metrics, "short_gross_profit", 0) or 0,
        "short_gross_loss": getattr(metrics, "short_gross_loss", 0) or 0,
        "short_net_profit": metrics.short_profit or 0,
        "short_profit_factor": getattr(metrics, "short_profit_factor", 0) or 0,
        "short_avg_win": getattr(metrics, "short_avg_win", 0) or 0,
        "short_avg_loss": getattr(metrics, "short_avg_loss", 0) or 0,
        # Duration
        "avg_bars_in_trade": metrics.avg_trade_duration or 0,
        "avg_bars_in_winning": metrics.avg_winning_duration or 0,
        "avg_bars_in_losing": metrics.avg_losing_duration or 0,
        # Commission
        "total_commission": sum(t.fees for t in bt_output.trades) if bt_output.trades else 0,
    }

    return result


def serialize_trades(bt_output, max_trades: int = 500) -> list[dict]:
    """
    Serialize trade objects to dicts for API response.

    Only stores trades for top results to avoid memory explosion.

    Args:
        bt_output: BacktestOutput with .trades list.
        max_trades: Max number of trades to include.

    Returns:
        List of trade dicts.
    """
    if not bt_output.trades:
        return []

    trades_data = []
    for t in bt_output.trades[:max_trades]:
        duration_hours = 0
        if t.entry_time and t.exit_time:
            duration_hours = (t.exit_time - t.entry_time).total_seconds() / 3600

        trades_data.append(
            {
                "entry_time": t.entry_time.isoformat() if t.entry_time else None,
                "exit_time": t.exit_time.isoformat() if t.exit_time else None,
                "side": (
                    t.direction
                    if hasattr(t, "direction")
                    else (
                        t.side.value
                        if hasattr(t, "side") and hasattr(t.side, "value")
                        else str(getattr(t, "side", "unknown"))
                    )
                ),
                "entry_price": float(t.entry_price) if t.entry_price else 0,
                "exit_price": float(t.exit_price) if t.exit_price else 0,
                "size": float(t.size) if t.size else 0,
                "pnl": float(t.pnl) if t.pnl else 0,
                "pnl_pct": float(t.pnl_pct) if hasattr(t, "pnl_pct") and t.pnl_pct else 0,
                "return_pct": float(t.pnl_pct) if hasattr(t, "pnl_pct") and t.pnl_pct else 0,
                "fees": float(t.fees) if hasattr(t, "fees") and t.fees else 0,
                "duration_hours": duration_hours,
                "mfe": float(t.mfe) if hasattr(t, "mfe") and t.mfe else 0,
                "mae": float(t.mae) if hasattr(t, "mae") and t.mae else 0,
                "mfe_pct": float(t.mfe) if hasattr(t, "mfe") and t.mfe else 0,
                "mae_pct": float(t.mae) if hasattr(t, "mae") and t.mae else 0,
            }
        )

    return trades_data


def serialize_equity_curve(bt_output, max_points: int = 500) -> dict | None:
    """
    Serialize equity curve for API response.

    Downsamples if too many points.

    Args:
        bt_output: BacktestOutput with equity_curve and timestamps.
        max_points: Max number of equity data points.

    Returns:
        Dict with timestamps, equity, drawdown, returns. Or None.
    """
    if bt_output.equity_curve is None or len(bt_output.equity_curve) == 0:
        return None

    equity = bt_output.equity_curve
    timestamps = bt_output.timestamps if bt_output.timestamps is not None else []

    step = max(1, len(equity) // max_points)
    return {
        "timestamps": [
            t.isoformat() if hasattr(t, "isoformat") else str(t)
            for t in (timestamps[::step] if len(timestamps) > 0 else [])
        ],
        "equity": [float(e) for e in equity[::step]],
        "drawdown": [],
        "returns": [],
    }


def parse_trade_direction(direction_str: str) -> TradeDirection:
    """Parse direction string to TradeDirection enum."""
    from backend.backtesting.interfaces import TradeDirection

    if direction_str == "long":
        return TradeDirection.LONG
    elif direction_str == "short":
        return TradeDirection.SHORT
    return TradeDirection.BOTH
