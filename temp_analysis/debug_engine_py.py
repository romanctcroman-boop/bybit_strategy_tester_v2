"""
Debug: Trace engine.py _run_fallback around the Jan 8 spurious long window.
Compare with Numba (ground truth) to find exactly where they diverge.
"""

import json
import sqlite3
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter  # noqa: E402

# ---- Load OHLCV from DB (same as calibrate_engines.py) ----
print("Loading OHLCV data...")
conn = sqlite3.connect(r"d:\bybit_strategy_tester_v2\data.sqlite3")

cur = conn.execute(
    "SELECT open_time, open_price, high_price, low_price, close_price, volume "
    "FROM bybit_kline_audit "
    "WHERE symbol='ETHUSDT' AND interval='30' AND market_type='linear' "
    "AND open_time_dt >= '2025-01-01' AND open_time_dt < '2026-03-01' "
    "ORDER BY open_time ASC"
)
rows = cur.fetchall()
ohlcv = pd.DataFrame(rows, columns=["open_time", "open", "high", "low", "close", "volume"])
ohlcv["open_time"] = pd.to_datetime(ohlcv["open_time"], unit="ms", utc=True)
ohlcv = ohlcv.set_index("open_time").astype(float)
print(f"  ETHUSDT 30m rows: {len(ohlcv)}")

cur = conn.execute(
    "SELECT open_time, open_price, high_price, low_price, close_price, volume "
    "FROM bybit_kline_audit "
    "WHERE symbol='BTCUSDT' AND interval='30' AND market_type='linear' "
    "AND open_time_dt >= '2025-01-01' AND open_time_dt < '2026-03-01' "
    "ORDER BY open_time ASC"
)
btc_rows = cur.fetchall()
btc_ohlcv = pd.DataFrame(btc_rows, columns=["open_time", "open", "high", "low", "close", "volume"])
btc_ohlcv["open_time"] = pd.to_datetime(btc_ohlcv["open_time"], unit="ms", utc=True)
btc_ohlcv = btc_ohlcv.set_index("open_time").astype(float)
print(f"  BTCUSDT 30m rows: {len(btc_ohlcv)}")

# ---- Load strategy graph ----
s_row = conn.execute(
    "SELECT builder_blocks, builder_connections, builder_graph FROM strategies WHERE id LIKE '149454c2%'"
).fetchone()
conn.close()

builder_blocks = json.loads(s_row[0]) if s_row[0] else []
builder_connections = json.loads(s_row[1]) if s_row[1] else []
builder_graph_raw = json.loads(s_row[2]) if s_row[2] else {}

strategy_graph = {
    "name": "Strategy-A2",
    "description": "",
    "interval": "30",
    "market_type": "linear",
    "direction": "both",
    "blocks": builder_blocks,
    "connections": builder_connections,
}
if "main_strategy" in builder_graph_raw:
    strategy_graph["main_strategy"] = builder_graph_raw["main_strategy"]

adapter = StrategyBuilderAdapter(strategy_graph, btcusdt_ohlcv=btc_ohlcv)
signals = adapter.generate_signals(ohlcv)

le = np.asarray(signals.entries.values, dtype=bool)
se = np.asarray(signals.short_entries.values, dtype=bool)
lx = signals.exits.values
sx = signals.short_exits.values
close = ohlcv["close"].values
open_prices = ohlcv["open"].values
high = ohlcv["high"].values
low = ohlcv["low"].values
timestamps = ohlcv.index.tolist()

print(f"\nLong signals: {le.sum()}, Short signals: {se.sum()}")

# Find bars around Jan 8-10
jan8_start = pd.Timestamp("2025-01-08 00:00:00", tz="UTC")
jan10_end = pd.Timestamp("2025-01-10 23:59:59", tz="UTC")
mask = (ohlcv.index >= jan8_start) & (ohlcv.index <= jan10_end)
jan8_indices = np.where(mask)[0]
print(f"\nJan 8-10 bar indices: {jan8_indices[0]} to {jan8_indices[-1]}")

