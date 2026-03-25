"""
GPU CUDA DCA Simulation Engine via Numba @cuda.jit.

Each CUDA thread simulates ONE parameter combination (sl, tp) over the full
OHLCV bar series. With 768 CUDA cores on GTX 1050 Ti (and 3,000+ concurrent
threads), 304,668 DCA combinations complete in seconds rather than hours.

Architecture:
    - kernel `_dca_kernel`: one thread per combo → bar-by-bar DCA simulation
    - device function `_calc_grid_prices_cuda`: grid price/size calc (per thread)
    - public API `run_dca_batch_cuda`: host-side orchestration
    - automatic CPU fallback when CUDA unavailable

Limitations (same as numba_dca_engine.py):
    ✗ Multi-TP, close conditions, breakeven, indent orders not supported
    ✔ Single SL/TP, grid orders, martingale sizing, commission

CUDA thread layout:
    - Block size: BLOCK_SIZE = 256 threads
    - Grid size:  ceil(N_combos / BLOCK_SIZE) blocks
    - Each thread i: reads sl_pct[i], tp_pct[i] from device arrays
                     reads close/high/low/signals from global device memory
                     writes result scalars to output device arrays
"""

from __future__ import annotations

import logging
import math

import numpy as np

logger = logging.getLogger(__name__)

# CUDA block size (threads per block)
_CUDA_BLOCK_SIZE: int = 256

# Max DCA orders per grid (matches CPU version)
_MAX_ORDERS_CUDA: int = 15

# Try to import Numba CUDA — fail gracefully
_CUDA_AVAILABLE: bool = False
try:
    from numba import cuda

    _CUDA_AVAILABLE = cuda.is_available()
except ImportError:
    pass


# ---------------------------------------------------------------------------
# CUDA device helper — called from inside the kernel
# ---------------------------------------------------------------------------

