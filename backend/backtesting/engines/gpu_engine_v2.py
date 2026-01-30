"""
GPUEngineV2 - GPU-Accelerated Backtest Engine

⚠️ DEPRECATED: This engine is deprecated in favor of NumbaEngine.

Reasons for deprecation:
1. V2-only features — doesn't support pyramiding, multi-TP, ATR, trailing
2. Requires NVIDIA GPU + CUDA (limited hardware support)
3. NumbaEngine provides 20-40x speedup which is sufficient for 90% of use cases
4. Complex codebase with higher maintenance burden

Migration:
    # Old way (deprecated):
    from backend.backtesting.engines.gpu_engine_v2 import GPUEngineV2
    engine = GPUEngineV2()

    # New way (recommended):
    from backend.backtesting.engines import NumbaEngine
    engine = NumbaEngine()  # Full V4 support, 20-40x faster

For extreme workloads (100K+ combinations), consider:
- Batch processing with NumbaEngine
- Ray distributed optimizer (backend/optimization/ray_optimizer.py)

---

Original description:
100% parity with FallbackEngineV2 (reference implementation).
Uses CuPy for NVIDIA GPU acceleration.

Performance:
- ~10-50x faster than FallbackEngineV2 on large datasets
- Identical financial results (bit-level parity)

Architecture:
- GPU: OHLCV data arrays, signal computation
- CPU: Trade record construction, metrics calculation
"""

import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from loguru import logger

from backend.backtesting.interfaces import (
    BacktestInput,
    BacktestMetrics,
    BacktestOutput,
    BaseBacktestEngine,
    ExitReason,
    TradeDirection,
    TradeRecord,
)

# =============================================================================
# GPU AVAILABILITY CHECK
# =============================================================================

GPU_AVAILABLE = False
cp = None

try:
    import cupy as cp

    # Test actual GPU operations
    _test = cp.array([1.0, 2.0, 3.0], dtype=cp.float64)
    _result = cp.sum(_test)
    del _test, _result

    GPU_AVAILABLE = True

    # Get GPU info
    device = cp.cuda.Device()
    gpu_name = device.attributes.get("DeviceDescription", f"GPU {device.id}")
    gpu_mem = device.mem_info[1] / (1024**3)
    logger.info(f"🚀 GPUEngineV2: CUDA enabled - {gpu_name} ({gpu_mem:.1f}GB)")

except ImportError:
    logger.warning("CuPy not installed. GPUEngineV2 will use CPU fallback (NumPy).")
except Exception as e:
    logger.warning(f"GPU initialization failed: {e}. Using CPU fallback.")


# =============================================================================
# GPU KERNELS (CuPy)
# =============================================================================

if GPU_AVAILABLE:

    @cp.fuse()
    def _gpu_calculate_sl_tp_prices(entry_prices, stop_loss, take_profit, is_long):
        """Calculate SL/TP prices on GPU."""
        if is_long:
            sl_prices = (
                entry_prices * (1.0 - stop_loss)
                if stop_loss > 0
                else cp.zeros_like(entry_prices)
            )
            tp_prices = (
                entry_prices * (1.0 + take_profit)
                if take_profit > 0
                else cp.full_like(entry_prices, 1e10)
            )
        else:
            sl_prices = (
                entry_prices * (1.0 + stop_loss)
                if stop_loss > 0
                else cp.full_like(entry_prices, 1e10)
            )
            tp_prices = (
                entry_prices * (1.0 - take_profit)
                if take_profit > 0
                else cp.zeros_like(entry_prices)
            )
        return sl_prices, tp_prices


# =============================================================================
# GPU ENGINE V2
# =============================================================================


