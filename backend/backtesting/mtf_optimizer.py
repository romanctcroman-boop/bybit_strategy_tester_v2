"""
🔧 MTF Grid Optimizer

Extends the Universal Optimizer with Multi-Timeframe parameters:
- HTF interval (1H, 4H, D)
- HTF filter type (SMA, EMA, SuperTrend, Ichimoku, MACD)
- HTF filter period (50, 100, 200)
- BTC correlation settings

Usage:
    from backend.backtesting.mtf_optimizer import MTFOptimizer

    result = MTFOptimizer().optimize(
        candles=ltf_candles,
        htf_candles=htf_candles,
        htf_index_map=htf_index_map,
        # Strategy params
        rsi_period_range=[7, 14, 21],
        rsi_overbought_range=[70, 75, 80],
        rsi_oversold_range=[20, 25, 30],
        # MTF params
        htf_filter_types=["sma", "ema", "supertrend"],
        htf_filter_periods=[50, 100, 200],
        ...
    )
"""

import itertools
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from loguru import logger

from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.mtf.filters import (
    HTFTrendFilter,
    IchimokuFilter,
    MACDFilter,
    SuperTrendFilter,
    calculate_ema,
    calculate_ichimoku,
    calculate_macd,
    calculate_sma,
    calculate_supertrend,
)
from backend.backtesting.mtf.signals import generate_mtf_rsi_signals


@dataclass
class MTFOptimizationResult:
    """Result of MTF optimization."""

    status: str
    total_combinations: int
    tested_combinations: int
    execution_time_seconds: float
    best_params: dict[str, Any]
    best_score: float
    best_metrics: dict[str, Any]
    top_results: list[dict[str, Any]]
    performance_stats: dict[str, Any]
    mtf_params_tested: dict[str, list[Any]] = field(default_factory=dict)