if _CUDA_AVAILABLE:
    from numba import cuda as _cuda

    @_cuda.jit(device=True)
    def _calc_grid_price(base_price: float, level: int, step_pct: float, direction: int) -> float:
        """Compute the trigger price for DCA grid level `level`."""
        if direction == 0:  # long
            return base_price * (1.0 - level * step_pct)
        else:  # short
            return base_price * (1.0 + level * step_pct)

    @_cuda.jit(device=True)
    def _calc_grid_size(
        capital_per_order0: float,
        leverage: float,
        taker_fee: float,
        trigger_price: float,
        weight: float,
    ) -> tuple[float, float]:
        """Return (size_coins, margin_usd) for one grid level given its weight."""
        margin_usd = capital_per_order0 * weight
        notional = margin_usd * leverage
        fee = notional * taker_fee
        size_coins = (notional - fee) / max(trigger_price, 1e-10)
        return size_coins, margin_usd

    # -------------------------------------------------------------------------
    # Main CUDA kernel — one thread = one (sl, tp) combination
    # -------------------------------------------------------------------------

    @_cuda.jit
    def _dca_kernel(
        close,  # float64[n_bars]
        high,  # float64[n_bars]
        low,  # float64[n_bars]
        signals,  # int8[n_bars]
        sl_pct_dev,  # float64[N]
        tp_pct_dev,  # float64[N]
        # DCA config scalars passed as 1-element arrays (CUDA can't pass Python scalars directly)
        cfg,  # float64[7]: [direction, order_count, grid_size_pct, martingale_coef,
        #              initial_capital, position_size_frac, leverage, taker_fee]
        # Outputs
        out_net_profit,  # float64[N]
        out_max_dd,  # float64[N]
        out_win_rate,  # float64[N]
        out_n_trades,  # int32[N]
        out_profit_factor,  # float64[N]
    ) -> None:
        """
        CUDA kernel: each thread i simulates DCA combo (sl_pct[i], tp_pct[i]).
        """
        i = _cuda.blockIdx.x * _cuda.blockDim.x + _cuda.threadIdx.x
        n_combos = len(sl_pct_dev)
        if i >= n_combos:
            return

        # Unpack config
        direction = int(cfg[0])
        order_count = int(cfg[1])
        grid_size = cfg[2]
        mart_coef = cfg[3]
        init_cap = cfg[4]
        pos_frac = cfg[5]
        leverage = cfg[6]
        taker_fee = cfg[7]

        n_bars = len(close)
        sl_pct = sl_pct_dev[i]
        tp_pct = tp_pct_dev[i]

        # Clamp order_count
        n_orders = min(order_count, _MAX_ORDERS_CUDA)
        if n_orders < 1:
            n_orders = 1

        # Grid step percent per level
        step_pct = grid_size / 100.0 / max(n_orders - 1, 1)

        # Pre-compute martingale weights (stack arrays — CUDA local memory)
        weights = _cuda.local.array(_MAX_ORDERS_CUDA, dtype=np.float64)
        w = 1.0
        for k in range(n_orders):
            weights[k] = w
            w *= mart_coef

        # --- State variables ---
        cash = init_cap
        in_pos = False
        pos_dir = 0
        pos_avg_entry = 0.0
        pos_total_size = 0.0
        pos_total_cost = 0.0
        pos_total_fee = 0.0

        # Grid order fill state (local arrays)
        g_filled = _cuda.local.array(_MAX_ORDERS_CUDA, dtype=np.bool_)
        g_prices = _cuda.local.array(_MAX_ORDERS_CUDA, dtype=np.float64)
        g_sizes = _cuda.local.array(_MAX_ORDERS_CUDA, dtype=np.float64)
        g_margins = _cuda.local.array(_MAX_ORDERS_CUDA, dtype=np.float64)
        pos_n_orders = 0

        # Trade stats
        n_trades = 0
        n_wins = 0
        gross_profit = 0.0
        gross_loss = 0.0

        # Equity tracking for max drawdown
        peak_equity = init_cap
        max_dd = 0.0
        equity_sum = 0.0  # for mean return approximation
        prev_equity = init_cap

        for bar in range(n_bars):
            cur_close = close[bar]
            cur_high = high[bar]
            cur_low = low[bar]
            sig = signals[bar]

            if in_pos:
                # Check unfilled grid order fills
                for k in range(pos_n_orders):
                    if not g_filled[k]:
                        fill = False
                        if (pos_dir == 0 and cur_low <= g_prices[k]) or (pos_dir == 1 and cur_high >= g_prices[k]):
                            fill = True
                        if fill:
                            g_filled[k] = True
                            pos_total_size += g_sizes[k]
                            pos_total_cost += g_margins[k]
                            fee_k = g_margins[k] * leverage * taker_fee
                            pos_total_fee += fee_k
                            cash -= g_margins[k]
                            if pos_total_size > 0.0:
                                pos_avg_entry = (pos_total_cost * leverage) / pos_total_size

                # Check TP and SL
                should_close = False
                exit_price = cur_close

                if pos_dir == 0:  # long
                    if tp_pct > 0.0:
                        tp_price = pos_avg_entry * (1.0 + tp_pct)
                        if cur_high >= tp_price:
                            should_close = True
                            exit_price = min(tp_price, cur_high)
                    if not should_close and sl_pct > 0.0:
                        sl_price = pos_avg_entry * (1.0 - sl_pct)
                        if cur_low <= sl_price:
                            should_close = True
                            exit_price = max(sl_price, cur_low)
                else:  # short
                    if tp_pct > 0.0:
                        tp_price = pos_avg_entry * (1.0 - tp_pct)
                        if cur_low <= tp_price:
                            should_close = True
                            exit_price = max(tp_price, cur_low)
                    if not should_close and sl_pct > 0.0:
                        sl_price = pos_avg_entry * (1.0 + sl_pct)
                        if cur_high >= sl_price:
                            should_close = True
                            exit_price = min(sl_price, cur_high)

                if should_close:
                    exit_fee = pos_total_size * exit_price * taker_fee
                    if pos_dir == 0:
                        pnl = (exit_price - pos_avg_entry) * pos_total_size - exit_fee - pos_total_fee
                    else:
                        pnl = (pos_avg_entry - exit_price) * pos_total_size - exit_fee - pos_total_fee

                    cash += pos_total_cost + pnl
                    n_trades += 1
                    if pnl > 0.0:
                        n_wins += 1
                        gross_profit += pnl
                    else:
                        gross_loss += abs(pnl)

                    in_pos = False
                    pos_avg_entry = 0.0
                    pos_total_size = 0.0
                    pos_total_cost = 0.0
                    pos_total_fee = 0.0

            else:
                # Check for entry signal
                enter_long = (direction == 0 or direction == 2) and sig > 0
                enter_short = (direction == 1 or direction == 2) and sig < 0

                if enter_long or enter_short:
                    pos_dir = 0 if enter_long else 1
                    entry_px = cur_close
                    alloc = cash * pos_frac
                    cap_per_order0 = alloc / max(n_orders, 1)

                    for k in range(n_orders):
                        g_filled[k] = False
                        trig = _calc_grid_price(entry_px, k, step_pct, pos_dir)
                        sz, mg = _calc_grid_size(cap_per_order0, leverage, taker_fee, trig, weights[k])
                        g_prices[k] = trig
                        g_sizes[k] = sz
                        g_margins[k] = mg
                    pos_n_orders = n_orders

                    # Fill order-0 immediately
                    g_filled[0] = True
                    entry_fee = g_margins[0] * leverage * taker_fee
                    cash -= g_margins[0] + entry_fee
                    pos_total_size = g_sizes[0]
                    pos_total_cost = g_margins[0]
                    pos_total_fee = entry_fee
                    pos_avg_entry = entry_px
                    in_pos = True

            # Equity tracking
            if in_pos and pos_total_size > 0.0:
                if pos_dir == 0:
                    unreal = (cur_close - pos_avg_entry) * pos_total_size
                else:
                    unreal = (pos_avg_entry - cur_close) * pos_total_size
                cur_equity = cash + pos_total_cost + unreal
            else:
                cur_equity = cash

            if cur_equity > peak_equity:
                peak_equity = cur_equity
            dd = (peak_equity - cur_equity) / max(peak_equity, 1e-10)
            if dd > max_dd:
                max_dd = dd
            prev_equity = cur_equity

        # Close remaining position at last bar
        if in_pos and pos_total_size > 0.0:
            lc = close[n_bars - 1]
            exit_fee = pos_total_size * lc * taker_fee
            if pos_dir == 0:
                pnl = (lc - pos_avg_entry) * pos_total_size - exit_fee - pos_total_fee
            else:
                pnl = (pos_avg_entry - lc) * pos_total_size - exit_fee - pos_total_fee
            cash += pos_total_cost + pnl
            n_trades += 1
            if pnl > 0.0:
                n_wins += 1
                gross_profit += pnl
            else:
                gross_loss += abs(pnl)

        # Write results
        out_net_profit[i] = cash - init_cap
        out_max_dd[i] = max_dd
        out_win_rate[i] = (n_wins / n_trades) if n_trades > 0 else 0.0
        out_n_trades[i] = n_trades
        out_profit_factor[i] = gross_profit / max(gross_loss, 1e-10)


