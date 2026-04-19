"""
HYPOTHESIS: 1-bar offset in BTC RSI alignment

When using an external source (BTC close) to calculate RSI on an ETH chart,
there might be a 1-bar alignment difference between TV and our engine.

Our engine:
- BTC RSI reindexed to ETH candles index with method='ffill'
- This means btc_rsi[ETH_bar_X] = the latest BTC RSI value available at ETH_bar_X

TV's approach:
- security("BTCUSDT", "30", close) gives BTC close at the SAME timestamp
- RSI is calculated on the BTC close series
- The RSI value at bar X is based on BTC close at bar X

These should be identical. But what if TV has a 1-bar delay when using
security() for cross-pair data? Something like:
- security(syminfo.tickerid, "30", ta.rsi(close, 14)) evaluates RSI on ETH
- security("BTCUSDT", "30", ta.rsi(close, 14)) evaluates RSI on BTC
  BUT returns the value at bar X-1 (1 bar lag due to security() lookahead prevention)

In Pine Script v5, security() by default has lookahead=barmerge.lookahead_off,
which means it returns the LATEST CONFIRMED value. For the SAME timeframe,
this means the value at bar X is actually the value from bar X-1!

Wait — this is a critical insight! If security() with same timeframe returns
the PREVIOUS bar's value by default...

security(syminfo.tickerid, "30", ta.rsi(close, 14)) → RSI of the CURRENT bar
But: security("BTCUSDT", "30", ta.rsi(close, 14)) → RSI of the PREVIOUS bar!

This would mean TV's crossunder detection uses:
- rsi_prev = btc_rsi at bar X-2 (prev of the 1-bar-lagged series)
- rsi_curr = btc_rsi at bar X-1 (current of the 1-bar-lagged series)

While OUR crossunder detection uses:
- rsi_prev = btc_rsi at bar X-1
- rsi_curr = btc_rsi at bar X

If there's a 1-bar shift, some crossunders would appear at different bars!

Let me test this by shifting the BTC RSI by 1 bar and regenerating signals.
"""

import asyncio
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.getcwd())

import numpy as np
import pandas as pd