# Show bars around the critical window (bars 325-345)
start_idx = max(0, jan8_indices[0] - 10)
end_idx = min(len(close), jan8_indices[-1] + 10)
print(f"\nBars {start_idx} to {end_idx}:")
print(f"{'i':>4} | {'timestamp':>24} | {'open':>8} | {'close':>8} | {'le':>3} | {'se':>3} | {'lx':>3} | {'sx':>3}")
print("-" * 75)
for i in range(start_idx, end_idx):
    ts = timestamps[i].strftime("%Y-%m-%d %H:%M UTC")
    print(
        f"{i:>4} | {ts:>24} | {open_prices[i]:>8.2f} | {close[i]:>8.2f} | {le[i]!s:>5} | {se[i]!s:>5} | {lx[i]!s:>5} | {sx[i]!s:>5}"
    )

# Now simulate engine.py _run_fallback with detailed tracing
print("\n" + "=" * 80)
print("SIMULATING engine.py _run_fallback (simplified, tracing only)")
print("=" * 80)

initial_capital = 10000.0
position_size = 0.1
leverage = 10.0
stop_loss = 0.132
take_profit = 0.023
commission = 0.0007
direction = "both"
slippage = 0.0

cash = initial_capital
position = 0.0
is_long = True
entry_price = 0.0
entry_time = None
entry_size = 0.0
entry_idx = 0
tp_sl_active_from = 1
margin_allocated = 0.0
entry_fees_paid = 0.0
last_entry_price = 0.0
signal_price = 0.0
max_favorable_price = 0.0
max_adverse_price = 0.0

trades = []
trace_start = start_idx - 5
trace_end = end_idx + 5