# ---------------------------------------------------------------------------
# Public Python-level API
# ---------------------------------------------------------------------------


def run_dca_batch_cuda(
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
) -> dict:
    """
    Run batch DCA simulation on GPU for N (sl, tp) combinations.

    Automatically falls back to CPU Numba if CUDA is unavailable.

    Args:
        close/high/low: OHLCV numpy arrays (float64)
        entry_signals: int8 array — >0 long entry, <0 short, 0 none
        sl_pct_arr: array of stop-loss fractions
        tp_pct_arr: array of take-profit fractions
        direction: 0=long, 1=short, 2=both
        order_count: number of DCA grid levels (1-15)
        grid_size_pct: total grid depth as % (e.g. 10.0)
        martingale_coef: size multiplier per level (≥1.0)
        initial_capital: starting capital in USD
        position_size_frac: fraction of equity per trade (0-1)
        leverage: multiplier
        taker_fee: commission fraction (e.g. 0.0007)

    Returns:
        dict with arrays: net_profit, max_drawdown, win_rate, profit_factor, n_trades
        and 'device' key: "cuda" or "cpu_numba" (fallback)
    """
    if not _CUDA_AVAILABLE:
        logger.info("CUDA not available — falling back to CPU Numba DCA batch")
        from backend.backtesting.numba_dca_engine import run_dca_batch_numba

        result = run_dca_batch_numba(
            close=close,
            high=high,
            low=low,
            entry_signals=entry_signals,
            sl_pct_arr=sl_pct_arr,
            tp_pct_arr=tp_pct_arr,
            direction=direction,
            order_count=order_count,
            grid_size_pct=grid_size_pct,
            martingale_coef=martingale_coef,
            initial_capital=initial_capital,
            position_size_frac=position_size_frac,
            leverage=leverage,
            taker_fee=taker_fee,
        )
        result["device"] = "cpu_numba"
        return result

    from numba import cuda as _cuda_mod

    n = len(sl_pct_arr)
    assert len(tp_pct_arr) == n, "sl_pct_arr and tp_pct_arr must have same length"

    # Ensure correct dtypes
    close = np.asarray(close, dtype=np.float64)
    high = np.asarray(high, dtype=np.float64)
    low = np.asarray(low, dtype=np.float64)
    signals = np.asarray(entry_signals, dtype=np.int8)
    sl_arr = np.asarray(sl_pct_arr, dtype=np.float64)
    tp_arr = np.asarray(tp_pct_arr, dtype=np.float64)

    # Config array (scalars → float64 array for CUDA)
    cfg = np.array(
        [
            float(direction),
            float(order_count),
            float(grid_size_pct),
            float(martingale_coef),
            float(initial_capital),
            float(position_size_frac),
            float(leverage),
            float(taker_fee),
        ],
        dtype=np.float64,
    )

    # Transfer to device
    d_close = _cuda_mod.to_device(close)
    d_high = _cuda_mod.to_device(high)
    d_low = _cuda_mod.to_device(low)
    d_signals = _cuda_mod.to_device(signals)
    d_sl = _cuda_mod.to_device(sl_arr)
    d_tp = _cuda_mod.to_device(tp_arr)
    d_cfg = _cuda_mod.to_device(cfg)

    # Output device arrays
    d_net_profit = _cuda_mod.device_array(n, dtype=np.float64)
    d_max_dd = _cuda_mod.device_array(n, dtype=np.float64)
    d_win_rate = _cuda_mod.device_array(n, dtype=np.float64)
    d_n_trades = _cuda_mod.device_array(n, dtype=np.int32)
    d_profit_factor = _cuda_mod.device_array(n, dtype=np.float64)

    # Launch kernel
    n_blocks = math.ceil(n / _CUDA_BLOCK_SIZE)
    _dca_kernel[n_blocks, _CUDA_BLOCK_SIZE](
        d_close,
        d_high,
        d_low,
        d_signals,
        d_sl,
        d_tp,
        d_cfg,
        d_net_profit,
        d_max_dd,
        d_win_rate,
        d_n_trades,
        d_profit_factor,
    )
    _cuda_mod.synchronize()

    # Copy results back to host
    return {
        "net_profit": d_net_profit.copy_to_host(),
        "max_drawdown": d_max_dd.copy_to_host(),
        "win_rate": d_win_rate.copy_to_host(),
        "profit_factor": d_profit_factor.copy_to_host(),
        "n_trades": d_n_trades.copy_to_host().astype(np.int64),
        "sharpe": np.zeros(n, dtype=np.float64),  # not computed on GPU (expensive)
        "device": "cuda",
    }