class MTFOptimizer:
    """
    Multi-Timeframe Strategy Optimizer.

    Optimizes both strategy parameters and MTF filter parameters:
    - RSI periods, overbought/oversold levels
    - Stop loss, take profit
    - HTF filter type (SMA, EMA, SuperTrend, Ichimoku, MACD)
    - HTF filter period
    - BTC correlation settings
    """

    def __init__(self, parallel_workers: int = 4, verbose: bool = True):
        """
        Initialize MTF Optimizer.

        Args:
            parallel_workers: Number of parallel workers (for future use)
            verbose: Print progress information
        """
        self.parallel_workers = parallel_workers
        self.verbose = verbose
        self._precomputed_indicators = {}

    def _precompute_htf_indicators(
        self,
        htf_candles: pd.DataFrame,
        htf_filter_types: list[str],
        htf_filter_periods: list[int],
    ) -> dict[str, dict[int, np.ndarray]]:
        """
        Precompute all HTF indicators to avoid redundant calculations.

        Args:
            htf_candles: HTF OHLCV data
            htf_filter_types: List of filter types to compute
            htf_filter_periods: List of periods to compute

        Returns:
            Dict mapping filter_type -> period -> indicator_values
        """
        indicators = {}

        close = htf_candles["close"].values.astype(float)
        high = (
            htf_candles["high"].values.astype(float) if "high" in htf_candles else close
        )
        low = htf_candles["low"].values.astype(float) if "low" in htf_candles else close

        for filter_type in htf_filter_types:
            indicators[filter_type] = {}

            for period in htf_filter_periods:
                if filter_type == "sma":
                    indicators[filter_type][period] = calculate_sma(close, period)
                elif filter_type == "ema":
                    indicators[filter_type][period] = calculate_ema(close, period)
                elif filter_type == "supertrend":
                    multiplier = 3.0  # Default multiplier
                    st_values, st_trend = calculate_supertrend(
                        high, low, close, period, multiplier
                    )
                    indicators[filter_type][period] = (st_values, st_trend)
                elif filter_type == "ichimoku":
                    ich = calculate_ichimoku(
                        high, low, tenkan_period=9, kijun_period=period
                    )
                    indicators[filter_type][period] = ich
                elif filter_type == "macd":
                    # Use period as slow period, fast = period // 2
                    fast = max(period // 2, 5)
                    signal = max(period // 3, 3)
                    macd_line, signal_line, histogram = calculate_macd(
                        close, fast, period, signal
                    )
                    indicators[filter_type][period] = (
                        macd_line,
                        signal_line,
                        histogram,
                    )

        return indicators

    def _get_htf_filter_values(
        self,
        htf_idx: int,
        htf_close: np.ndarray,
        filter_type: str,
        period: int,
        precomputed: dict,
    ) -> tuple[bool, bool]:
        """
        Get filter decision for a specific HTF bar.

        Args:
            htf_idx: HTF bar index
            htf_close: HTF close prices
            filter_type: Type of filter
            period: Filter period
            precomputed: Precomputed indicators

        Returns:
            (allow_long, allow_short)
        """
        if htf_idx < 0 or htf_idx >= len(htf_close):
            return True, True  # No valid HTF bar

        close_val = htf_close[htf_idx]

        if filter_type in ["sma", "ema"]:
            indicator = precomputed[filter_type][period]
            ind_val = indicator[htf_idx]
            if np.isnan(ind_val):
                return True, True
            filter_obj = HTFTrendFilter(period=period, filter_type=filter_type)
            return filter_obj.check(close_val, ind_val)

        elif filter_type == "supertrend":
            st_values, st_trend = precomputed[filter_type][period]
            trend = st_trend[htf_idx]
            filter_obj = SuperTrendFilter(period=period)
            return filter_obj.check(close_val, st_values[htf_idx], trend=trend)

        elif filter_type == "ichimoku":
            ich = precomputed[filter_type][period]
            sa = ich["senkou_a"][htf_idx]
            sb = ich["senkou_b"][htf_idx]
            filter_obj = IchimokuFilter()
            return filter_obj.check(close_val, 0, senkou_a=sa, senkou_b=sb)

        elif filter_type == "macd":
            macd_line, signal_line, histogram = precomputed[filter_type][period]
            filter_obj = MACDFilter()
            return filter_obj.check(
                0, 0, macd=macd_line[htf_idx], signal=signal_line[htf_idx]
            )

        return True, True

    def optimize(
        self,
        ltf_candles: pd.DataFrame,
        htf_candles: pd.DataFrame,
        htf_index_map: np.ndarray,
        # Strategy params
        rsi_period_range: list[int] | None = None,
        rsi_overbought_range: list[int] | None = None,
        rsi_oversold_range: list[int] | None = None,
        stop_loss_range: list[float] | None = None,
        take_profit_range: list[float] | None = None,
        # MTF params
        htf_filter_types: list[str] | None = None,
        htf_filter_periods: list[int] | None = None,
        # Trading params
        initial_capital: float = 10000.0,
        leverage: int = 10,
        commission: float = 0.0007,
        direction: str = "both",
        # Optimization params
        optimize_metric: str = "sharpe_ratio",
        top_k: int = 20,
    ) -> MTFOptimizationResult:
        """
        Run MTF strategy optimization.

        Args:
            ltf_candles: Lower timeframe OHLCV data
            htf_candles: Higher timeframe OHLCV data
            htf_index_map: LTF → HTF index mapping
            rsi_period_range: RSI periods to test (default: [14])
            rsi_overbought_range: Overbought levels to test (default: [70])
            rsi_oversold_range: Oversold levels to test (default: [30])
            stop_loss_range: Stop loss percentages to test (default: [0.02])
            take_profit_range: Take profit percentages to test (default: [0.03])
            htf_filter_types: HTF filter types to test (default: ["sma"])
            htf_filter_periods: HTF filter periods to test (default: [200])
            initial_capital: Starting capital
            leverage: Trading leverage
            commission: Commission rate
            direction: Trade direction
            optimize_metric: Metric to optimize
            top_k: Number of top results to return

        Returns:
            MTFOptimizationResult
        """
        # Initialise mutable defaults here to avoid B006
        if rsi_period_range is None:
            rsi_period_range = [14]
        if rsi_overbought_range is None:
            rsi_overbought_range = [70]
        if rsi_oversold_range is None:
            rsi_oversold_range = [30]
        if stop_loss_range is None:
            stop_loss_range = [0.02]
        if take_profit_range is None:
            take_profit_range = [0.03]
        if htf_filter_types is None:
            htf_filter_types = ["sma"]
        if htf_filter_periods is None:
            htf_filter_periods = [200]

        start_time = time.perf_counter()

        # Calculate total combinations
        total_combinations = (
            len(rsi_period_range)
            * len(rsi_overbought_range)
            * len(rsi_oversold_range)
            * len(stop_loss_range)
            * len(take_profit_range)
            * len(htf_filter_types)
            * len(htf_filter_periods)
        )

        if self.verbose:
            logger.info(f"🔧 MTF Optimization: {total_combinations} combinations")

        # Precompute HTF indicators (stored for potential future use)
        precomputed = self._precompute_htf_indicators(  # noqa: F841
            htf_candles, htf_filter_types, htf_filter_periods
        )

        # Prepare data (stored for potential future use)
        htf_close = htf_candles["close"].values.astype(float)  # noqa: F841

        # Results storage
        all_results = []
        tested = 0

        # Generate parameter grid
        param_grid = itertools.product(
            rsi_period_range,
            rsi_overbought_range,
            rsi_oversold_range,
            stop_loss_range,
            take_profit_range,
            htf_filter_types,
            htf_filter_periods,
        )

        for params in param_grid:
            rsi_period, overbought, oversold, sl, tp, filter_type, filter_period = (
                params
            )

            # Skip invalid RSI params
            if overbought <= oversold:
                continue

            tested += 1

            # Generate signals with MTF filter
            long_signals, long_exits, short_signals, short_exits = (
                generate_mtf_rsi_signals(
                    ltf_candles=ltf_candles,
                    htf_candles=htf_candles,
                    htf_index_map=htf_index_map,
                    htf_filter_type=filter_type,
                    htf_filter_period=filter_period,
                    direction=direction,
                    rsi_period=rsi_period,
                    overbought=overbought,
                    oversold=oversold,
                )
            )

            # Run backtest
            try:
                from backend.backtesting.interfaces import BacktestInput

                bt_input = BacktestInput(
                    candles=ltf_candles,
                    long_entries=long_signals,
                    long_exits=long_exits,
                    short_entries=short_signals,
                    short_exits=short_exits,
                    initial_capital=initial_capital,
                    leverage=leverage,
                    stop_loss=sl,
                    take_profit=tp,
                    direction=direction,
                )

                engine = FallbackEngineV4()
                result = engine.run(bt_input)

                # Convert metrics to dict for easy access
                metrics_dict = (
                    result.metrics.to_dict()
                    if hasattr(result.metrics, "to_dict")
                    else {}
                )

                # Extract score (using getattr for dataclass)
                if optimize_metric == "sharpe_ratio":
                    score = getattr(result.metrics, "sharpe_ratio", -999)
                elif optimize_metric == "total_return":
                    score = getattr(result.metrics, "total_return", -999)
                elif optimize_metric == "calmar_ratio":
                    score = getattr(result.metrics, "calmar_ratio", -999)
                elif optimize_metric == "profit_factor":
                    score = getattr(result.metrics, "profit_factor", 0)
                else:
                    score = getattr(result.metrics, optimize_metric, -999)

                # Handle NaN scores
                if np.isnan(score) or np.isinf(score):
                    score = -999

                all_results.append(
                    {
                        "params": {
                            "rsi_period": rsi_period,
                            "overbought": overbought,
                            "oversold": oversold,
                            "stop_loss": sl,
                            "take_profit": tp,
                            "htf_filter_type": filter_type,
                            "htf_filter_period": filter_period,
                        },
                        "score": score,
                        "metrics": metrics_dict,
                        "trades": getattr(result.metrics, "total_trades", 0),
                    }
                )

            except Exception as e:
                logger.warning(f"Backtest failed for params {params}: {e}")
                continue

            # Progress update
            if self.verbose and tested % 100 == 0:
                elapsed = time.perf_counter() - start_time
                speed = tested / elapsed if elapsed > 0 else 0
                logger.info(
                    f"  Progress: {tested}/{total_combinations} ({speed:.1f} comb/s)"
                )

        # Sort by score
        all_results.sort(key=lambda x: x["score"], reverse=True)
        top_results = all_results[:top_k]

        elapsed = time.perf_counter() - start_time

        best = (
            top_results[0]
            if top_results
            else {"params": {}, "score": -999, "metrics": {}}
        )

        if self.verbose:
            logger.info(
                f"✅ MTF Optimization complete: {tested} tested in {elapsed:.2f}s"
            )
            logger.info(f"   Best score ({optimize_metric}): {best['score']:.4f}")
            logger.info(f"   Best params: {best['params']}")

        return MTFOptimizationResult(
            status="completed",
            total_combinations=total_combinations,
            tested_combinations=tested,
            execution_time_seconds=elapsed,
            best_params=best["params"],
            best_score=best["score"],
            best_metrics=best["metrics"],
            top_results=top_results,
            performance_stats={
                "combinations_per_second": tested / elapsed if elapsed > 0 else 0,
            },
            mtf_params_tested={
                "htf_filter_types": htf_filter_types,
                "htf_filter_periods": htf_filter_periods,
            },
        )


def optimize_mtf(
    ltf_candles: pd.DataFrame,
    htf_candles: pd.DataFrame,
    htf_index_map: np.ndarray,
    **kwargs,
) -> MTFOptimizationResult:
    """
    Convenience function for MTF optimization.

    Args:
        ltf_candles: Lower timeframe OHLCV data
        htf_candles: Higher timeframe OHLCV data
        htf_index_map: LTF → HTF index mapping
        **kwargs: Additional parameters for MTFOptimizer.optimize()

    Returns:
        MTFOptimizationResult
    """
    optimizer = MTFOptimizer()
    return optimizer.optimize(ltf_candles, htf_candles, htf_index_map, **kwargs)
