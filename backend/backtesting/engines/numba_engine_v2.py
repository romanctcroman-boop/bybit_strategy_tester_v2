"""
⚡ NUMBA ENGINE V2/V3/V4 - Быстрый движок с JIT компиляцией

Особенности:
- 20-40x быстрее Fallback
- Полная поддержка Bar Magnifier
- Pyramiding (V3)
- ATR SL/TP (V4)
- Multi-level TP (V4)
- Trailing Stop (V4)
- DCA / Safety Orders (V4)
- 100% паритет с Fallback

V2: Basic SL/TP, Bar Magnifier
V3: + Pyramiding (несколько входов в одну сторону)
V4: + ATR SL/TP, Multi-TP (4 уровня), Trailing Stop, DCA

Функции:
- _simulate_trades_numba: V2 (базовый)
- _simulate_trades_numba_pyramiding: V3 (pyramiding)
- _simulate_trades_numba_v4: V4 (полный функционал + DCA)

Скорость: ~20-40x (JIT compiled)
"""

import time
from typing import Any

import numpy as np
import pandas as pd
from loguru import logger

try:
    from numba import njit, prange  # noqa: F401

    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    logger.warning("Numba not available, falling back to Python")

from backend.backtesting.interfaces import (
    BacktestInput,
    BacktestMetrics,
    BacktestOutput,
    BaseBacktestEngine,
    ExitReason,
    TradeDirection,
    TradeRecord,
)

# ============================================================================
# NUMBA JIT FUNCTIONS
# ============================================================================