def cuda_device_info() -> dict:
    """Return basic info about the available CUDA device."""
    if not _CUDA_AVAILABLE:
        return {"available": False}
    try:
        from numba import cuda as _c

        dev = _c.get_current_device()
        return {
            "available": True,
            "name": dev.name.decode() if isinstance(dev.name, bytes) else str(dev.name),
            "compute_capability": dev.compute_capability,
        }
    except Exception as exc:
        return {"available": True, "error": str(exc)}


def warmup_cuda_dca() -> None:
    """Pre-compile CUDA kernel with a tiny dummy run."""
    if not _CUDA_AVAILABLE:
        logger.info("CUDA not available — warmup skipped")
        return
    try:
        n = 20
        close = np.linspace(100.0, 105.0, n)
        high = close * 1.005
        low = close * 0.995
        sigs = np.zeros(n, dtype=np.int8)
        sigs[3] = 1
        sl = np.array([0.03, 0.05])
        tp = np.array([0.06, 0.10])
        run_dca_batch_cuda(
            close, high, low, sigs, sl, tp, order_count=2, grid_size_pct=3.0, initial_capital=100.0, leverage=1.0
        )
        info = cuda_device_info()
        logger.info(f"CUDA DCA engine warmed up on {info.get('name', 'GPU')}")
    except Exception as exc:
        logger.warning(f"CUDA DCA warmup skipped: {exc}")
