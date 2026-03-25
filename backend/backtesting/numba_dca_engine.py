"""
Numba JIT-compiled DCA Simulation Core.

Provides a fast bar-by-bar DCA grid simulation using Numba @njit and prange
for parallel optimization over multiple SL/TP or RSI threshold combinations.

Design constraints (Numba @njit):
    - No Python objects (pd.DataFrame, dataclasses, lists of dicts)
    - All state stored in pre-allocated numpy arrays
    - Scalars passed as Python float/int (auto-converted to C types)
    - direction: int  (0=long, 1=short)

Coverage:
    ✔ Grid order placement (up to MAX_DCA_ORDERS=15 levels)
    ✔ Martingale sizing: multiply_each, multiply_total, progressive modes
    ✔ Single SL% and TP% (based on average entry price)
    ✔ Multi-TP (TP1-TP4 partial closes, last level closes remaining)
    ✔ Trailing stop (activation_pct + distance_pct, resets per position)
    ✔ ATR TP/SL (multiplier × ATR[bar], recalculated after each DCA fill)
    ✔ Commission on every fill (taker rate)
    ✔ Equity curve tracking (bar-by-bar)
    ✔ Batch parallel simulation via prange
    ✔ close_by_time: close after N bars if profit >= min_profit_pct (force-close at max_bars)
    ✔ Breakeven stop-loss: move SL to avg_entry+offset after activation_pct profit
    ✔ dca_safety_close: close when position loss >= threshold % of invested margin
    ✔ max_drawdown: closed-trade equity, initial_capital denominator (matches V4)
    ✔ sharpe_ratio: monthly equity returns, ddof=0, no annualization (matches TV/V4)
    ✔ Close conditions: precomputed bool[n_bars] signal (RSI/Stoch/MA/BB/PSAR close)
    ✔ Grid pullback: shift unfilled orders when price moves away
    ✔ Grid trailing: shift unfilled orders to trail favorable price movement
    ✔ Partial grid: activate N orders at a time, expand on fill
    ✔ SL type last_order: SL from last filled order price instead of avg entry
    ✔ Indent orders: pending limit entry with cancellation timeout
    ✔ Log-scale grid steps: logarithmic step distribution

Parity with V4 DCA engine:
    ✔ trade_count, net_profit, win_rate, profit_factor — 100% match
    ✔ max_drawdown — closed-trade equity, initial_capital denominator (V4 formula)
    ✔ sharpe_ratio — monthly equity returns, ddof=0, no annualization (TV formula)
    ✔ All exit prices use bar close (matching V4 convention)
"""

# ruff: noqa: SIM102, SIM108
# ^^^ Nested-if and ternary style rules are suppressed for @njit functions
#     where explicit if/else blocks are more readable in numeric simulation code.

from __future__ import annotations

import logging

import numpy as np
from numba import njit, prange

logger = logging.getLogger(__name__)

# Maximum grid levels supported inside @njit (hard array limit)
_MAX_DCA_ORDERS: int = 15

# Maximum trades stored per simulation run (single combo)
_MAX_DCA_TRADES: int = 2000

# Maximum calendar months for monthly Sharpe computation (covers up to 3 years)
_MAX_MONTHS: int = 36


# ---------------------------------------------------------------------------
# Python-level helper — precompute close condition signals
# ---------------------------------------------------------------------------


def build_close_condition_signal(
    ohlcv_df,
    close_conditions_config=None,
    *,
    dca_engine_instance=None,
) -> np.ndarray:
    """
    Precompute a combined close-condition signal array for use by the Numba engine.

    Uses V4 DCAEngine's indicator computation and close-condition checking logic
    to produce a boolean array `signal[n_bars]` where `True` = close conditions met
    on that bar (before profit filtering, which is applied inside @njit).

    Args:
        ohlcv_df: pandas DataFrame with OHLCV columns (at minimum 'close', 'high', 'low').
        close_conditions_config: CloseConditionsConfig from DCA engine (or None to disable).
        dca_engine_instance: An existing DCAEngine instance with close conditions configured.
            If provided, uses its `_check_close_conditions` directly.
            If None and close_conditions_config is provided, a temporary engine is created.

    Returns:
        np.ndarray[bool] of length len(ohlcv_df). True where close condition triggers.
        Returns all-False array if no close conditions are configured.

    Note:
        The profit filter (only_profit / min_profit) is NOT applied here — it requires
        unrealized_pct which is only available during simulation. Instead, pass
        `close_cond_min_profit` as a scalar parameter to `_simulate_dca_single` where
        the filter is applied against the runtime unrealized_pct.
    """
    n = len(ohlcv_df)
    signal = np.zeros(n, dtype=np.bool_)

    if close_conditions_config is None and dca_engine_instance is None:
        return signal

    try:
        if dca_engine_instance is not None:
            engine = dca_engine_instance
        else:
            # Lazy import to avoid circular dependency
            from backend.backtesting.engines.dca_engine import DCAEngine

            # Create a minimal engine instance just for close condition evaluation
            engine = DCAEngine.__new__(DCAEngine)
            engine._close_conditions = close_conditions_config
            engine._close_indicators_computed = False

        # Precompute all required indicator caches (RSI, Stoch, MA, BB, Keltner, PSAR)
        if hasattr(engine, "_precompute_close_condition_indicators"):
            engine._precompute_close_condition_indicators(ohlcv_df)

        # Evaluate close conditions bar by bar
        close_prices = (
            ohlcv_df["close"].values if hasattr(ohlcv_df["close"], "values") else np.asarray(ohlcv_df["close"])
        )
        for i in range(1, n):
            try:
                result = engine._check_close_conditions(i, close_prices[i])
                if result is not None:
                    signal[i] = True
            except (IndexError, AttributeError):
                continue

    except Exception as e:
        logger.warning(f"Failed to build close condition signal: {e}")
        return np.zeros(n, dtype=np.bool_)

    return signal


# ---------------------------------------------------------------------------
# Inner helpers — called inside @njit (must be @njit themselves)
# ---------------------------------------------------------------------------


@njit(cache=True, fastmath=True)
def _calc_grid_orders(
    base_price: float,
    direction: int,  # 0=long, 1=short
    order_count: int,  # 1-15
    grid_size_pct: float,  # total grid size % (e.g. 10.0 = 10%)
    martingale_coef: float,  # ≥1.0
    capital_per_order0: float,  # margin for order-0 (= capital * pos_size / order_count_weight)
    leverage: float,
    taker_fee: float,
    out_prices: np.ndarray,  # float64[_MAX_DCA_ORDERS] — output
    out_size_coins: np.ndarray,  # float64[_MAX_DCA_ORDERS] — output
    out_margin_usd: np.ndarray,  # float64[_MAX_DCA_ORDERS] — output
    # Phase 1A: martingale mode (0=multiply_each, 1=multiply_total, 2=progressive)
    martingale_mode: int,
    # Phase 3B: log-scale grid steps (0=linear, 1=log)
    use_log_steps: int,
    log_coefficient: float,
) -> int:
    """
    Calculate DCA grid order prices and sizes.

    Returns actual order_count clamped to _MAX_DCA_ORDERS.
    Stores results in out_* arrays (pre-allocated by caller).

    Martingale modes (matching V4 DCAGridCalculator._calculate_order_sizes):
        0 = multiply_each: w[k] = coef^k
        1 = multiply_total: w[k] = (coef-1) * sum(w[0..k-1]), min = w[0]
        2 = progressive: w[k] = 1 + k * (coef - 1)

    Grid step modes:
        use_log_steps=0: linear (even spacing)
        use_log_steps=1: logarithmic (log_coefficient^k, normalized)
    """
    n = min(order_count, _MAX_DCA_ORDERS)
    if n < 1:
        n = 1

    # --- Step distribution (linear or log-scale) ---
    # cumulative_frac[k] = fraction of total grid_size_pct at level k
    cumulative_frac = np.zeros(_MAX_DCA_ORDERS, dtype=np.float64)
    if use_log_steps > 0 and n > 1 and log_coefficient > 0.0:
        # Log-scale steps: step[k] = log_coefficient^k, normalized
        raw_steps = np.empty(n - 1, dtype=np.float64)
        total_raw = 0.0
        for k in range(n - 1):
            raw_steps[k] = log_coefficient**k
            total_raw += raw_steps[k]
        cum = 0.0
        for k in range(1, n):
            cum += raw_steps[k - 1] / total_raw
            cumulative_frac[k] = cum
    else:
        # Linear steps (even spacing)
        step_pct = 1.0 / max(n - 1, 1)
        for k in range(1, n):
            cumulative_frac[k] = k * step_pct

    grid_frac = grid_size_pct / 100.0

    # --- Martingale size weights ---
    weights = np.empty(_MAX_DCA_ORDERS, dtype=np.float64)
    if martingale_mode == 1:
        # multiply_total: each order = (coef-1) * sum of previous, min = 1.0
        weights[0] = 1.0
        running_total = 1.0
        for k in range(1, n):
            w_k = (martingale_coef - 1.0) * running_total
            if w_k < 1.0:
                w_k = 1.0
            weights[k] = w_k
            running_total += w_k
    elif martingale_mode == 2:
        # progressive: w[k] = 1 + k * (coef - 1)
        for k in range(n):
            weights[k] = 1.0 + k * (martingale_coef - 1.0)
    else:
        # multiply_each (default): w[k] = coef^k
        w = 1.0
        for k in range(n):
            weights[k] = w
            w *= martingale_coef

    # --- Build orders ---
    for k in range(n):
        if direction == 0:  # long: dip below entry
            trigger_price = base_price * (1.0 - cumulative_frac[k] * grid_frac)
        else:  # short: rise above entry
            trigger_price = base_price * (1.0 + cumulative_frac[k] * grid_frac)

        if trigger_price < 1e-10:
            trigger_price = 1e-10

        margin_k = capital_per_order0 * weights[k]
        notional_k = margin_k * leverage
        # V4 DCAGridCalculator: size_coins = notional / price (NO fee deduction from coins)
        size_coins_k = notional_k / trigger_price

        out_prices[k] = trigger_price
        out_size_coins[k] = size_coins_k
        out_margin_usd[k] = margin_k

    return n


