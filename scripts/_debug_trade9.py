"""Debug trade 9 divergence: engine short at 2025-01-28 18:00 vs TV 14:30"""

import asyncio
import json
import sqlite3
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
from loguru import logger

logger.remove()

import numpy as np
import pandas as pd

from backend.backtesting.service import BacktestService
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

STRATEGY_ID = "dd2969a2-bbba-410e-b190-be1e8cc50b21"
DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"


async def main():
    svc = BacktestService()

    # Load strategy
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT name,builder_blocks,builder_connections,builder_graph FROM strategies WHERE id=?",
        (STRATEGY_ID,),
    ).fetchone()
    conn.close()
    name, br, cr, gr = row
    blocks = json.loads(br)
    conns = json.loads(cr)
    gp = json.loads(gr)
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

    # Fetch data
    candles = await svc._fetch_historical_data(
        symbol="ETHUSDT",
        interval="30",
        start_date=pd.Timestamp("2025-01-01", tz="UTC"),
        end_date=pd.Timestamp("2026-02-24", tz="UTC"),
    )
    btc_w = await svc._fetch_historical_data(
        symbol="BTCUSDT",
        interval="30",
        start_date=pd.Timestamp("2020-01-01", tz="UTC"),
        end_date=pd.Timestamp("2025-01-01", tz="UTC"),
    )
    btc_m = await svc._fetch_historical_data(
        symbol="BTCUSDT",
        interval="30",
        start_date=pd.Timestamp("2025-01-01", tz="UTC"),
        end_date=pd.Timestamp("2026-02-24", tz="UTC"),
    )
    btc = pd.concat([btc_w, btc_m]).sort_index()
    btc = btc[~btc.index.duplicated(keep="last")]

    # Generate signals
    adapter = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc, btcusdt_5m_ohlcv=None)
    signals = adapter.generate_signals(candles)

    # Focus on the region around trade 8 exit (2025-01-27 18:30) and trade 9 entry
    # TV trade 9 entry: 2025-01-28 14:30 UTC (short)
    # Engine trade 9 entry: 2025-01-28 18:00 UTC (short)
    focus_start = pd.Timestamp("2025-01-27 14:00")
    focus_end = pd.Timestamp("2025-01-29 06:00")

    mask = (candles.index >= focus_start) & (candles.index <= focus_end)
    focus_candles = candles[mask]

    le = signals.entries
    se = signals.short_entries if signals.short_entries is not None else pd.Series(False, index=candles.index)
    lx = signals.exits if signals.exits is not None else pd.Series(False, index=candles.index)
    sx = signals.short_exits if signals.short_exits is not None else pd.Series(False, index=candles.index)

    print("=" * 100)
    print("DEBUG: Signals around trade 9 divergence")
    print("TV trade 8: short exit at 2025-01-27 18:30 (TP)")
    print("TV trade 9: short entry at 2025-01-28 14:30")
    print("Engine trade 9: short entry at 2025-01-28 18:00")
    print("=" * 100)

    # Also look at what the adapter's internal RSI looks like
    # The adapter stores intermediate data - let's check
    print("\nSignals in the focus window:")
    print(f"{'time':25s}  {'close':>10}  {'LE':>4}  {'SE':>4}  {'LX':>4}  {'SX':>4}")
    for ts in focus_candles.index:
        close_val = focus_candles.loc[ts, "close"]
        le_val = bool(le.loc[ts]) if ts in le.index else False
        se_val = bool(se.loc[ts]) if ts in se.index else False
        lx_val = bool(lx.loc[ts]) if ts in lx.index else False
        sx_val = bool(sx.loc[ts]) if ts in sx.index else False
        marker = ""
        if le_val:
            marker += " <<< LONG_ENTRY"
        if se_val:
            marker += " <<< SHORT_ENTRY"
        if lx_val:
            marker += " <<< LONG_EXIT"
        if sx_val:
            marker += " <<< SHORT_EXIT"
        print(f"{str(ts):25s}  {close_val:10.2f}  {le_val!s:>4}  {se_val!s:>4}  {lx_val!s:>4}  {sx_val!s:>4}{marker}")

    # Now let's see what the BTC RSI values are at the signal points
    # The strategy uses crossunder(BTC RSI, 52) for short entry
    # Let's manually compute BTC RSI around this period
    print("\n" + "=" * 100)
    print("BTC RSI(14) values around trade 9 divergence:")
    print("=" * 100)

    # Get BTC data for the same period
    btc_focus_start = pd.Timestamp("2025-01-27 00:00")
    btc_focus_end = pd.Timestamp("2025-01-29 12:00")
    btc_mask = (btc.index >= btc_focus_start) & (btc.index <= btc_focus_end)
    btc_focus = btc[btc_mask]

    # Compute RSI(14) on BTC using the FULL BTC series (for proper warmup)
    # Manual RSI calculation (avoid talib import issues)
    def calc_rsi(series, length=14):
        delta = series.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.ewm(alpha=1.0 / length, min_periods=length, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1.0 / length, min_periods=length, adjust=False).mean()
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    btc_rsi = calc_rsi(btc["close"], 14)

    print(f"\n{'time':25s}  {'btc_close':>10}  {'btc_rsi':>8}  {'prev_rsi':>8}  {'cross_dn_52':>11}")
    for i, ts in enumerate(btc_focus.index):
        if ts not in btc_rsi.index:
            continue
        rsi_val = btc_rsi.loc[ts]
        # Get previous RSI
        idx_pos = btc_rsi.index.get_loc(ts)
        if idx_pos > 0:
            prev_rsi = btc_rsi.iloc[idx_pos - 1]
        else:
            prev_rsi = float("nan")
        cross = prev_rsi >= 52 and rsi_val < 52
        btc_close = btc.loc[ts, "close"]
        marker = " <<< CROSSUNDER 52!" if cross else ""
        print(f"{str(ts):25s}  {btc_close:10.2f}  {rsi_val:8.4f}  {prev_rsi:8.4f}  {str(cross):>11}{marker}")

    # Also check: what signal does the adapter generate at 2025-01-28 14:30?
    ts_tv = pd.Timestamp("2025-01-28 14:30")
    ts_eng = pd.Timestamp("2025-01-28 18:00")
    print(f"\nAt TV entry {ts_tv}:")
    if ts_tv in se.index:
        print(f"  SE={bool(se.loc[ts_tv])}, LE={bool(le.loc[ts_tv])}")
    else:
        print(f"  NOT IN INDEX")
    print(f"At Engine entry {ts_eng}:")
    if ts_eng in se.index:
        print(f"  SE={bool(se.loc[ts_eng])}, LE={bool(le.loc[ts_eng])}")
    else:
        print(f"  NOT IN INDEX")

    # Count all short entry signals between trade 8 exit and trade 10
    t8_exit = pd.Timestamp("2025-01-27 18:30")
    t10_entry = pd.Timestamp("2025-01-29 05:00")
    se_between = se[(se.index >= t8_exit) & (se.index <= t10_entry)]
    se_true = se_between[se_between]
    print(f"\nShort entry signals between trade 8 exit ({t8_exit}) and trade 10 entry ({t10_entry}):")
    for ts in se_true.index:
        print(f"  {ts}")

    # Also check: what about the SECOND divergence cluster at trade 85?
    # Trade 85: engine entry 2025-08-16 01:30, TV entry 2025-08-16 14:00
    print("\n" + "=" * 100)
    print("BTC RSI around trade 85 divergence:")
    print("Engine: 2025-08-16 01:30, TV: 2025-08-16 14:00")
    print("=" * 100)
    t85_start = pd.Timestamp("2025-08-15 12:00")
    t85_end = pd.Timestamp("2025-08-17 00:00")
    btc_mask85 = (btc.index >= t85_start) & (btc.index <= t85_end)
    for ts in btc.index[btc_mask85]:
        rsi_val = btc_rsi.loc[ts]
        idx_pos = btc_rsi.index.get_loc(ts)
        prev_rsi = btc_rsi.iloc[idx_pos - 1] if idx_pos > 0 else float("nan")
        cross = prev_rsi >= 52 and rsi_val < 52
        btc_close = btc.loc[ts, "close"]
        marker = " <<< CROSSUNDER 52!" if cross else ""
        print(f"{str(ts):25s}  {btc_close:10.2f}  {rsi_val:8.4f}  {prev_rsi:8.4f}  {str(cross):>11}{marker}")

    # Check short entry signals
    se_85 = se[(se.index >= t85_start) & (se.index <= t85_end)]
    se_85_true = se_85[se_85]
    print(f"\nShort entry signals in window:")
    for ts in se_85_true.index:
        print(f"  {ts}")


asyncio.run(main())
