"""Check BTC RSI around last long signal (2026-02-23 20:30)."""

import sys

sys.path.insert(0, "d:\\bybit_strategy_tester_v2")

import asyncio
from datetime import UTC, datetime, timezone

import pandas as pd


async def main():
    from backend.backtesting.indicator_handlers import calculate_rsi
    from backend.backtesting.service import BacktestService

    svc = BacktestService()
    start_date = datetime(2025, 1, 1, tzinfo=UTC)
    end_date = datetime(2026, 2, 25, tzinfo=UTC)
    _btc_start = start_date - pd.Timedelta(minutes=500 * 30)

    btc_ohlcv = await svc._fetch_historical_data(
        symbol="BTCUSDT",
        interval="30",
        start_date=_btc_start,
        end_date=end_date,
        market_type="linear",
    )

    rsi = calculate_rsi(btc_ohlcv["close"], period=14)
    # Align to strategy start
    rsi_strat = rsi[rsi.index >= start_date]
    close_strat = btc_ohlcv["close"][btc_ohlcv.index >= start_date]

    # Show BTC RSI around 2026-02-23 signal
    target = pd.Timestamp("2026-02-23 20:30:00", tz="UTC")
    start_window = target - pd.Timedelta(hours=6)
    end_window = target + pd.Timedelta(hours=3)
    mask = (rsi_strat.index >= start_window) & (rsi_strat.index <= end_window)
    window_rsi = rsi_strat[mask]
    window_close = close_strat[close_strat.index >= start_window]
    window_close = window_close[window_close.index <= end_window]

    print("BTC RSI around 2026-02-23 20:30 long signal:")
    print(f"{'Time':25s} {'Close':10s} {'RSI':10s} {'Signal':10s}")
    for t in window_rsi.index:
        rsi_val = window_rsi[t]
        close_val = window_close.get(t, float("nan"))
        # Long: cross ABOVE 24, RSI in [28-70]
        prev_t_idx = window_rsi.index.get_loc(t)
        if prev_t_idx > 0:
            prev_t = window_rsi.index[prev_t_idx - 1]
            prev_rsi = window_rsi.iloc[prev_t_idx - 1]
            cross = (prev_rsi <= 24) and (rsi_val > 24)
            in_range = (rsi_val >= 28) and (rsi_val <= 70)
            signal = "LONG!" if (cross and in_range) else ""
        else:
            signal = ""
        marker = " <<<" if t == target else ""
        print(f"  {t!s:25s} {close_val:10.4f} {rsi_val:10.4f} {signal:10s}{marker}")


asyncio.run(main())