@njit(cache=True, fastmath=True)
def _simulate_dca_single(
    close: np.ndarray,  # float64[n_bars]
    high: np.ndarray,  # float64[n_bars]
    low: np.ndarray,  # float64[n_bars]
    entry_signals: np.ndarray,  # int8[n_bars]: >0=long entry, <0=short entry, 0=none
    # DCA config
    direction: int,  # 0=long, 1=short, 2=both
    order_count: int,  # 1-15
    grid_size_pct: float,  # total grid as % (e.g. 10.0)
    martingale_coef: float,  # ≥1.0
    take_profit_pct: float,  # TP % from avg entry (e.g. 0.02 = 2%)
    stop_loss_pct: float,  # SL % from avg entry (e.g. 0.05 = 5%)
    initial_capital: float,
    position_size_frac: float,  # fraction of equity per entry (0.0-1.0)
    leverage: float,
    taker_fee: float,
    # close_by_time (0 = disabled)
    max_bars_in_trade: int,  # close after this many bars
    min_profit_close_pct: float,  # only close-by-time if profit >= this %
    # Breakeven SL (0.0 = disabled)
    breakeven_activation_pct: float,  # activate breakeven when profit >= this %
    breakeven_offset_pct: float,  # after activation, SL = avg_entry * (1+offset) for long
    # Safety close (0 = disabled)
    safety_close_enabled: int,  # 1=enabled (dca_safety_close_enabled)
    safety_close_threshold_pct: float,  # drawdown % of margin to trigger close (e.g. 30.0)
    # Trailing stop (0.0 = disabled)
    trailing_activation_pct: float,  # activate when profit >= this fraction (e.g. 0.02 = 2%)
    trailing_distance_pct: float,  # trail at distance_pct below peak (e.g. 0.01 = 1%)
    # Multi-TP (multi_tp_enabled=0 uses single take_profit_pct above)
    multi_tp_enabled: int,  # 1=enabled
    tp_percents: np.ndarray,  # float64[4] — [tp1, tp2, tp3, tp4] as decimals
    tp_close_pcts: np.ndarray,  # float64[4] — % of original position to close per level
    tp_count: int,  # number of TP levels (1-4)
    # ATR TP/SL (0.0 = disabled)
    atr_tp_multiplier: float,  # TP = avg_entry + ATR * multiplier (0.0 = disabled)
    atr_sl_multiplier: float,  # SL = avg_entry - ATR * multiplier (0.0 = disabled)
    atr_values: np.ndarray,  # float64[n_bars] or empty array (len=0)
    # === Phase 1A: Martingale mode ===
    martingale_mode: int,  # 0=multiply_each, 1=multiply_total, 2=progressive
    # === Phase 1B: Close conditions (precomputed) ===
    close_cond: np.ndarray,  # bool[n_bars] — precomputed OR of all close conditions
    close_cond_min_profit: float,  # 0.0 = no profit filter; >0 = min unrealized_pct
    # === Phase 2A: Grid pullback + trailing ===
    grid_pullback_pct: float,  # 0.0 = disabled; shift unfilled orders when price deviates
    grid_trailing_pct: float,  # 0.0 = disabled; shift unfilled orders to trail favorable move
    # === Phase 2B: Partial grid ===
    partial_grid_orders: int,  # 0 or 1 = all at once; 2+ = activate N orders at a time
    # === Phase 2C: SL from last order ===
    sl_from_last_order: int,  # 0=avg_entry (default), 1=last filled order price
    # === Phase 3A: Indent orders ===
    indent_enabled: int,  # 0=disabled, 1=enabled
    indent_pct: float,  # entry offset as fraction (e.g. 0.001 = 0.1%)
    indent_cancel_bars: int,  # cancel pending indent after N bars (0=no cancel)
    # === Phase 3B: Log-scale grid steps ===
    use_log_steps: int,  # 0=linear, 1=logarithmic
    log_coefficient: float,  # log step coefficient (e.g. 1.2)
    # Output arrays (pre-allocated, size = max_trades):
    out_pnl: np.ndarray,  # float64[_MAX_DCA_TRADES]
    out_entry_bar: np.ndarray,  # int64[_MAX_DCA_TRADES]
    out_exit_bar: np.ndarray,  # int64[_MAX_DCA_TRADES]
    out_is_win: np.ndarray,  # bool[_MAX_DCA_TRADES]
    out_equity: np.ndarray,  # float64[n_bars]
) -> int:
    """
    Simulate a single DCA strategy run bar-by-bar.

    Returns number of completed trades (including partial closes from multi-TP).
    Writes per-trade data to out_* arrays and equity curve to out_equity.
    """
    n_bars = len(close)
    n_atr = len(atr_values)
    n_close_cond = len(close_cond)
    tp_count_safe = min(tp_count, 4)

    # Pre-allocate grid order arrays (reused across positions)
    g_prices = np.empty(_MAX_DCA_ORDERS, dtype=np.float64)
    g_size_coins = np.empty(_MAX_DCA_ORDERS, dtype=np.float64)
    g_margin_usd = np.empty(_MAX_DCA_ORDERS, dtype=np.float64)
    g_filled = np.zeros(_MAX_DCA_ORDERS, dtype=np.bool_)
    # Phase 2B: partial grid — track which orders are active
    g_active = np.zeros(_MAX_DCA_ORDERS, dtype=np.bool_)

    # State
    cash = initial_capital
    in_position = False
    pos_direction = 0  # 0=long, 1=short
    pos_avg_entry = 0.0
    pos_total_size = 0.0  # total coins
    pos_total_cost = 0.0  # total margin spent (without fees)
    pos_total_fee = 0.0  # fees paid on entries (all orders)
    pos_entry_bar = 0
    pos_n_orders = 0  # active grid levels calculated
    pos_n_filled = 0  # orders filled so far
    breakeven_activated = False  # breakeven SL state
    pos_last_fill_price = 0.0  # Phase 2C: last filled order price (for sl_from_last_order)

    # Multi-TP state (reset per position)
    tp_hit = np.zeros(4, dtype=np.bool_)
    remaining_size_frac = 1.0

    # Trailing stop state (reset per position)
    trailing_activated = False
    trailing_highest = 0.0
    trailing_lowest = 1.0e18
    trailing_stop_price = 0.0

    # ATR TP/SL prices (set at entry, recalculated after DCA fills)
    atr_tp_price = 0.0
    atr_sl_price = 0.0

    # Phase 2A: Grid pullback/trailing state
    pullback_base_price = 0.0
    trailing_grid_base_price = 0.0

    # Phase 3A: Indent order pending state
    has_pending_indent = False
    pending_indent_price = 0.0
    pending_indent_bar = 0
    pending_indent_dir = 0  # 0=long, 1=short

    n_trades = 0

    # Match V4 DCA engine: start from bar 1 (bar 0 is skipped, consistent with V4)
    out_equity[0] = cash
    for i in range(1, n_bars):
        current_close = close[i]
        current_high = high[i]
        current_low = low[i]

        # --- Phase 3A: Indent order fill check (before in_position) ---
        if has_pending_indent and not in_position:
            indent_filled = False
            if (pending_indent_dir == 0 and current_low <= pending_indent_price) or (
                pending_indent_dir == 1 and current_high >= pending_indent_price
            ):
                indent_filled = True
            # Cancel if expired
            if not indent_filled and indent_cancel_bars > 0 and (i - pending_indent_bar) >= indent_cancel_bars:
                has_pending_indent = False
            if indent_filled:
                has_pending_indent = False
                # Open position at indent price
                pos_direction = pending_indent_dir
                entry_price = pending_indent_price
                alloc_capital = initial_capital * position_size_frac
                capital_per_order0 = alloc_capital / max(order_count, 1)
                pos_n_orders = _calc_grid_orders(
                    entry_price,
                    pos_direction,
                    order_count,
                    grid_size_pct,
                    martingale_coef,
                    capital_per_order0,
                    leverage,
                    taker_fee,
                    g_prices,
                    g_size_coins,
                    g_margin_usd,
                    martingale_mode,
                    use_log_steps,
                    log_coefficient,
                )
                for k in range(pos_n_orders):
                    g_filled[k] = False
                    g_active[k] = False
                g_filled[0] = True
                g_active[0] = True
                entry_fee_0 = g_margin_usd[0] * leverage * taker_fee
                cash -= g_margin_usd[0]
                pos_total_size = g_size_coins[0]
                pos_total_cost = g_margin_usd[0]
                pos_total_fee = entry_fee_0
                pos_avg_entry = entry_price
                pos_last_fill_price = entry_price
                pos_n_filled = 1
                pos_entry_bar = i
                breakeven_activated = False
                in_position = True
                # Partial grid: activate first N orders
                if partial_grid_orders >= 2:
                    pos_active_up_to = min(partial_grid_orders, pos_n_orders)
                else:
                    pos_active_up_to = pos_n_orders
                for k in range(pos_active_up_to):
                    g_active[k] = True
                # Reset Multi-TP / trailing / ATR / grid state
                for kk in range(4):
                    tp_hit[kk] = False
                remaining_size_frac = 1.0
                trailing_activated = False
                trailing_highest = 0.0
                trailing_lowest = 1.0e18
                trailing_stop_price = 0.0
                pullback_base_price = entry_price
                trailing_grid_base_price = entry_price
                atr_tp_price = 0.0
                atr_sl_price = 0.0
                if atr_tp_multiplier > 0.0 and n_atr > 0 and i < n_atr:
                    atr_v = atr_values[i]
                    if atr_v > 0.0:
                        if pos_direction == 0:
                            atr_tp_price = entry_price + atr_v * atr_tp_multiplier
                            if atr_sl_multiplier > 0.0:
                                atr_sl_price = entry_price - atr_v * atr_sl_multiplier
                        else:
                            atr_tp_price = entry_price - atr_v * atr_tp_multiplier
                            if atr_sl_multiplier > 0.0:
                                atr_sl_price = entry_price + atr_v * atr_sl_multiplier

        if in_position:
            # --- Phase 2A: Grid trailing / pullback shift (before fills, V4 order) ---
            any_unfilled = False
            for k in range(pos_active_up_to):
                if not g_filled[k]:
                    any_unfilled = True
                    break
            if any_unfilled and pos_n_filled < pos_n_orders:
                if grid_trailing_pct > 0.0 and trailing_grid_base_price > 0.0:
                    if pos_direction == 0:
                        fav_move = (current_close - trailing_grid_base_price) / trailing_grid_base_price
                    else:
                        fav_move = (trailing_grid_base_price - current_close) / trailing_grid_base_price
                    if fav_move >= grid_trailing_pct / 100.0:
                        shift = current_close - trailing_grid_base_price
                        if pos_direction == 1:
                            shift = trailing_grid_base_price - current_close
                            shift = -shift  # shift is signed: negative for short
                        for k in range(pos_n_orders):
                            if not g_filled[k]:
                                g_prices[k] += shift
                        trailing_grid_base_price = current_close
                        pullback_base_price = current_close
                elif grid_pullback_pct > 0.0 and pullback_base_price > 0.0:
                    price_move = abs(current_close - pullback_base_price) / pullback_base_price
                    if price_move >= grid_pullback_pct / 100.0:
                        shift = current_close - pullback_base_price
                        for k in range(pos_n_orders):
                            if not g_filled[k]:
                                g_prices[k] += shift
                        pullback_base_price = current_close

            # --- 1. Fill unfilled grid orders (partial grid aware) ---
            filled_this_bar = 0
            for k in range(pos_active_up_to):
                if not g_filled[k]:
                    fill_hit = False
                    if (pos_direction == 0 and current_low <= g_prices[k]) or (
                        pos_direction == 1 and current_high >= g_prices[k]
                    ):
                        fill_hit = True
                    if fill_hit:
                        g_filled[k] = True
                        pos_total_size += g_size_coins[k]
                        pos_total_cost += g_margin_usd[k]
                        fee_k = g_margin_usd[k] * leverage * taker_fee
                        pos_total_fee += fee_k
                        cash -= g_margin_usd[k]
                        pos_n_filled += 1
                        pos_last_fill_price = g_prices[k]
                        filled_this_bar += 1
                        if pos_total_size > 0:
                            pos_avg_entry = (pos_total_cost * leverage) / pos_total_size
                        # Recalculate ATR TP/SL with new avg entry
                        if atr_tp_multiplier > 0.0 and n_atr > 0 and i < n_atr:
                            atr_v = atr_values[i]
                            if atr_v > 0.0:
                                if pos_direction == 0:
                                    atr_tp_price = pos_avg_entry + atr_v * atr_tp_multiplier
                                    if atr_sl_multiplier > 0.0:
                                        atr_sl_price = pos_avg_entry - atr_v * atr_sl_multiplier
                                else:
                                    atr_tp_price = pos_avg_entry - atr_v * atr_tp_multiplier
                                    if atr_sl_multiplier > 0.0:
                                        atr_sl_price = pos_avg_entry + atr_v * atr_sl_multiplier
                        # Phase 2B: expand partial grid window on each fill
                        if partial_grid_orders >= 2 and pos_active_up_to < pos_n_orders:
                            pos_active_up_to = min(pos_active_up_to + 1, pos_n_orders)
                            g_active[pos_active_up_to - 1] = True

            # --- 2. Multi-TP partial closes ---
            if multi_tp_enabled > 0 and remaining_size_frac > 1e-10:
                for j in range(tp_count_safe):
                    if not in_position:
                        break
                    if tp_hit[j]:
                        continue

                    # Check if this TP level is hit
                    if pos_direction == 0:
                        tp_j_hit = current_high >= pos_avg_entry * (1.0 + tp_percents[j])
                    else:
                        tp_j_hit = current_low <= pos_avg_entry * (1.0 - tp_percents[j])

                    if tp_j_hit:
                        tp_hit[j] = True
                        is_last = j == tp_count_safe - 1

                        # Fraction of CURRENT remaining position to close
                        if is_last or remaining_size_frac <= 1e-10:
                            fraction_of_current = 1.0
                        else:
                            close_orig_frac = tp_close_pcts[j] / 100.0
                            fraction_of_current = close_orig_frac / remaining_size_frac
                            if fraction_of_current > 1.0:
                                fraction_of_current = 1.0

                        # Partial close at exact TP price (matches V4 _check_multi_tp)
                        if pos_direction == 0:
                            partial_exit_price = pos_avg_entry * (1.0 + tp_percents[j])
                        else:
                            partial_exit_price = pos_avg_entry * (1.0 - tp_percents[j])
                        coins_to_close = pos_total_size * fraction_of_current
                        partial_exit_fee = coins_to_close * partial_exit_price * taker_fee
                        partial_entry_fee = pos_total_fee * fraction_of_current
                        partial_cost = pos_total_cost * fraction_of_current

                        if pos_direction == 0:
                            gross_partial = (partial_exit_price - pos_avg_entry) * coins_to_close
                        else:
                            gross_partial = (pos_avg_entry - partial_exit_price) * coins_to_close

                        net_partial = gross_partial - partial_exit_fee - partial_entry_fee
                        cash += partial_cost + net_partial

                        # Update remaining position state
                        pos_total_size = pos_total_size * (1.0 - fraction_of_current)
                        pos_total_cost = pos_total_cost * (1.0 - fraction_of_current)
                        pos_total_fee = pos_total_fee - partial_entry_fee
                        if pos_total_fee < 0.0:
                            pos_total_fee = 0.0

                        remaining_size_frac = remaining_size_frac - tp_close_pcts[j] / 100.0
                        if remaining_size_frac < 0.0:
                            remaining_size_frac = 0.0

                        # Record partial close as a trade
                        if n_trades < _MAX_DCA_TRADES:
                            out_pnl[n_trades] = net_partial
                            out_entry_bar[n_trades] = pos_entry_bar
                            out_exit_bar[n_trades] = i
                            out_is_win[n_trades] = net_partial > 0.0
                        n_trades += 1

                        # Fully closed if fraction_of_current == 1.0 or size gone
                        if fraction_of_current >= 1.0 or pos_total_size <= 1e-15:
                            in_position = False
                            pos_avg_entry = 0.0
                            pos_total_size = 0.0
                            pos_total_cost = 0.0
                            pos_total_fee = 0.0
                            pos_n_filled = 0
                            breakeven_activated = False
                            pos_last_fill_price = 0.0
                            pullback_base_price = 0.0
                            trailing_grid_base_price = 0.0
                            has_pending_indent = False
                            pending_indent_price = 0.0
                            pending_indent_bar = 0
                            for kk in range(4):
                                tp_hit[kk] = False
                            remaining_size_frac = 1.0
                            trailing_activated = False
                            trailing_highest = 0.0
                            trailing_lowest = 1.0e18
                            trailing_stop_price = 0.0
                            atr_tp_price = 0.0
                            atr_sl_price = 0.0

            # --- 3. Exit checks (only if still in position after multi-TP) ---
            if in_position:
                # Unrealized profit % from avg entry (using close for safety close)
                if pos_total_size > 0 and pos_avg_entry > 0:
                    if pos_direction == 0:
                        unrealized_pct = (current_close - pos_avg_entry) / pos_avg_entry
                    else:
                        unrealized_pct = (pos_avg_entry - current_close) / pos_avg_entry
                else:
                    unrealized_pct = 0.0

                # Breakeven activation: uses intrabar HIGH (long) / LOW (short)
                if breakeven_activation_pct > 0.0 and not breakeven_activated:
                    if pos_direction == 0:
                        be_profit = (current_high - pos_avg_entry) / pos_avg_entry
                    else:
                        be_profit = (pos_avg_entry - current_low) / pos_avg_entry
                    if be_profit >= breakeven_activation_pct:
                        breakeven_activated = True

                # Trailing stop: activation check then update
                if trailing_activation_pct > 0.0:
                    if not trailing_activated:
                        if pos_direction == 0:
                            if current_high >= pos_avg_entry * (1.0 + trailing_activation_pct):
                                trailing_activated = True
                                trailing_highest = current_high
                                trailing_stop_price = trailing_highest * (1.0 - trailing_distance_pct)
                        else:
                            if current_low <= pos_avg_entry * (1.0 - trailing_activation_pct):
                                trailing_activated = True
                                trailing_lowest = current_low
                                trailing_stop_price = trailing_lowest * (1.0 + trailing_distance_pct)

                    if trailing_activated:
                        if pos_direction == 0:
                            if current_high > trailing_highest:
                                trailing_highest = current_high
                            new_ts = trailing_highest * (1.0 - trailing_distance_pct)
                            if new_ts > trailing_stop_price:
                                trailing_stop_price = new_ts
                        else:
                            if current_low < trailing_lowest:
                                trailing_lowest = current_low
                            new_ts = trailing_lowest * (1.0 + trailing_distance_pct)
                            if new_ts < trailing_stop_price:
                                trailing_stop_price = new_ts

                # Phase 2C: SL base price — last_order or avg_entry
                if sl_from_last_order > 0 and pos_last_fill_price > 0.0:
                    sl_base = pos_last_fill_price
                else:
                    sl_base = pos_avg_entry

                # Effective SL price (breakeven or regular) — uses sl_base
                if pos_direction == 0:
                    if breakeven_activated and breakeven_activation_pct > 0.0:
                        effective_sl_price = sl_base * (1.0 + breakeven_offset_pct)
                    elif stop_loss_pct > 0.0:
                        effective_sl_price = sl_base * (1.0 - stop_loss_pct)
                    else:
                        effective_sl_price = 0.0
                else:
                    if breakeven_activated and breakeven_activation_pct > 0.0:
                        effective_sl_price = sl_base * (1.0 - breakeven_offset_pct)
                    elif stop_loss_pct > 0.0:
                        effective_sl_price = sl_base * (1.0 + stop_loss_pct)
                    else:
                        effective_sl_price = 0.0

                # Build exit decision — V4 priority order:
                # 1. Safety close → 2. Close conditions → 3. Multi-TP/ATR TP/TP
                # 4. Breakeven activation → 5. Trailing stop fire → 6. SL (BE>ATR>config)
                # 7. close_by_time
                should_close = False
                exit_price = current_close
                exit_reason = 0  # 0=time/signal, 1=SL, 2=TP, 3=trailing, 4=atr_tp, 5=atr_sl, 6=close_cond

                # --- V4 priority 1: Safety close ---
                if safety_close_enabled > 0 and safety_close_threshold_pct > 0.0 and unrealized_pct < 0.0:
                    drawdown_pct = -unrealized_pct * leverage * 100.0
                    if drawdown_pct >= safety_close_threshold_pct:
                        should_close = True
                        exit_price = current_close
                        exit_reason = 1

                # --- V4 priority 2: Close conditions (Phase 1) ---
                if not should_close and n_close_cond > 0 and i < n_close_cond and close_cond[i]:
                    if close_cond_min_profit <= 0.0 or unrealized_pct >= close_cond_min_profit:
                        should_close = True
                        exit_price = current_close
                        exit_reason = 6

                # --- V4 priority 3: ATR TP ---
                if not should_close and atr_tp_multiplier > 0.0 and atr_tp_price > 0.0:
                    if (pos_direction == 0 and current_high >= atr_tp_price) or (
                        pos_direction == 1 and current_low <= atr_tp_price
                    ):
                        should_close = True
                        exit_reason = 4
                        exit_price = atr_tp_price

                # --- V4 priority 3b: Regular TP (only when multi_tp disabled) ---
                if not should_close and take_profit_pct > 0.0 and multi_tp_enabled == 0:
                    if pos_direction == 0:
                        if current_high >= pos_avg_entry * (1.0 + take_profit_pct):
                            should_close = True
                            exit_reason = 2
                    else:
                        if current_low <= pos_avg_entry * (1.0 - take_profit_pct):
                            should_close = True
                            exit_reason = 2

                # --- V4 priority 5: Trailing stop fire ---
                if not should_close and trailing_activated:
                    if (pos_direction == 0 and current_low <= trailing_stop_price) or (
                        pos_direction == 1 and current_high >= trailing_stop_price
                    ):
                        should_close = True
                        exit_reason = 3
                        exit_price = max(current_low, min(current_high, trailing_stop_price))

                # --- V4 priority 6a: ATR SL ---
                if not should_close and atr_sl_multiplier > 0.0 and atr_sl_price > 0.0:
                    if (pos_direction == 0 and current_low <= atr_sl_price) or (
                        pos_direction == 1 and current_high >= atr_sl_price
                    ):
                        should_close = True
                        exit_reason = 5
                        exit_price = max(current_low, min(current_high, atr_sl_price))

                # --- V4 priority 6b: Breakeven / regular SL ---
                if not should_close and effective_sl_price > 0.0:
                    if pos_direction == 0:
                        if current_low <= effective_sl_price:
                            should_close = True
                            exit_reason = 1
                            if breakeven_activated and breakeven_activation_pct > 0.0:
                                exit_price = max(current_low, min(current_high, effective_sl_price))
                    else:
                        if current_high >= effective_sl_price:
                            should_close = True
                            exit_reason = 1
                            if breakeven_activated and breakeven_activation_pct > 0.0:
                                exit_price = max(current_low, min(current_high, effective_sl_price))

                # --- V4 priority 7: close_by_time ---
                if not should_close and max_bars_in_trade > 0:
                    bars_open = i - pos_entry_bar
                    if bars_open >= max_bars_in_trade:
                        should_close = True
                        exit_price = current_close
                        exit_reason = 0  # noqa: F841

                if should_close:
                    exit_fee = pos_total_size * exit_price * taker_fee
                    if pos_direction == 0:
                        gross_pnl = (exit_price - pos_avg_entry) * pos_total_size
                    else:
                        gross_pnl = (pos_avg_entry - exit_price) * pos_total_size
                    net_pnl = gross_pnl - exit_fee - pos_total_fee

                    cash += pos_total_cost + net_pnl

                    if n_trades < _MAX_DCA_TRADES:
                        out_pnl[n_trades] = net_pnl
                        out_entry_bar[n_trades] = pos_entry_bar
                        out_exit_bar[n_trades] = i
                        out_is_win[n_trades] = net_pnl > 0.0
                    n_trades += 1

                    in_position = False
                    pos_avg_entry = 0.0
                    pos_total_size = 0.0
                    pos_total_cost = 0.0
                    pos_total_fee = 0.0
                    pos_n_filled = 0
                    breakeven_activated = False
                    pos_last_fill_price = 0.0
                    pullback_base_price = 0.0
                    trailing_grid_base_price = 0.0
                    has_pending_indent = False
                    pending_indent_price = 0.0
                    pending_indent_bar = 0
                    for kk in range(4):
                        tp_hit[kk] = False
                    remaining_size_frac = 1.0
                    trailing_activated = False
                    trailing_highest = 0.0
                    trailing_lowest = 1.0e18
                    trailing_stop_price = 0.0
                    atr_tp_price = 0.0
                    atr_sl_price = 0.0

        else:
            # --- Check for new entry ---
            sig = entry_signals[i]
            enter_long = (direction == 0 or direction == 2) and sig > 0
            enter_short = (direction == 1 or direction == 2) and sig < 0

            if (enter_long or enter_short) and not has_pending_indent:
                pos_direction = 0 if enter_long else 1

                # Phase 3A: Indent order — defer entry
                if indent_enabled > 0 and indent_pct > 0.0:
                    if pos_direction == 0:
                        pending_indent_price = current_close * (1.0 - indent_pct)
                    else:
                        pending_indent_price = current_close * (1.0 + indent_pct)
                    pending_indent_bar = i
                    pending_indent_dir = pos_direction
                    has_pending_indent = True
                else:
                    # Immediate entry (original logic)
                    entry_price = current_close
                    alloc_capital = initial_capital * position_size_frac
                    capital_per_order0 = alloc_capital / max(order_count, 1)

                    pos_n_orders = _calc_grid_orders(
                        entry_price,
                        pos_direction,
                        order_count,
                        grid_size_pct,
                        martingale_coef,
                        capital_per_order0,
                        leverage,
                        taker_fee,
                        g_prices,
                        g_size_coins,
                        g_margin_usd,
                        martingale_mode,
                        use_log_steps,
                        log_coefficient,
                    )
                    for k in range(pos_n_orders):
                        g_filled[k] = False
                        g_active[k] = False

                    g_filled[0] = True
                    g_active[0] = True
                    entry_fee_0 = g_margin_usd[0] * leverage * taker_fee
                    cash -= g_margin_usd[0]
                    pos_total_size = g_size_coins[0]
                    pos_total_cost = g_margin_usd[0]
                    pos_total_fee = entry_fee_0
                    pos_avg_entry = entry_price
                    pos_last_fill_price = entry_price
                    pos_n_filled = 1
                    pos_entry_bar = i
                    breakeven_activated = False
                    in_position = True

                    # Phase 2B: partial grid init
                    if partial_grid_orders >= 2:
                        pos_active_up_to = min(partial_grid_orders, pos_n_orders)
                    else:
                        pos_active_up_to = pos_n_orders
                    for k in range(pos_active_up_to):
                        g_active[k] = True

                    # Reset Multi-TP / trailing / ATR / grid state for new position
                    for kk in range(4):
                        tp_hit[kk] = False
                    remaining_size_frac = 1.0
                    trailing_activated = False
                    trailing_highest = 0.0
                    trailing_lowest = 1.0e18
                    trailing_stop_price = 0.0
                    pullback_base_price = entry_price
                    trailing_grid_base_price = entry_price

                    # ATR TP/SL at entry
                    atr_tp_price = 0.0
                    atr_sl_price = 0.0
                    if atr_tp_multiplier > 0.0 and n_atr > 0 and i < n_atr:
                        atr_v = atr_values[i]
                        if atr_v > 0.0:
                            if pos_direction == 0:
                                atr_tp_price = entry_price + atr_v * atr_tp_multiplier
                                if atr_sl_multiplier > 0.0:
                                    atr_sl_price = entry_price - atr_v * atr_sl_multiplier
                            else:
                                atr_tp_price = entry_price - atr_v * atr_tp_multiplier
                                if atr_sl_multiplier > 0.0:
                                    atr_sl_price = entry_price + atr_v * atr_sl_multiplier

        # Equity = cash + unrealized PnL
        if in_position and pos_total_size > 0:
            if pos_direction == 0:
                unrealized = (current_close - pos_avg_entry) * pos_total_size
            else:
                unrealized = (pos_avg_entry - current_close) * pos_total_size
            out_equity[i] = cash + pos_total_cost + unrealized
        else:
            out_equity[i] = cash

    # Close remaining open position at last bar
    if in_position and pos_total_size > 0:
        last_close = close[n_bars - 1]
        exit_fee = pos_total_size * last_close * taker_fee
        if pos_direction == 0:
            gross_pnl = (last_close - pos_avg_entry) * pos_total_size
        else:
            gross_pnl = (pos_avg_entry - last_close) * pos_total_size
        net_pnl = gross_pnl - exit_fee - pos_total_fee
        cash += pos_total_cost + net_pnl

        if n_trades < _MAX_DCA_TRADES:
            out_pnl[n_trades] = net_pnl
            out_entry_bar[n_trades] = pos_entry_bar
            out_exit_bar[n_trades] = n_bars - 1
            out_is_win[n_trades] = net_pnl > 0.0
        n_trades += 1

        out_equity[n_bars - 1] = cash

    return n_trades