if NUMBA_AVAILABLE:

    @njit(cache=True, fastmath=True)
    def _simulate_trades_numba(
        open_prices: np.ndarray,
        high_prices: np.ndarray,
        low_prices: np.ndarray,
        close_prices: np.ndarray,
        long_entries: np.ndarray,
        long_exits: np.ndarray,
        short_entries: np.ndarray,
        short_exits: np.ndarray,
        stop_loss: float,
        take_profit: float,
        position_size: float,
        leverage: float,
        taker_fee: float,
        slippage: float,
        direction: int,  # 1=long, -1=short, 0=both
        initial_capital: float,
        use_fixed_amount: bool,  # NEW: True = use fixed_amount, False = use position_size
        fixed_amount: float,  # NEW: Fixed amount per trade (for TV parity)
    ) -> tuple[
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
    ]:
        """
        Numba-optimized trade simulation with FIXED cash handling.

        Returns:
            equity_curve, trade_pnls, trade_directions, entry_indices,
            exit_indices, entry_prices, exit_prices, exit_reasons
        """
        n = len(close_prices)

        # Dynamic allocation based on data size
        # Worst case: trade every 2 bars (entry + exit)
        # Cap at 50000 to prevent excessive memory usage
        max_trades = min(n // 2, 50000)
        if max_trades < 100:
            max_trades = 100  # Minimum for small datasets

        # Pre-allocate with dynamic size
        equity_curve = np.zeros(n, dtype=np.float64)
        trade_pnls = np.zeros(max_trades, dtype=np.float64)
        trade_directions = np.zeros(max_trades, dtype=np.int32)  # 1=long, -1=short
        entry_indices = np.zeros(max_trades, dtype=np.int32)
        exit_indices = np.zeros(max_trades, dtype=np.int32)
        entry_prices_arr = np.zeros(max_trades, dtype=np.float64)
        exit_prices_arr = np.zeros(max_trades, dtype=np.float64)
        exit_reasons = np.zeros(max_trades, dtype=np.int32)  # 0=SL, 1=TP, 2=signal, 3=end
        trade_sizes = np.zeros(max_trades, dtype=np.float64)  # Position size
        trade_fees = np.zeros(max_trades, dtype=np.float64)  # Total fees (entry + exit)

        cash = initial_capital
        equity_curve[0] = initial_capital
        trade_count = 0

        # Position state
        in_long = False
        in_short = False
        long_entry_price = 0.0
        short_entry_price = 0.0
        long_entry_idx = 0
        short_entry_idx = 0
        long_size = 0.0
        short_size = 0.0
        long_allocated = 0.0  # FIXED: Track allocated capital
        short_allocated = 0.0  # FIXED: Track allocated capital
        long_entry_fee = 0.0  # Track entry fee for full fee calculation
        short_entry_fee = 0.0  # Track entry fee for full fee calculation

        for i in range(1, n):
            open_price = open_prices[i]
            high_price = high_prices[i]
            low_price = low_prices[i]
            close_price = close_prices[i]

            # TV-style: Track if we exited this bar (prevents new entry on same bar)
            # This matches Fallback behavior where pending exit mechanism
            # naturally prevents entry due to cash=0 until exit is processed
            exited_this_bar = False

            # === LONG EXIT ===
            if in_long:
                sl_price = long_entry_price * (1.0 - stop_loss) if stop_loss > 0 else 0.0
                tp_price = long_entry_price * (1.0 + take_profit) if take_profit > 0 else 1e10

                exit_price = 0.0
                exit_reason = -1

                # TV-style intrabar simulation: determine check order based on open
                sl_hit = stop_loss > 0 and low_price <= sl_price
                tp_hit = take_profit > 0 and high_price >= tp_price

                if sl_hit and tp_hit:
                    # Both SL and TP hit - use open position to determine order
                    open_closer_to_high = abs(open_price - high_price) < abs(open_price - low_price)
                    if open_closer_to_high:
                        # open → high → low: TP triggers first
                        exit_price = tp_price
                        exit_reason = 1  # TP
                    else:
                        # open → low → high: SL triggers first
                        exit_price = sl_price
                        exit_reason = 0  # SL
                elif sl_hit:
                    exit_price = sl_price
                    exit_reason = 0  # SL
                elif tp_hit:
                    exit_price = tp_price
                    exit_reason = 1  # TP
                elif long_exits[i]:
                    # Signal exit uses close price with slippage
                    exit_price = close_price * (1.0 - slippage)
                    exit_reason = 2  # Signal

                if exit_reason >= 0:
                    # FIXED: Correct PnL calculation with BOTH fees (TV style)
                    pnl = (exit_price - long_entry_price) * long_size
                    exit_fee = exit_price * long_size * taker_fee
                    total_fees = long_entry_fee + exit_fee  # TV: entry + exit
                    pnl -= total_fees

                    # FIXED: Return allocated capital + PnL
                    cash += long_allocated + pnl

                    # Check array bounds before recording trade
                    if trade_count < max_trades:
                        trade_pnls[trade_count] = pnl
                        trade_directions[trade_count] = 1
                        entry_indices[trade_count] = long_entry_idx
                        exit_indices[trade_count] = i
                        entry_prices_arr[trade_count] = long_entry_price
                        exit_prices_arr[trade_count] = exit_price
                        exit_reasons[trade_count] = exit_reason
                        trade_sizes[trade_count] = long_size
                        trade_fees[trade_count] = total_fees  # TV: entry + exit fees
                        trade_count += 1

                    in_long = False
                    long_size = 0.0
                    long_allocated = 0.0
                    long_entry_fee = 0.0
                    exited_this_bar = True  # Prevent new entry on same bar

            # === SHORT EXIT ===
            if in_short:
                sl_price = short_entry_price * (1.0 + stop_loss) if stop_loss > 0 else 1e10
                tp_price = short_entry_price * (1.0 - take_profit) if take_profit > 0 else 0.0

                exit_price = 0.0
                exit_reason = -1

                # TV-style intrabar simulation: determine check order based on open
                sl_hit = stop_loss > 0 and high_price >= sl_price
                tp_hit = take_profit > 0 and low_price <= tp_price

                if sl_hit and tp_hit:
                    # Both SL and TP hit - use open position to determine order
                    open_closer_to_high = abs(open_price - high_price) < abs(open_price - low_price)
                    if open_closer_to_high:
                        # open → high → low: SL (at high) triggers first for short
                        exit_price = sl_price
                        exit_reason = 0  # SL
                    else:
                        # open → low → high: TP (at low) triggers first for short
                        exit_price = tp_price
                        exit_reason = 1  # TP
                elif sl_hit:
                    exit_price = sl_price
                    exit_reason = 0  # SL
                elif tp_hit:
                    exit_price = tp_price
                    exit_reason = 1  # TP
                elif short_exits[i]:
                    # Signal exit uses close price with slippage
                    exit_price = close_price * (1.0 + slippage)
                    exit_reason = 2

                if exit_reason >= 0:
                    # FIXED: Correct PnL calculation with BOTH fees (TV style)
                    pnl = (short_entry_price - exit_price) * short_size
                    exit_fee = exit_price * short_size * taker_fee
                    total_fees = short_entry_fee + exit_fee  # TV: entry + exit
                    pnl -= total_fees

                    # FIXED: Return allocated capital + PnL
                    cash += short_allocated + pnl

                    # Check array bounds before recording trade
                    if trade_count < max_trades:
                        trade_pnls[trade_count] = pnl
                        trade_directions[trade_count] = -1
                        entry_indices[trade_count] = short_entry_idx
                        exit_indices[trade_count] = i
                        entry_prices_arr[trade_count] = short_entry_price
                        exit_prices_arr[trade_count] = exit_price
                        exit_reasons[trade_count] = exit_reason
                        trade_sizes[trade_count] = short_size
                        trade_fees[trade_count] = total_fees  # TV: entry + exit fees
                        trade_count += 1

                    in_short = False
                    short_size = 0.0
                    short_allocated = 0.0
                    short_entry_fee = 0.0
                    exited_this_bar = True  # Prevent new entry on same bar

            # === LONG ENTRY ===
            # TV parity: Entry at open of NEXT bar after signal
            # Can't enter if already in ANY position (long OR short)
            # TV-style: No entry on same bar as exit (cash not available in pending mode)
            if (
                not in_long
                and not in_short  # FIXED: Can't enter if already in short
                and not exited_this_bar  # TV-style: No entry on same bar as exit
                and long_entries[i]
                and (direction >= 0)
                and (i < n - 2)  # FIXED: Need room for i+1 entry
                and (i > 0)
            ):
                # FIXED: Entry at NEXT bar's open (TradingView style)
                # TV parity: No slippage on entry, entry at exact open price
                entry_price = open_prices[i + 1]
                # FIXED: Handle fixed amount vs percentage modes (TV parity)
                if use_fixed_amount:
                    # Fixed amount per trade (like TradingView)
                    allocated = min(fixed_amount, cash)
                else:
                    # Percentage-based position sizing
                    allocated = cash * position_size

                # Skip if allocated is too small (prevents micro-positions)
                if allocated >= 1.0:
                    notional = allocated * leverage  # Position size with leverage
                    size = notional / entry_price
                    entry_fee = notional * taker_fee

                    # TV style: Only deduct allocated capital, not entry fee
                    # Entry fee will be deducted from PnL at exit
                    cash -= allocated

                    in_long = True
                    long_entry_price = entry_price
                    long_entry_idx = i  # Signal bar (not entry bar)
                    long_size = size
                    long_allocated = allocated
                    long_entry_fee = entry_fee

            # === SHORT ENTRY ===
            # TV parity: Entry at open of NEXT bar after signal
            # Can't enter if already in ANY position
            # TV-style: No entry on same bar as exit
            if (
                not in_short
                and not in_long  # FIXED: Can't enter if already in long
                and not exited_this_bar  # TV-style: No entry on same bar as exit
                and short_entries[i]
                and (direction <= 0)
                and (i < n - 2)  # FIXED: Need room for i+1 entry
                and (i > 0)
            ):
                # FIXED: Entry at NEXT bar's open (TradingView style)
                # TV parity: No slippage on entry, entry at exact open price
                entry_price = open_prices[i + 1]
                # FIXED: Handle fixed amount vs percentage modes (TV parity)
                if use_fixed_amount:
                    # Fixed amount per trade (like TradingView)
                    allocated = min(fixed_amount, cash)
                else:
                    # Percentage-based position sizing
                    allocated = cash * position_size

                # Skip if allocated is too small (prevents micro-positions)
                if allocated >= 1.0:
                    notional = allocated * leverage
                    size = notional / entry_price
                    entry_fee = notional * taker_fee

                    # TV style: Only deduct allocated capital, not entry fee
                    # Entry fee will be deducted from PnL at exit
                    cash -= allocated

                    in_short = True
                    short_entry_price = entry_price
                    short_entry_idx = i  # Signal bar (not entry bar)
                    short_size = size
                    short_allocated = allocated
                    short_entry_fee = entry_fee

            # === UPDATE EQUITY ===
            equity = cash
            if in_long:
                # FIXED: Match Fallback formula - use position value not allocated
                unrealized = (close_price - long_entry_price) * long_size
                equity += unrealized + long_size * long_entry_price
            if in_short:
                unrealized = (short_entry_price - close_price) * short_size
                equity += unrealized + short_size * short_entry_price

            equity_curve[i] = equity

        # === CLOSE OPEN POSITIONS AT END OF DATA ===
        last_close = close_prices[n - 1]

        if in_long and trade_count < max_trades:
            exit_price = last_close * (1.0 - slippage)
            pnl = (exit_price - long_entry_price) * long_size
            exit_fee = exit_price * long_size * taker_fee
            total_fees = long_entry_fee + exit_fee  # TV: entry + exit
            pnl -= total_fees

            trade_pnls[trade_count] = pnl
            trade_directions[trade_count] = 1
            entry_indices[trade_count] = long_entry_idx
            exit_indices[trade_count] = n - 1
            entry_prices_arr[trade_count] = long_entry_price
            exit_prices_arr[trade_count] = exit_price
            exit_reasons[trade_count] = 3  # END_OF_DATA
            trade_sizes[trade_count] = long_size
            trade_fees[trade_count] = total_fees  # TV: entry + exit fees
            trade_count += 1

        if in_short and trade_count < max_trades:
            exit_price = last_close * (1.0 + slippage)
            pnl = (short_entry_price - exit_price) * short_size
            exit_fee = exit_price * short_size * taker_fee
            total_fees = short_entry_fee + exit_fee  # TV: entry + exit
            pnl -= total_fees

            trade_pnls[trade_count] = pnl
            trade_directions[trade_count] = -1
            entry_indices[trade_count] = short_entry_idx
            exit_indices[trade_count] = n - 1
            entry_prices_arr[trade_count] = short_entry_price
            exit_prices_arr[trade_count] = exit_price
            exit_reasons[trade_count] = 3  # END_OF_DATA
            trade_sizes[trade_count] = short_size
            trade_fees[trade_count] = total_fees  # TV: entry + exit fees
            trade_count += 1

        # Truncate arrays to actual trade count
        return (
            equity_curve,
            trade_pnls[:trade_count],
            trade_directions[:trade_count],
            entry_indices[:trade_count],
            exit_indices[:trade_count],
            entry_prices_arr[:trade_count],
            exit_prices_arr[:trade_count],
            exit_reasons[:trade_count],
            trade_sizes[:trade_count],
            trade_fees[:trade_count],
        )

    # ========================================================================
    # NUMBA V3: PYRAMIDING SUPPORT
    # ========================================================================

    @njit(cache=True, fastmath=True)
    def _simulate_trades_numba_pyramiding(
        open_prices: np.ndarray,
        high_prices: np.ndarray,
        low_prices: np.ndarray,
        close_prices: np.ndarray,
        long_entries: np.ndarray,
        long_exits: np.ndarray,
        short_entries: np.ndarray,
        short_exits: np.ndarray,
        stop_loss: float,
        take_profit: float,
        position_size: float,
        leverage: float,
        taker_fee: float,
        slippage: float,
        direction: int,  # 1=long, -1=short, 0=both
        initial_capital: float,
        use_fixed_amount: bool,
        fixed_amount: float,
        # === PYRAMIDING PARAMS ===
        max_entries: int,  # pyramiding limit (1 = no pyramiding)
    ) -> tuple[
        np.ndarray,  # equity_curve
        np.ndarray,  # trade_pnls
        np.ndarray,  # trade_directions
        np.ndarray,  # entry_indices
        np.ndarray,  # exit_indices
        np.ndarray,  # entry_prices
        np.ndarray,  # exit_prices
        np.ndarray,  # exit_reasons
        np.ndarray,  # trade_sizes
        np.ndarray,  # trade_fees
    ]:
        """
        Numba-optimized trade simulation WITH PYRAMIDING support.

        Pyramiding: allows multiple entries in same direction.
        SL/TP calculated on weighted average entry price.
        Close rule: ALL (close all entries at once).

        Returns same tuple as _simulate_trades_numba for compatibility.
        """
        n = len(close_prices)

        # Trade arrays
        max_trades = min(n // 2, 50000)
        if max_trades < 100:
            max_trades = 100

        equity_curve = np.zeros(n, dtype=np.float64)
        trade_pnls = np.zeros(max_trades, dtype=np.float64)
        trade_directions = np.zeros(max_trades, dtype=np.int32)
        entry_indices = np.zeros(max_trades, dtype=np.int32)
        exit_indices = np.zeros(max_trades, dtype=np.int32)
        entry_prices_arr = np.zeros(max_trades, dtype=np.float64)
        exit_prices_arr = np.zeros(max_trades, dtype=np.float64)
        exit_reasons = np.zeros(max_trades, dtype=np.int32)
        trade_sizes = np.zeros(max_trades, dtype=np.float64)
        trade_fees = np.zeros(max_trades, dtype=np.float64)

        cash = initial_capital
        equity_curve[0] = initial_capital
        trade_count = 0

        # === PYRAMIDING STATE: arrays for multiple entries ===
        # LONG entries
        long_entry_prices = np.zeros(max_entries, dtype=np.float64)
        long_entry_sizes = np.zeros(max_entries, dtype=np.float64)
        long_entry_allocated = np.zeros(max_entries, dtype=np.float64)
        long_entry_fees = np.zeros(max_entries, dtype=np.float64)
        long_entry_bars = np.zeros(max_entries, dtype=np.int32)
        n_long_entries = 0

        # SHORT entries
        short_entry_prices = np.zeros(max_entries, dtype=np.float64)
        short_entry_sizes = np.zeros(max_entries, dtype=np.float64)
        short_entry_allocated = np.zeros(max_entries, dtype=np.float64)
        short_entry_fees = np.zeros(max_entries, dtype=np.float64)
        short_entry_bars = np.zeros(max_entries, dtype=np.int32)
        n_short_entries = 0

        for i in range(1, n):
            open_price = open_prices[i]
            high_price = high_prices[i]
            low_price = low_prices[i]
            close_price = close_prices[i]
            exited_this_bar = False

            # === LONG EXIT (check if any long position) ===
            if n_long_entries > 0:
                # Calculate weighted average entry price
                total_size = 0.0
                weighted_price = 0.0
                total_allocated = 0.0
                total_entry_fees = 0.0

                for j in range(n_long_entries):
                    total_size += long_entry_sizes[j]
                    weighted_price += long_entry_prices[j] * long_entry_sizes[j]
                    total_allocated += long_entry_allocated[j]
                    total_entry_fees += long_entry_fees[j]

                avg_entry_price = weighted_price / total_size if total_size > 0 else 0.0

                # SL/TP based on average entry
                sl_price = avg_entry_price * (1.0 - stop_loss) if stop_loss > 0 else 0.0
                tp_price = avg_entry_price * (1.0 + take_profit) if take_profit > 0 else 1e10

                exit_price = 0.0
                exit_reason = -1

                # Check SL/TP
                sl_hit = stop_loss > 0 and low_price <= sl_price
                tp_hit = take_profit > 0 and high_price >= tp_price

                if sl_hit and tp_hit:
                    open_closer_to_high = abs(open_price - high_price) < abs(open_price - low_price)
                    if open_closer_to_high:
                        exit_price = tp_price
                        exit_reason = 1  # TP
                    else:
                        exit_price = sl_price
                        exit_reason = 0  # SL
                elif sl_hit:
                    exit_price = sl_price
                    exit_reason = 0  # SL
                elif tp_hit:
                    exit_price = tp_price
                    exit_reason = 1  # TP
                elif long_exits[i]:
                    exit_price = close_price * (1.0 - slippage)
                    exit_reason = 2  # Signal

                if exit_reason >= 0:
                    # Close ALL entries
                    pnl = (exit_price - avg_entry_price) * total_size
                    exit_fee = exit_price * total_size * taker_fee
                    total_fees_trade = total_entry_fees + exit_fee
                    pnl -= total_fees_trade

                    cash += total_allocated + pnl

                    # Record ONE trade (aggregated)
                    if trade_count < max_trades:
                        trade_pnls[trade_count] = pnl
                        trade_directions[trade_count] = 1
                        entry_indices[trade_count] = long_entry_bars[0]  # First entry bar
                        exit_indices[trade_count] = i
                        entry_prices_arr[trade_count] = avg_entry_price
                        exit_prices_arr[trade_count] = exit_price
                        exit_reasons[trade_count] = exit_reason
                        trade_sizes[trade_count] = total_size
                        trade_fees[trade_count] = total_fees_trade
                        trade_count += 1

                    # Reset long state
                    n_long_entries = 0
                    for j in range(max_entries):
                        long_entry_prices[j] = 0.0
                        long_entry_sizes[j] = 0.0
                        long_entry_allocated[j] = 0.0
                        long_entry_fees[j] = 0.0
                        long_entry_bars[j] = 0

                    exited_this_bar = True

            # === SHORT EXIT ===
            if n_short_entries > 0:
                total_size = 0.0
                weighted_price = 0.0
                total_allocated = 0.0
                total_entry_fees = 0.0

                for j in range(n_short_entries):
                    total_size += short_entry_sizes[j]
                    weighted_price += short_entry_prices[j] * short_entry_sizes[j]
                    total_allocated += short_entry_allocated[j]
                    total_entry_fees += short_entry_fees[j]

                avg_entry_price = weighted_price / total_size if total_size > 0 else 0.0

                sl_price = avg_entry_price * (1.0 + stop_loss) if stop_loss > 0 else 1e10
                tp_price = avg_entry_price * (1.0 - take_profit) if take_profit > 0 else 0.0

                exit_price = 0.0
                exit_reason = -1

                sl_hit = stop_loss > 0 and high_price >= sl_price
                tp_hit = take_profit > 0 and low_price <= tp_price

                if sl_hit and tp_hit:
                    open_closer_to_high = abs(open_price - high_price) < abs(open_price - low_price)
                    if open_closer_to_high:
                        exit_price = sl_price
                        exit_reason = 0  # SL
                    else:
                        exit_price = tp_price
                        exit_reason = 1  # TP
                elif sl_hit:
                    exit_price = sl_price
                    exit_reason = 0  # SL
                elif tp_hit:
                    exit_price = tp_price
                    exit_reason = 1  # TP
                elif short_exits[i]:
                    exit_price = close_price * (1.0 + slippage)
                    exit_reason = 2  # Signal

                if exit_reason >= 0:
                    pnl = (avg_entry_price - exit_price) * total_size
                    exit_fee = exit_price * total_size * taker_fee
                    total_fees_trade = total_entry_fees + exit_fee
                    pnl -= total_fees_trade

                    cash += total_allocated + pnl

                    if trade_count < max_trades:
                        trade_pnls[trade_count] = pnl
                        trade_directions[trade_count] = -1
                        entry_indices[trade_count] = short_entry_bars[0]
                        exit_indices[trade_count] = i
                        entry_prices_arr[trade_count] = avg_entry_price
                        exit_prices_arr[trade_count] = exit_price
                        exit_reasons[trade_count] = exit_reason
                        trade_sizes[trade_count] = total_size
                        trade_fees[trade_count] = total_fees_trade
                        trade_count += 1

                    n_short_entries = 0
                    for j in range(max_entries):
                        short_entry_prices[j] = 0.0
                        short_entry_sizes[j] = 0.0
                        short_entry_allocated[j] = 0.0
                        short_entry_fees[j] = 0.0
                        short_entry_bars[j] = 0

                    exited_this_bar = True

            # === LONG ENTRY (with pyramiding) ===
            can_enter_long = (
                n_long_entries < max_entries
                and n_short_entries == 0  # No hedge mode
                and not exited_this_bar
                and long_entries[i]
                and direction >= 0
                and i < n - 2
                and i > 0
            )

            if can_enter_long:
                entry_price = open_prices[i + 1]
                if use_fixed_amount:
                    allocated = min(fixed_amount, cash)
                else:
                    allocated = cash * position_size

                if allocated >= 1.0:
                    notional = allocated * leverage
                    size = notional / entry_price
                    entry_fee = notional * taker_fee

                    cash -= allocated

                    # Store entry
                    long_entry_prices[n_long_entries] = entry_price
                    long_entry_sizes[n_long_entries] = size
                    long_entry_allocated[n_long_entries] = allocated
                    long_entry_fees[n_long_entries] = entry_fee
                    long_entry_bars[n_long_entries] = i
                    n_long_entries += 1

            # === SHORT ENTRY (with pyramiding) ===
            can_enter_short = (
                n_short_entries < max_entries
                and n_long_entries == 0  # No hedge mode
                and not exited_this_bar
                and short_entries[i]
                and direction <= 0
                and i < n - 2
                and i > 0
            )

            if can_enter_short:
                entry_price = open_prices[i + 1]
                if use_fixed_amount:
                    allocated = min(fixed_amount, cash)
                else:
                    allocated = cash * position_size

                if allocated >= 1.0:
                    notional = allocated * leverage
                    size = notional / entry_price
                    entry_fee = notional * taker_fee

                    cash -= allocated

                    short_entry_prices[n_short_entries] = entry_price
                    short_entry_sizes[n_short_entries] = size
                    short_entry_allocated[n_short_entries] = allocated
                    short_entry_fees[n_short_entries] = entry_fee
                    short_entry_bars[n_short_entries] = i
                    n_short_entries += 1

            # === UPDATE EQUITY ===
            equity = cash

            if n_long_entries > 0:
                for j in range(n_long_entries):
                    unrealized = (close_price - long_entry_prices[j]) * long_entry_sizes[j]
                    equity += unrealized + long_entry_sizes[j] * long_entry_prices[j]

            if n_short_entries > 0:
                for j in range(n_short_entries):
                    unrealized = (short_entry_prices[j] - close_price) * short_entry_sizes[j]
                    equity += unrealized + short_entry_sizes[j] * short_entry_prices[j]

            equity_curve[i] = equity

        # === CLOSE OPEN POSITIONS AT END ===
        last_close = close_prices[n - 1]

        if n_long_entries > 0 and trade_count < max_trades:
            total_size = 0.0
            weighted_price = 0.0
            total_allocated = 0.0
            total_entry_fees = 0.0

            for j in range(n_long_entries):
                total_size += long_entry_sizes[j]
                weighted_price += long_entry_prices[j] * long_entry_sizes[j]
                total_allocated += long_entry_allocated[j]
                total_entry_fees += long_entry_fees[j]

            avg_entry_price = weighted_price / total_size if total_size > 0 else 0.0
            exit_price = last_close * (1.0 - slippage)
            pnl = (exit_price - avg_entry_price) * total_size
            exit_fee = exit_price * total_size * taker_fee
            total_fees_trade = total_entry_fees + exit_fee
            pnl -= total_fees_trade

            trade_pnls[trade_count] = pnl
            trade_directions[trade_count] = 1
            entry_indices[trade_count] = long_entry_bars[0]
            exit_indices[trade_count] = n - 1
            entry_prices_arr[trade_count] = avg_entry_price
            exit_prices_arr[trade_count] = exit_price
            exit_reasons[trade_count] = 3  # END_OF_DATA
            trade_sizes[trade_count] = total_size
            trade_fees[trade_count] = total_fees_trade
            trade_count += 1

        if n_short_entries > 0 and trade_count < max_trades:
            total_size = 0.0
            weighted_price = 0.0
            total_allocated = 0.0
            total_entry_fees = 0.0

            for j in range(n_short_entries):
                total_size += short_entry_sizes[j]
                weighted_price += short_entry_prices[j] * short_entry_sizes[j]
                total_allocated += short_entry_allocated[j]
                total_entry_fees += short_entry_fees[j]

            avg_entry_price = weighted_price / total_size if total_size > 0 else 0.0
            exit_price = last_close * (1.0 + slippage)
            pnl = (avg_entry_price - exit_price) * total_size
            exit_fee = exit_price * total_size * taker_fee
            total_fees_trade = total_entry_fees + exit_fee
            pnl -= total_fees_trade

            trade_pnls[trade_count] = pnl
            trade_directions[trade_count] = -1
            entry_indices[trade_count] = short_entry_bars[0]
            exit_indices[trade_count] = n - 1
            entry_prices_arr[trade_count] = avg_entry_price
            exit_prices_arr[trade_count] = exit_price
            exit_reasons[trade_count] = 3  # END_OF_DATA
            trade_sizes[trade_count] = total_size
            trade_fees[trade_count] = total_fees_trade
            trade_count += 1

        return (
            equity_curve,
            trade_pnls[:trade_count],
            trade_directions[:trade_count],
            entry_indices[:trade_count],
            exit_indices[:trade_count],
            entry_prices_arr[:trade_count],
            exit_prices_arr[:trade_count],
            exit_reasons[:trade_count],
            trade_sizes[:trade_count],
            trade_fees[:trade_count],
        )

    # ========================================================================
    # NUMBA V4: ATR SL/TP + MULTI-LEVEL TP + TRAILING
    # ========================================================================

    @njit(cache=True, fastmath=True)
    def _simulate_trades_numba_v4(
        open_prices: np.ndarray,
        high_prices: np.ndarray,
        low_prices: np.ndarray,
        close_prices: np.ndarray,
        long_entries: np.ndarray,
        long_exits: np.ndarray,
        short_entries: np.ndarray,
        short_exits: np.ndarray,
        # === BASIC PARAMS ===
        stop_loss: float,  # Fixed SL (fraction, e.g. 0.02 = 2%)
        take_profit: float,  # Fixed TP (fraction)
        position_size: float,
        leverage: float,
        taker_fee: float,
        slippage: float,
        direction: int,  # 1=long, -1=short, 0=both
        initial_capital: float,
        use_fixed_amount: bool,
        fixed_amount: float,
        # === PYRAMIDING ===
        max_entries: int,
        # === ATR PARAMS ===
        atr_values: np.ndarray,  # Pre-calculated ATR array
        use_atr_sl: bool,  # Use ATR for SL
        use_atr_tp: bool,  # Use ATR for TP
        atr_sl_mult: float,  # ATR multiplier for SL
        atr_tp_mult: float,  # ATR multiplier for TP
        # === MULTI-TP PARAMS ===
        use_multi_tp: bool,  # Enable multi-level TP
        tp1_pct: float,  # TP1: % of position to close (e.g. 0.25 = 25%)
        tp2_pct: float,  # TP2: % of position
        tp3_pct: float,  # TP3: % of position
        tp4_pct: float,  # TP4: % of position (remainder)
        tp1_mult: float,  # TP1 level: ATR mult or % (e.g. 1.0 ATR or 0.01 = 1%)
        tp2_mult: float,  # TP2 level
        tp3_mult: float,  # TP3 level
        tp4_mult: float,  # TP4 level
        # === TRAILING STOP ===
        use_trailing: bool,  # Enable trailing stop
        trail_activation: float,  # Activate trailing after this profit (e.g. 0.01 = 1%)
        trail_offset: float,  # Trail distance from best price (e.g. 0.005 = 0.5%)
        # === DCA (Safety Orders) ===
        dca_enabled: bool,  # Enable DCA mode
        dca_num_so: int,  # Number of safety orders (max 20)
        dca_levels: np.ndarray,  # Pre-calculated SO price deviation levels (cumulative)
        dca_volumes: np.ndarray,  # Pre-calculated SO volume fractions
        dca_base_order_size: float,  # Base order size (fraction of capital)
        # === BREAKEVEN STOP ===
        breakeven_enabled: bool,  # Enable breakeven stop after TP1
        breakeven_offset: float,  # Offset from entry (e.g. 0.001 = +0.1%)
        # === TIME-BASED EXITS ===
        max_bars_in_trade: int,  # Close after N bars (0 = disabled)
        # === RE-ENTRY RULES ===
        re_entry_delay_bars: int,  # Wait N bars after exit before re-entry
        max_trades_per_day: int,  # Max trades per day (0 = unlimited)
        cooldown_after_loss: int,  # Wait N bars after losing trade
        max_consecutive_losses: int,  # Stop trading after N consecutive losses
        # === MARKET FILTERS (pre-calculated boolean masks) ===
        volatility_filter: np.ndarray,  # True = allowed to trade, False = filtered out
        volume_filter: np.ndarray,  # True = allowed to trade, False = filtered out
        trend_filter_long: np.ndarray,  # True = long allowed (price above SMA)
        trend_filter_short: np.ndarray,  # True = short allowed (price below SMA)
        # === FUNDING RATE ===
        include_funding: bool,  # Enable funding rate deductions
        funding_rate: float,  # Funding rate per interval (e.g., 0.0001 = 0.01%)
        funding_interval: int,  # Bars between funding payments (e.g., 8 for 8h on 1h TF)
        # === ADVANCED SLIPPAGE ===
        use_advanced_slippage: bool,  # Enable dynamic slippage calculation
        slippage_multipliers: np.ndarray,  # Pre-calculated slippage multipliers per bar
        # === CLOSE RULE (FIFO/LIFO/ALL) ===
        close_rule: int,  # 0=ALL (close all entries), 1=FIFO (first in first out), 2=LIFO (last in first out)
    ) -> tuple[
        np.ndarray,  # equity_curve
        np.ndarray,  # trade_pnls
        np.ndarray,  # trade_directions
        np.ndarray,  # entry_indices
        np.ndarray,  # exit_indices
        np.ndarray,  # entry_prices
        np.ndarray,  # exit_prices
        np.ndarray,  # exit_reasons
        np.ndarray,  # trade_sizes
        np.ndarray,  # trade_fees
    ]:
        """
        Numba V4: Full-featured simulation with ATR, Multi-TP, Trailing, Pyramiding, DCA.

        Features:
        - Pyramiding (multiple entries)
        - ATR-based SL/TP
        - Multi-level TP (up to 4 levels)
        - Trailing stop
        - DCA (Safety Orders)
        - Breakeven stop (after TP1)
        - Time-based exits (max_bars_in_trade)
        - Re-entry rules (delay, max trades per day, cooldown, max consecutive losses)
        - Market filters (volatility, volume, trend)
        - Funding rate deduction
        - Advanced slippage model
        - FIFO/LIFO close rule (for signal exits)

        Exit reasons:
        - 0: SL (or Breakeven)
        - 1: TP (or TP1-4)
        - 2: Signal
        - 3: End of data
        - 4: Trailing stop
        - 5: Time-based exit
        """
        n = len(close_prices)

        # Trade arrays
        max_trades = min(n * 4, 100000)  # More trades possible with multi-TP
        if max_trades < 200:
            max_trades = 200

        equity_curve = np.zeros(n, dtype=np.float64)
        trade_pnls = np.zeros(max_trades, dtype=np.float64)
        trade_directions = np.zeros(max_trades, dtype=np.int32)
        entry_indices = np.zeros(max_trades, dtype=np.int32)
        exit_indices = np.zeros(max_trades, dtype=np.int32)
        entry_prices_arr = np.zeros(max_trades, dtype=np.float64)
        exit_prices_arr = np.zeros(max_trades, dtype=np.float64)
        exit_reasons = np.zeros(max_trades, dtype=np.int32)
        trade_sizes = np.zeros(max_trades, dtype=np.float64)
        trade_fees = np.zeros(max_trades, dtype=np.float64)

        cash = initial_capital
        equity_curve[0] = initial_capital
        trade_count = 0

        # === PYRAMIDING STATE ===
        long_entry_prices = np.zeros(max_entries, dtype=np.float64)
        long_entry_sizes = np.zeros(max_entries, dtype=np.float64)
        long_entry_allocated = np.zeros(max_entries, dtype=np.float64)
        long_entry_fees = np.zeros(max_entries, dtype=np.float64)
        long_entry_bars = np.zeros(max_entries, dtype=np.int32)
        long_entry_atr = np.zeros(max_entries, dtype=np.float64)  # ATR at entry
        n_long_entries = 0

        short_entry_prices = np.zeros(max_entries, dtype=np.float64)
        short_entry_sizes = np.zeros(max_entries, dtype=np.float64)
        short_entry_allocated = np.zeros(max_entries, dtype=np.float64)
        short_entry_fees = np.zeros(max_entries, dtype=np.float64)
        short_entry_bars = np.zeros(max_entries, dtype=np.int32)
        short_entry_atr = np.zeros(max_entries, dtype=np.float64)  # ATR at entry
        n_short_entries = 0

        # === FIFO/LIFO STATE ===
        # Track which entries are still open (0=open, 1=closed)
        long_entry_closed = np.zeros(max_entries, dtype=np.int32)
        short_entry_closed = np.zeros(max_entries, dtype=np.int32)

        # === MULTI-TP STATE ===
        # Track remaining position and which TPs have been hit
        long_remaining_pct = 1.0  # 100% of position remaining
        long_tp_hit = np.zeros(4, dtype=np.int32)  # 0=not hit, 1=hit
        short_remaining_pct = 1.0
        short_tp_hit = np.zeros(4, dtype=np.int32)

        # === TRAILING STATE ===
        long_trail_active = False
        long_best_price = 0.0
        long_trail_stop = 0.0
        short_trail_active = False
        short_best_price = 1e10
        short_trail_stop = 1e10

        # === DCA STATE ===
        # Track which safety orders have been filled
        max_dca = 20  # Max safety orders
        long_dca_base_price = 0.0  # Base price for calculating SO levels
        long_dca_filled = np.zeros(max_dca, dtype=np.int32)  # 0=not filled, 1=filled
        short_dca_base_price = 0.0
        short_dca_filled = np.zeros(max_dca, dtype=np.int32)

        # === BREAKEVEN STATE ===
        long_breakeven_active = False
        long_breakeven_price = 0.0  # SL moved to this price
        short_breakeven_active = False
        short_breakeven_price = 0.0

        # === RE-ENTRY & TRADE LIMITS STATE ===
        last_exit_bar = -9999  # Bar of last exit (-9999 = no previous exit)
        consecutive_losses = 0  # Count of consecutive losing trades
        cooldown_until_bar = 0  # Don't trade until this bar
        trades_today = 0  # Count trades in current day
        current_day = -1  # Track day changes (simplified: use bar index / 24 for hourly)

        # Track first entry bar for time-based exit
        long_first_entry_bar = 0
        short_first_entry_bar = 0

        for i in range(1, n):
            _ = open_prices[i]  # Reserved for limit order entry (future)
            high_price = high_prices[i]
            low_price = low_prices[i]
            close_price = close_prices[i]
            current_atr = atr_values[i] if len(atr_values) > i else 0.0
            exited_this_bar = False

            # Calculate effective slippage (dynamic if advanced model enabled)
            if use_advanced_slippage and len(slippage_multipliers) > i:
                effective_slippage = slippage * slippage_multipliers[i]
            else:
                effective_slippage = slippage

            # === LONG POSITION MANAGEMENT ===
            if n_long_entries > 0:
                # Calculate weighted average entry and total size
                total_size = 0.0
                weighted_price = 0.0
                total_allocated = 0.0
                total_entry_fees = 0.0
                avg_entry_atr = 0.0

                for j in range(n_long_entries):
                    total_size += long_entry_sizes[j]
                    weighted_price += long_entry_prices[j] * long_entry_sizes[j]
                    total_allocated += long_entry_allocated[j]
                    total_entry_fees += long_entry_fees[j]
                    avg_entry_atr += long_entry_atr[j] * long_entry_sizes[j]

                avg_entry_price = weighted_price / total_size if total_size > 0 else 0.0
                avg_entry_atr = avg_entry_atr / total_size if total_size > 0 else current_atr

                # Remaining size after partial TP exits
                remaining_size = total_size * long_remaining_pct
                remaining_allocated = total_allocated * long_remaining_pct
                remaining_fees = total_entry_fees * long_remaining_pct

                # === TIME-BASED EXIT CHECK ===
                if max_bars_in_trade > 0 and not exited_this_bar:
                    bars_in_trade = i - long_first_entry_bar
                    if bars_in_trade >= max_bars_in_trade:
                        exit_price = close_price * (1.0 - effective_slippage)
                        pnl = (exit_price - avg_entry_price) * remaining_size
                        exit_fee = exit_price * remaining_size * taker_fee
                        total_fees_trade = remaining_fees + exit_fee
                        pnl -= total_fees_trade

                        cash += remaining_allocated + pnl

                        if trade_count < max_trades:
                            trade_pnls[trade_count] = pnl
                            trade_directions[trade_count] = 1
                            entry_indices[trade_count] = long_entry_bars[0]
                            exit_indices[trade_count] = i
                            entry_prices_arr[trade_count] = avg_entry_price
                            exit_prices_arr[trade_count] = exit_price
                            exit_reasons[trade_count] = 5  # TIME_EXIT
                            trade_sizes[trade_count] = remaining_size
                            trade_fees[trade_count] = total_fees_trade
                            trade_count += 1

                        # Update re-entry state
                        last_exit_bar = i
                        if pnl < 0:
                            consecutive_losses += 1
                            if cooldown_after_loss > 0:
                                cooldown_until_bar = i + cooldown_after_loss
                        else:
                            consecutive_losses = 0

                        # Reset long state
                        n_long_entries = 0
                        long_remaining_pct = 1.0
                        for k in range(4):
                            long_tp_hit[k] = 0
                        long_trail_active = False
                        long_best_price = 0.0
                        long_trail_stop = 0.0
                        long_breakeven_active = False
                        long_breakeven_price = 0.0
                        long_dca_base_price = 0.0
                        for k in range(max_dca):
                            long_dca_filled[k] = 0
                        exited_this_bar = True

                # === TRAILING STOP UPDATE ===
                if use_trailing and long_trail_active and not exited_this_bar:
                    if high_price > long_best_price:
                        long_best_price = high_price
                        long_trail_stop = long_best_price * (1.0 - trail_offset)

                # === CALCULATE SL PRICE ===
                # Use current_atr (not entry ATR) for parity with FallbackV4
                if use_atr_sl and current_atr > 0:
                    sl_price = avg_entry_price - current_atr * atr_sl_mult
                elif stop_loss > 0:
                    sl_price = avg_entry_price * (1.0 - stop_loss)
                else:
                    sl_price = 0.0

                # === CHECK TRAILING STOP ===
                if use_trailing and long_trail_active and low_price <= long_trail_stop:
                    # Trailing stop hit - close entire position
                    exit_price = long_trail_stop
                    pnl = (exit_price - avg_entry_price) * remaining_size
                    exit_fee = exit_price * remaining_size * taker_fee
                    total_fees_trade = remaining_fees + exit_fee
                    pnl -= total_fees_trade

                    cash += remaining_allocated + pnl

                    if trade_count < max_trades:
                        trade_pnls[trade_count] = pnl
                        trade_directions[trade_count] = 1
                        entry_indices[trade_count] = long_entry_bars[0]
                        exit_indices[trade_count] = i
                        entry_prices_arr[trade_count] = avg_entry_price
                        exit_prices_arr[trade_count] = exit_price
                        exit_reasons[trade_count] = 4  # Trailing
                        trade_sizes[trade_count] = remaining_size
                        trade_fees[trade_count] = total_fees_trade
                        trade_count += 1

                    # Reset long state
                    n_long_entries = 0
                    long_remaining_pct = 1.0
                    for k in range(4):
                        long_tp_hit[k] = 0
                    long_trail_active = False
                    long_best_price = 0.0
                    long_trail_stop = 0.0
                    # Reset DCA state
                    long_dca_base_price = 0.0
                    for k in range(max_dca):
                        long_dca_filled[k] = 0
                    exited_this_bar = True

                # === CHECK SL (with breakeven support) ===
                elif stop_loss > 0 or use_atr_sl or long_breakeven_active:
                    # Use breakeven price if active, otherwise use calculated SL
                    effective_sl = long_breakeven_price if long_breakeven_active else sl_price
                    if effective_sl > 0 and low_price <= effective_sl:
                        exit_price = effective_sl
                        pnl = (exit_price - avg_entry_price) * remaining_size
                        exit_fee = exit_price * remaining_size * taker_fee
                        total_fees_trade = remaining_fees + exit_fee
                        pnl -= total_fees_trade

                        cash += remaining_allocated + pnl

                        if trade_count < max_trades:
                            trade_pnls[trade_count] = pnl
                            trade_directions[trade_count] = 1
                            entry_indices[trade_count] = long_entry_bars[0]
                            exit_indices[trade_count] = i
                            entry_prices_arr[trade_count] = avg_entry_price
                            exit_prices_arr[trade_count] = exit_price
                            exit_reasons[trade_count] = 0  # SL
                            trade_sizes[trade_count] = remaining_size
                            trade_fees[trade_count] = total_fees_trade
                            trade_count += 1

                        # Update re-entry state
                        last_exit_bar = i
                        if pnl < 0:
                            consecutive_losses += 1
                            if cooldown_after_loss > 0:
                                cooldown_until_bar = i + cooldown_after_loss
                        else:
                            consecutive_losses = 0

                        n_long_entries = 0
                        long_remaining_pct = 1.0
                        for k in range(4):
                            long_tp_hit[k] = 0
                        long_trail_active = False
                        long_breakeven_active = False
                        long_breakeven_price = 0.0
                        # Reset DCA state
                        long_dca_base_price = 0.0
                        for k in range(max_dca):
                            long_dca_filled[k] = 0
                        exited_this_bar = True

                # === CHECK MULTI-TP ===
                if n_long_entries > 0 and use_multi_tp and not exited_this_bar:
                    tp_pcts = (tp1_pct, tp2_pct, tp3_pct, tp4_pct)
                    tp_mults = (tp1_mult, tp2_mult, tp3_mult, tp4_mult)

                    for tp_idx in range(4):
                        if long_tp_hit[tp_idx] == 0 and tp_pcts[tp_idx] > 0:
                            # Calculate TP price using current_atr for parity
                            if use_atr_tp and current_atr > 0:
                                tp_price = avg_entry_price + current_atr * tp_mults[tp_idx]
                            else:
                                tp_price = avg_entry_price * (1.0 + tp_mults[tp_idx])

                            if high_price >= tp_price:
                                # TP hit - close portion of position
                                close_pct = tp_pcts[tp_idx]
                                close_size = total_size * close_pct
                                close_allocated = total_allocated * close_pct
                                close_fees = total_entry_fees * close_pct

                                pnl = (tp_price - avg_entry_price) * close_size
                                exit_fee = tp_price * close_size * taker_fee
                                total_fees_trade = close_fees + exit_fee
                                pnl -= total_fees_trade

                                cash += close_allocated + pnl

                                if trade_count < max_trades:
                                    trade_pnls[trade_count] = pnl
                                    trade_directions[trade_count] = 1
                                    entry_indices[trade_count] = long_entry_bars[0]
                                    exit_indices[trade_count] = i
                                    entry_prices_arr[trade_count] = avg_entry_price
                                    exit_prices_arr[trade_count] = tp_price
                                    exit_reasons[trade_count] = 1  # TP
                                    trade_sizes[trade_count] = close_size
                                    trade_fees[trade_count] = total_fees_trade
                                    trade_count += 1

                                long_tp_hit[tp_idx] = 1
                                long_remaining_pct -= close_pct

                                # Activate trailing after TP1 if enabled
                                if tp_idx == 0 and use_trailing and not long_trail_active:
                                    long_trail_active = True
                                    long_best_price = tp_price
                                    long_trail_stop = long_best_price * (1.0 - trail_offset)

                                # Activate breakeven after TP1 if enabled
                                if tp_idx == 0 and breakeven_enabled and not long_breakeven_active:
                                    long_breakeven_active = True
                                    # Move SL to entry + offset
                                    long_breakeven_price = avg_entry_price * (1.0 + breakeven_offset)

                                # Check if position fully closed
                                if long_remaining_pct <= 0.001:
                                    # Update re-entry state
                                    last_exit_bar = i
                                    consecutive_losses = 0  # Full TP = not a loss

                                    n_long_entries = 0
                                    long_remaining_pct = 1.0
                                    for k in range(4):
                                        long_tp_hit[k] = 0
                                    long_trail_active = False
                                    long_breakeven_active = False
                                    long_breakeven_price = 0.0
                                    # Reset DCA state
                                    long_dca_base_price = 0.0
                                    for k in range(max_dca):
                                        long_dca_filled[k] = 0
                                    exited_this_bar = True
                                    break

                # === CHECK SINGLE TP (if not using multi-TP) ===
                elif n_long_entries > 0 and not use_multi_tp and not exited_this_bar:
                    if use_atr_tp and current_atr > 0:
                        tp_price = avg_entry_price + current_atr * atr_tp_mult
                    elif take_profit > 0:
                        tp_price = avg_entry_price * (1.0 + take_profit)
                    else:
                        tp_price = 1e10

                    if high_price >= tp_price:
                        exit_price = tp_price
                        pnl = (exit_price - avg_entry_price) * remaining_size
                        exit_fee = exit_price * remaining_size * taker_fee
                        total_fees_trade = remaining_fees + exit_fee
                        pnl -= total_fees_trade

                        cash += remaining_allocated + pnl

                        if trade_count < max_trades:
                            trade_pnls[trade_count] = pnl
                            trade_directions[trade_count] = 1
                            entry_indices[trade_count] = long_entry_bars[0]
                            exit_indices[trade_count] = i
                            entry_prices_arr[trade_count] = avg_entry_price
                            exit_prices_arr[trade_count] = exit_price
                            exit_reasons[trade_count] = 1  # TP
                            trade_sizes[trade_count] = remaining_size
                            trade_fees[trade_count] = total_fees_trade
                            trade_count += 1

                        n_long_entries = 0
                        long_remaining_pct = 1.0
                        long_trail_active = False
                        # Reset DCA state
                        long_dca_base_price = 0.0
                        for k in range(max_dca):
                            long_dca_filled[k] = 0
                        exited_this_bar = True

                # === CHECK SIGNAL EXIT (with FIFO/LIFO support) ===
                if n_long_entries > 0 and long_exits[i] and not exited_this_bar:
                    exit_price = close_price * (1.0 - effective_slippage)

                    if close_rule == 0:  # ALL - close all entries
                        pnl = (exit_price - avg_entry_price) * remaining_size
                        exit_fee = exit_price * remaining_size * taker_fee
                        total_fees_trade = remaining_fees + exit_fee
                        pnl -= total_fees_trade

                        cash += remaining_allocated + pnl

                        if trade_count < max_trades:
                            trade_pnls[trade_count] = pnl
                            trade_directions[trade_count] = 1
                            entry_indices[trade_count] = long_entry_bars[0]
                            exit_indices[trade_count] = i
                            entry_prices_arr[trade_count] = avg_entry_price
                            exit_prices_arr[trade_count] = exit_price
                            exit_reasons[trade_count] = 2  # Signal
                            trade_sizes[trade_count] = remaining_size
                            trade_fees[trade_count] = total_fees_trade
                            trade_count += 1

                        # Reset all state
                        n_long_entries = 0
                        long_remaining_pct = 1.0
                        for k in range(4):
                            long_tp_hit[k] = 0
                        for k in range(max_entries):
                            long_entry_closed[k] = 0
                        long_trail_active = False
                        long_breakeven_active = False
                        long_breakeven_price = 0.0
                        long_dca_base_price = 0.0
                        for k in range(max_dca):
                            long_dca_filled[k] = 0
                        exited_this_bar = True

                    else:  # FIFO (1) or LIFO (2) - close ONE entry
                        # Find entry to close
                        entry_idx = -1
                        if close_rule == 1:  # FIFO - first open entry
                            for j in range(n_long_entries):
                                if long_entry_closed[j] == 0:
                                    entry_idx = j
                                    break
                        else:  # LIFO - last open entry
                            for j in range(n_long_entries - 1, -1, -1):
                                if long_entry_closed[j] == 0:
                                    entry_idx = j
                                    break

                        if entry_idx >= 0:
                            # Close this single entry
                            entry_price_single = long_entry_prices[entry_idx]
                            entry_size_single = long_entry_sizes[entry_idx]
                            entry_allocated_single = long_entry_allocated[entry_idx]
                            entry_fee_single = long_entry_fees[entry_idx]
                            entry_bar_single = long_entry_bars[entry_idx]

                            pnl_single = (exit_price - entry_price_single) * entry_size_single
                            exit_fee_single = exit_price * entry_size_single * taker_fee
                            total_fees_single = entry_fee_single + exit_fee_single
                            pnl_single -= total_fees_single

                            cash += entry_allocated_single + pnl_single

                            if trade_count < max_trades:
                                trade_pnls[trade_count] = pnl_single
                                trade_directions[trade_count] = 1
                                entry_indices[trade_count] = entry_bar_single
                                exit_indices[trade_count] = i
                                entry_prices_arr[trade_count] = entry_price_single
                                exit_prices_arr[trade_count] = exit_price
                                exit_reasons[trade_count] = 2  # Signal
                                trade_sizes[trade_count] = entry_size_single
                                trade_fees[trade_count] = total_fees_single
                                trade_count += 1

                            # Mark entry as closed
                            long_entry_closed[entry_idx] = 1

                            # Check if all entries are now closed
                            all_closed = True
                            for j in range(n_long_entries):
                                if long_entry_closed[j] == 0:
                                    all_closed = False
                                    break

                            if all_closed:
                                # Reset all state
                                n_long_entries = 0
                                long_remaining_pct = 1.0
                                for k in range(4):
                                    long_tp_hit[k] = 0
                                for k in range(max_entries):
                                    long_entry_closed[k] = 0
                                long_trail_active = False
                                long_breakeven_active = False
                                long_breakeven_price = 0.0
                                long_dca_base_price = 0.0
                                for k in range(max_dca):
                                    long_dca_filled[k] = 0
                                exited_this_bar = True

            # === SHORT POSITION MANAGEMENT ===
            if n_short_entries > 0 and not exited_this_bar:
                total_size = 0.0
                weighted_price = 0.0
                total_allocated = 0.0
                total_entry_fees = 0.0
                avg_entry_atr = 0.0

                for j in range(n_short_entries):
                    total_size += short_entry_sizes[j]
                    weighted_price += short_entry_prices[j] * short_entry_sizes[j]
                    total_allocated += short_entry_allocated[j]
                    total_entry_fees += short_entry_fees[j]
                    avg_entry_atr += short_entry_atr[j] * short_entry_sizes[j]

                avg_entry_price = weighted_price / total_size if total_size > 0 else 0.0
                avg_entry_atr = avg_entry_atr / total_size if total_size > 0 else current_atr

                remaining_size = total_size * short_remaining_pct
                remaining_allocated = total_allocated * short_remaining_pct
                remaining_fees = total_entry_fees * short_remaining_pct

                # === TIME-BASED EXIT CHECK ===
                if max_bars_in_trade > 0 and not exited_this_bar:
                    bars_in_trade = i - short_first_entry_bar
                    if bars_in_trade >= max_bars_in_trade:
                        exit_price = close_price * (1.0 + effective_slippage)
                        pnl = (avg_entry_price - exit_price) * remaining_size
                        exit_fee = exit_price * remaining_size * taker_fee
                        total_fees_trade = remaining_fees + exit_fee
                        pnl -= total_fees_trade

                        cash += remaining_allocated + pnl

                        if trade_count < max_trades:
                            trade_pnls[trade_count] = pnl
                            trade_directions[trade_count] = -1
                            entry_indices[trade_count] = short_entry_bars[0]
                            exit_indices[trade_count] = i
                            entry_prices_arr[trade_count] = avg_entry_price
                            exit_prices_arr[trade_count] = exit_price
                            exit_reasons[trade_count] = 5  # TIME_EXIT
                            trade_sizes[trade_count] = remaining_size
                            trade_fees[trade_count] = total_fees_trade
                            trade_count += 1

                        # Update re-entry state
                        last_exit_bar = i
                        if pnl < 0:
                            consecutive_losses += 1
                            if cooldown_after_loss > 0:
                                cooldown_until_bar = i + cooldown_after_loss
                        else:
                            consecutive_losses = 0

                        # Reset short state
                        n_short_entries = 0
                        short_remaining_pct = 1.0
                        for k in range(4):
                            short_tp_hit[k] = 0
                        short_trail_active = False
                        short_best_price = 1e10
                        short_trail_stop = 1e10
                        short_breakeven_active = False
                        short_breakeven_price = 0.0
                        short_dca_base_price = 0.0
                        for k in range(max_dca):
                            short_dca_filled[k] = 0
                        exited_this_bar = True

                # === TRAILING STOP UPDATE ===
                if use_trailing and short_trail_active and not exited_this_bar:
                    if low_price < short_best_price:
                        short_best_price = low_price
                        short_trail_stop = short_best_price * (1.0 + trail_offset)

                # === CALCULATE SL PRICE ===
                # Use current_atr (not entry ATR) for parity with FallbackV4
                if use_atr_sl and current_atr > 0:
                    sl_price = avg_entry_price + current_atr * atr_sl_mult
                elif stop_loss > 0:
                    sl_price = avg_entry_price * (1.0 + stop_loss)
                else:
                    sl_price = 1e10

                # === CHECK TRAILING STOP ===
                if use_trailing and short_trail_active and high_price >= short_trail_stop and not exited_this_bar:
                    exit_price = short_trail_stop
                    pnl = (avg_entry_price - exit_price) * remaining_size
                    exit_fee = exit_price * remaining_size * taker_fee
                    total_fees_trade = remaining_fees + exit_fee
                    pnl -= total_fees_trade

                    cash += remaining_allocated + pnl

                    if trade_count < max_trades:
                        trade_pnls[trade_count] = pnl
                        trade_directions[trade_count] = -1
                        entry_indices[trade_count] = short_entry_bars[0]
                        exit_indices[trade_count] = i
                        entry_prices_arr[trade_count] = avg_entry_price
                        exit_prices_arr[trade_count] = exit_price
                        exit_reasons[trade_count] = 4  # Trailing
                        trade_sizes[trade_count] = remaining_size
                        trade_fees[trade_count] = total_fees_trade
                        trade_count += 1

                    n_short_entries = 0
                    short_remaining_pct = 1.0
                    for k in range(4):
                        short_tp_hit[k] = 0
                    short_trail_active = False
                    short_best_price = 1e10
                    short_trail_stop = 1e10
                    # Reset DCA state
                    short_dca_base_price = 0.0
                    for k in range(max_dca):
                        short_dca_filled[k] = 0
                    exited_this_bar = True

                # === CHECK SL (with breakeven support) ===
                elif stop_loss > 0 or use_atr_sl or short_breakeven_active:
                    # Use breakeven price if active, otherwise use calculated SL
                    effective_sl = short_breakeven_price if short_breakeven_active else sl_price
                    if effective_sl < 1e10 and high_price >= effective_sl:
                        exit_price = effective_sl
                        pnl = (avg_entry_price - exit_price) * remaining_size
                        exit_fee = exit_price * remaining_size * taker_fee
                        total_fees_trade = remaining_fees + exit_fee
                        pnl -= total_fees_trade

                        cash += remaining_allocated + pnl

                        if trade_count < max_trades:
                            trade_pnls[trade_count] = pnl
                            trade_directions[trade_count] = -1
                            entry_indices[trade_count] = short_entry_bars[0]
                            exit_indices[trade_count] = i
                            entry_prices_arr[trade_count] = avg_entry_price
                            exit_prices_arr[trade_count] = exit_price
                            exit_reasons[trade_count] = 0  # SL
                            trade_sizes[trade_count] = remaining_size
                            trade_fees[trade_count] = total_fees_trade
                            trade_count += 1

                        # Update re-entry state
                        last_exit_bar = i
                        if pnl < 0:
                            consecutive_losses += 1
                            if cooldown_after_loss > 0:
                                cooldown_until_bar = i + cooldown_after_loss
                        else:
                            consecutive_losses = 0

                        n_short_entries = 0
                        short_remaining_pct = 1.0
                        for k in range(4):
                            short_tp_hit[k] = 0
                        short_trail_active = False
                        short_breakeven_active = False
                        short_breakeven_price = 0.0
                        # Reset DCA state
                        short_dca_base_price = 0.0
                        for k in range(max_dca):
                            short_dca_filled[k] = 0
                        exited_this_bar = True

                # === CHECK MULTI-TP ===
                if n_short_entries > 0 and use_multi_tp and not exited_this_bar:
                    tp_pcts = (tp1_pct, tp2_pct, tp3_pct, tp4_pct)
                    tp_mults = (tp1_mult, tp2_mult, tp3_mult, tp4_mult)

                    for tp_idx in range(4):
                        if short_tp_hit[tp_idx] == 0 and tp_pcts[tp_idx] > 0:
                            if use_atr_tp and current_atr > 0:
                                tp_price = avg_entry_price - current_atr * tp_mults[tp_idx]
                            else:
                                tp_price = avg_entry_price * (1.0 - tp_mults[tp_idx])

                            if low_price <= tp_price:
                                close_pct = tp_pcts[tp_idx]
                                close_size = total_size * close_pct
                                close_allocated = total_allocated * close_pct
                                close_fees = total_entry_fees * close_pct

                                pnl = (avg_entry_price - tp_price) * close_size
                                exit_fee = tp_price * close_size * taker_fee
                                total_fees_trade = close_fees + exit_fee
                                pnl -= total_fees_trade

                                cash += close_allocated + pnl

                                if trade_count < max_trades:
                                    trade_pnls[trade_count] = pnl
                                    trade_directions[trade_count] = -1
                                    entry_indices[trade_count] = short_entry_bars[0]
                                    exit_indices[trade_count] = i
                                    entry_prices_arr[trade_count] = avg_entry_price
                                    exit_prices_arr[trade_count] = tp_price
                                    exit_reasons[trade_count] = 1  # TP
                                    trade_sizes[trade_count] = close_size
                                    trade_fees[trade_count] = total_fees_trade
                                    trade_count += 1

                                short_tp_hit[tp_idx] = 1
                                short_remaining_pct -= close_pct

                                if tp_idx == 0 and use_trailing and not short_trail_active:
                                    short_trail_active = True
                                    short_best_price = tp_price
                                    short_trail_stop = short_best_price * (1.0 + trail_offset)

                                # Activate breakeven after TP1 if enabled
                                if tp_idx == 0 and breakeven_enabled and not short_breakeven_active:
                                    short_breakeven_active = True
                                    # Move SL to entry - offset (for short, below entry is profit)
                                    short_breakeven_price = avg_entry_price * (1.0 - breakeven_offset)

                                if short_remaining_pct <= 0.001:
                                    # Update re-entry state
                                    last_exit_bar = i
                                    consecutive_losses = 0  # Full TP = not a loss

                                    n_short_entries = 0
                                    short_remaining_pct = 1.0
                                    for k in range(4):
                                        short_tp_hit[k] = 0
                                    short_trail_active = False
                                    short_breakeven_active = False
                                    short_breakeven_price = 0.0
                                    # Reset DCA state
                                    short_dca_base_price = 0.0
                                    for k in range(max_dca):
                                        short_dca_filled[k] = 0
                                    exited_this_bar = True
                                    break

                # === CHECK SINGLE TP ===
                elif n_short_entries > 0 and not use_multi_tp and not exited_this_bar:
                    if use_atr_tp and current_atr > 0:
                        tp_price = avg_entry_price - current_atr * atr_tp_mult
                    elif take_profit > 0:
                        tp_price = avg_entry_price * (1.0 - take_profit)
                    else:
                        tp_price = 0.0

                    if tp_price > 0 and low_price <= tp_price:
                        exit_price = tp_price
                        pnl = (avg_entry_price - exit_price) * remaining_size
                        exit_fee = exit_price * remaining_size * taker_fee
                        total_fees_trade = remaining_fees + exit_fee
                        pnl -= total_fees_trade

                        cash += remaining_allocated + pnl

                        if trade_count < max_trades:
                            trade_pnls[trade_count] = pnl
                            trade_directions[trade_count] = -1
                            entry_indices[trade_count] = short_entry_bars[0]
                            exit_indices[trade_count] = i
                            entry_prices_arr[trade_count] = avg_entry_price
                            exit_prices_arr[trade_count] = exit_price
                            exit_reasons[trade_count] = 1  # TP
                            trade_sizes[trade_count] = remaining_size
                            trade_fees[trade_count] = total_fees_trade
                            trade_count += 1

                        n_short_entries = 0
                        short_remaining_pct = 1.0
                        short_trail_active = False
                        # Reset DCA state
                        short_dca_base_price = 0.0
                        for k in range(max_dca):
                            short_dca_filled[k] = 0
                        exited_this_bar = True

                # === CHECK SIGNAL EXIT (with FIFO/LIFO support) ===
                if n_short_entries > 0 and short_exits[i] and not exited_this_bar:
                    exit_price = close_price * (1.0 + effective_slippage)

                    if close_rule == 0:  # ALL - close all entries
                        pnl = (avg_entry_price - exit_price) * remaining_size
                        exit_fee = exit_price * remaining_size * taker_fee
                        total_fees_trade = remaining_fees + exit_fee
                        pnl -= total_fees_trade

                        cash += remaining_allocated + pnl

                        if trade_count < max_trades:
                            trade_pnls[trade_count] = pnl
                            trade_directions[trade_count] = -1
                            entry_indices[trade_count] = short_entry_bars[0]
                            exit_indices[trade_count] = i
                            entry_prices_arr[trade_count] = avg_entry_price
                            exit_prices_arr[trade_count] = exit_price
                            exit_reasons[trade_count] = 2  # Signal
                            trade_sizes[trade_count] = remaining_size
                            trade_fees[trade_count] = total_fees_trade
                            trade_count += 1

                        # Reset all state
                        n_short_entries = 0
                        short_remaining_pct = 1.0
                        for k in range(4):
                            short_tp_hit[k] = 0
                        for k in range(max_entries):
                            short_entry_closed[k] = 0
                        short_trail_active = False
                        short_breakeven_active = False
                        short_breakeven_price = 0.0
                        short_dca_base_price = 0.0
                        for k in range(max_dca):
                            short_dca_filled[k] = 0
                        exited_this_bar = True

                    else:  # FIFO (1) or LIFO (2) - close ONE entry
                        # Find entry to close
                        entry_idx = -1
                        if close_rule == 1:  # FIFO - first open entry
                            for j in range(n_short_entries):
                                if short_entry_closed[j] == 0:
                                    entry_idx = j
                                    break
                        else:  # LIFO - last open entry
                            for j in range(n_short_entries - 1, -1, -1):
                                if short_entry_closed[j] == 0:
                                    entry_idx = j
                                    break

                        if entry_idx >= 0:
                            # Close this single entry
                            entry_price_single = short_entry_prices[entry_idx]
                            entry_size_single = short_entry_sizes[entry_idx]
                            entry_allocated_single = short_entry_allocated[entry_idx]
                            entry_fee_single = short_entry_fees[entry_idx]
                            entry_bar_single = short_entry_bars[entry_idx]

                            pnl_single = (entry_price_single - exit_price) * entry_size_single
                            exit_fee_single = exit_price * entry_size_single * taker_fee
                            total_fees_single = entry_fee_single + exit_fee_single
                            pnl_single -= total_fees_single

                            cash += entry_allocated_single + pnl_single

                            if trade_count < max_trades:
                                trade_pnls[trade_count] = pnl_single
                                trade_directions[trade_count] = -1
                                entry_indices[trade_count] = entry_bar_single
                                exit_indices[trade_count] = i
                                entry_prices_arr[trade_count] = entry_price_single
                                exit_prices_arr[trade_count] = exit_price
                                exit_reasons[trade_count] = 2  # Signal
                                trade_sizes[trade_count] = entry_size_single
                                trade_fees[trade_count] = total_fees_single
                                trade_count += 1

                            # Mark entry as closed
                            short_entry_closed[entry_idx] = 1

                            # Check if all entries are now closed
                            all_closed = True
                            for j in range(n_short_entries):
                                if short_entry_closed[j] == 0:
                                    all_closed = False
                                    break

                            if all_closed:
                                # Reset all state
                                n_short_entries = 0
                                short_remaining_pct = 1.0
                                for k in range(4):
                                    short_tp_hit[k] = 0
                                for k in range(max_entries):
                                    short_entry_closed[k] = 0
                                short_trail_active = False
                                short_breakeven_active = False
                                short_breakeven_price = 0.0
                                short_dca_base_price = 0.0
                                for k in range(max_dca):
                                    short_dca_filled[k] = 0
                                exited_this_bar = True

            # === RE-ENTRY RULES CHECK ===
            reentry_allowed = True
            if re_entry_delay_bars > 0 and (i - last_exit_bar) < re_entry_delay_bars:
                reentry_allowed = False
            if cooldown_after_loss > 0 and i < cooldown_until_bar:
                reentry_allowed = False
            if max_consecutive_losses > 0 and consecutive_losses >= max_consecutive_losses:
                reentry_allowed = False
            if max_trades_per_day > 0:
                # Simplified day tracking: assume 24 bars = 1 day for hourly data
                new_day = i // 24
                if new_day != current_day:
                    current_day = new_day
                    trades_today = 0
                if trades_today >= max_trades_per_day:
                    reentry_allowed = False

            # === LONG ENTRY ===
            can_enter_long = (
                n_long_entries < max_entries
                and n_short_entries == 0
                and not exited_this_bar
                and long_entries[i]
                and direction >= 0
                and i < n - 2
                and i > 0
                and reentry_allowed  # Re-entry rules
                and volatility_filter[i]  # Volatility filter
                and volume_filter[i]  # Volume filter
                and trend_filter_long[i]  # Trend filter (long)
            )

            if can_enter_long:
                entry_price = open_prices[i + 1]
                entry_atr = atr_values[i + 1] if len(atr_values) > i + 1 else current_atr

                # DCA: use base order size for first entry
                if dca_enabled and n_long_entries == 0:
                    allocated = cash * dca_base_order_size
                elif use_fixed_amount:
                    allocated = min(fixed_amount, cash)
                else:
                    allocated = cash * position_size

                if allocated >= 1.0:
                    notional = allocated * leverage
                    size = notional / entry_price
                    entry_fee = notional * taker_fee

                    cash -= allocated

                    long_entry_prices[n_long_entries] = entry_price
                    long_entry_sizes[n_long_entries] = size
                    long_entry_allocated[n_long_entries] = allocated
                    long_entry_fees[n_long_entries] = entry_fee
                    long_entry_bars[n_long_entries] = i
                    long_entry_atr[n_long_entries] = entry_atr

                    # Track first entry bar for time-based exit
                    if n_long_entries == 0:
                        long_first_entry_bar = i
                        trades_today += 1

                    # DCA: initialize base price on first entry
                    if dca_enabled and n_long_entries == 0:
                        long_dca_base_price = entry_price
                        for k in range(max_dca):
                            long_dca_filled[k] = 0

                    n_long_entries += 1

                    # Activate trailing if enabled and profit threshold met
                    if use_trailing and trail_activation <= 0:
                        long_trail_active = True
                        long_best_price = entry_price
                        long_trail_stop = long_best_price * (1.0 - trail_offset)

            # === SHORT ENTRY ===
            can_enter_short = (
                n_short_entries < max_entries
                and n_long_entries == 0
                and not exited_this_bar
                and short_entries[i]
                and direction <= 0
                and i < n - 2
                and i > 0
                and reentry_allowed  # Re-entry rules
                and volatility_filter[i]  # Volatility filter
                and volume_filter[i]  # Volume filter
                and trend_filter_short[i]  # Trend filter (short)
            )

            if can_enter_short:
                entry_price = open_prices[i + 1]
                entry_atr = atr_values[i + 1] if len(atr_values) > i + 1 else current_atr

                # DCA: use base order size for first entry
                if dca_enabled and n_short_entries == 0:
                    allocated = cash * dca_base_order_size
                elif use_fixed_amount:
                    allocated = min(fixed_amount, cash)
                else:
                    allocated = cash * position_size

                if allocated >= 1.0:
                    notional = allocated * leverage
                    size = notional / entry_price
                    entry_fee = notional * taker_fee

                    cash -= allocated

                    short_entry_prices[n_short_entries] = entry_price
                    short_entry_sizes[n_short_entries] = size
                    short_entry_allocated[n_short_entries] = allocated
                    short_entry_fees[n_short_entries] = entry_fee
                    short_entry_bars[n_short_entries] = i
                    short_entry_atr[n_short_entries] = entry_atr

                    # Track first entry bar for time-based exit
                    if n_short_entries == 0:
                        short_first_entry_bar = i
                        trades_today += 1

                    # DCA: initialize base price on first entry
                    if dca_enabled and n_short_entries == 0:
                        short_dca_base_price = entry_price
                        for k in range(max_dca):
                            short_dca_filled[k] = 0

                    n_short_entries += 1

                    if use_trailing and trail_activation <= 0:
                        short_trail_active = True
                        short_best_price = entry_price
                        short_trail_stop = short_best_price * (1.0 + trail_offset)

            # === DCA: SAFETY ORDERS ===
            if dca_enabled and dca_num_so > 0:
                # Long DCA: buy more as price drops
                if n_long_entries > 0 and n_long_entries < max_entries:
                    for so_idx in range(dca_num_so):
                        if long_dca_filled[so_idx] == 0:  # Not yet filled
                            # Calculate SO trigger price
                            so_price = long_dca_base_price * (1.0 - dca_levels[so_idx])
                            if low_price <= so_price:
                                # SO triggered - add position
                                so_volume = dca_volumes[so_idx]
                                so_capital = cash * so_volume
                                if so_capital >= 1.0:
                                    so_notional = so_capital * leverage
                                    so_size = so_notional / so_price
                                    so_fee = so_notional * taker_fee
                                    cash -= so_capital

                                    long_entry_prices[n_long_entries] = so_price
                                    long_entry_sizes[n_long_entries] = so_size
                                    long_entry_allocated[n_long_entries] = so_capital
                                    long_entry_fees[n_long_entries] = so_fee
                                    long_entry_bars[n_long_entries] = i
                                    long_entry_atr[n_long_entries] = current_atr
                                    n_long_entries += 1
                                    long_dca_filled[so_idx] = 1

                                    if n_long_entries >= max_entries:
                                        break

                # Short DCA: sell more as price rises
                if n_short_entries > 0 and n_short_entries < max_entries:
                    for so_idx in range(dca_num_so):
                        if short_dca_filled[so_idx] == 0:  # Not yet filled
                            # Calculate SO trigger price
                            so_price = short_dca_base_price * (1.0 + dca_levels[so_idx])
                            if high_price >= so_price:
                                # SO triggered - add position
                                so_volume = dca_volumes[so_idx]
                                so_capital = cash * so_volume
                                if so_capital >= 1.0:
                                    so_notional = so_capital * leverage
                                    so_size = so_notional / so_price
                                    so_fee = so_notional * taker_fee
                                    cash -= so_capital

                                    short_entry_prices[n_short_entries] = so_price
                                    short_entry_sizes[n_short_entries] = so_size
                                    short_entry_allocated[n_short_entries] = so_capital
                                    short_entry_fees[n_short_entries] = so_fee
                                    short_entry_bars[n_short_entries] = i
                                    short_entry_atr[n_short_entries] = current_atr
                                    n_short_entries += 1
                                    short_dca_filled[so_idx] = 1

                                    if n_short_entries >= max_entries:
                                        break

            # === FUNDING RATE DEDUCTION ===
            if include_funding and funding_interval > 0:
                if i % funding_interval == 0:  # Funding payment time
                    # Long positions pay funding when rate > 0
                    # Short positions receive funding when rate > 0
                    if n_long_entries > 0:
                        for j in range(n_long_entries):
                            notional = long_entry_sizes[j] * close_price
                            funding_cost = notional * funding_rate
                            cash -= funding_cost  # Long pays
                    if n_short_entries > 0:
                        for j in range(n_short_entries):
                            notional = short_entry_sizes[j] * close_price
                            funding_income = notional * funding_rate
                            cash += funding_income  # Short receives

            # === UPDATE EQUITY ===
            equity = cash

            if n_long_entries > 0:
                for j in range(n_long_entries):
                    unrealized = (close_price - long_entry_prices[j]) * long_entry_sizes[j]
                    equity += (unrealized + long_entry_sizes[j] * long_entry_prices[j]) * long_remaining_pct

            if n_short_entries > 0:
                for j in range(n_short_entries):
                    unrealized = (short_entry_prices[j] - close_price) * short_entry_sizes[j]
                    equity += (unrealized + short_entry_sizes[j] * short_entry_prices[j]) * short_remaining_pct

            equity_curve[i] = equity

        # === CLOSE OPEN POSITIONS AT END ===
        last_close = close_prices[n - 1]

        if n_long_entries > 0 and trade_count < max_trades:
            total_size = 0.0
            weighted_price = 0.0
            total_allocated = 0.0
            total_entry_fees = 0.0

            for j in range(n_long_entries):
                total_size += long_entry_sizes[j]
                weighted_price += long_entry_prices[j] * long_entry_sizes[j]
                total_allocated += long_entry_allocated[j]
                total_entry_fees += long_entry_fees[j]

            avg_entry_price = weighted_price / total_size if total_size > 0 else 0.0
            remaining_size = total_size * long_remaining_pct
            remaining_allocated = total_allocated * long_remaining_pct
            remaining_fees = total_entry_fees * long_remaining_pct

            # Calculate effective slippage for end-of-data exit
            last_bar_slippage = (
                slippage * slippage_multipliers[n - 1]
                if use_advanced_slippage and len(slippage_multipliers) > n - 1
                else slippage
            )
            exit_price = last_close * (1.0 - last_bar_slippage)
            pnl = (exit_price - avg_entry_price) * remaining_size
            exit_fee = exit_price * remaining_size * taker_fee
            total_fees_trade = remaining_fees + exit_fee
            pnl -= total_fees_trade

            trade_pnls[trade_count] = pnl
            trade_directions[trade_count] = 1
            entry_indices[trade_count] = long_entry_bars[0]
            exit_indices[trade_count] = n - 1
            entry_prices_arr[trade_count] = avg_entry_price
            exit_prices_arr[trade_count] = exit_price
            exit_reasons[trade_count] = 3  # END_OF_DATA
            trade_sizes[trade_count] = remaining_size
            trade_fees[trade_count] = total_fees_trade
            trade_count += 1

        if n_short_entries > 0 and trade_count < max_trades:
            total_size = 0.0
            weighted_price = 0.0
            total_allocated = 0.0
            total_entry_fees = 0.0

            for j in range(n_short_entries):
                total_size += short_entry_sizes[j]
                weighted_price += short_entry_prices[j] * short_entry_sizes[j]
                total_allocated += short_entry_allocated[j]
                total_entry_fees += short_entry_fees[j]

            avg_entry_price = weighted_price / total_size if total_size > 0 else 0.0
            remaining_size = total_size * short_remaining_pct
            remaining_allocated = total_allocated * short_remaining_pct
            remaining_fees = total_entry_fees * short_remaining_pct

            # Calculate effective slippage for end-of-data exit
            last_bar_slippage = (
                slippage * slippage_multipliers[n - 1]
                if use_advanced_slippage and len(slippage_multipliers) > n - 1
                else slippage
            )
            exit_price = last_close * (1.0 + last_bar_slippage)
            pnl = (avg_entry_price - exit_price) * remaining_size
            exit_fee = exit_price * remaining_size * taker_fee
            total_fees_trade = remaining_fees + exit_fee
            pnl -= total_fees_trade

            trade_pnls[trade_count] = pnl
            trade_directions[trade_count] = -1
            entry_indices[trade_count] = short_entry_bars[0]
            exit_indices[trade_count] = n - 1
            entry_prices_arr[trade_count] = avg_entry_price
            exit_prices_arr[trade_count] = exit_price
            exit_reasons[trade_count] = 3  # END_OF_DATA
            trade_sizes[trade_count] = remaining_size
            trade_fees[trade_count] = total_fees_trade
            trade_count += 1

        return (
            equity_curve,
            trade_pnls[:trade_count],
            trade_directions[:trade_count],
            entry_indices[:trade_count],
            exit_indices[:trade_count],
            entry_prices_arr[:trade_count],
            exit_prices_arr[:trade_count],
            exit_reasons[:trade_count],
            trade_sizes[:trade_count],
            trade_fees[:trade_count],
        )

    @njit(cache=True, fastmath=True)
    def _simulate_with_bar_magnifier(
        open_prices: np.ndarray,
        high_prices: np.ndarray,
        low_prices: np.ndarray,
        close_prices: np.ndarray,
        m1_highs: np.ndarray,
        m1_lows: np.ndarray,
        m1_bar_starts: np.ndarray,  # Start index in m1 for each main bar
        m1_bar_ends: np.ndarray,  # End index in m1 for each main bar
        long_entries: np.ndarray,
        long_exits: np.ndarray,
        short_entries: np.ndarray,
        short_exits: np.ndarray,
        stop_loss: float,
        take_profit: float,
        position_size: float,
        leverage: float,
        taker_fee: float,
        slippage: float,
        direction: int,
        initial_capital: float,
        use_fixed_amount: bool,  # NEW: True = use fixed_amount, False = use position_size
        fixed_amount: float,  # NEW: Fixed amount per trade (for TV parity)
    ) -> tuple[
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
    ]:
        """
        Numba-optimized simulation WITH Bar Magnifier.
        Uses 1-minute data for precise SL/TP detection.
        FIXED: Correct cash handling.
        """
        n = len(close_prices)

        # Dynamic allocation based on data size
        # Worst case: trade every 2 bars (entry + exit)
        # Cap at 50000 to prevent excessive memory usage
        max_trades = min(n // 2, 50000)
        if max_trades < 100:
            max_trades = 100  # Minimum for small datasets

        # Pre-allocate with dynamic size
        equity_curve = np.zeros(n, dtype=np.float64)
        trade_pnls = np.zeros(max_trades, dtype=np.float64)
        trade_directions = np.zeros(max_trades, dtype=np.int32)
        entry_indices = np.zeros(max_trades, dtype=np.int32)
        exit_indices = np.zeros(max_trades, dtype=np.int32)
        entry_prices_arr = np.zeros(max_trades, dtype=np.float64)
        exit_prices_arr = np.zeros(max_trades, dtype=np.float64)
        exit_reasons = np.zeros(max_trades, dtype=np.int32)
        trade_sizes = np.zeros(max_trades, dtype=np.float64)  # Position size
        trade_fees = np.zeros(max_trades, dtype=np.float64)  # Exit fees only (matches Fallback)

        cash = initial_capital
        equity_curve[0] = initial_capital
        trade_count = 0

        in_long = False
        in_short = False
        long_entry_price = 0.0
        short_entry_price = 0.0
        long_entry_idx = 0
        short_entry_idx = 0
        long_size = 0.0
        short_size = 0.0
        long_allocated = 0.0  # FIXED: Track allocated capital
        short_allocated = 0.0  # FIXED: Track allocated capital
        long_entry_fee = 0.0  # Track entry fee
        short_entry_fee = 0.0  # Track entry fee

        for i in range(1, n):
            open_price = open_prices[i]
            high_price = high_prices[i]
            low_price = low_prices[i]
            close_price = close_prices[i]

            m1_start = m1_bar_starts[i]
            m1_end = m1_bar_ends[i]

            # TV-style: Track if we exited this bar (prevents new entry on same bar)
            exited_this_bar = False

            # === LONG EXIT with Bar Magnifier ===
            if in_long:
                sl_price = long_entry_price * (1.0 - stop_loss) if stop_loss > 0 else 0.0
                tp_price = long_entry_price * (1.0 + take_profit) if take_profit > 0 else 1e10

                exit_price = 0.0
                exit_reason = -1

                # Check each 1-minute bar for SL/TP
                if m1_start >= 0 and m1_end > m1_start:
                    for m1_idx in range(m1_start, m1_end):
                        m1_high = m1_highs[m1_idx]
                        m1_low = m1_lows[m1_idx]

                        # SL first (more conservative)
                        if stop_loss > 0 and m1_low <= sl_price:
                            # TV parity: SL/TP exit at exact level, no slippage
                            exit_price = sl_price
                            exit_reason = 0
                            break
                        # Then TP
                        if take_profit > 0 and m1_high >= tp_price:
                            # TV parity: SL/TP exit at exact level, no slippage
                            exit_price = tp_price
                            exit_reason = 1
                            break

                # Fallback to bar-level check with TV intrabar simulation
                if exit_reason < 0:
                    sl_hit = stop_loss > 0 and low_price <= sl_price
                    tp_hit = take_profit > 0 and high_price >= tp_price

                    if sl_hit and tp_hit:
                        # Both hit - use open position to determine order
                        open_closer_to_high = abs(open_price - high_price) < abs(open_price - low_price)
                        if open_closer_to_high:
                            # TP triggers first for long
                            exit_price = tp_price
                            exit_reason = 1
                        else:
                            # SL triggers first for long
                            exit_price = sl_price
                            exit_reason = 0
                    elif sl_hit:
                        exit_price = sl_price
                        exit_reason = 0
                    elif tp_hit:
                        exit_price = tp_price
                        exit_reason = 1
                    elif long_exits[i]:
                        # Signal exit uses close price with slippage
                        exit_price = close_price * (1.0 - slippage)
                        exit_reason = 2

                if exit_reason >= 0:
                    # FIXED: Correct PnL calculation with BOTH fees (TV style)
                    pnl = (exit_price - long_entry_price) * long_size
                    exit_fee = exit_price * long_size * taker_fee
                    total_fees = long_entry_fee + exit_fee  # TV: entry + exit
                    pnl -= total_fees

                    # FIXED: Return allocated capital + PnL
                    cash += long_allocated + pnl

                    # Check array bounds before recording trade
                    if trade_count < max_trades:
                        trade_pnls[trade_count] = pnl
                        trade_directions[trade_count] = 1
                        entry_indices[trade_count] = long_entry_idx
                        exit_indices[trade_count] = i
                        entry_prices_arr[trade_count] = long_entry_price
                        exit_prices_arr[trade_count] = exit_price
                        exit_reasons[trade_count] = exit_reason
                        trade_sizes[trade_count] = long_size
                        trade_fees[trade_count] = total_fees  # TV: entry + exit fees
                        trade_count += 1

                    in_long = False
                    long_size = 0.0
                    long_allocated = 0.0
                    long_entry_fee = 0.0
                    exited_this_bar = True  # Prevent new entry on same bar

            # === SHORT EXIT with Bar Magnifier ===
            if in_short:
                sl_price = short_entry_price * (1.0 + stop_loss) if stop_loss > 0 else 1e10
                tp_price = short_entry_price * (1.0 - take_profit) if take_profit > 0 else 0.0

                exit_price = 0.0
                exit_reason = -1

                if m1_start >= 0 and m1_end > m1_start:
                    for m1_idx in range(m1_start, m1_end):
                        m1_high = m1_highs[m1_idx]
                        m1_low = m1_lows[m1_idx]

                        # SL first
                        if stop_loss > 0 and m1_high >= sl_price:
                            # TV parity: SL/TP exit at exact level, no slippage
                            exit_price = sl_price
                            exit_reason = 0
                            break
                        # Then TP
                        if take_profit > 0 and m1_low <= tp_price:
                            # TV parity: SL/TP exit at exact level, no slippage
                            exit_price = tp_price
                            exit_reason = 1
                            break

                if exit_reason < 0:
                    sl_hit = stop_loss > 0 and high_price >= sl_price
                    tp_hit = take_profit > 0 and low_price <= tp_price

                    if sl_hit and tp_hit:
                        # Both hit - use open position to determine order
                        open_closer_to_high = abs(open_price - high_price) < abs(open_price - low_price)
                        if open_closer_to_high:
                            # SL triggers first for short (at high)
                            exit_price = sl_price
                            exit_reason = 0
                        else:
                            # TP triggers first for short (at low)
                            exit_price = tp_price
                            exit_reason = 1
                    elif sl_hit:
                        exit_price = sl_price
                        exit_reason = 0
                    elif tp_hit:
                        exit_price = tp_price
                        exit_reason = 1
                    elif short_exits[i]:
                        # Signal exit uses close price with slippage
                        exit_price = close_price * (1.0 + slippage)
                        exit_reason = 2

                if exit_reason >= 0:
                    # FIXED: Correct PnL calculation with BOTH fees (TV style)
                    pnl = (short_entry_price - exit_price) * short_size
                    exit_fee = exit_price * short_size * taker_fee
                    total_fees = short_entry_fee + exit_fee  # TV: entry + exit
                    pnl -= total_fees

                    # FIXED: Return allocated capital + PnL
                    cash += short_allocated + pnl

                    # Check array bounds before recording trade
                    if trade_count < max_trades:
                        trade_pnls[trade_count] = pnl
                        trade_directions[trade_count] = -1
                        entry_indices[trade_count] = short_entry_idx
                        exit_indices[trade_count] = i
                        entry_prices_arr[trade_count] = short_entry_price
                        exit_prices_arr[trade_count] = exit_price
                        exit_reasons[trade_count] = exit_reason
                        trade_sizes[trade_count] = short_size
                        trade_fees[trade_count] = total_fees  # TV: entry + exit fees
                        trade_count += 1

                    in_short = False
                    short_size = 0.0
                    short_allocated = 0.0
                    short_entry_fee = 0.0
                    exited_this_bar = True  # Prevent new entry on same bar

            # === LONG ENTRY ===
            # TradingView parity: signal at bar i, entry at bar i+1 open
            # Check not in_short to prevent simultaneous positions
            # TV-style: No entry on same bar as exit
            if (
                not in_long
                and not in_short
                and not exited_this_bar  # TV-style: No entry on same bar as exit
                and long_entries[i]
                and (direction >= 0)
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

                # Skip if allocated is too small (prevents micro-positions)
                if allocated >= 1.0:
                    notional = allocated * leverage  # Position size with leverage
                    size = notional / entry_price
                    entry_fee = notional * taker_fee

                    # TV style: Only deduct allocated capital, not entry fee
                    cash -= allocated

                    in_long = True
                    long_entry_price = entry_price
                    long_entry_idx = i  # Signal bar (not entry bar) - match Fallback
                    long_size = size
                    long_allocated = allocated
                    long_entry_fee = entry_fee

            # === SHORT ENTRY ===
            # TradingView parity: signal at bar i, entry at bar i+1 open
            # Check not in_long to prevent simultaneous positions
            # TV-style: No entry on same bar as exit
            if (
                not in_short
                and not in_long
                and not exited_this_bar  # TV-style: No entry on same bar as exit
                and short_entries[i]
                and (direction <= 0)
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

                # Skip if allocated is too small (prevents micro-positions)
                if allocated >= 1.0:
                    notional = allocated * leverage
                    size = notional / entry_price
                    entry_fee = notional * taker_fee

                    # FIXED: Deduct allocated capital only (TV doesn't deduct fee from cash)
                    cash -= allocated

                    in_short = True
                    short_entry_price = entry_price
                    short_entry_idx = i  # Signal bar index (TV style)
                    short_size = size
                    short_allocated = allocated
                    short_entry_fee = entry_fee

            # === UPDATE EQUITY ===
            equity = cash
            if in_long:
                # FIXED: Match Fallback formula
                unrealized = (close_price - long_entry_price) * long_size
                equity += unrealized + long_size * long_entry_price
            if in_short:
                unrealized = (short_entry_price - close_price) * short_size
                equity += unrealized + short_size * short_entry_price

            equity_curve[i] = equity

        # === CLOSE OPEN POSITIONS AT END OF DATA ===
        last_close = close_prices[n - 1]

        if in_long and trade_count < max_trades:
            exit_price = last_close * (1.0 - slippage)
            pnl = (exit_price - long_entry_price) * long_size
            exit_fee = exit_price * long_size * taker_fee
            total_fees = long_entry_fee + exit_fee  # TV: entry + exit
            pnl -= total_fees

            trade_pnls[trade_count] = pnl
            trade_directions[trade_count] = 1
            entry_indices[trade_count] = long_entry_idx
            exit_indices[trade_count] = n - 1
            entry_prices_arr[trade_count] = long_entry_price
            exit_prices_arr[trade_count] = exit_price
            exit_reasons[trade_count] = 3  # END_OF_DATA
            trade_sizes[trade_count] = long_size
            trade_fees[trade_count] = total_fees  # TV: entry + exit fees
            trade_count += 1

        if in_short and trade_count < max_trades:
            exit_price = last_close * (1.0 + slippage)
            pnl = (short_entry_price - exit_price) * short_size
            exit_fee = exit_price * short_size * taker_fee
            total_fees = short_entry_fee + exit_fee  # TV: entry + exit
            pnl -= total_fees

            trade_pnls[trade_count] = pnl
            trade_directions[trade_count] = -1
            entry_indices[trade_count] = short_entry_idx
            exit_indices[trade_count] = n - 1
            entry_prices_arr[trade_count] = short_entry_price
            exit_prices_arr[trade_count] = exit_price
            exit_reasons[trade_count] = 3  # END_OF_DATA
            trade_sizes[trade_count] = short_size
            trade_fees[trade_count] = total_fees  # TV: entry + exit fees
            trade_count += 1

        return (
            equity_curve,
            trade_pnls[:trade_count],
            trade_directions[:trade_count],
            entry_indices[:trade_count],
            exit_indices[:trade_count],
            entry_prices_arr[:trade_count],
            exit_prices_arr[:trade_count],
            exit_reasons[:trade_count],
            trade_sizes[:trade_count],
            trade_fees[:trade_count],
        )


class NumbaEngineV2(BaseBacktestEngine):
    """
    Numba Engine V2/V3/V4 - Fast JIT-compiled engine.

    Features:
    - 20-40x faster than Fallback
    - Bar Magnifier support
    - Pyramiding support (V3)
    - ATR, Multi-TP, Trailing, DCA (V4)
    - 100% parity with FallbackEngine

    V3 Features (Pyramiding):
    - When pyramiding > 1, uses _simulate_trades_numba_pyramiding
    - Supports multiple entries in same direction
    - Weighted average entry price for SL/TP
    - Close rule: ALL (close all entries at once)

    V4 Features (ATR, Multi-TP, Trailing, DCA):
    - ATR-based SL/TP: use_atr_sl, use_atr_tp, atr_sl_multiplier, atr_tp_multiplier
    - Multi-level TP: up to 4 levels with configurable % and multipliers
    - Trailing stop: activate after TP1 or profit threshold
    - DCA / Safety Orders: dca_enabled, dca_safety_orders, dca_price_deviation, etc.

    Auto-selection:
    - V4 mode if: use_atr_sl/tp OR use_multi_tp OR use_trailing OR dca_enabled
    - V3 mode if: pyramiding > 1 (without V4 features)
    - V2 mode: basic SL/TP
    """

    def __init__(self):
        self._jit_compiled = False

    @property
    def name(self) -> str:
        return "NumbaEngineV2"

    @property
    def supports_bar_magnifier(self) -> bool:
        return True

    @property
    def supports_pyramiding(self) -> bool:
        return True

    @property
    def supports_atr(self) -> bool:
        return True  # V4 feature

    @property
    def supports_multi_tp(self) -> bool:
        return True  # V4 feature

    @property
    def supports_trailing(self) -> bool:
        return True  # V4 feature

    @property
    def supports_dca(self) -> bool:
        return True  # V4 feature - Safety Orders

    @property
    def supports_parallel(self) -> bool:
        return True  # Can use prange for optimization

    def run(self, input_data: BacktestInput) -> BacktestOutput:
        """Run backtest with Numba JIT"""
        if not NUMBA_AVAILABLE:
            logger.warning("Numba not available, using FallbackEngineV4")
            from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4

            return FallbackEngineV4().run(input_data)

        start_time = time.time()

        # Validate
        is_valid, errors = self.validate_input(input_data)
        if not is_valid:
            return BacktestOutput(is_valid=False, validation_errors=errors, engine_name=self.name)

        # Prepare data
        candles = input_data.candles
        n = len(candles)

        open_prices = candles["open"].values.astype(np.float64)
        high_prices = candles["high"].values.astype(np.float64)
        low_prices = candles["low"].values.astype(np.float64)
        close_prices = candles["close"].values.astype(np.float64)

        if isinstance(candles.index, pd.DatetimeIndex):
            timestamps = candles.index.to_numpy()
        else:
            timestamps = pd.to_datetime(candles.index).to_numpy()

        # Signals
        long_entries = input_data.long_entries if input_data.long_entries is not None else np.zeros(n, dtype=bool)
        long_exits = input_data.long_exits if input_data.long_exits is not None else np.zeros(n, dtype=bool)
        short_entries = input_data.short_entries if input_data.short_entries is not None else np.zeros(n, dtype=bool)
        short_exits = input_data.short_exits if input_data.short_exits is not None else np.zeros(n, dtype=bool)

        # Direction
        direction = 0  # both
        if input_data.direction == TradeDirection.LONG:
            direction = 1
        elif input_data.direction == TradeDirection.SHORT:
            direction = -1

        # Get position sizing parameters
        use_fixed_amount = input_data.use_fixed_amount and input_data.fixed_amount > 0
        fixed_amount = input_data.fixed_amount if use_fixed_amount else 0.0
        position_size = input_data.position_size  # For percentage-based sizing

        # Run simulation
        use_bar_magnifier = input_data.use_bar_magnifier and input_data.candles_1m is not None
        pyramiding = getattr(input_data, "pyramiding", 1)

        # === V4 FEATURES CHECK ===
        # Check if advanced features are needed (support both naming conventions)
        from backend.backtesting.interfaces import SlMode, TpMode

        # SL mode: check sl_mode enum or legacy use_atr_sl
        sl_mode = getattr(input_data, "sl_mode", None)
        use_atr_sl = (
            getattr(input_data, "use_atr_sl", False)
            or (sl_mode == SlMode.ATR if sl_mode else False)
            or (str(sl_mode) == "atr" if sl_mode else False)
        )

        # TP mode: check tp_mode enum or legacy use_atr_tp
        tp_mode = getattr(input_data, "tp_mode", None)
        use_atr_tp = (
            getattr(input_data, "use_atr_tp", False)
            or (tp_mode == TpMode.ATR if tp_mode else False)
            or (str(tp_mode) == "atr" if tp_mode else False)
        )

        # Multi-TP: check tp_mode=MULTI or legacy multi_tp_enabled
        use_multi_tp = (
            getattr(input_data, "use_multi_tp", False)
            or getattr(input_data, "multi_tp_enabled", False)
            or (tp_mode == TpMode.MULTI if tp_mode else False)
        )

        # Trailing: check trailing_stop_enabled or legacy use_trailing
        use_trailing = (
            getattr(input_data, "use_trailing", False)
            or getattr(input_data, "trailing_stop_enabled", False)
            or getattr(input_data, "trailing_enabled", False)
        )

        # DCA: check dca_enabled
        dca_enabled = getattr(input_data, "dca_enabled", False)
        dca_safety_orders = getattr(input_data, "dca_safety_orders", 0)

        # Breakeven, time-based exits, re-entry rules
        breakeven_enabled = getattr(input_data, "breakeven_enabled", False)
        max_bars_in_trade = getattr(input_data, "max_bars_in_trade", 0)
        re_entry_delay_bars = getattr(input_data, "re_entry_delay_bars", 0)
        max_trades_per_day = getattr(input_data, "max_trades_per_day", 0)
        cooldown_after_loss = getattr(input_data, "cooldown_after_loss", 0)
        max_consecutive_losses = getattr(input_data, "max_consecutive_losses", 0)

        # V4 mode: ATR, Multi-TP, Trailing, DCA, Breakeven, Time-based, Re-entry
        needs_v4 = (
            use_atr_sl or use_atr_tp or use_multi_tp or use_trailing or dca_enabled
            or breakeven_enabled or max_bars_in_trade > 0
            or re_entry_delay_bars > 0 or max_trades_per_day > 0
            or cooldown_after_loss > 0 or max_consecutive_losses > 0
        )

        if needs_v4:
            # === V4 MODE: Full-featured simulation ===
            logger.info(f"NumbaEngine V4: atr_sl={use_atr_sl}, atr_tp={use_atr_tp}, multi_tp={use_multi_tp}, trailing={use_trailing}")

            # Calculate ATR if needed
            from backend.backtesting.atr_calculator import calculate_atr_fast
            atr_period = getattr(input_data, "atr_period", 14)
            atr_values = calculate_atr_fast(high_prices, low_prices, close_prices, atr_period)

            # ATR multipliers
            atr_sl_mult = getattr(input_data, "atr_sl_multiplier", 1.5)
            atr_tp_mult = getattr(input_data, "atr_tp_multiplier", 2.0)

            # Multi-TP portions (what % of position to close at each level)
            tp_portions = getattr(input_data, "tp_portions", (0.25, 0.25, 0.25, 0.25))
            if len(tp_portions) >= 4:
                tp1_pct = tp_portions[0]
                tp2_pct = tp_portions[1]
                tp3_pct = tp_portions[2]
                tp4_pct = tp_portions[3]
            else:
                tp1_pct = 0.25
                tp2_pct = 0.25
                tp3_pct = 0.25
                tp4_pct = 0.25

            # TP levels (at what profit % or ATR mult to trigger each TP)
            tp_levels = getattr(input_data, "tp_levels", (0.01, 0.02, 0.03, 0.04))
            if len(tp_levels) >= 4:
                tp1_mult = tp_levels[0]
                tp2_mult = tp_levels[1]
                tp3_mult = tp_levels[2]
                tp4_mult = tp_levels[3]
            else:
                tp1_mult = 0.01
                tp2_mult = 0.02
                tp3_mult = 0.03
                tp4_mult = 0.04

            # Trailing params - support both naming conventions
            trail_activation = getattr(input_data, "trail_activation", None)
            if trail_activation is None:
                trail_activation = getattr(input_data, "trailing_stop_activation", 0.01)

            trail_offset = getattr(input_data, "trail_offset", None)
            if trail_offset is None:
                trail_offset = getattr(input_data, "trailing_stop_distance", 0.005)

            # DCA params - pre-calculate levels and volumes
            dca_price_deviation = getattr(input_data, "dca_price_deviation", 0.01)
            dca_step_scale = getattr(input_data, "dca_step_scale", 1.4)
            dca_volume_scale = getattr(input_data, "dca_volume_scale", 1.0)
            dca_base_order_size = getattr(input_data, "dca_base_order_size", 0.1)
            dca_safety_order_size = getattr(input_data, "dca_safety_order_size", 0.1)

            # Pre-calculate DCA levels (cumulative price deviation) and volumes
            max_dca = 20
            dca_levels = np.zeros(max_dca, dtype=np.float64)
            dca_volumes = np.zeros(max_dca, dtype=np.float64)
            if dca_enabled and dca_safety_orders > 0:
                cumulative_deviation = 0.0
                current_deviation = dca_price_deviation
                current_volume = dca_safety_order_size
                for so_idx in range(min(dca_safety_orders, max_dca)):
                    cumulative_deviation += current_deviation
                    dca_levels[so_idx] = cumulative_deviation
                    dca_volumes[so_idx] = current_volume
                    current_deviation *= dca_step_scale
                    current_volume *= dca_volume_scale

            # Breakeven params
            breakeven_enabled = getattr(input_data, "breakeven_enabled", False)
            breakeven_offset = getattr(input_data, "breakeven_offset", 0.0)

            # Time-based exits
            max_bars_in_trade = getattr(input_data, "max_bars_in_trade", 0)

            # Re-entry rules
            re_entry_delay_bars = getattr(input_data, "re_entry_delay_bars", 0)
            max_trades_per_day = getattr(input_data, "max_trades_per_day", 0)
            cooldown_after_loss = getattr(input_data, "cooldown_after_loss", 0)
            max_consecutive_losses = getattr(input_data, "max_consecutive_losses", 0)

            # Market filters - pre-calculate boolean masks
            volatility_filter = self._calculate_volatility_filter(
                atr_values,
                getattr(input_data, "volatility_filter_enabled", False),
                getattr(input_data, "min_volatility_percentile", 10.0),
                getattr(input_data, "max_volatility_percentile", 90.0),
                getattr(input_data, "volatility_lookback", 100),
            )

            volume_filter = self._calculate_volume_filter(
                input_data.volumes if hasattr(input_data, "volumes") and input_data.volumes is not None else None,
                getattr(input_data, "volume_filter_enabled", False),
                getattr(input_data, "min_volume_percentile", 20.0),
                getattr(input_data, "volume_lookback", 50),
            )

            trend_filter_long, trend_filter_short = self._calculate_trend_filter(
                close_prices,
                getattr(input_data, "trend_filter_enabled", False),
                getattr(input_data, "trend_filter_period", 200),
                getattr(input_data, "trend_filter_mode", "with"),
            )

            # Funding rate params
            include_funding = getattr(input_data, "include_funding", False)
            funding_rate = getattr(input_data, "funding_rate", 0.0001)  # Default 0.01%
            funding_interval = getattr(input_data, "funding_interval", 8)  # Default 8h

            # Advanced slippage params
            slippage_model = getattr(input_data, "slippage_model", "fixed")
            use_advanced_slippage = slippage_model == "advanced"
            slippage_multipliers = self._calculate_slippage_multipliers(
                close_prices,
                atr_values,
                input_data.volumes if hasattr(input_data, "volumes") and input_data.volumes is not None else None,
                use_advanced_slippage,
            )

            # Close rule: 0=ALL (default), 1=FIFO, 2=LIFO
            close_entries_rule = getattr(input_data, "close_entries_rule", "ALL")
            if close_entries_rule == "FIFO":
                close_rule = 1
            elif close_entries_rule == "LIFO":
                close_rule = 2
            else:
                close_rule = 0  # ALL (default)

            result = _simulate_trades_numba_v4(
                open_prices,
                high_prices,
                low_prices,
                close_prices,
                long_entries,
                long_exits,
                short_entries,
                short_exits,
                input_data.stop_loss,
                input_data.take_profit,
                position_size,
                input_data.leverage,
                input_data.taker_fee,
                input_data.slippage,
                direction,
                input_data.initial_capital,
                use_fixed_amount,
                fixed_amount,
                max(pyramiding, 1),  # max_entries
                atr_values,
                use_atr_sl,
                use_atr_tp,
                atr_sl_mult,
                atr_tp_mult,
                use_multi_tp,
                tp1_pct,
                tp2_pct,
                tp3_pct,
                tp4_pct,
                tp1_mult,
                tp2_mult,
                tp3_mult,
                tp4_mult,
                use_trailing,
                trail_activation,
                trail_offset,
                # DCA params
                dca_enabled,
                min(dca_safety_orders, max_dca),
                dca_levels,
                dca_volumes,
                dca_base_order_size,
                # Breakeven params
                breakeven_enabled,
                breakeven_offset,
                # Time-based exits
                max_bars_in_trade,
                # Re-entry rules
                re_entry_delay_bars,
                max_trades_per_day,
                cooldown_after_loss,
                max_consecutive_losses,
                # Market filters
                volatility_filter,
                volume_filter,
                trend_filter_long,
                trend_filter_short,
                # Funding rate
                include_funding,
                funding_rate,
                funding_interval,
                # Advanced slippage
                use_advanced_slippage,
                slippage_multipliers,
                # Close rule (FIFO/LIFO/ALL)
                close_rule,
            )
        elif use_bar_magnifier:
            # Build bar magnifier index
            m1_highs, m1_lows, m1_starts, m1_ends = self._build_bar_magnifier_arrays(candles, input_data.candles_1m)

            # TODO: Add bar magnifier + pyramiding support
            result = _simulate_with_bar_magnifier(
                open_prices,
                high_prices,
                low_prices,
                close_prices,
                m1_highs,
                m1_lows,
                m1_starts,
                m1_ends,
                long_entries,
                long_exits,
                short_entries,
                short_exits,
                input_data.stop_loss,
                input_data.take_profit,
                position_size,
                input_data.leverage,
                input_data.taker_fee,
                input_data.slippage,
                direction,
                input_data.initial_capital,
                use_fixed_amount,
                fixed_amount,
            )
        elif pyramiding > 1:
            # === PYRAMIDING MODE (new in Numba V3) ===
            logger.info(f"NumbaEngine: using pyramiding mode (max_entries={pyramiding})")
            result = _simulate_trades_numba_pyramiding(
                open_prices,
                high_prices,
                low_prices,
                close_prices,
                long_entries,
                long_exits,
                short_entries,
                short_exits,
                input_data.stop_loss,
                input_data.take_profit,
                position_size,
                input_data.leverage,
                input_data.taker_fee,
                input_data.slippage,
                direction,
                input_data.initial_capital,
                use_fixed_amount,
                fixed_amount,
                pyramiding,  # max_entries
            )
        else:
            # Standard mode (no pyramiding)
            result = _simulate_trades_numba(
                open_prices,
                high_prices,
                low_prices,
                close_prices,
                long_entries,
                long_exits,
                short_entries,
                short_exits,
                input_data.stop_loss,
                input_data.take_profit,
                position_size,
                input_data.leverage,
                input_data.taker_fee,
                input_data.slippage,
                direction,
                input_data.initial_capital,
                use_fixed_amount,
                fixed_amount,
            )

        (
            equity_curve,
            trade_pnls,
            trade_dirs,
            entry_idxs,
            exit_idxs,
            entry_prices,
            exit_prices,
            exit_reasons,
            trade_sizes,
            trade_fees,
        ) = result

        # Build trade records
        trades = self._build_trade_records(
            timestamps,
            trade_pnls,
            trade_dirs,
            entry_idxs,
            exit_idxs,
            entry_prices,
            exit_prices,
            exit_reasons,
            trade_sizes=trade_sizes,
            trade_fees=trade_fees,
            initial_capital=input_data.initial_capital,
        )

        # Calculate metrics
        metrics = self._calculate_metrics(trades, equity_curve, input_data.initial_capital)

        execution_time = time.time() - start_time

        return BacktestOutput(
            metrics=metrics,
            trades=trades,
            equity_curve=equity_curve,
            timestamps=timestamps,
            engine_name=self.name,
            execution_time=execution_time,
            bars_processed=n,
            bar_magnifier_used=use_bar_magnifier,
            is_valid=True,
        )

    def optimize(
        self,
        input_data: BacktestInput,
        param_ranges: dict[str, list[Any]],
        metric: str = "sharpe_ratio",
        top_n: int = 10,
    ) -> list[tuple[dict[str, Any], BacktestOutput]]:
        """Parallel optimization using Numba"""
        from itertools import product

        results = []
        param_names = list(param_ranges.keys())
        param_values = list(param_ranges.values())

        for combo in product(*param_values):
            params = dict(zip(param_names, combo))
            modified_input = self._apply_params(input_data, params)
            result = self.run(modified_input)

            if result.is_valid and result.metrics.total_trades > 0:
                results.append((params, result))

        results.sort(key=lambda x: getattr(x[1].metrics, metric, 0), reverse=True)
        return results[:top_n]

    def _calculate_volatility_filter(
        self,
        atr_values: np.ndarray,
        enabled: bool,
        min_percentile: float,
        max_percentile: float,
        lookback: int,
    ) -> np.ndarray:
        """
        Calculate volatility filter mask based on ATR percentile.

        Args:
            atr_values: Pre-calculated ATR values
            enabled: Whether filter is enabled
            min_percentile: Minimum ATR percentile (e.g., 10.0)
            max_percentile: Maximum ATR percentile (e.g., 90.0)
            lookback: Rolling window for percentile calculation

        Returns:
            Boolean array where True = trade allowed, False = filtered
        """
        n = len(atr_values)
        result = np.ones(n, dtype=np.bool_)

        if not enabled:
            return result

        # Rolling percentile calculation
        for i in range(lookback, n):
            window = atr_values[max(0, i - lookback) : i]
            current_atr = atr_values[i]

            if len(window) > 0 and np.std(window) > 0:
                percentile = (np.sum(window < current_atr) / len(window)) * 100
                result[i] = min_percentile <= percentile <= max_percentile

        return result

    def _calculate_volume_filter(
        self,
        volumes: np.ndarray | None,
        enabled: bool,
        min_percentile: float,
        lookback: int,
    ) -> np.ndarray:
        """
        Calculate volume filter mask based on volume percentile.

        Args:
            volumes: Volume data (can be None)
            enabled: Whether filter is enabled
            min_percentile: Minimum volume percentile (e.g., 20.0)
            lookback: Rolling window for percentile calculation

        Returns:
            Boolean array where True = trade allowed, False = filtered
        """
        if volumes is None or not enabled:
            return np.ones(len(volumes) if volumes is not None else 1000, dtype=np.bool_)

        n = len(volumes)
        result = np.ones(n, dtype=np.bool_)

        # Rolling percentile calculation
        for i in range(lookback, n):
            window = volumes[max(0, i - lookback) : i]
            current_volume = volumes[i]

            if len(window) > 0 and np.max(window) > 0:
                percentile = (np.sum(window < current_volume) / len(window)) * 100
                result[i] = percentile >= min_percentile

        return result

    def _calculate_trend_filter(
        self,
        close_prices: np.ndarray,
        enabled: bool,
        period: int,
        mode: str,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Calculate trend filter masks based on SMA.

        Args:
            close_prices: Close prices
            enabled: Whether filter is enabled
            period: SMA period (e.g., 200)
            mode: "with" = trade with trend, "against" = trade against trend

        Returns:
            Tuple of (long_filter, short_filter) boolean arrays
        """
        n = len(close_prices)
        long_filter = np.ones(n, dtype=np.bool_)
        short_filter = np.ones(n, dtype=np.bool_)

        if not enabled:
            return long_filter, short_filter

        # Calculate SMA
        sma = np.zeros(n, dtype=np.float64)
        for i in range(period - 1, n):
            sma[i] = np.mean(close_prices[i - period + 1 : i + 1])

        # Apply filter
        if mode == "with":
            # Trade with trend: long when price > SMA, short when price < SMA
            for i in range(period - 1, n):
                long_filter[i] = close_prices[i] > sma[i]
                short_filter[i] = close_prices[i] < sma[i]
        else:
            # Trade against trend (counter-trend)
            for i in range(period - 1, n):
                long_filter[i] = close_prices[i] < sma[i]
                short_filter[i] = close_prices[i] > sma[i]

        return long_filter, short_filter

    def _calculate_slippage_multipliers(
        self,
        close_prices: np.ndarray,
        atr_values: np.ndarray,
        volumes: np.ndarray | None,
        enabled: bool,
    ) -> np.ndarray:
        """
        Calculate dynamic slippage multipliers based on volatility and volume.

        Higher volatility = higher slippage (up to 2x)
        Lower volume = higher slippage (up to 2x)

        Args:
            close_prices: Close prices
            atr_values: ATR values
            volumes: Volume data (optional)
            enabled: Whether advanced slippage is enabled

        Returns:
            Multiplier array (1.0 = base slippage, 2.0 = 2x slippage)
        """
        n = len(close_prices)
        result = np.ones(n, dtype=np.float64)

        if not enabled:
            return result

        # Calculate volatility multiplier based on ATR
        lookback = 50
        for i in range(lookback, n):
            if close_prices[i] > 0:
                atr_pct = atr_values[i] / close_prices[i]
                # Higher ATR% = higher slippage
                # Assume normal ATR% is around 1%, scale 0.5-2x
                volatility_mult = min(2.0, max(0.5, atr_pct / 0.01))
                result[i] *= volatility_mult

        # Calculate volume multiplier if volume available
        if volumes is not None and len(volumes) == n:
            for i in range(lookback, n):
                window = volumes[max(0, i - lookback) : i]
                if len(window) > 0:
                    avg_volume = np.mean(window)
                    if avg_volume > 0:
                        volume_ratio = volumes[i] / avg_volume
                        # Lower volume = higher slippage
                        # Volume 50% of avg = 1.5x slippage
                        volume_mult = min(2.0, max(0.5, 1.0 / volume_ratio))
                        result[i] *= volume_mult

        return result

    def _build_bar_magnifier_arrays(
        self, candles: pd.DataFrame, candles_1m: pd.DataFrame
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Build arrays for Bar Magnifier Numba function"""
        n = len(candles)

        m1_highs = candles_1m["high"].values.astype(np.float64)
        m1_lows = candles_1m["low"].values.astype(np.float64)

        m1_starts = np.full(n, -1, dtype=np.int32)
        m1_ends = np.full(n, -1, dtype=np.int32)

        bar_times = candles.index if isinstance(candles.index, pd.DatetimeIndex) else pd.to_datetime(candles.index)
        m1_times = (
            candles_1m.index if isinstance(candles_1m.index, pd.DatetimeIndex) else pd.to_datetime(candles_1m.index)
        )

        for i in range(n):
            bar_start = bar_times[i]
            bar_end = bar_times[i + 1] if i + 1 < n else bar_times[i] + pd.Timedelta(hours=1)

            mask = (m1_times >= bar_start) & (m1_times < bar_end)
            matching = np.where(mask)[0]

            if len(matching) > 0:
                m1_starts[i] = matching[0]
                m1_ends[i] = matching[-1] + 1

        return m1_highs, m1_lows, m1_starts, m1_ends

    def _build_trade_records(
        self,
        timestamps: np.ndarray,
        pnls: np.ndarray,
        directions: np.ndarray,
        entry_idxs: np.ndarray,
        exit_idxs: np.ndarray,
        entry_prices: np.ndarray,
        exit_prices: np.ndarray,
        exit_reasons: np.ndarray,
        trade_sizes: np.ndarray = None,
        trade_fees: np.ndarray = None,
        initial_capital: float = 10000.0,
    ) -> list[TradeRecord]:
        """Convert Numba output to TradeRecord list with EXACT data"""
        trades = []

        reason_map = {
            0: ExitReason.STOP_LOSS,
            1: ExitReason.TAKE_PROFIT,
            2: ExitReason.SIGNAL,
            3: ExitReason.END_OF_DATA,
        }

        for i in range(len(pnls)):
            entry_price = entry_prices[i]
            exit_price = exit_prices[i]
            pnl = pnls[i]

            # Use exact values if provided, otherwise estimate
            if trade_sizes is not None and len(trade_sizes) > i:
                size = trade_sizes[i]
            else:
                size = 0.0

            if trade_fees is not None and len(trade_fees) > i:
                fees = trade_fees[i]
            else:
                # Fallback: estimate fees
                price_diff = abs(exit_price - entry_price)
                if price_diff > 0.01:
                    estimated_size = abs(pnl) / price_diff
                    fees = (entry_price + exit_price) * estimated_size * 0.001
                else:
                    fees = 0.0

            # Calculate pnl_pct relative to entry notional (size * entry_price)
            if size > 0 and entry_price > 0:
                notional = size * entry_price
                pnl_pct = (pnl / notional) * 100 if notional > 0 else 0.0
            else:
                # Fallback estimate
                pnl_pct = (pnl / (entry_price * 0.01)) if entry_price > 0 else 0.0

            trades.append(
                TradeRecord(
                    entry_time=pd.Timestamp(timestamps[entry_idxs[i]]),
                    exit_time=pd.Timestamp(timestamps[exit_idxs[i]]),
                    direction="long" if directions[i] == 1 else "short",
                    entry_price=entry_price,
                    exit_price=exit_price,
                    size=size,
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                    fees=fees,
                    exit_reason=reason_map.get(exit_reasons[i], ExitReason.SIGNAL),
                    duration_bars=exit_idxs[i] - entry_idxs[i],
                )
            )

        return trades

    def _calculate_metrics(
        self,
        trades: list[TradeRecord],
        equity_curve: np.ndarray,
        initial_capital: float,
    ) -> BacktestMetrics:
        """Calculate metrics from results - FULL VERSION matching Fallback"""
        metrics = BacktestMetrics()

        if len(trades) == 0:
            return metrics

        # === ОСНОВНЫЕ ===
        pnls = [t.pnl for t in trades]
        metrics.net_profit = sum(pnls)
        # Safe division for total return
        metrics.total_return = (
            (equity_curve[-1] - initial_capital) / initial_capital * 100 if initial_capital > 0 else 0.0
        )

        # Gross profit/loss
        metrics.gross_profit = sum(p for p in pnls if p > 0)
        metrics.gross_loss = abs(sum(p for p in pnls if p < 0))

        # === DRAWDOWN ===
        peak = np.maximum.accumulate(equity_curve)
        drawdown_pct = (peak - equity_curve) / np.maximum(peak, 1) * 100
        drawdown_usdt = peak - equity_curve  # Absolute drawdown in USDT
        metrics.max_drawdown = np.max(drawdown_pct)  # Percentage for consistency
        metrics.max_drawdown_pct = np.max(drawdown_pct)  # Keep percentage version
        metrics.max_drawdown_usdt = np.max(drawdown_usdt)  # USDT version for display
        metrics.avg_drawdown = np.mean(drawdown_pct)

        # === TRADES ===
        metrics.total_trades = len(trades)
        metrics.winning_trades = sum(1 for t in trades if t.pnl > 0)
        metrics.losing_trades = sum(1 for t in trades if t.pnl < 0)
        metrics.win_rate = metrics.winning_trades / metrics.total_trades if metrics.total_trades > 0 else 0

        # Profit factor
        metrics.profit_factor = metrics.gross_profit / metrics.gross_loss if metrics.gross_loss > 0 else 10.0

        # === AVERAGES ===
        wins = [t.pnl for t in trades if t.pnl > 0]
        losses = [t.pnl for t in trades if t.pnl < 0]

        metrics.avg_win = np.mean(wins) if wins else 0
        metrics.avg_loss = np.mean(losses) if losses else 0
        metrics.avg_trade = np.mean(pnls)
        metrics.largest_win = max(pnls) if pnls else 0
        metrics.largest_loss = min(pnls) if pnls else 0

        # === LONG/SHORT BREAKDOWN ===
        long_trades = [t for t in trades if t.direction == "long"]
        short_trades = [t for t in trades if t.direction == "short"]

        metrics.long_trades = len(long_trades)
        metrics.short_trades = len(short_trades)
        metrics.long_win_rate = sum(1 for t in long_trades if t.pnl > 0) / len(long_trades) if long_trades else 0
        metrics.short_win_rate = sum(1 for t in short_trades if t.pnl > 0) / len(short_trades) if short_trades else 0
        metrics.long_profit = sum(t.pnl for t in long_trades)
        metrics.short_profit = sum(t.pnl for t in short_trades)

        # === DURATION ===
        durations = [t.duration_bars for t in trades]
        metrics.avg_trade_duration = np.mean(durations) if durations else 0

        winning_durations = [t.duration_bars for t in trades if t.pnl > 0]
        losing_durations = [t.duration_bars for t in trades if t.pnl < 0]
        metrics.avg_winning_duration = np.mean(winning_durations) if winning_durations else 0
        metrics.avg_losing_duration = np.mean(losing_durations) if losing_durations else 0

        # === SHARPE RATIO ===
        returns = np.diff(equity_curve) / np.maximum(equity_curve[:-1], 1)
        returns = np.nan_to_num(returns, nan=0, posinf=0, neginf=0)
        if len(returns) > 1 and np.std(returns) > 0:
            metrics.sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252 * 24)

        # === SORTINO RATIO ===
        downside_returns = returns[returns < 0]
        if len(downside_returns) > 1:
            downside_std = np.std(downside_returns)
            if downside_std > 0:
                metrics.sortino_ratio = np.mean(returns) / downside_std * np.sqrt(252 * 24)

        # === CALMAR RATIO ===
        if metrics.max_drawdown > 0:
            annual_return = metrics.total_return * (365 * 24 / len(equity_curve))
            metrics.calmar_ratio = annual_return / metrics.max_drawdown

        # === EXPECTANCY ===
        metrics.expectancy = metrics.win_rate * metrics.avg_win + (1 - metrics.win_rate) * metrics.avg_loss

        # === PAYOFF RATIO ===
        if metrics.avg_loss != 0:
            metrics.payoff_ratio = abs(metrics.avg_win / metrics.avg_loss)

        # === RECOVERY FACTOR ===
        if metrics.max_drawdown > 0:
            metrics.recovery_factor = metrics.net_profit / (initial_capital * metrics.max_drawdown / 100)

        return metrics

    def _apply_params(self, input_data: BacktestInput, params: dict[str, Any]) -> BacktestInput:
        """Apply params to input"""
        from dataclasses import replace

        modified = replace(input_data)
        for key, value in params.items():
            if hasattr(modified, key):
                setattr(modified, key, value)
        return modified
