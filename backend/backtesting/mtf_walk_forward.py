"""
MTF Walk-Forward Analysis

Implements rolling walk-forward optimization and testing
to validate MTF strategy robustness on out-of-sample data.
"""

import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from loguru import logger

from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.interfaces import BacktestInput
from backend.backtesting.mtf.signals import generate_mtf_rsi_signals
from backend.backtesting.mtf_optimizer import MTFOptimizer


@dataclass
class WalkForwardWindow:
    """Single walk-forward window result."""

    window_id: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str

    # Optimization results
    best_params: dict[str, Any] = field(default_factory=dict)
    train_score: float = 0.0
    train_trades: int = 0

    # Out-of-sample results
    oos_return: float = 0.0
    oos_sharpe: float = 0.0
    oos_max_dd: float = 0.0
    oos_trades: int = 0
    oos_win_rate: float = 0.0


@dataclass
class WalkForwardResult:
    """Complete walk-forward analysis result."""

    status: str
    total_windows: int
    completed_windows: int
    execution_time_seconds: float

    # Aggregated OOS metrics
    avg_oos_return: float = 0.0
    total_oos_return: float = 0.0
    avg_oos_sharpe: float = 0.0
    avg_oos_win_rate: float = 0.0
    avg_oos_trades: int = 0

    # Stability metrics
    oos_return_std: float = 0.0
    profitable_windows: int = 0
    profitable_pct: float = 0.0

    # Details
    windows: list[WalkForwardWindow] = field(default_factory=list)

    # Performance
    performance_stats: dict[str, Any] = field(default_factory=dict)