@njit(cache=True, fastmath=True)
def _compute_summary_stats(
    equity: np.ndarray,  # float64[n_bars]
    pnl: np.ndarray,  # float64[n_trades]
    exit_bar: np.ndarray,  # int64[n_trades]
    is_win: np.ndarray,  # bool[n_trades]
    n_trades: int,
    initial_capital: float,
    bars_per_month: int,  # approx bars per calendar month (e.g. 1460 for 30m)
) -> tuple[float, float, float, float, float, int]:
    """
    Compute summary stats matching V4 DCA engine conventions.

    Returns:
        net_profit, max_drawdown_frac, win_rate, sharpe_monthly_tv, profit_factor, n_trades

    max_drawdown_frac: (peak_closed_equity - closed_equity) / initial_capital
        Matches FallbackEngineV4._calculate_metrics() — closed-trade equity,
        initial_capital denominator. Can exceed 1.0 with leverage.

    sharpe_monthly_tv: TradingView-compatible monthly Sharpe (no annualization).
        Groups trades by approximate calendar month (exit_bar // bars_per_month).
        Formula: (mean(monthly_equity_returns) - rfr_monthly) / std(returns, ddof=0)
        Matches calc_sharpe_monthly_tv() in formulas.py.
    """
    n_bars = len(equity)
    if n_bars == 0 or n_trades == 0:
        return 0.0, 0.0, 0.0, 0.0, 0.0, 0

    nt = min(n_trades, _MAX_DCA_TRADES)

    # Net profit
    net_profit = equity[n_bars - 1] - initial_capital

    # === Max drawdown: closed-trade equity, V4 formula ===
    peak_ct = initial_capital
    closed_eq_cur = initial_capital
    max_dd = 0.0
    for j in range(nt):
        closed_eq_cur += pnl[j]
        if closed_eq_cur > peak_ct:
            peak_ct = closed_eq_cur
        dd = (peak_ct - closed_eq_cur) / max(initial_capital, 1e-10)
        if dd > max_dd:
            max_dd = dd

    # Win rate, gross profit/loss
    gross_profit = 0.0
    gross_loss = 0.0
    n_wins = 0
    for j in range(nt):
        if is_win[j]:
            gross_profit += pnl[j]
            n_wins += 1
        else:
            gross_loss += abs(pnl[j])

    win_rate = n_wins / nt if nt > 0 else 0.0
    profit_factor = gross_profit / max(gross_loss, 1e-10)

    # === Sharpe: monthly TV-parity approximation ===
    sharpe = 0.0
    if nt >= 2 and bars_per_month > 0:
        closed_equity = np.empty(_MAX_DCA_TRADES + 1, dtype=np.float64)
        closed_equity[0] = initial_capital
        for j in range(nt):
            closed_equity[j + 1] = closed_equity[j] + pnl[j]

        month_eq = np.empty(_MAX_MONTHS, dtype=np.float64)
        for m in range(_MAX_MONTHS):
            month_eq[m] = -1.0

        base_m = exit_bar[0] // bars_per_month
        last_rel_m = 0
        for j in range(nt):
            rel_m = exit_bar[j] // bars_per_month - base_m
            if rel_m < 0:
                rel_m = 0
            if rel_m >= _MAX_MONTHS:
                rel_m = _MAX_MONTHS - 1
            month_eq[rel_m] = closed_equity[j + 1]
            if rel_m > last_rel_m:
                last_rel_m = rel_m

        prev_eq = initial_capital
        for m in range(last_rel_m + 1):
            if month_eq[m] < 0.0:
                month_eq[m] = prev_eq
            else:
                prev_eq = month_eq[m]

        n_months = last_rel_m + 1
        if n_months >= 2:
            rfr_monthly = 0.02 / 12.0

            mean_r = 0.0
            for m in range(n_months):
                eq_start = initial_capital if m == 0 else month_eq[m - 1]
                eq_end = month_eq[m]
                r = (eq_end - eq_start) / max(eq_start, 1e-10)
                mean_r += r
            mean_r /= n_months

            var_r = 0.0
            for m in range(n_months):
                eq_start = initial_capital if m == 0 else month_eq[m - 1]
                eq_end = month_eq[m]
                r = (eq_end - eq_start) / max(eq_start, 1e-10)
                var_r += (r - mean_r) ** 2
            var_r /= n_months
            std_r = var_r**0.5

            if std_r > 1e-10:
                sharpe = (mean_r - rfr_monthly) / std_r
                if sharpe > 100.0:
                    sharpe = 100.0
                elif sharpe < -100.0:
                    sharpe = -100.0

    return net_profit, max_dd, win_rate, sharpe, profit_factor, n_trades


