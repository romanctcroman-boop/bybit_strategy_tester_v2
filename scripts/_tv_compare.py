"""
Print ALL engine trades with their corresponding signal index.
Show any gaps in signal consumption.
"""

import asyncio
import json
import sqlite3
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

import numpy as np
import pandas as pd
from loguru import logger

logger.remove()

from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.indicator_handlers import calculate_rsi
from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.service import BacktestService
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRATEGY_ID = "30501562-69f0-4d35-ac63-b2b47644ee8b"


def load_graph():
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT name, builder_blocks, builder_connections, builder_graph FROM strategies WHERE id=?",
        (STRATEGY_ID,),
    ).fetchone()
    conn.close()
    name, br, cr, gr = row
    blocks = json.loads(br) if isinstance(br, str) else (br or [])
    conns = json.loads(cr) if isinstance(cr, str) else (cr or [])
    gp = json.loads(gr) if isinstance(gr, str) else (gr or {})
    ms = gp.get("main_strategy", {})
    graph = {
        "name": name,
        "blocks": blocks,
        "connections": conns,
        "market_type": "linear",
        "direction": "both",
        "interval": "30",
    }
    if ms:
        graph["main_strategy"] = ms
    return graph


# TV trades from z4.csv (full list from previous sessions)
# TV entry_time is bar_open_time[T+1], equivalent to our bar_open_time[T] - 30 min
# To compare apples-to-apples: TV_entry_time = our_signal_bar_open_time + 30min
TV_TRADES = [
    # (direction, TV_entry_opentime_UTC, entry_price, TV_exit_opentime_UTC, exit_price)
    # Note: TV exit time is the bar where exit happened; exit price is the close/TP/SL price
    ("short", "2025-01-01 13:30", 3334.62, "2025-01-08 17:00", 3257.92),
    ("short", "2025-01-09 00:00", 3322.53, "2025-01-09 13:30", 3246.11),
    ("short", "2025-01-09 17:30", 3285.67, "2025-01-09 19:30", 3210.09),
    ("short", "2025-01-10 21:00", 3257.99, "2025-01-13 06:30", 3183.05),
    ("long", "2025-01-13 13:30", 3075.39, "2025-01-14 00:00", 3146.13),
    ("short", "2025-01-14 16:30", 3191.83, "2025-01-27 05:30", 3118.41),
    ("long", "2025-01-27 08:00", 3068.83, "2025-01-27 14:30", 3139.42),
    ("short", "2025-01-27 16:30", 3117.00, "2025-01-27 18:30", 3045.30),
    ("short", "2025-01-28 18:00", 3165.71, "2025-01-28 20:30", 3092.89),
    ("short", "2025-01-29 05:00", 3122.65, "2025-02-02 11:30", 3050.82),
    ("short", "2025-02-05 13:00", 2786.32, "2025-02-05 19:00", 2719.52),
    ("short", "2025-02-06 14:30", 2764.79, "2025-02-06 16:00", 2697.52),
    ("short", "2025-02-07 05:30", 2707.94, "2025-02-07 20:30", 2642.99),
    ("short", "2025-02-09 00:30", 2630.84, "2025-02-09 22:00", 2567.21),
    ("short", "2025-02-10 20:00", 2671.23, "2025-02-11 19:00", 2607.35),
    ("short", "2025-02-12 10:00", 2628.13, "2025-02-13 05:30", 2616.56),  # <-- TV fires here
    ("short", "2025-02-13 04:30", 2738.96, "2025-02-13 07:30", 2672.81),
    ("short", "2025-02-15 00:30", 2710.78, "2025-02-17 05:30", 2645.47),
    ("short", "2025-02-17 13:30", 2768.77, "2025-02-17 19:00", 2700.81),
    ("short", "2025-02-18 05:00", 2700.38, "2025-02-18 17:00", 2635.79),
]


