"""
Deep analysis of the Feb 12 07:30 RSI crossunder discrepancy.
TV fires short at 10:00, engine fires at 07:30.
Check what BTC close price would be needed for RSI to stay ABOVE 52 at 07:30.
"""

import asyncio
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

import numpy as np
import pandas as pd
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")

from backend.backtesting.service import BacktestService
from backend.core.indicators import calculate_rsi

START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
END_DATE = pd.Timestamp("2025-02-13", tz="UTC")
WARMUP_BARS = 500
PERIOD = 14


async def main():
    svc = BacktestService()

    # Fetch linear BTC with warmup
    btc_start = START_DATE - pd.Timedelta(minutes=WARMUP_BARS * 30)
    btc_main = await svc._fetch_historical_data("BTCUSDT", "30", START_DATE, END_DATE, market_type="linear")
    warmup_ts_start = int(btc_start.timestamp() * 1000)
    warmup_ts_end = int(START_DATE.timestamp() * 1000)
    raw_warmup = await svc.adapter.get_historical_klines(
        "BTCUSDT", "30", warmup_ts_start, warmup_ts_end, market_type="linear"
    )
    df_w = pd.DataFrame(raw_warmup)
    for old, new in {
        "startTime": "timestamp",
        "open_time": "timestamp",
        "openPrice": "open",
        "highPrice": "high",
        "lowPrice": "low",
        "closePrice": "close",
    }.items():
        if old in df_w.columns and new not in df_w.columns:
            df_w = df_w.rename(columns={old: new})
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df_w.columns:
            df_w[col] = pd.to_numeric(df_w[col], errors="coerce")
    if df_w["timestamp"].dtype in ["int64", "float64"]:
        df_w["timestamp"] = pd.to_datetime(df_w["timestamp"], unit="ms")
    df_w = df_w.set_index("timestamp").sort_index()
    if btc_main.index.tz is None:
        df_w.index = df_w.index.tz_localize(None)
    btc = pd.concat([df_w, btc_main]).sort_index()
    btc = btc[~btc.index.duplicated(keep="last")]

    # The critical bar: 2025-02-12 07:30
    # Linear close = 96025.70, RSI = 51.6728 (cross below 52)
    # Spot close   = 96077.47, RSI = 51.7655 (also cross below 52)
    # TV does NOT fire at 07:30 — so TV's BTC close must give RSI >= 52

    # Let's binary-search: what close price at 07:30 would give RSI >= 52?
    ts_critical = pd.Timestamp("2025-02-12 07:30")
    idx = btc.index.get_loc(ts_critical)

    # Use the series up to (not including) the critical bar, then vary the close
    prefix_close = btc["close"].iloc[:idx].values.copy()
    rsi_prefix = calculate_rsi(prefix_close, period=PERIOD)

    # Last Wilder avg_gain and avg_loss before the critical bar
    # We need to reconstruct the Wilder state at bar idx-1
    # then compute what close value makes RSI = exactly 52

    # Wilder RSI at bar n:
    #   delta = close[n] - close[n-1]
    #   avg_gain_n = ((PERIOD-1)*avg_gain_{n-1} + max(delta,0)) / PERIOD
    #   avg_loss_n = ((PERIOD-1)*avg_loss_{n-1} + max(-delta,0)) / PERIOD
    #   RSI = 100 - 100/(1 + avg_gain_n/avg_loss_n)

    # So for RSI=52: 100/(1 + ag/al) = 48 => 1+ag/al = 100/48 => ag/al = 52/48
    # ag_n = ((P-1)*ag_prev + max(delta,0)) / P
    # al_n = ((P-1)*al_prev + max(-delta,0)) / P

    # Let's compute the Wilder state manually at bar idx-1 (07:00)
    P = PERIOD
    close_vals = btc["close"].values

    # Seed: first P bars
    seed_gains = []
    seed_losses = []
    for i in range(1, P):
        d = close_vals[i] - close_vals[i - 1]
        seed_gains.append(max(d, 0))
        seed_losses.append(max(-d, 0))
    avg_gain = sum(seed_gains) / P
    avg_loss = sum(seed_losses) / P

    # Wilder smoothing from bar P to idx-1 (07:00)
    for i in range(P, idx):
        d = close_vals[i] - close_vals[i - 1]
        gain = max(d, 0)
        loss = max(-d, 0)
        avg_gain = ((P - 1) * avg_gain + gain) / P
        avg_loss = ((P - 1) * avg_loss + loss) / P

    print(f"Wilder state at bar {idx - 1} (07:00):")
    prev_close = close_vals[idx - 1]
    print(f"  prev_close = {prev_close:.2f}")
    print(f"  avg_gain   = {avg_gain:.8f}")
    print(f"  avg_loss   = {avg_loss:.8f}")
    rsi_prev = 100 - 100 / (1 + avg_gain / avg_loss) if avg_loss > 0 else 100
    print(f"  RSI at 07:00 = {rsi_prev:.4f}")

    # Now for bar idx (07:30), compute RSI as function of close
    # delta = close - prev_close
    # If close > prev_close: gain=delta, loss=0
    #   avg_gain_new = ((P-1)*avg_gain + delta) / P
    #   avg_loss_new = ((P-1)*avg_loss) / P
    # If close < prev_close: gain=0, loss=-delta
    #   avg_gain_new = ((P-1)*avg_gain) / P
    #   avg_loss_new = ((P-1)*avg_loss + (-delta)) / P

    actual_close = close_vals[idx]
    print(f"\nActual close at 07:30 = {actual_close:.2f}")

    # Compute RSI for a range of close values around actual
    print(f"\nRSI sensitivity around actual close ({actual_close:.2f}):")
    print(f"{'Close':>12} {'RSI':>10} {'Cross<52?':>10}")
    for offset in [-200, -100, -50, -10, 0, 10, 50, 100, 200]:
        c = actual_close + offset
        d = c - prev_close
        if d > 0:
            ag_new = ((P - 1) * avg_gain + d) / P
            al_new = ((P - 1) * avg_loss) / P
        else:
            ag_new = ((P - 1) * avg_gain) / P
            al_new = ((P - 1) * avg_loss + (-d)) / P
        rsi_new = 100 - 100 / (1 + ag_new / al_new) if al_new > 0 else 100
        cross = "YES" if rsi_prev >= 52 and rsi_new < 52 else "no"
        marker = " <-- actual" if offset == 0 else ""
        print(f"  {c:>12.2f} {rsi_new:>10.4f} {cross:>10}{marker}")

    # Find the break-even close: RSI = 52.0000
    # For close < prev_close (delta < 0):
    # RSI = 100 - 100 / (1 + ((P-1)*ag) / ((P-1)*al + (-delta)))
    # 100 - 100 / (1 + AG / (AL + (-delta))) = 52
    # 1 + AG / (AL - delta) = 100/48
    # AG / (AL - delta) = 52/48
    # 48*AG = 52*(AL - delta)   [delta = c - prev_close < 0, so -delta > 0]
    # 48*AG = 52*AL - 52*delta
    # 52*delta = 52*AL - 48*AG
    # delta = (52*AL - 48*AG) / 52
    AG = (P - 1) * avg_gain
    AL = (P - 1) * avg_loss
    delta_breakeven = (52 * AL - 48 * AG) / 52
    c_breakeven = prev_close + delta_breakeven
    print(f"\nBreak-even close for RSI=52 at 07:30: {c_breakeven:.4f}")
    print(f"  (actual linear close: {actual_close:.2f}, diff: {actual_close - c_breakeven:.4f})")
    print(f"  TV would NOT fire if close >= {c_breakeven:.4f}")


asyncio.run(main())