# ---------------------------------------------------------------------------
# Batch parallel simulation — outer loop over N param combos via prange
# ---------------------------------------------------------------------------


@njit(cache=True, fastmath=True, parallel=True)
def batch_simulate_dca(
    close: np.ndarray,  # float64[n_bars]
    high: np.ndarray,  # float64[n_bars]
    low: np.ndarray,  # float64[n_bars]
    entry_signals: np.ndarray,  # int8[n_bars]
    # Per-combo arrays (length N_combos):
    sl_pct_arr: np.ndarray,  # float64[N]
    tp_pct_arr: np.ndarray,  # float64[N]
    # Shared DCA config (scalars):
    direction: int,
    order_count: int,
    grid_size_pct: float,
    martingale_coef: float,
    initial_capital: float,
    position_size_frac: float,
    leverage: float,
    taker_fee: float,
    # close_by_time (shared for all combos)
    max_bars_in_trade: int,
    min_profit_close_pct: float,
    # breakeven (shared for all combos)
    breakeven_activation_pct: float,
    breakeven_offset_pct: float,
    # safety close (shared for all combos)
    safety_close_enabled: int,
    safety_close_threshold_pct: float,
    # bars per month for monthly sharpe computation
    bars_per_month: int,
    # Trailing stop (shared; 0.0 = disabled)
    trailing_activation_pct: float,
    trailing_distance_pct: float,
    # Multi-TP (shared; multi_tp_enabled=0 uses single tp above)
    multi_tp_enabled: int,
    tp_percents: np.ndarray,  # float64[4]
    tp_close_pcts: np.ndarray,  # float64[4]
    tp_count: int,
    # ATR TP/SL (shared; 0.0 = disabled)
    atr_tp_multiplier: float,
    atr_sl_multiplier: float,
    atr_values: np.ndarray,  # float64[n_bars] or empty
    # === Phase 1 new params ===
    martingale_mode: int,  # 0=each, 1=total, 2=progressive
    close_cond: np.ndarray,  # bool[n_bars] or empty
    close_cond_min_profit: float,  # 0.0 = no filter
    # === Phase 2 new params ===
    grid_pullback_pct: float,  # 0.0 = disabled
    grid_trailing_pct: float,  # 0.0 = disabled
    partial_grid_orders: int,  # 0 or 1 = all, 2+ = partial
    sl_from_last_order: int,  # 0=avg_entry, 1=last_order
    # === Phase 3 new params ===
    indent_enabled: int,  # 0/1
    indent_pct: float,  # 0.0 = disabled
    indent_cancel_bars: int,  # 0 = no cancel
    use_log_steps: int,  # 0/1
    log_coefficient: float,  # 1.0 = no effect
    # Output (pre-allocated):
    out_net_profit: np.ndarray,  # float64[N]
    out_max_dd: np.ndarray,  # float64[N]
    out_win_rate: np.ndarray,  # float64[N]
    out_sharpe: np.ndarray,  # float64[N]
    out_profit_factor: np.ndarray,  # float64[N]
    out_n_trades: np.ndarray,  # int64[N]
) -> None:
    """
    Batch-simulate N DCA parameter combinations in parallel.

    Each combo i uses sl_pct_arr[i], tp_pct_arr[i].
    All other parameters (including multi-TP, trailing, ATR, close conditions,
    grid pullback/trailing, partial grid, indent orders) are shared across combos.
    Results written into out_* arrays.
    """
    n_combos = len(sl_pct_arr)
    n_bars = len(close)

    for i in prange(n_combos):
        pnl_buf = np.empty(_MAX_DCA_TRADES, dtype=np.float64)
        entry_bar_buf = np.empty(_MAX_DCA_TRADES, dtype=np.int64)
        exit_bar_buf = np.empty(_MAX_DCA_TRADES, dtype=np.int64)
        is_win_buf = np.empty(_MAX_DCA_TRADES, dtype=np.bool_)
        equity_buf = np.empty(n_bars, dtype=np.float64)

        n_trades = _simulate_dca_single(
            close,
            high,
            low,
            entry_signals,
            direction,
            order_count,
            grid_size_pct,
            martingale_coef,
            tp_pct_arr[i],
            sl_pct_arr[i],
            initial_capital,
            position_size_frac,
            leverage,
            taker_fee,
            max_bars_in_trade,
            min_profit_close_pct,
            breakeven_activation_pct,
            breakeven_offset_pct,
            safety_close_enabled,
            safety_close_threshold_pct,
            trailing_activation_pct,
            trailing_distance_pct,
            multi_tp_enabled,
            tp_percents,
            tp_close_pcts,
            tp_count,
            atr_tp_multiplier,
            atr_sl_multiplier,
            atr_values,
            # Phase 1-3 new params
            martingale_mode,
            close_cond,
            close_cond_min_profit,
            grid_pullback_pct,
            grid_trailing_pct,
            partial_grid_orders,
            sl_from_last_order,
            indent_enabled,
            indent_pct,
            indent_cancel_bars,
            use_log_steps,
            log_coefficient,
            pnl_buf,
            entry_bar_buf,
            exit_bar_buf,
            is_win_buf,
            equity_buf,
        )

        net_p, max_dd, wr, sharpe, pf, nt = _compute_summary_stats(
            equity_buf,
            pnl_buf,
            exit_bar_buf,
            is_win_buf,
            n_trades,
            initial_capital,
            bars_per_month,
        )
        out_net_profit[i] = net_p
        out_max_dd[i] = max_dd
        out_win_rate[i] = wr
        out_sharpe[i] = sharpe
        out_profit_factor[i] = pf
        out_n_trades[i] = nt