for i in range(len(close)):
    price = close[i]
    current_high = high[i]
    current_low = low[i]

    trace = trace_start <= i <= trace_end

    if position == 0:
        if cash <= 0:
            pass
        # Long entry
        elif direction in ("long", "both") and le[i]:
            if i + 1 < len(close):
                ep = open_prices[i + 1] * (1 + slippage)
                sp = price
                pv = initial_capital * position_size
                alloc = pv / leverage
                es = pv / ep
                fees = pv * commission
                cash -= alloc + fees
                margin_allocated = alloc
                entry_fees_paid = fees
                entry_price = ep
                signal_price = sp
                last_entry_price = ep
                position = es
                entry_size = es
                is_long = True
                entry_time = timestamps[i + 1]
                entry_idx = i + 1
                tp_sl_active_from = i + 1
                max_favorable_price = high[i + 1]
                max_adverse_price = low[i + 1]
                if trace:
                    print(f"  [LONG ENTRY] bar={i} ep={ep:.2f} signal_bar={i} entry_bar={i + 1} ts={timestamps[i + 1]}")
        # Short entry
        elif direction in ("short", "both") and se[i]:
            if i + 1 < len(close):
                ep = open_prices[i + 1] * (1 - slippage)
                sp = price
                pv = initial_capital * position_size
                alloc = pv / leverage
                es = pv / ep
                fees = pv * commission
                cash -= alloc + fees
                margin_allocated = alloc
                entry_fees_paid = fees
                entry_price = ep
                signal_price = sp
                last_entry_price = ep
                position = es
                entry_size = es
                is_long = False
                entry_time = timestamps[i + 1]
                entry_idx = i + 1
                tp_sl_active_from = i + 1
                max_favorable_price = low[i + 1]
                max_adverse_price = high[i + 1]
                if trace:
                    print(
                        f"  [SHORT ENTRY] bar={i} ep={ep:.2f} signal_bar={i} entry_bar={i + 1} ts={timestamps[i + 1]}"
                    )

    elif position > 0:
        if is_long:
            max_favorable_price = max(max_favorable_price, current_high)
            max_adverse_price = min(max_adverse_price, current_low)
        else:
            max_favorable_price = min(max_favorable_price, current_low)
            max_adverse_price = max(max_adverse_price, current_high)

        sl_ref_price = signal_price if signal_price > 0 else entry_price
        if is_long:
            worst_pnl_pct = (current_low - sl_ref_price) / sl_ref_price
            best_pnl_pct = (current_high - signal_price) / signal_price
        else:
            worst_pnl_pct = (sl_ref_price - current_high) / sl_ref_price
            best_pnl_pct = (signal_price - current_low) / signal_price

        should_exit = False
        exit_reason = ""
        exit_price = price

        # Stop loss
        if not should_exit and stop_loss and worst_pnl_pct <= -stop_loss and i >= tp_sl_active_from + 1:
            should_exit = True
            exit_reason = "stop_loss"
            sl_px = sl_ref_price * (1 - stop_loss) if is_long else sl_ref_price * (1 + stop_loss)
            exit_price = max(current_low, min(current_high, sl_px))

        # Take profit
        if not should_exit and take_profit and best_pnl_pct >= take_profit and i >= tp_sl_active_from + 1:
            should_exit = True
            exit_reason = "take_profit"
            tp_target = signal_price * (1 + take_profit) if is_long else signal_price * (1 - take_profit)
            bar_open = open_prices[i]
            if is_long and bar_open >= tp_target:
                exit_price = bar_open
            elif not is_long and bar_open <= tp_target:
                exit_price = bar_open
            else:
                exit_price = tp_target
            exit_price = max(current_low, min(current_high, exit_price))

        # Signal exit
        if not should_exit:
            if (is_long and lx[i]) or (not is_long and sx[i]):
                should_exit = True
                exit_reason = "signal"
                exit_price = price

        if should_exit:
            pv = position * exit_price
            fees = pv * commission
            total_fees = entry_fees_paid + fees
            if is_long:
                gross = (exit_price - entry_price) * entry_size
            else:
                gross = (entry_price - exit_price) * entry_size
            pnl = gross - total_fees
            cash += margin_allocated + pnl + entry_fees_paid

            trade_side = "LONG" if is_long else "SHORT"
            if trace:
                print(
                    f"  [{trade_side} EXIT] bar={i} reason={exit_reason} ep={entry_price:.2f} xp={exit_price:.2f} pnl={pnl:.2f} ts={timestamps[i]}"
                )

            trades.append(
                {
                    "side": trade_side,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "pnl": pnl,
                    "exit_bar": i,
                    "entry_bar": entry_idx,
                    "exit_time": timestamps[i],
                    "reason": exit_reason,
                }
            )

            position = 0.0
            entry_price = 0.0
            signal_price = 0.0
            last_entry_price = 0.0
            entry_time = None
            entry_size = 0.0
            margin_allocated = 0.0
            entry_fees_paid = 0.0

            # SAME-BAR RE-ENTRY
            if exit_reason in ("take_profit", "stop_loss") and cash > 0:
                _can_long = direction in ("long", "both") and le[i]
                _can_short = direction in ("short", "both") and se[i]
                if _can_long or _can_short:
                    _ep = price * (1 + slippage) if _can_long else price * (1 - slippage)
                    _sp = price
                    _pv = initial_capital * position_size
                    _alloc = _pv / leverage
                    _es = _pv / _ep
                    _fees = _pv * commission
                    if cash >= _alloc + _fees:
                        cash -= _alloc + _fees
                        margin_allocated = _alloc
                        entry_fees_paid = _fees
                        entry_price = _ep
                        signal_price = _sp
                        last_entry_price = _ep
                        position = _es
                        entry_size = _es
                        is_long = _can_long
                        entry_time = timestamps[i]
                        entry_idx = i
                        tp_sl_active_from = i + 1
                        if is_long:
                            max_favorable_price = current_high
                            max_adverse_price = current_low
                        else:
                            max_favorable_price = current_low
                            max_adverse_price = current_high
                        _side = "LONG" if _can_long else "SHORT"
                        if trace:
                            print(f"  [SAME-BAR RE-ENTRY {_side}] bar={i} ep={_ep:.2f} ts={timestamps[i]}")

print(f"\nTotal trades: {len(trades)}")

# Show trades around the critical window
print("\nTrades in critical window (entry bars 310-370):")
for t in trades:
    if 310 <= t["entry_bar"] <= 370:
        print(
            f"  {t['side']:5} ep={t['entry_price']:8.2f} xp={t['exit_price']:8.2f} pnl={t['pnl']:8.2f} entry_bar={t['entry_bar']:3} exit_bar={t['exit_bar']:3} reason={t['reason']}"
        )

# Show ALL trades entry prices
print(f"\nAll {len(trades)} trade entry prices:")
for t in trades:
    print(f"  {t['side']:5} ep={t['entry_price']:.2f}")
