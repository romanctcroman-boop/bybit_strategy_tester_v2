"""Check BTC 5m bars and compute intra-bar RSI around 2025-02-12 09:30."""

import sys

sys.path.insert(0, ".")
import asyncio
import pandas as pd
import numpy as np
from loguru import logger

logger.remove()
from backend.backtesting.service import BacktestService
from backend.core.indicators import calculate_rsi

START = pd.Timestamp("2025-01-01", tz="UTC")
WARMUP_START = pd.Timestamp("2020-01-01", tz="UTC")
TARGET = pd.Timestamp("2025-02-12", tz="UTC")
END = pd.Timestamp("2025-02-13", tz="UTC")


async def main():
    svc = BacktestService()

    # ── Build full BTC 30m series with 2020 warmup ──
    raw = await svc.adapter.get_historical_klines(
        symbol="BTCUSDT",
        interval="30",
        start_time=int(WARMUP_START.timestamp() * 1000),
        end_time=int(START.timestamp() * 1000),
        market_type="linear",
    )
    df_w = pd.DataFrame(raw)
    df_w["timestamp"] = pd.to_datetime(df_w["open_time"], unit="ms", utc=True)
    df_w = df_w.set_index("timestamp").sort_index()

    btc_main = await svc._fetch_historical_data(symbol="BTCUSDT", interval="30", start_date=START, end_date=END)
    if btc_main.index.tz is None:
        btc_main.index = btc_main.index.tz_localize("UTC")
    btc = pd.concat([df_w, btc_main]).sort_index()
    btc = btc[~btc.index.duplicated(keep="last")]

    close30 = btc["close"]
    rsi30 = pd.Series(calculate_rsi(close30.values, period=14), index=close30.index)

    # Show 30m RSI around 07:00-11:00
    window30 = rsi30["2025-02-12 06:00":"2025-02-12 11:00"]
    close30w = close30["2025-02-12 06:00":"2025-02-12 11:00"]
    print("BTC 30m close + RSI around 07:00-11:00 UTC (2025-02-12):")
    for ts in window30.index:
        rsi_val = window30[ts]
        c = close30w[ts]
        flag = " <<< BELOW 52" if rsi_val < 52 else ""
        print(f"  {ts.strftime('%H:%M')}  close={c:.2f}  RSI={rsi_val:.4f}{flag}")

    # ── Get BTC 5m data for the day ──
    raw5 = await svc.adapter.get_historical_klines(
        symbol="BTCUSDT",
        interval="5",
        start_time=int(TARGET.timestamp() * 1000),
        end_time=int(END.timestamp() * 1000),
        market_type="linear",
    )
    df5 = pd.DataFrame(raw5)
    df5["timestamp"] = pd.to_datetime(df5["open_time"], unit="ms", utc=True)
    df5 = df5.set_index("timestamp").sort_index()

    # Wilder state at 2025-02-12 07:00 (from 30m series)
    # Rebuild state step by step to get exact ag/al at each 30m bar
    n = len(close30)
    vals = close30.values
    deltas = np.diff(vals)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    ag = np.mean(gains[:14])
    al = np.mean(losses[:14])
    state_at = {}  # ts -> (ag, al)
    for i in range(14, len(gains)):
        ag = (ag * 13 + gains[i]) / 14
        al = (al * 13 + losses[i]) / 14
        state_at[close30.index[i + 1]] = (ag, al, vals[i + 1])

    # Now simulate intra-bar RSI using 5m data within each 30m bar
    # For the 09:30 bar: 5m sub-bars are 09:30, 09:35, 09:40, 09:45, 09:50, 09:55
    print("\nSimulating intra-bar RSI using 5m data within 30m bars (09:00-10:30):")
    bar_starts = [
        pd.Timestamp("2025-02-12 09:00", tz="UTC"),
        pd.Timestamp("2025-02-12 09:30", tz="UTC"),
        pd.Timestamp("2025-02-12 10:00", tz="UTC"),
    ]
    for bar_start in bar_starts:
        prev_bar = bar_start - pd.Timedelta("30min")
        if prev_bar not in state_at:
            print(f"  {bar_start.strftime('%H:%M')}: No Wilder state found for prev bar {prev_bar}")
            continue
        ag_prev, al_prev, prev_close = state_at[prev_bar]
        rsi_prev_close = 100 - 100 / (1 + ag_prev / al_prev) if al_prev > 0 else 100.0
        print(
            f"\n  30m bar {bar_start.strftime('%H:%M')} (prev close={prev_close:.2f}, prev RSI={rsi_prev_close:.4f}):"
        )
        print(f"    Wilder state: ag={ag_prev:.6f}  al={al_prev:.6f}")

        # Get 5m sub-bars for this 30m bar
        bar_end = bar_start + pd.Timedelta("30min")
        sub = df5[bar_start : bar_end - pd.Timedelta("1s")]
        if sub.empty:
            print(f"    No 5m sub-bars found")
            continue

        # Simulate Wilder update using each 5m close as if it were the next 30m bar
        ag_sim = ag_prev
        al_sim = al_prev
        c_prev = prev_close
        for sub_ts, sub_row in sub.iterrows():
            c_now = float(sub_row["close"])
            delta = c_now - c_prev
            g = max(delta, 0.0)
            l = max(-delta, 0.0)
            ag_sim = (ag_sim * 13 + g) / 14
            al_sim = (al_sim * 13 + l) / 14
            rsi_sim = 100 - 100 / (1 + ag_sim / al_sim) if al_sim > 0 else 100.0
            flag = " <<< RSI CROSSES 52" if (rsi_prev_close >= 52 and rsi_sim < 52) else ""
            print(f"    5m {sub_ts.strftime('%H:%M')}  close={c_now:.2f}  RSI_sim={rsi_sim:.4f}{flag}")
            c_prev = c_now
            rsi_prev_close = rsi_sim


asyncio.run(main())