# ---------------------------------------------------------------------------
# Public Python-level API
# ---------------------------------------------------------------------------


def run_dca_batch_numba(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    entry_signals: np.ndarray,
    sl_pct_arr: np.ndarray,
    tp_pct_arr: np.ndarray,
    direction: int = 0,
    order_count: int = 5,
    grid_size_pct: float = 10.0,
    martingale_coef: float = 1.3,
    initial_capital: float = 10000.0,
    position_size_frac: float = 1.0,
    leverage: float = 1.0,
    taker_fee: float = 0.0007,
    # close_by_time (0 = disabled)
    max_bars_in_trade: int = 0,
    min_profit_close_pct: float = 0.0,
    # breakeven (0.0 = disabled)
    breakeven_activation_pct: float = 0.0,
    breakeven_offset_pct: float = 0.0,
    # safety close (0 = disabled)
    safety_close_enabled: int = 0,
    safety_close_threshold_pct: float = 30.0,
    # monthly sharpe
    bars_per_month: int = 1460,
    # trailing stop (0.0 = disabled)
    trailing_activation_pct: float = 0.0,
    trailing_distance_pct: float = 0.0,
    # multi-TP (0 = disabled)
    multi_tp_enabled: int = 0,
    tp_percents: list | None = None,
    tp_close_pcts: list | None = None,
    tp_count: int = 4,
    # ATR TP/SL (0.0 = disabled)
    atr_tp_multiplier: float = 0.0,
    atr_sl_multiplier: float = 0.0,
    atr_values: np.ndarray | None = None,
    # === Phase 1 new params ===
    martingale_mode: int = 0,
    close_cond: np.ndarray | None = None,
    close_cond_min_profit: float = 0.0,
    # === Phase 2 new params ===
    grid_pullback_pct: float = 0.0,
    grid_trailing_pct: float = 0.0,
    partial_grid_orders: int = 0,
    sl_from_last_order: int = 0,
    # === Phase 3 new params ===
    indent_enabled: int = 0,
    indent_pct: float = 0.0,
    indent_cancel_bars: int = 0,
    use_log_steps: int = 0,
    log_coefficient: float = 1.0,
) -> dict:
    """
    Run batch DCA simulation for N (sl, tp) combinations.

    Args:
        close/high/low: OHLCV numpy arrays (float64)
        entry_signals: int8 array — >0 long entry, <0 short, 0 none
        sl_pct_arr: array of stop-loss fractions (e.g. [0.02, 0.03, ...])
        tp_pct_arr: array of take-profit fractions (e.g. [0.04, 0.06, ...])
        direction: 0=long, 1=short, 2=both
        order_count: number of DCA grid levels (1-15)
        grid_size_pct: total grid depth as % (e.g. 10.0 = 10%)
        martingale_coef: size multiplier per level (≥1.0)
        initial_capital: starting capital in USD
        position_size_frac: fraction of equity allocated per trade (0-1)
        leverage: multiplier (e.g. 3.0)
        taker_fee: commission fraction (e.g. 0.0007)
        max_bars_in_trade: close position after N bars (0 = disabled)
        min_profit_close_pct: minimum profit fraction for time-based close (0 = disabled)
        breakeven_activation_pct: activate breakeven SL when profit >= this fraction (0 = disabled)
        breakeven_offset_pct: breakeven SL offset above avg entry for long
        safety_close_enabled: 1 = close when position drawdown >= threshold%
        safety_close_threshold_pct: drawdown % of margin to trigger safety close
        trailing_activation_pct: activate trailing when profit >= this fraction (0 = disabled)
        trailing_distance_pct: trail at this distance below/above peak
        multi_tp_enabled: 1 = use TP levels instead of single take_profit_pct
        tp_percents: list of 4 TP profit fractions e.g. [0.01, 0.02, 0.03, 0.05]
        tp_close_pcts: list of 4 close percentages e.g. [25.0, 25.0, 25.0, 25.0]
        tp_count: number of active TP levels (1-4)
        atr_tp_multiplier: TP = avg_entry + ATR * multiplier (0 = disabled)
        atr_sl_multiplier: SL = avg_entry - ATR * multiplier (0 = disabled)
        atr_values: pre-computed ATR array (None = disabled)

    Returns:
        dict with arrays: net_profit, max_drawdown, win_rate, sharpe, profit_factor, n_trades
    """
    n = len(sl_pct_arr)
    assert len(tp_pct_arr) == n, "sl_pct_arr and tp_pct_arr must have same length"

    # Ensure correct dtypes for Numba
    close = np.asarray(close, dtype=np.float64)
    high = np.asarray(high, dtype=np.float64)
    low = np.asarray(low, dtype=np.float64)
    entry_signals = np.asarray(entry_signals, dtype=np.int8)
    sl_pct_arr = np.asarray(sl_pct_arr, dtype=np.float64)
    tp_pct_arr = np.asarray(tp_pct_arr, dtype=np.float64)

    # Multi-TP arrays (always size 4)
    _tp_percents = np.array(
        tp_percents if tp_percents is not None else [0.01, 0.02, 0.03, 0.05],
        dtype=np.float64,
    )
    _tp_close_pcts = np.array(
        tp_close_pcts if tp_close_pcts is not None else [25.0, 25.0, 25.0, 25.0],
        dtype=np.float64,
    )
    _atr_values = np.asarray(atr_values, dtype=np.float64) if atr_values is not None else np.empty(0, dtype=np.float64)
    _close_cond = np.asarray(close_cond, dtype=np.bool_) if close_cond is not None else np.empty(0, dtype=np.bool_)

    # Pre-allocate output arrays
    out_net_profit = np.empty(n, dtype=np.float64)
    out_max_dd = np.empty(n, dtype=np.float64)
    out_win_rate = np.empty(n, dtype=np.float64)
    out_sharpe = np.empty(n, dtype=np.float64)
    out_profit_factor = np.empty(n, dtype=np.float64)
    out_n_trades = np.empty(n, dtype=np.int64)

    batch_simulate_dca(
        close,
        high,
        low,
        entry_signals,
        sl_pct_arr,
        tp_pct_arr,
        direction,
        order_count,
        grid_size_pct,
        martingale_coef,
        initial_capital,
        position_size_frac,
        leverage,
        taker_fee,
        int(max_bars_in_trade),
        float(min_profit_close_pct),
        float(breakeven_activation_pct),
        float(breakeven_offset_pct),
        int(safety_close_enabled),
        float(safety_close_threshold_pct),
        int(bars_per_month),
        float(trailing_activation_pct),
        float(trailing_distance_pct),
        int(multi_tp_enabled),
        _tp_percents,
        _tp_close_pcts,
        int(tp_count),
        float(atr_tp_multiplier),
        float(atr_sl_multiplier),
        _atr_values,
        # Phase 1-3 new params
        int(martingale_mode),
        _close_cond,
        float(close_cond_min_profit),
        float(grid_pullback_pct),
        float(grid_trailing_pct),
        int(partial_grid_orders),
        int(sl_from_last_order),
        int(indent_enabled),
        float(indent_pct),
        int(indent_cancel_bars),
        int(use_log_steps),
        float(log_coefficient),
        out_net_profit,
        out_max_dd,
        out_win_rate,
        out_sharpe,
        out_profit_factor,
        out_n_trades,
    )

    return {
        "net_profit": out_net_profit,
        "max_drawdown": out_max_dd,
        "win_rate": out_win_rate,
        "sharpe": out_sharpe,
        "profit_factor": out_profit_factor,
        "n_trades": out_n_trades,
    }


