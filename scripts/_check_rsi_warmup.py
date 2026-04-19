"""Check whether warmup bars actually change RSI values."""

import asyncio
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

import pandas as pd

from backend.backtesting.service import BacktestService
from backend.core.indicators import calculate_rsi

START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
END_DATE = pd.Timestamp("2025-01-10", tz="UTC")
WARMUP_BARS = 500


async def main():
    svc = BacktestService()

    # In-range BTC (from DB)
    main_btc = await svc._fetch_historical_data(
        symbol="BTCUSDT", interval="30", start_date=START_DATE, end_date=END_DATE
    )
    print(f"Main BTC bars: {len(main_btc)}, first={main_btc.index[0]}, last={main_btc.index[-1]}")

    # Warmup BTC (direct API call)
    btc_start = START_DATE - pd.Timedelta(minutes=WARMUP_BARS * 30)
    warmup_ts_start = int(btc_start.timestamp() * 1000)
    warmup_ts_end = int(START_DATE.timestamp() * 1000)
    raw = await svc.adapter.get_historical_klines("BTCUSDT", "30", warmup_ts_start, warmup_ts_end, market_type="linear")
    print(f"Warmup bars from API: {len(raw)}")

    # Build warmup DataFrame
    df_w = pd.DataFrame(raw)
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
    else:
        df_w["timestamp"] = pd.to_datetime(df_w["timestamp"])
    df_w = df_w.set_index("timestamp").sort_index()
    print(f"Warmup df: {len(df_w)} bars, first={df_w.index[0]}, last={df_w.index[-1]}")

    # RSI without warmup
    rsi_no_warmup = calculate_rsi(main_btc["close"].values, period=14)

    # RSI with warmup (concat, strip tz to match)
    if main_btc.index.tz is not None and df_w.index.tz is None:
        main_btc_plain = main_btc.copy()
        main_btc_plain.index = main_btc_plain.index.tz_localize(None)
    else:
        main_btc_plain = main_btc

    combined = pd.concat([df_w, main_btc_plain]).sort_index()
    combined = combined[~combined.index.duplicated(keep="last")]
    rsi_with_warmup_full = calculate_rsi(combined["close"].values, period=14)
    offset = len(df_w)
    print(f"\nRSI comparison at main-range start (offset={offset}):")
    for i in range(10):
        ts = combined.index[offset + i]
        nw = rsi_no_warmup[i]
        ww = rsi_with_warmup_full[offset + i]
        print(f"  {str(ts)[:16]}  no_warmup={nw:.4f}  with_warmup={ww:.4f}  diff={abs(nw - ww):.4f}")

    # Key question: does the RSI cross below 52 in either version?
    print("\nRSI crossunders below 52 (first 20 bars):")
    for i in range(1, 20):
        nw_cross = rsi_no_warmup[i - 1] >= 52 and rsi_no_warmup[i] < 52
        ww_cross = rsi_with_warmup_full[offset + i - 1] >= 52 and rsi_with_warmup_full[offset + i] < 52
        if nw_cross or ww_cross:
            ts = combined.index[offset + i]
            print(
                f"  {str(ts)[:16]}  no_warmup: {rsi_no_warmup[i - 1]:.3f}->{rsi_no_warmup[i]:.3f} (cross={nw_cross})  "
                f"with_warmup: {rsi_with_warmup_full[offset + i - 1]:.3f}->{rsi_with_warmup_full[offset + i]:.3f} (cross={ww_cross})"
            )


asyncio.run(main())