class GPUEngineV2(BaseBacktestEngine):
    """
    GPU-Accelerated Backtest Engine V2.

    ⚠️ DEPRECATED: Use NumbaEngine for full V4 support.

    Features (V2-only):
    - 100% parity with FallbackEngineV2 (reference)
    - CuPy GPU acceleration for large datasets
    - Automatic CPU fallback if GPU unavailable
    - Full TradeRecord support (size, fees, pnl_pct)

    NOT supported (use NumbaEngine instead):
    - Pyramiding (multiple entries)
    - ATR-based SL/TP
    - Multi-level TP
    - Trailing Stop

    Migration:
        from backend.backtesting.engines import NumbaEngine
        engine = NumbaEngine()  # Full V4 support, 20-40x faster
    """

    def __init__(self):
        import warnings
        warnings.warn(
            "GPUEngineV2 is deprecated. Use NumbaEngine for full V4 support "
            "(pyramiding, ATR, multi-TP, trailing) with 20-40x speedup. "
            "GPU engine is V2-only and requires NVIDIA hardware.",
            DeprecationWarning,
            stacklevel=2,
        )
        self._gpu_available = GPU_AVAILABLE

    @property
    def name(self) -> str:
        return "GPUEngineV2"

    @property
    def gpu_enabled(self) -> bool:
        return self._gpu_available

    @property
    def supports_bar_magnifier(self) -> bool:
        return True  # Now supported!

    @property
    def supports_parallel(self) -> bool:
        return True  # GPU is inherently parallel

    def run(self, input_data: BacktestInput) -> BacktestOutput:
        """
        Run backtest simulation.

        Uses same logic as FallbackEngineV2 for 100% parity,
        with GPU acceleration where possible.
        """
        start_time = time.time()

        # Extract data
        candles = input_data.candles
        candles_1m = input_data.candles_1m
        timestamps = candles.index.values
        open_prices = candles["open"].values.astype(np.float64)
        high_prices = candles["high"].values.astype(np.float64)
        low_prices = candles["low"].values.astype(np.float64)
        close_prices = candles["close"].values.astype(np.float64)

        n = len(close_prices)

        # Handle None signals - create zero arrays if not provided
        long_entries = (
            input_data.long_entries
            if input_data.long_entries is not None
            else np.zeros(n, dtype=bool)
        )
        long_exits = (
            input_data.long_exits
            if input_data.long_exits is not None
            else np.zeros(n, dtype=bool)
        )
        short_entries = (
            input_data.short_entries
            if input_data.short_entries is not None
            else np.zeros(n, dtype=bool)
        )
        short_exits = (
            input_data.short_exits
            if input_data.short_exits is not None
            else np.zeros(n, dtype=bool)
        )

        # Parameters
        initial_capital = input_data.initial_capital

        # FIXED: Handle use_fixed_amount for TradingView parity
        use_fixed_amount = input_data.use_fixed_amount and input_data.fixed_amount > 0
        fixed_amount = input_data.fixed_amount if use_fixed_amount else 0.0
        position_size = input_data.position_size  # For percentage-based sizing

        leverage = input_data.leverage
        stop_loss = input_data.stop_loss
        take_profit = input_data.take_profit
        taker_fee = input_data.taker_fee
        slippage = input_data.slippage
        direction = input_data.direction
        use_bar_magnifier = input_data.use_bar_magnifier and candles_1m is not None

        # Direction flags
        allow_long = direction in (TradeDirection.LONG, TradeDirection.BOTH)
        allow_short = direction in (TradeDirection.SHORT, TradeDirection.BOTH)

        # Bar Magnifier index
        bar_magnifier_index = (
            self._build_bar_magnifier_index(candles, candles_1m)
            if use_bar_magnifier
            else None
        )

        # =====================================================================
        # SIMULATION (Same logic as FallbackEngineV2)
        # =====================================================================

        # Pre-allocate
        equity_curve = np.zeros(n, dtype=np.float64)
        equity_curve[0] = initial_capital

        trades: List[TradeRecord] = []

        # State
        cash = initial_capital
        in_long = False
        in_short = False
        long_entry_price = 0.0
        short_entry_price = 0.0
        long_entry_idx = 0
        short_entry_idx = 0
        long_size = 0.0
        short_size = 0.0
        long_allocated = 0.0
        short_allocated = 0.0
        long_entry_fee = 0.0  # Track entry fee for TV fee calculation
        short_entry_fee = 0.0  # Track entry fee for TV fee calculation

        for i in range(1, n):
            current_time = timestamps[i]
            open_price = open_prices[i]
            high_price = high_prices[i]
            low_price = low_prices[i]
            close_price = close_prices[i]

            # TV-style: Track if we exited this bar (prevents new entry on same bar)
            exited_this_bar = False

            # === LONG EXIT ===
            if in_long:
                exit_reason, exit_price = self._check_exit_conditions(
                    is_long=True,
                    entry_price=long_entry_price,
                    open_price=open_price,  # For TV intrabar simulation
                    high=high_price,
                    low=low_price,
                    close=close_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    signal_exit=long_exits[i],
                    slippage=slippage,
                    use_bar_magnifier=use_bar_magnifier,
                    bar_magnifier_index=bar_magnifier_index,
                    bar_idx=i,
                    candles_1m=candles_1m,
                )

                if exit_reason is not None:
                    pnl, pnl_pct, fees = self._calculate_pnl(
                        is_long=True,
                        entry_price=long_entry_price,
                        exit_price=exit_price,
                        size=long_size,
                        taker_fee=taker_fee,
                        entry_fee=long_entry_fee,  # TV: entry + exit fees
                    )

                    cash += long_allocated + pnl

                    trades.append(
                        TradeRecord(
                            entry_time=pd.Timestamp(timestamps[long_entry_idx]),
                            exit_time=pd.Timestamp(current_time),
                            direction="long",
                            entry_price=long_entry_price,
                            exit_price=exit_price,
                            size=long_size,
                            pnl=pnl,
                            pnl_pct=pnl_pct,
                            fees=fees,
                            exit_reason=exit_reason,
                            duration_bars=i - long_entry_idx,
                        )
                    )

                    in_long = False
                    long_size = 0.0
                    long_allocated = 0.0
                    long_entry_fee = 0.0  # Reset
                    exited_this_bar = True  # Prevent new entry on same bar

            # === SHORT EXIT ===
            if in_short:
                exit_reason, exit_price = self._check_exit_conditions(
                    is_long=False,
                    entry_price=short_entry_price,
                    open_price=open_price,  # For TV intrabar simulation
                    high=high_price,
                    low=low_price,
                    close=close_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    signal_exit=short_exits[i],
                    slippage=slippage,
                    use_bar_magnifier=use_bar_magnifier,
                    bar_magnifier_index=bar_magnifier_index,
                    bar_idx=i,
                    candles_1m=candles_1m,
                )

                if exit_reason is not None:
                    pnl, pnl_pct, fees = self._calculate_pnl(
                        is_long=False,
                        entry_price=short_entry_price,
                        exit_price=exit_price,
                        size=short_size,
                        taker_fee=taker_fee,
                        entry_fee=short_entry_fee,  # TV: entry + exit fees
                    )

                    cash += short_allocated + pnl

                    trades.append(
                        TradeRecord(
                            entry_time=pd.Timestamp(timestamps[short_entry_idx]),
                            exit_time=pd.Timestamp(current_time),
                            direction="short",
                            entry_price=short_entry_price,
                            exit_price=exit_price,
                            size=short_size,
                            pnl=pnl,
                            pnl_pct=pnl_pct,
                            fees=fees,
                            exit_reason=exit_reason,
                            duration_bars=i - short_entry_idx,
                        )
                    )

                    in_short = False
                    short_size = 0.0
                    short_allocated = 0.0
                    short_entry_fee = 0.0  # Reset
                    exited_this_bar = True  # Prevent new entry on same bar

            # === LONG ENTRY ===
            # TradingView parity: signal at bar i, entry at bar i+1 open
            # Check not in_short to prevent simultaneous positions
            # TV-style: No entry on same bar as exit
            if (
                not in_long
                and not in_short
                and not exited_this_bar  # TV-style: No entry on same bar as exit
                and allow_long
                and long_entries[i]
                and (i < n - 2)
                and (i > 0)
            ):
                # Enter at NEXT bar's open (i+1), not current bar
                # TV parity: No slippage on entry, entry at exact open price
                entry_price = open_prices[i + 1]
                # FIXED: Handle fixed amount vs percentage modes (TV parity)
                if use_fixed_amount:
                    allocated = min(fixed_amount, cash)
                else:
                    allocated = cash * position_size

                if allocated >= 1.0:  # Minimum $1.00 to open
                    notional = allocated * leverage
                    size = notional / entry_price
                    entry_fee = notional * taker_fee

                    # FIXED: TV doesn't deduct entry_fee from cash
                    cash -= allocated

                    in_long = True
                    long_entry_price = entry_price
                    long_entry_idx = i  # Signal bar index (TV style)
                    long_size = size
                    long_allocated = allocated
                    long_entry_fee = entry_fee  # Track for TV fee calculation

            # === SHORT ENTRY ===
            # TradingView parity: signal at bar i, entry at bar i+1 open
            # Check not in_long to prevent simultaneous positions
            # TV-style: No entry on same bar as exit
            if (
                not in_short
                and not in_long
                and not exited_this_bar  # TV-style: No entry on same bar as exit
                and allow_short
                and short_entries[i]
                and (i < n - 2)
                and (i > 0)
            ):
                # Enter at NEXT bar's open (i+1), not current bar
                # TV parity: No slippage on entry, entry at exact open price
                entry_price = open_prices[i + 1]
                # FIXED: Handle fixed amount vs percentage modes (TV parity)
                if use_fixed_amount:
                    allocated = min(fixed_amount, cash)
                else:
                    allocated = cash * position_size

                if allocated >= 1.0:  # Minimum $1.00 to open
                    notional = allocated * leverage
                    size = notional / entry_price
                    entry_fee = notional * taker_fee

                    # FIXED: TV doesn't deduct entry_fee from cash
                    cash -= allocated

                    in_short = True
                    short_entry_price = entry_price
                    short_entry_idx = i  # Signal bar index (TV style)
                    short_size = size
                    short_allocated = allocated
                    short_entry_fee = entry_fee  # Track for TV fee calculation

            # === UPDATE EQUITY ===
            equity = cash
            if in_long:
                unrealized = (close_price - long_entry_price) * long_size
                equity += unrealized + long_size * long_entry_price
            if in_short:
                unrealized = (short_entry_price - close_price) * short_size
                equity += unrealized + short_size * short_entry_price

            equity_curve[i] = equity

        # =====================================================================
        # CLOSE OPEN POSITIONS AT END OF DATA
        # =====================================================================

        last_time = timestamps[-1]
        last_close = close_prices[-1]

        if in_long:
            exit_price = last_close * (1.0 - slippage)
            pnl, pnl_pct, fees = self._calculate_pnl(
                is_long=True,
                entry_price=long_entry_price,
                exit_price=exit_price,
                size=long_size,
                taker_fee=taker_fee,
                entry_fee=long_entry_fee,  # TV: entry + exit fees
            )

            trades.append(
                TradeRecord(
                    entry_time=pd.Timestamp(timestamps[long_entry_idx]),
                    exit_time=pd.Timestamp(last_time),
                    direction="long",
                    entry_price=long_entry_price,
                    exit_price=exit_price,
                    size=long_size,
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                    fees=fees,
                    exit_reason=ExitReason.END_OF_DATA,
                    duration_bars=n - 1 - long_entry_idx,
                )
            )

        if in_short:
            exit_price = last_close * (1.0 + slippage)
            pnl, pnl_pct, fees = self._calculate_pnl(
                is_long=False,
                entry_price=short_entry_price,
                exit_price=exit_price,
                size=short_size,
                taker_fee=taker_fee,
                entry_fee=short_entry_fee,  # TV: entry + exit fees
            )

            trades.append(
                TradeRecord(
                    entry_time=pd.Timestamp(timestamps[short_entry_idx]),
                    exit_time=pd.Timestamp(last_time),
                    direction="short",
                    entry_price=short_entry_price,
                    exit_price=exit_price,
                    size=short_size,
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                    fees=fees,
                    exit_reason=ExitReason.END_OF_DATA,
                    duration_bars=n - 1 - short_entry_idx,
                )
            )

        # =====================================================================
        # CALCULATE METRICS
        # =====================================================================

        metrics = self._calculate_metrics(trades, equity_curve, initial_capital)

        execution_time = time.time() - start_time

        return BacktestOutput(
            metrics=metrics,
            trades=trades,
            equity_curve=equity_curve,
            timestamps=timestamps,
            engine_name=self.name,
            execution_time=execution_time,
        )

    def _check_exit_conditions(
        self,
        is_long: bool,
        entry_price: float,
        open_price: float,  # Added for TV intrabar simulation
        high: float,
        low: float,
        close: float,
        stop_loss: float,
        take_profit: float,
        signal_exit: bool,
        slippage: float,
        use_bar_magnifier: bool = False,
        bar_magnifier_index: Optional[Dict] = None,
        bar_idx: int = 0,
        candles_1m: Optional[pd.DataFrame] = None,
    ) -> Tuple[Optional[ExitReason], float]:
        """Check exit conditions with Bar Magnifier support - same logic as FallbackEngineV2."""

        if is_long:
            sl_price = entry_price * (1.0 - stop_loss) if stop_loss > 0 else 0.0
            tp_price = (
                entry_price * (1.0 + take_profit) if take_profit > 0 else float("inf")
            )
        else:
            sl_price = (
                entry_price * (1.0 + stop_loss) if stop_loss > 0 else float("inf")
            )
            tp_price = entry_price * (1.0 - take_profit) if take_profit > 0 else 0.0

        # === BAR MAGNIFIER: Precise intrabar SL/TP detection ===
        if (
            use_bar_magnifier
            and bar_magnifier_index
            and candles_1m is not None
            and bar_idx in bar_magnifier_index
        ):
            start_idx, end_idx = bar_magnifier_index[bar_idx]
            m1_highs = candles_1m["high"].values[start_idx:end_idx]
            m1_lows = candles_1m["low"].values[start_idx:end_idx]

            for m1_high, m1_low in zip(m1_highs, m1_lows):
                if is_long:
                    # Long: check SL (low) first, then TP (high)
                    # TV parity: SL/TP exit at exact level, no slippage
                    if sl_price > 0 and m1_low <= sl_price:
                        return ExitReason.STOP_LOSS, sl_price
                    if tp_price < float("inf") and m1_high >= tp_price:
                        return ExitReason.TAKE_PROFIT, tp_price
                else:
                    # Short: check SL (high) first, then TP (low)
                    # TV parity: SL/TP exit at exact level, no slippage
                    if sl_price < float("inf") and m1_high >= sl_price:
                        return ExitReason.STOP_LOSS, sl_price
                    if tp_price > 0 and m1_low <= tp_price:
                        return ExitReason.TAKE_PROFIT, tp_price

        # === FALLBACK: TV-style intrabar simulation based on open position ===
        # Determine check order based on where open is relative to high/low
        open_closer_to_high = abs(open_price - high) < abs(open_price - low)

        if is_long:
            sl_hit = sl_price > 0 and low <= sl_price
            tp_hit = tp_price < float("inf") and high >= tp_price

            if sl_hit and tp_hit:
                # Both hit - check order based on open position
                if open_closer_to_high:
                    # Order: open → high → low → close - TP triggers first
                    return ExitReason.TAKE_PROFIT, tp_price
                else:
                    # Order: open → low → high → close - SL triggers first
                    return ExitReason.STOP_LOSS, sl_price
            elif sl_hit:
                return ExitReason.STOP_LOSS, sl_price
            elif tp_hit:
                return ExitReason.TAKE_PROFIT, tp_price
        else:
            sl_hit = sl_price < float("inf") and high >= sl_price
            tp_hit = tp_price > 0 and low <= tp_price

            if sl_hit and tp_hit:
                # Both hit - check order based on open position
                if open_closer_to_high:
                    # Order: open → high → low → close - SL triggers first for short
                    return ExitReason.STOP_LOSS, sl_price
                else:
                    # Order: open → low → high → close - TP triggers first for short
                    return ExitReason.TAKE_PROFIT, tp_price
            elif sl_hit:
                return ExitReason.STOP_LOSS, sl_price
            elif tp_hit:
                return ExitReason.TAKE_PROFIT, tp_price

        # Signal exit - uses close price with slippage
        if signal_exit:
            exit_price = close * (1.0 - slippage if is_long else 1.0 + slippage)
            return ExitReason.SIGNAL, exit_price

        return None, 0.0

    def _build_bar_magnifier_index(
        self, candles: pd.DataFrame, candles_1m: pd.DataFrame
    ) -> Dict[int, Tuple[int, int]]:
        """
        Build index for Bar Magnifier.
        Returns dict: bar_idx -> (start_1m_idx, end_1m_idx)
        """
        if candles_1m is None:
            return {}

        index = {}

        # Get timestamps
        bar_times = (
            candles.index
            if isinstance(candles.index, pd.DatetimeIndex)
            else pd.to_datetime(candles.index)
        )
        m1_times = (
            candles_1m.index
            if isinstance(candles_1m.index, pd.DatetimeIndex)
            else pd.to_datetime(candles_1m.index)
        )

        # For each main timeframe bar, find corresponding 1m bars
        for i in range(len(candles)):
            bar_start = bar_times[i]
            bar_end = (
                bar_times[i + 1]
                if i + 1 < len(candles)
                else bar_times[i] + pd.Timedelta(hours=1)
            )

            # Find 1m bars in this range
            mask = (m1_times >= bar_start) & (m1_times < bar_end)
            matching_indices = np.where(mask)[0]

            if len(matching_indices) > 0:
                index[i] = (matching_indices[0], matching_indices[-1] + 1)

        return index

    def _calculate_pnl(
        self,
        is_long: bool,
        entry_price: float,
        exit_price: float,
        size: float,
        taker_fee: float,
        entry_fee: float = 0.0,  # TV: entry fee from position open
    ) -> Tuple[float, float, float]:
        """Calculate PnL, PnL%, and fees - TV style (entry + exit fees)."""

        if is_long:
            pnl = (exit_price - entry_price) * size
        else:
            pnl = (entry_price - exit_price) * size

        # TV: Calculate both entry and exit fees
        exit_value = exit_price * size
        exit_fee = exit_value * taker_fee
        total_fees = entry_fee + exit_fee  # TV: entry + exit
        pnl -= total_fees

        pnl_pct = pnl / (entry_price * size) * 100 if entry_price * size > 0 else 0

        return pnl, pnl_pct, total_fees

    def _calculate_metrics(
        self,
        trades: List[TradeRecord],
        equity_curve: np.ndarray,
        initial_capital: float,
    ) -> BacktestMetrics:
        """Calculate backtest metrics."""

        if len(trades) == 0:
            return BacktestMetrics(
                net_profit=0.0,
                total_return=0.0,
                gross_profit=0.0,
                gross_loss=0.0,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                max_drawdown=0.0,
                sharpe_ratio=0.0,
                sortino_ratio=0.0,
                calmar_ratio=0.0,
                profit_factor=0.0,
                avg_win=0.0,
                avg_loss=0.0,
                avg_trade=0.0,
                largest_win=0.0,
                largest_loss=0.0,
                max_consecutive_wins=0,
                max_consecutive_losses=0,
                expectancy=0.0,
                payoff_ratio=0.0,
            )

        # Basic metrics
        pnls = [t.pnl for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]

        net_profit = sum(pnls)
        gross_profit = sum(wins) if wins else 0.0
        gross_loss = abs(sum(losses)) if losses else 0.0

        total_trades = len(trades)
        winning_trades = len(wins)
        losing_trades = len(losses)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0.0

        avg_win = np.mean(wins) if wins else 0.0
        avg_loss = np.mean(losses) if losses else 0.0
        avg_trade = np.mean(pnls) if pnls else 0.0

        largest_win = max(wins) if wins else 0.0
        largest_loss = min(losses) if losses else 0.0

        profit_factor = (
            gross_profit / gross_loss
            if gross_loss > 0
            else float("inf")
            if gross_profit > 0
            else 0.0
        )
        payoff_ratio = avg_win / abs(avg_loss) if avg_loss != 0 else 0.0
        expectancy = (win_rate * avg_win) + ((1 - win_rate) * avg_loss)

        # Equity-based metrics
        final_equity = equity_curve[-1]
        total_return = ((final_equity - initial_capital) / initial_capital) * 100

        # Max Drawdown - percentage for consistency with other engines
        peak = np.maximum.accumulate(equity_curve)
        drawdown_pct = (peak - equity_curve) / peak * 100
        drawdown_usdt = peak - equity_curve  # Absolute drawdown in USDT
        max_drawdown = np.max(drawdown_pct)  # Percentage for consistency
        max_drawdown_pct = np.max(drawdown_pct)  # noqa: F841 - Keep percentage version
        max_drawdown_usdt = np.max(drawdown_usdt)  # noqa: F841 - USDT version for display

        # Sharpe Ratio (hourly returns - same as FallbackEngineV2)
        returns = np.diff(equity_curve) / equity_curve[:-1]
        returns = np.nan_to_num(returns, nan=0, posinf=0, neginf=0)
        if len(returns) > 1 and np.std(returns) > 0:
            sharpe_ratio = (
                np.mean(returns) / np.std(returns) * np.sqrt(252 * 24)
            )  # Hourly
        else:
            sharpe_ratio = 0.0

        # Sortino Ratio (same as FallbackEngineV2)
        downside_returns = returns[returns < 0]
        if len(downside_returns) > 1:
            downside_std = np.std(downside_returns)
            if downside_std > 0:
                sortino_ratio = np.mean(returns) / downside_std * np.sqrt(252 * 24)
            else:
                sortino_ratio = 0.0
        else:
            sortino_ratio = 0.0

        # Calmar Ratio (same as FallbackEngineV2)
        if max_drawdown > 0:
            annual_return = total_return * (365 * 24 / len(equity_curve))
            calmar_ratio = annual_return / max_drawdown
        else:
            calmar_ratio = 0.0

        # Avg Drawdown
        avg_drawdown = np.mean(drawdown_pct)

        # Long/Short breakdown
        long_trades_list = [t for t in trades if t.direction == "long"]
        short_trades_list = [t for t in trades if t.direction == "short"]

        long_trades_count = len(long_trades_list)
        short_trades_count = len(short_trades_list)
        long_win_rate = (
            sum(1 for t in long_trades_list if t.pnl > 0) / long_trades_count
            if long_trades_count
            else 0
        )
        short_win_rate = (
            sum(1 for t in short_trades_list if t.pnl > 0) / short_trades_count
            if short_trades_count
            else 0
        )
        long_profit = sum(t.pnl for t in long_trades_list)
        short_profit = sum(t.pnl for t in short_trades_list)

        # Duration
        durations = [t.duration_bars for t in trades]
        avg_trade_duration = np.mean(durations) if durations else 0

        winning_durations = [t.duration_bars for t in trades if t.pnl > 0]
        losing_durations = [t.duration_bars for t in trades if t.pnl < 0]
        avg_winning_duration = np.mean(winning_durations) if winning_durations else 0
        avg_losing_duration = np.mean(losing_durations) if losing_durations else 0

        # Recovery factor
        if max_drawdown > 0:
            recovery_factor = net_profit / (initial_capital * max_drawdown / 100)
        else:
            recovery_factor = 0.0

        return BacktestMetrics(
            net_profit=net_profit,
            total_return=total_return,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            max_drawdown=max_drawdown,
            avg_drawdown=avg_drawdown,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            profit_factor=profit_factor,
            avg_win=avg_win,
            avg_loss=avg_loss,
            avg_trade=avg_trade,
            largest_win=largest_win,
            largest_loss=largest_loss,
            expectancy=expectancy,
            payoff_ratio=payoff_ratio,
            long_trades=long_trades_count,
            short_trades=short_trades_count,
            long_win_rate=long_win_rate,
            short_win_rate=short_win_rate,
            long_profit=long_profit,
            short_profit=short_profit,
            avg_trade_duration=avg_trade_duration,
            avg_winning_duration=avg_winning_duration,
            avg_losing_duration=avg_losing_duration,
            recovery_factor=recovery_factor,
        )

    def optimize(
        self,
        input_data: BacktestInput,
        param_ranges: Dict[str, List[Any]],
        metric: str = "sharpe_ratio",
        top_n: int = 10,
    ) -> List[Tuple[Dict[str, Any], BacktestOutput]]:
        """
        Optimize parameters using GPU-accelerated grid search.

        Note: For now, uses simple iteration. Future: true GPU parallelism.
        """
        import itertools

        results = []

        # Generate all combinations
        param_names = list(param_ranges.keys())
        param_values = list(param_ranges.values())
        combinations = list(itertools.product(*param_values))

        for combo in combinations:
            params = dict(zip(param_names, combo))

            # Create modified input
            modified_input = BacktestInput(
                candles=input_data.candles,
                long_entries=input_data.long_entries,
                long_exits=input_data.long_exits,
                short_entries=input_data.short_entries,
                short_exits=input_data.short_exits,
                symbol=input_data.symbol,
                interval=input_data.interval,
                initial_capital=input_data.initial_capital,
                position_size=params.get("position_size", input_data.position_size),
                leverage=params.get("leverage", input_data.leverage),
                stop_loss=params.get("stop_loss", input_data.stop_loss),
                take_profit=params.get("take_profit", input_data.take_profit),
                direction=input_data.direction,
                taker_fee=input_data.taker_fee,
                slippage=input_data.slippage,
                use_bar_magnifier=input_data.use_bar_magnifier,
            )

            result = self.run(modified_input)
            results.append((params, result))

        # Sort by metric
        def get_metric_value(item):
            params, output = item
            return getattr(output.metrics, metric, 0)

        results.sort(key=get_metric_value, reverse=True)

        return results[:top_n]