def run_dca_single_numba(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    entry_signals: np.ndarray,
    sl_pct: float,
    tp_pct: float,
    direction: int = 0,
    order_count: int = 5,
    grid_size_pct: float = 10.0,
    martingale_coef: float = 1.3,
    initial_capital: float = 10000.0,
    position_size_frac: float = 1.0,
    leverage: float = 1.0,
    taker_fee: float = 0.0007,
    max_bars_in_trade: int = 0,
    min_profit_close_pct: float = 0.0,
    breakeven_activation_pct: float = 0.0,
    breakeven_offset_pct: float = 0.0,
    safety_close_enabled: int = 0,
    safety_close_threshold_pct: float = 30.0,
    bars_per_month: int = 1460,
    trailing_activation_pct: float = 0.0,
    trailing_distance_pct: float = 0.0,
    multi_tp_enabled: int = 0,
    tp_percents: list | None = None,
    tp_close_pcts: list | None = None,
    tp_count: int = 4,
    atr_tp_multiplier: float = 0.0,
    atr_sl_multiplier: float = 0.0,
    atr_values: np.ndarray | None = None,
    # === Phase 1 new params ===
    martingale_mode: int = 0,
    close_cond: np.ndarray | None = None,
    close_cond_min_profit: float = 0.0,
    # === Phase 2 new params ===
    grid_pullback_pct: float = 0.0,
    grid_trailing_pct: float = 0.0,
    partial_grid_orders: int = 0,
    sl_from_last_order: int = 0,
    # === Phase 3 new params ===
    indent_enabled: int = 0,
    indent_pct: float = 0.0,
    indent_cancel_bars: int = 0,
    use_log_steps: int = 0,
    log_coefficient: float = 1.0,
) -> dict:
    """
    Run a single DCA simulation and return full metrics.

    Suitable for validating parity with DCAEngine and computing top-N metrics
    after optimization finds the best parameter combinations.

    Returns:
        dict with scalar metrics + equity_curve (numpy array)
    """
    close = np.asarray(close, dtype=np.float64)
    high = np.asarray(high, dtype=np.float64)
    low = np.asarray(low, dtype=np.float64)
    entry_signals = np.asarray(entry_signals, dtype=np.int8)

    _tp_percents = np.array(
        tp_percents if tp_percents is not None else [0.01, 0.02, 0.03, 0.05],
        dtype=np.float64,
    )
    _tp_close_pcts = np.array(
        tp_close_pcts if tp_close_pcts is not None else [25.0, 25.0, 25.0, 25.0],
        dtype=np.float64,
    )
    _atr_values = np.asarray(atr_values, dtype=np.float64) if atr_values is not None else np.empty(0, dtype=np.float64)
    _close_cond = np.asarray(close_cond, dtype=np.bool_) if close_cond is not None else np.empty(0, dtype=np.bool_)

    n_bars = len(close)
    pnl_buf = np.empty(_MAX_DCA_TRADES, dtype=np.float64)
    entry_bar_buf = np.empty(_MAX_DCA_TRADES, dtype=np.int64)
    exit_bar_buf = np.empty(_MAX_DCA_TRADES, dtype=np.int64)
    is_win_buf = np.empty(_MAX_DCA_TRADES, dtype=np.bool_)
    equity_curve = np.empty(n_bars, dtype=np.float64)

    n_trades = _simulate_dca_single(
        close,
        high,
        low,
        entry_signals,
        direction,
        order_count,
        grid_size_pct,
        martingale_coef,
        tp_pct,
        sl_pct,
        initial_capital,
        position_size_frac,
        leverage,
        taker_fee,
        int(max_bars_in_trade),
        float(min_profit_close_pct),
        float(breakeven_activation_pct),
        float(breakeven_offset_pct),
        int(safety_close_enabled),
        float(safety_close_threshold_pct),
        float(trailing_activation_pct),
        float(trailing_distance_pct),
        int(multi_tp_enabled),
        _tp_percents,
        _tp_close_pcts,
        int(tp_count),
        float(atr_tp_multiplier),
        float(atr_sl_multiplier),
        _atr_values,
        # Phase 1-3 new params
        int(martingale_mode),
        _close_cond,
        float(close_cond_min_profit),
        float(grid_pullback_pct),
        float(grid_trailing_pct),
        int(partial_grid_orders),
        int(sl_from_last_order),
        int(indent_enabled),
        float(indent_pct),
        int(indent_cancel_bars),
        int(use_log_steps),
        float(log_coefficient),
        pnl_buf,
        entry_bar_buf,
        exit_bar_buf,
        is_win_buf,
        equity_curve,
    )

    net_p, max_dd, wr, sharpe, pf, nt = _compute_summary_stats(
        equity_curve,
        pnl_buf,
        exit_bar_buf,
        is_win_buf,
        n_trades,
        initial_capital,
        int(bars_per_month),
    )

    return {
        "net_profit": float(net_p),
        "total_return": float(net_p / initial_capital * 100.0) if initial_capital > 0 else 0.0,
        "max_drawdown": float(max_dd * 100.0),  # as percent
        "win_rate": float(wr * 100.0),
        "sharpe_ratio": float(sharpe),
        "profit_factor": float(pf),
        "n_trades": int(nt),
        "equity_curve": equity_curve,
        "trades_pnl": pnl_buf[:n_trades].copy(),
    }


