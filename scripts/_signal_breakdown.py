"""Detailed signal breakdown: cross, range, and combined."""

import asyncio
import json
import sqlite3
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")

from backend.backtesting.service import BacktestService
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter


async def main():
    svc = BacktestService()
    conn = sqlite3.connect(r"d:\bybit_strategy_tester_v2\data.sqlite3")
    row = conn.execute(
        "SELECT name, builder_blocks, builder_connections, builder_graph FROM strategies WHERE id=?",
        ("dd2969a2-bbba-410e-b190-be1e8cc50b21",),
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

    candles = await svc._fetch_historical_data(
        "ETHUSDT",
        "30",
        pd.Timestamp("2025-01-01", tz="UTC"),
        pd.Timestamp("2026-02-24", tz="UTC"),
    )
    btc_warmup = await svc._fetch_historical_data(
        "BTCUSDT",
        "30",
        pd.Timestamp("2020-01-01", tz="UTC"),
        pd.Timestamp("2025-01-01", tz="UTC"),
    )
    btc_main = await svc._fetch_historical_data(
        "BTCUSDT",
        "30",
        pd.Timestamp("2025-01-01", tz="UTC"),
        pd.Timestamp("2026-02-24", tz="UTC"),
    )
    btc = pd.concat([btc_warmup, btc_main]).sort_index()
    btc = btc[~btc.index.duplicated(keep="last")]

    # Manually compute RSI to check cross and range
    close = candles["close"]
    btc_close_full = btc["close"]

    # Compute BTC RSI-14 with RMA (same as Pine ta.rsi)
    period = 14
    delta = btc_close_full.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    # RMA (Wilder's smoothing) = EMA with alpha=1/period
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    btc_rsi_full = 100 - (100 / (1 + rs))

    # Reindex to ETH candle timestamps
    btc_rsi = btc_rsi_full.reindex(close.index, method="ffill")

    # Cross and range conditions
    rsi = btc_rsi.values
    rsi_prev = np.roll(rsi, 1)
    rsi_prev[0] = np.nan

    # Short cross: crossunder level 52
    cross_short = (rsi_prev >= 52) & (rsi < 52)
    # Short range: RSI in [50, 70]
    range_short = (rsi >= 50) & (rsi <= 70)
    # Combined
    se_signal = cross_short & range_short

    # Long cross: crossover level 24
    cross_long = (rsi_prev <= 24) & (rsi > 24)
    # Long range: RSI in [28, 50]
    range_long = (rsi >= 28) & (rsi <= 50)
    # Combined
    le_signal = cross_long & range_long

    print("=== Signal Component Counts ===")
    print(f"Short cross↓52:              {np.nansum(cross_short)}")
    print(f"Short range [50,70]:         {np.nansum(range_short)}")
    print(f"Short combined (SE):         {np.nansum(se_signal)}")
    print(f"Long cross↑24:               {np.nansum(cross_long)}")
    print(f"Long range [28,50]:          {np.nansum(range_long)}")
    print(f"Long combined (LE):          {np.nansum(le_signal)}")
    print()

    # Now check what the adapter actually produces
    adapter = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc, btcusdt_5m_ohlcv=None)
    signals = adapter.generate_signals(candles)
    se_adapter = np.asarray(signals.short_entries.values, dtype=bool)
    le_adapter = np.asarray(signals.entries.values, dtype=bool)

    print("=== Adapter Signal Counts ===")
    print(f"SE from adapter:             {se_adapter.sum()}")
    print(f"LE from adapter:             {le_adapter.sum()}")
    print()

    # Check: does adapter SE match our manual SE?
    manual_se = se_signal.astype(bool)
    match = np.all(manual_se == se_adapter)
    if not match:
        diff_idx = np.where(manual_se != se_adapter)[0]
        print(f"Manual vs adapter SE differ at {len(diff_idx)} bars")
        for idx in diff_idx[:20]:
            ts = candles.index[idx]
            print(
                f"  {ts}: manual={manual_se[idx]}, adapter={se_adapter[idx]}, rsi={rsi[idx]:.4f}, rsi_prev={rsi_prev[idx]:.4f}"
            )
    else:
        print("Manual SE matches adapter SE exactly!")

    # Now, the KEY question: how does TV get only 121 shorts?
    # TV has 121 executed short trades, but how many SHORT SIGNALS does TV generate?
    # If TV uses ta.crossunder(rsi, 52) with "range" condition, it should match our logic.
    # The difference might be that TV's RSI computation differs.

    # Check: bars where cross_short is True but range fails
    cross_no_range = cross_short & ~range_short
    print(f"\nCross↓52 but range FAILS:    {np.nansum(cross_no_range)}")
    print(f"Cross↓52 but RSI < 50:       {np.nansum(cross_short & (rsi < 50))}")
    print(f"Cross↓52 but RSI > 70:       {np.nansum(cross_short & (rsi > 70))}")

    # Check: how many crosses have rsi_prev RIGHT at 52 (equality edge case)
    exactly_52 = cross_short & (np.abs(rsi_prev - 52) < 0.0001)
    print(f"Cross with rsi_prev exactly 52: {np.nansum(exactly_52)}")

    # Check: cross with >= vs >
    cross_strict = (rsi_prev > 52) & (rsi < 52)  # strict >
    print(f"\nWith strict > (not >=):      {np.nansum(cross_strict)}")
    print(f"With >= (our current):       {np.nansum(cross_short)}")
    print(f"Difference: {np.nansum(cross_short) - np.nansum(cross_strict)}")

    # Check: what if range is strictly > and <
    range_strict = (rsi > 50) & (rsi < 70)
    se_strict_range = cross_short & range_strict
    print(f"\nWith strict range (50,70):   {np.nansum(se_strict_range)}")
    print(f"With inclusive [50,70]:      {np.nansum(se_signal)}")

    # IMPORTANT: What if cross means rsi_prev > level (not >=) AND rsi <= level (not <)?
    # Pine's ta.crossunder: "when value1 crosses under value2"
    # Typically: prev >= level AND curr < level
    # But what if TV checks: prev > level AND curr <= level?
    cross_alt1 = (rsi_prev > 52) & (rsi <= 52)
    cross_alt2 = (rsi_prev >= 52) & (rsi <= 52)
    cross_alt3 = (rsi_prev > 52) & (rsi < 52)
    print("\nCross variants:")
    print(f"  prev>=52 & curr<52  (ours): {np.nansum(cross_short)}")
    print(f"  prev>52  & curr<=52:        {np.nansum(cross_alt1)}")
    print(f"  prev>=52 & curr<=52:        {np.nansum(cross_alt2)}")
    print(f"  prev>52  & curr<52:         {np.nansum(cross_alt3)}")


asyncio.run(main())