class MTFWalkForward:
    """
    Multi-Timeframe Walk-Forward Analyzer.

    Performs rolling walk-forward optimization:
    1. Split data into windows (train/test pairs)
    2. Optimize on each training window
    3. Test best params on out-of-sample window
    4. Aggregate results to assess robustness
    """

    def __init__(self, verbose: bool = True):
        """Initialize walk-forward analyzer."""
        self.verbose = verbose
        self.optimizer = MTFOptimizer(verbose=False)

    def analyze(
        self,
        ltf_candles: pd.DataFrame,
        htf_candles: pd.DataFrame,
        htf_index_map: np.ndarray,
        # Window configuration
        train_pct: float = 0.7,  # 70% train, 30% test
        n_windows: int = 5,  # Number of walk-forward windows
        overlap_pct: float = 0.5,  # Window overlap (anchored = 0)
        # Optimization params
        rsi_period_range: list[int] = None,
        rsi_overbought_range: list[int] = None,
        rsi_oversold_range: list[int] = None,
        stop_loss_range: list[float] = None,
        take_profit_range: list[float] = None,
        htf_filter_types: list[str] = None,
        htf_filter_periods: list[int] = None,
        # Trading config
        initial_capital: float = 10000,
        leverage: int = 10,
        direction: str = "both",
        optimize_metric: str = "sharpe_ratio",
    ) -> WalkForwardResult:
        """
        Run walk-forward analysis.

        Args:
            ltf_candles: LTF OHLCV data
            htf_candles: HTF OHLCV data
            htf_index_map: LTF->HTF index mapping
            train_pct: Training window percentage (0.6-0.8)
            n_windows: Number of rolling windows
            overlap_pct: Window overlap (0 = anchored, 0.5 = 50% overlap)
            ... (same as MTFOptimizer)

        Returns:
            WalkForwardResult with aggregated metrics
        """
        start_time = time.perf_counter()

        # Defaults
        rsi_period_range = rsi_period_range or [14, 21]
        rsi_overbought_range = rsi_overbought_range or [70, 75]
        rsi_oversold_range = rsi_oversold_range or [25, 30]
        stop_loss_range = stop_loss_range or [0.02, 0.03]
        take_profit_range = take_profit_range or [0.03, 0.05]
        htf_filter_types = htf_filter_types or ["sma", "ema"]
        htf_filter_periods = htf_filter_periods or [50, 200]

        n_ltf = len(ltf_candles)
        n_htf = len(htf_candles)

        if self.verbose:
            logger.info(f"🔄 Walk-Forward Analysis: {n_windows} windows")
            logger.info(f"   Data: {n_ltf} LTF bars, {n_htf} HTF bars")
            logger.info(
                f"   Train/Test split: {train_pct * 100:.0f}% / {(1 - train_pct) * 100:.0f}%"
            )

        # Create windows
        windows = self._create_windows(n_ltf, train_pct, n_windows, overlap_pct)

        if self.verbose:
            logger.info(f"   Created {len(windows)} windows")

        # Process each window
        results = []
        for i, (train_start, train_end, test_start, test_end) in enumerate(windows):
            if self.verbose:
                logger.info(f"\n📊 Window {i + 1}/{len(windows)}")
                logger.info(f"   Train: bars {train_start}-{train_end}")
                logger.info(f"   Test:  bars {test_start}-{test_end}")

            # Extract training data
            train_ltf = (
                ltf_candles.iloc[train_start : train_end + 1]
                .copy()
                .reset_index(drop=True)
            )

            # Get HTF indices for train window
            # Find first valid HTF index (skip -1 values)
            train_htf_start = htf_index_map[train_start]
            if train_htf_start < 0:
                # Find first valid index in window
                for j in range(train_start, train_end + 1):
                    if htf_index_map[j] >= 0:
                        train_htf_start = htf_index_map[j]
                        break
                else:
                    train_htf_start = 0  # Fallback to start

            train_htf_end = htf_index_map[min(train_end, len(htf_index_map) - 1)]
            if train_htf_end < 0:
                train_htf_end = len(htf_candles) - 1

            # Ensure we have enough HTF data
            if train_htf_end <= train_htf_start:
                train_htf_end = min(train_htf_start + 100, len(htf_candles) - 1)

            train_htf = (
                htf_candles.iloc[train_htf_start : train_htf_end + 1]
                .copy()
                .reset_index(drop=True)
            )

            if self.verbose:
                logger.debug(
                    f"   Train HTF: {train_htf_start}-{train_htf_end} ({len(train_htf)} bars)"
                )

            # Create training index map
            train_htf_map = self._create_subset_map(
                htf_index_map, train_start, train_end, train_htf_start
            )

            if len(train_ltf) < 200 or len(train_htf) < 50:
                if self.verbose:
                    logger.warning(
                        f"   ⚠️ Window too small (LTF={len(train_ltf)}, HTF={len(train_htf)}), skipping"
                    )
                continue

            # Optimize on training data
            opt_result = self.optimizer.optimize(
                ltf_candles=train_ltf,
                htf_candles=train_htf,
                htf_index_map=train_htf_map,
                rsi_period_range=rsi_period_range,
                rsi_overbought_range=rsi_overbought_range,
                rsi_oversold_range=rsi_oversold_range,
                stop_loss_range=stop_loss_range,
                take_profit_range=take_profit_range,
                htf_filter_types=htf_filter_types,
                htf_filter_periods=htf_filter_periods,
                initial_capital=initial_capital,
                leverage=leverage,
                direction=direction,
                optimize_metric=optimize_metric,
                top_k=1,
            )

            best_params = opt_result.best_params

            if not best_params:
                if self.verbose:
                    logger.warning("   ⚠️ No valid params found, skipping")
                continue

            if self.verbose:
                logger.info(f"   🏆 Best: {best_params}")
                logger.info(f"      Train score: {opt_result.best_score:.4f}")

            # Test on OOS data
            test_ltf = (
                ltf_candles.iloc[test_start : test_end + 1]
                .copy()
                .reset_index(drop=True)
            )

            # Get HTF indices for test window
            # Get HTF indices for test window (skip -1 values)
            test_htf_start = htf_index_map[test_start]
            if test_htf_start < 0:
                for j in range(test_start, test_end + 1):
                    if htf_index_map[j] >= 0:
                        test_htf_start = htf_index_map[j]
                        break
                else:
                    test_htf_start = 0

            test_htf_end = htf_index_map[min(test_end, len(htf_index_map) - 1)]
            if test_htf_end < 0:
                test_htf_end = len(htf_candles) - 1

            # Ensure we have enough HTF data
            if test_htf_end <= test_htf_start:
                test_htf_end = min(test_htf_start + 50, len(htf_candles) - 1)

            test_htf = (
                htf_candles.iloc[test_htf_start : test_htf_end + 1]
                .copy()
                .reset_index(drop=True)
            )

            if self.verbose:
                logger.debug(
                    f"   Test HTF: {test_htf_start}-{test_htf_end} ({len(test_htf)} bars)"
                )

            # Create test index map
            test_htf_map = self._create_subset_map(
                htf_index_map, test_start, test_end, test_htf_start
            )

            if len(test_ltf) < 50 or len(test_htf) < 10:
                if self.verbose:
                    logger.warning(
                        f"   ⚠️ Test window too small (LTF={len(test_ltf)}, HTF={len(test_htf)}), skipping"
                    )
                continue

            # Run OOS backtest with best params
            oos_metrics = self._run_oos_test(
                test_ltf,
                test_htf,
                test_htf_map,
                best_params,
                initial_capital,
                leverage,
                direction,
            )

            if self.verbose:
                logger.info(
                    f"   📈 OOS: return={oos_metrics['total_return']:.2f}%, "
                    f"sharpe={oos_metrics['sharpe_ratio']:.2f}, "
                    f"trades={oos_metrics['total_trades']}"
                )

            # Record window result
            window_result = WalkForwardWindow(
                window_id=i + 1,
                train_start=str(
                    ltf_candles.iloc[train_start].get("open_time", train_start)
                ),
                train_end=str(ltf_candles.iloc[train_end].get("open_time", train_end)),
                test_start=str(
                    ltf_candles.iloc[test_start].get("open_time", test_start)
                ),
                test_end=str(ltf_candles.iloc[test_end].get("open_time", test_end)),
                best_params=best_params,
                train_score=opt_result.best_score,
                train_trades=opt_result.best_metrics.get("total_trades", 0),
                oos_return=oos_metrics["total_return"],
                oos_sharpe=oos_metrics["sharpe_ratio"],
                oos_max_dd=oos_metrics["max_drawdown"],
                oos_trades=oos_metrics["total_trades"],
                oos_win_rate=oos_metrics["win_rate"],
            )
            results.append(window_result)

        # Aggregate results
        elapsed = time.perf_counter() - start_time

        if not results:
            return WalkForwardResult(
                status="no_valid_windows",
                total_windows=len(windows),
                completed_windows=0,
                execution_time_seconds=elapsed,
            )

        oos_returns = [w.oos_return for w in results]
        oos_sharpes = [w.oos_sharpe for w in results]
        oos_win_rates = [w.oos_win_rate for w in results]
        oos_trades = [w.oos_trades for w in results]

        profitable_windows = sum(1 for r in oos_returns if r > 0)

        result = WalkForwardResult(
            status="completed",
            total_windows=len(windows),
            completed_windows=len(results),
            execution_time_seconds=elapsed,
            avg_oos_return=np.mean(oos_returns),
            total_oos_return=np.sum(oos_returns),
            avg_oos_sharpe=np.mean(oos_sharpes),
            avg_oos_win_rate=np.mean(oos_win_rates),
            avg_oos_trades=int(np.mean(oos_trades)),
            oos_return_std=np.std(oos_returns),
            profitable_windows=profitable_windows,
            profitable_pct=profitable_windows / len(results) * 100 if results else 0,
            windows=results,
            performance_stats={
                "windows_per_second": len(results) / elapsed if elapsed > 0 else 0,
            },
        )

        if self.verbose:
            logger.info(
                f"\n✅ Walk-Forward complete: {len(results)} windows in {elapsed:.2f}s"
            )
            logger.info(f"   Avg OOS Return: {result.avg_oos_return:.2f}%")
            logger.info(f"   Total OOS Return: {result.total_oos_return:.2f}%")
            logger.info(f"   Avg OOS Sharpe: {result.avg_oos_sharpe:.2f}")
            logger.info(
                f"   Profitable Windows: {profitable_windows}/{len(results)} ({result.profitable_pct:.0f}%)"
            )

        return result

    def _create_windows(
        self, n_bars: int, train_pct: float, n_windows: int, overlap_pct: float
    ) -> list[tuple[int, int, int, int]]:
        """Create rolling walk-forward windows."""
        windows = []

        # Calculate window size
        window_size = n_bars // n_windows
        train_size = int(window_size * train_pct)
        test_size = window_size - train_size

        # Ensure minimum sizes
        train_size = max(train_size, 200)
        test_size = max(test_size, 50)

        # Calculate step size based on overlap
        step_size = int(window_size * (1 - overlap_pct))
        step_size = max(step_size, test_size)  # At least test_size step

        start = 0
        while start + train_size + test_size <= n_bars:
            train_start = start
            train_end = start + train_size - 1
            test_start = train_end + 1
            test_end = min(test_start + test_size - 1, n_bars - 1)

            windows.append((train_start, train_end, test_start, test_end))

            start += step_size

            if len(windows) >= n_windows:
                break

        return windows

    def _create_subset_map(
        self, full_map: np.ndarray, start: int, end: int, htf_offset: int
    ) -> np.ndarray:
        """Create index map for data subset."""
        subset_len = end - start + 1
        subset_map = np.zeros(subset_len, dtype=np.int32)

        for i in range(subset_len):
            orig_idx = start + i
            if orig_idx < len(full_map):
                htf_idx = full_map[orig_idx] - htf_offset
                subset_map[i] = max(0, htf_idx)
            else:
                subset_map[i] = subset_map[i - 1] if i > 0 else 0

        return subset_map

    def _run_oos_test(
        self,
        ltf_candles: pd.DataFrame,
        htf_candles: pd.DataFrame,
        htf_index_map: np.ndarray,
        params: dict[str, Any],
        initial_capital: float,
        leverage: int,
        direction: str,
    ) -> dict[str, float]:
        """Run out-of-sample test with given params."""
        try:
            # Generate signals with best params
            long_signals, long_exits, short_signals, short_exits = (
                generate_mtf_rsi_signals(
                    ltf_candles=ltf_candles,
                    htf_candles=htf_candles,
                    htf_index_map=htf_index_map,
                    htf_filter_type=params.get("htf_filter_type", "sma"),
                    htf_filter_period=params.get("htf_filter_period", 200),
                    direction=direction,
                    rsi_period=params.get("rsi_period", 14),
                    overbought=params.get("overbought", 70),
                    oversold=params.get("oversold", 30),
                )
            )

            # Run backtest
            bt_input = BacktestInput(
                candles=ltf_candles,
                long_entries=long_signals,
                long_exits=long_exits,
                short_entries=short_signals,
                short_exits=short_exits,
                initial_capital=initial_capital,
                leverage=leverage,
                stop_loss=params.get("stop_loss", 0.02),
                take_profit=params.get("take_profit", 0.03),
                direction=direction,
            )

            engine = FallbackEngineV4()
            result = engine.run(bt_input)

            return {
                "total_return": getattr(result.metrics, "total_return", 0),
                "sharpe_ratio": getattr(result.metrics, "sharpe_ratio", 0),
                "max_drawdown": getattr(result.metrics, "max_drawdown", 0),
                "total_trades": getattr(result.metrics, "total_trades", 0),
                "win_rate": getattr(result.metrics, "win_rate", 0),
            }

        except Exception as e:
            logger.warning(f"OOS test failed: {e}")
            return {
                "total_return": 0,
                "sharpe_ratio": 0,
                "max_drawdown": 0,
                "total_trades": 0,
                "win_rate": 0,
            }


# Convenience function
def run_mtf_walk_forward(
    ltf_candles: pd.DataFrame,
    htf_candles: pd.DataFrame,
    htf_index_map: np.ndarray,
    n_windows: int = 5,
    **kwargs,
) -> WalkForwardResult:
    """
    Run MTF walk-forward analysis.

    Example:
        result = run_mtf_walk_forward(ltf, htf, index_map, n_windows=5)
        print(f"Avg OOS Return: {result.avg_oos_return:.2f}%")
        print(f"Profitable Windows: {result.profitable_pct:.0f}%")
    """
    analyzer = MTFWalkForward(verbose=True)
    return analyzer.analyze(
        ltf_candles=ltf_candles,
        htf_candles=htf_candles,
        htf_index_map=htf_index_map,
        n_windows=n_windows,
        **kwargs,
    )