async def main():
    from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
    from backend.backtesting.interfaces import BacktestInput, TradeDirection
    from backend.backtesting.service import BacktestService

    svc = BacktestService()
    START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
    END_DATE = pd.Timestamp("2026-02-24T00:00:00", tz="UTC")

    candles = await svc._fetch_historical_data("ETHUSDT", "30", START_DATE, END_DATE)
    btc_warmup = await svc._fetch_historical_data("BTCUSDT", "30", pd.Timestamp("2020-01-01", tz="UTC"), START_DATE)
    btc_main = await svc._fetch_historical_data("BTCUSDT", "30", START_DATE, END_DATE)
    btc = pd.concat([btc_warmup, btc_main]).sort_index()
    btc = btc[~btc.index.duplicated(keep="last")]

    # Compute BTC RSI
    btc_close = btc["close"]
    delta = btc_close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss
    btc_rsi_full = 100 - (100 / (1 + rs))

    # Normal alignment (what we currently do)
    btc_rsi_normal = btc_rsi_full.reindex(candles.index, method="ffill")

    # Shifted alignment (simulating security() 1-bar lag)
    btc_rsi_shifted = btc_rsi_full.shift(1).reindex(candles.index, method="ffill")

    rsi_n = btc_rsi_normal.values
    rsi_s = btc_rsi_shifted.values
    idx_arr = candles.index

    # Compute crossunders for both
    cross_level = 52.0
    range_more = 50.0
    range_less = 70.0

    def compute_se(rsi_vals):
        """Compute SE signals: range condition AND cross condition"""
        se = np.zeros(len(rsi_vals), dtype=bool)
        for i in range(1, len(rsi_vals)):
            range_ok = (rsi_vals[i] >= range_more) and (rsi_vals[i] <= range_less)
            cross_ok = (rsi_vals[i - 1] >= cross_level) and (rsi_vals[i] < cross_level)
            se[i] = range_ok and cross_ok
        return se

    se_normal = compute_se(rsi_n)
    se_shifted = compute_se(rsi_s)

    print(f"SE signals (normal):  {se_normal.sum()}")
    print(f"SE signals (shifted): {se_shifted.sum()}")

    # Compare: where do they differ?
    diff_mask = se_normal != se_shifted
    n_diff = diff_mask.sum()
    print(f"Differences: {n_diff}")

    # For the 5 UNKNOWN cases, check if shifted version matches TV
    first_se_bars = {
        23: pd.Timestamp("2025-02-22 10:30:00"),  # Engine takes this (1st), TV takes next
        85: pd.Timestamp("2025-08-16 01:00:00"),
        89: pd.Timestamp("2025-08-27 02:30:00"),
        91: pd.Timestamp("2025-09-02 11:00:00"),
        120: pd.Timestamp("2025-11-25 00:00:00"),
    }

    second_se_bars = {
        23: pd.Timestamp("2025-02-22 13:30:00"),  # TV takes this (2nd)
        85: pd.Timestamp("2025-08-16 13:30:00"),
        89: pd.Timestamp("2025-08-27 12:00:00"),
        91: pd.Timestamp("2025-09-02 18:00:00"),
        120: pd.Timestamp("2025-11-25 05:00:00"),
    }

    print("\n" + "=" * 140)
    print("COMPARISON AT UNKNOWN CASE BARS")
    print("=" * 140)

    for eng_num in [23, 85, 89, 91, 120]:
        first_bar = first_se_bars[eng_num]
        second_bar = second_se_bars[eng_num]

        # Find positions
        first_pos = None
        second_pos = None
        for j, ts in enumerate(idx_arr):
            if ts == first_bar:
                first_pos = j
            if ts == second_bar:
                second_pos = j

        if first_pos is None or second_pos is None:
            print(f"  E#{eng_num}: bar not found!")
            continue

        print(f"\n  E#{eng_num}:")
        print(f"    1st SE bar ({first_bar}):")
        print(
            f"      Normal: RSI_prev={rsi_n[first_pos - 1]:.4f}, RSI_curr={rsi_n[first_pos]:.4f}, "
            f"SE={se_normal[first_pos]}"
        )
        print(
            f"      Shifted: RSI_prev={rsi_s[first_pos - 1]:.4f}, RSI_curr={rsi_s[first_pos]:.4f}, "
            f"SE={se_shifted[first_pos]}"
        )

        print(f"    2nd SE bar ({second_bar}):")
        print(
            f"      Normal: RSI_prev={rsi_n[second_pos - 1]:.4f}, RSI_curr={rsi_n[second_pos]:.4f}, "
            f"SE={se_normal[second_pos]}"
        )
        print(
            f"      Shifted: RSI_prev={rsi_s[second_pos - 1]:.4f}, RSI_curr={rsi_s[second_pos]:.4f}, "
            f"SE={se_shifted[second_pos]}"
        )

        # Check: does the shifted version NOT fire at 1st but DOES fire at 2nd?
        if not se_shifted[first_pos] and se_shifted[second_pos]:
            print(f"    *** SHIFTED MATCHES TV: skips 1st, takes 2nd!")
        elif se_shifted[first_pos] and se_shifted[second_pos]:
            print(f"    Shifted fires at BOTH (same as normal)")
        elif not se_shifted[first_pos] and not se_shifted[second_pos]:
            print(f"    Shifted fires at NEITHER")
        else:
            print(f"    Shifted fires at 1st only")

    # Now run a full backtest with shifted RSI to see trade count
    print("\n\n" + "=" * 140)
    print("FULL BACKTEST WITH SHIFTED BTC RSI")
    print("=" * 140)

    # Generate signals manually with shifted RSI
    # We need to replicate what the indicator handler does, but with shifted RSI
    # Long signals
    cross_long_level = 24.0
    long_range_more = 28.0
    long_range_less = 50.0

    le = np.zeros(len(candles), dtype=bool)
    for i in range(1, len(candles)):
        range_ok = (rsi_s[i] >= long_range_more) and (rsi_s[i] <= long_range_less)
        cross_ok = (rsi_s[i - 1] <= cross_long_level) and (rsi_s[i] > cross_long_level)
        le[i] = range_ok and cross_ok

    print(f"  Long entries (shifted): {le.sum()} (normal: 50)")
    print(f"  Short entries (shifted): {se_shifted.sum()} (normal: 600)")

    # Run backtest with shifted signals
    bi_shifted = BacktestInput(
        candles=candles,
        long_entries=le,
        long_exits=np.zeros(len(candles), dtype=bool),
        short_entries=se_shifted,
        short_exits=np.zeros(len(candles), dtype=bool),
        initial_capital=1_000_000.0,
        position_size=0.001,
        use_fixed_amount=False,
        leverage=1,
        stop_loss=0.132,
        take_profit=0.023,
        taker_fee=0.0007,
        slippage=0.0,
        direction=TradeDirection.BOTH,
        pyramiding=1,
        interval="30",
        entry_on_next_bar_open=True,
    )
    engine = FallbackEngineV4()
    out_shifted = engine.run(bi_shifted)
    print(f"  Trades (shifted): {len(out_shifted.trades)} (normal: 151, TV: 151)")


asyncio.run(main())