async def main():
    graph = load_graph()
    svc = BacktestService()
    START = pd.Timestamp("2025-01-01", tz="UTC")
    END = pd.Timestamp("2026-02-24", tz="UTC")
    candles = await svc._fetch_historical_data("ETHUSDT", "30", START, END)
    WARMUP = 500
    btc_start = START - pd.Timedelta(minutes=WARMUP * 30)
    btc_main = await svc._fetch_historical_data("BTCUSDT", "30", START, END)
    warmup_start_ts = int(btc_start.timestamp() * 1000)
    warmup_end_ts = int(START.timestamp() * 1000)
    raw_warmup = await svc.adapter.get_historical_klines(
        symbol="BTCUSDT",
        interval="30",
        start_time=warmup_start_ts,
        end_time=warmup_end_ts,
        market_type="linear",
    )
    df_w = pd.DataFrame(raw_warmup)
    col_map = {
        "startTime": "timestamp",
        "open_time": "timestamp",
        "openPrice": "open",
        "highPrice": "high",
        "lowPrice": "low",
        "closePrice": "close",
    }
    for old, new in col_map.items():
        if old in df_w.columns and new not in df_w.columns:
            df_w = df_w.rename(columns={old: new})
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df_w.columns:
            df_w[col] = pd.to_numeric(df_w[col], errors="coerce")
    if "timestamp" in df_w.columns:
        if df_w["timestamp"].dtype in ["int64", "float64"]:
            df_w["timestamp"] = pd.to_datetime(df_w["timestamp"], unit="ms", utc=True)
        else:
            df_w["timestamp"] = pd.to_datetime(df_w["timestamp"], utc=True)
        df_w = df_w.set_index("timestamp").sort_index()
    if btc_main.index.tz is None:
        btc_main.index = btc_main.index.tz_localize("UTC")
    btc_all = pd.concat([df_w, btc_main]).sort_index()
    btc_all = btc_all[~btc_all.index.duplicated(keep="last")]

    adapter = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc_all)
    signals = adapter.generate_signals(candles)
    le = np.asarray(signals.entries.values, dtype=bool)
    se = (
        np.asarray(signals.short_entries.values, dtype=bool)
        if signals.short_entries is not None
        else np.zeros(len(le), dtype=bool)
    )
    lx = np.asarray(signals.exits.values, dtype=bool) if signals.exits is not None else np.zeros(len(le), dtype=bool)
    sx = (
        np.asarray(signals.short_exits.values, dtype=bool)
        if signals.short_exits is not None
        else np.zeros(len(le), dtype=bool)
    )

    # Recompute RSI
    btc_close = btc_all["close"].copy()
    if candles.index.tz is None and btc_close.index.tz is not None:
        btc_close.index = btc_close.index.tz_localize(None)
    btc_rsi_arr = calculate_rsi(btc_close.values, period=14)
    btc_rsi = pd.Series(btc_rsi_arr, index=btc_close.index)
    rsi = btc_rsi.reindex(candles.index, method="ffill")

    result = FallbackEngineV4().run(
        BacktestInput(
            candles=candles,
            long_entries=le,
            long_exits=lx,
            short_entries=se,
            short_exits=sx,
            initial_capital=10_000.0,
            position_size=0.10,
            use_fixed_amount=True,
            fixed_amount=100.0,
            leverage=10,
            stop_loss=0.132,
            take_profit=0.023,
            taker_fee=0.0007,
            slippage=0.0,
            direction=TradeDirection.BOTH,
            pyramiding=1,
            interval="30",
        )
    )

    trades = result.trades
    print(f"Engine: {len(trades)} trades  |  TV reference: 147 (146+1 open)")

    # Convert TV times to UTC Timestamps (offset by -30min to match our bar_open_time[T])
    tv_signal_times = []
    for row in TV_TRADES:
        d, et, ep, xt, xp = row
        # TV entry_time = bar_open[T+1] → our signal bar = bar_open[T] = TV_time - 30min
        tv_signal_t = pd.Timestamp(et, tz="UTC") - pd.Timedelta(minutes=30)
        tv_exit_t = pd.Timestamp(xt, tz="UTC")
        tv_signal_times.append((d, tv_signal_t, ep, tv_exit_t, xp))

    # Compare first 20 engine trades vs first 20 TV trades side by side
    print("\nSide-by-side comparison (first 20 trades):")
    print(
        f"{'#':>3}  {'ENG entry':>20}  {'ENG ep':>8}  {'ENG exit':>20}  {'ENG reason':>12}  |  {'TV signal(T)':>20}  {'TV ep':>8}  {'TV exit':>20}"
    )
    print("-" * 135)

    for idx in range(20):
        if idx < len(trades):
            t = trades[idx]
            eng_entry = str(pd.Timestamp(t.entry_time))[:16]
            eng_exit = str(pd.Timestamp(t.exit_time))[:16]
            eng_ep = t.entry_price
            eng_reason = str(t.exit_reason).replace("ExitReason.", "")[:12]
        else:
            eng_entry = eng_exit = "---"
            eng_ep = 0.0
            eng_reason = "---"

        if idx < len(tv_signal_times):
            d, tv_sig_t, tv_ep, tv_exit_t, tv_xp = tv_signal_times[idx]
            tv_signal = str(tv_sig_t)[:16]
            tv_exit = str(tv_exit_t)[:16]
        else:
            tv_signal = tv_exit = "---"
            tv_ep = 0.0

        match = "  ✓" if abs(eng_ep - tv_ep) < 0.1 else "  ✗"
        print(
            f"{idx + 1:>3}  {eng_entry:>20}  {eng_ep:>8.2f}  {eng_exit:>20}  {eng_reason:>12}{match}  |  {tv_signal:>20}  {tv_ep:>8.2f}  {tv_exit:>20}"
        )


asyncio.run(main())