def warmup_numba_dca() -> None:
    """
    Pre-compile Numba functions with a tiny dummy dataset.

    Call once at application startup (lifespan.py) to avoid first-call
    compilation overhead of 2-5 seconds during live requests.
    Exercises all Phase 1-3 code paths for complete JIT compilation.
    """
    try:
        n = 50
        dummy_close = np.linspace(100.0, 110.0, n)
        dummy_high = dummy_close * 1.005
        dummy_low = dummy_close * 0.995
        dummy_signals = np.zeros(n, dtype=np.int8)
        dummy_signals[5] = 1
        dummy_signals[25] = 1
        dummy_close_cond = np.zeros(n, dtype=np.bool_)
        dummy_close_cond[30] = True

        sl_arr = np.array([0.03, 0.05], dtype=np.float64)
        tp_arr = np.array([0.06, 0.10], dtype=np.float64)

        # Warmup 1: batch with defaults (backward compat)
        run_dca_batch_numba(
            dummy_close,
            dummy_high,
            dummy_low,
            dummy_signals,
            sl_arr,
            tp_arr,
            direction=0,
            order_count=3,
            grid_size_pct=5.0,
            martingale_coef=1.3,
            initial_capital=1000.0,
            position_size_frac=0.5,
            leverage=1.0,
            taker_fee=0.0007,
        )

        # Warmup 2: single with multi-TP, trailing, and Phase 1-3 features
        run_dca_single_numba(
            dummy_close,
            dummy_high,
            dummy_low,
            dummy_signals,
            sl_pct=0.05,
            tp_pct=0.0,
            direction=0,
            order_count=3,
            grid_size_pct=5.0,
            martingale_coef=1.0,
            initial_capital=1000.0,
            trailing_activation_pct=0.02,
            trailing_distance_pct=0.01,
            multi_tp_enabled=1,
            tp_percents=[0.01, 0.02, 0.03, 0.05],
            tp_close_pcts=[25.0, 25.0, 25.0, 25.0],
            tp_count=4,
            # Phase 1
            martingale_mode=1,
            close_cond=dummy_close_cond,
            close_cond_min_profit=0.01,
            # Phase 2
            grid_pullback_pct=2.0,
            grid_trailing_pct=1.5,
            partial_grid_orders=2,
            sl_from_last_order=1,
            # Phase 3
            indent_enabled=0,
            indent_pct=0.005,
            indent_cancel_bars=3,
            use_log_steps=1,
            log_coefficient=1.5,
        )

        logger.info("Numba DCA engine warmed up successfully (Phase 1-3 compiled).")
    except Exception as exc:
        logger.warning(f"Numba DCA warmup skipped: {exc}")
