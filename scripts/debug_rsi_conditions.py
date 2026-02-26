"""
Deep debug: check BTC RSI values at signal bars and cross conditions.
"""

import asyncio
import sys
from datetime import datetime, timezone

sys.path.insert(0, "d:\\bybit_strategy_tester_v2")

import pandas as pd


async def main():
    from backend.backtesting.service import BacktestService
    from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter
    from backend.core.indicators import calculate_rsi

    svc = BacktestService()
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    end = datetime(2025, 1, 10, tzinfo=timezone.utc)

    strategy_graph = {
        "name": "Strategy_RSI_LS_11",
        "interval": "30",
        "blocks": [
            {
                "id": "price_input",
                "type": "price",
                "category": "input",
                "name": "PRICE",
                "x": 50,
                "y": 200,
                "params": {"source": "close"},
            },
            {
                "id": "rsi_block",
                "type": "rsi",
                "category": "indicator",
                "name": "RSI",
                "x": 400,
                "y": 100,
                "params": {
                    "period": 14,
                    "source": "close",
                    "timeframe": "30",
                    "use_btc_source": True,
                    "use_long_range": True,
                    "long_rsi_more": 28,
                    "long_rsi_less": 70,
                    "use_short_range": True,
                    "short_rsi_more": 50,
                    "short_rsi_less": 70,
                    "use_cross_level": True,
                    "cross_long_level": 24,
                    "cross_short_level": 52,
                    "opposite_signal": False,
                    "use_cross_memory": False,
                    "cross_memory_bars": 5,
                },
            },
            {
                "id": "static_sltp",
                "type": "static_sltp",
                "category": "exit",
                "name": "Static SL/TP",
                "x": 400,
                "y": 300,
                "params": {"take_profit_percent": 2.3, "stop_loss_percent": 13.2, "sl_type": "average_price"},
            },
            {
                "id": "strategy_node",
                "type": "strategy",
                "category": "output",
                "name": "STRATEGY",
                "x": 700,
                "y": 200,
                "params": {},
            },
        ],
        "connections": [
            {
                "id": "c1",
                "source": {"blockId": "rsi_block", "portId": "long"},
                "target": {"blockId": "strategy_node", "portId": "entry_long"},
            },
            {
                "id": "c2",
                "source": {"blockId": "rsi_block", "portId": "short"},
                "target": {"blockId": "strategy_node", "portId": "entry_short"},
            },
            {
                "id": "c3",
                "source": {"blockId": "static_sltp", "portId": "config"},
                "target": {"blockId": "strategy_node", "portId": "exit_config"},
            },
        ],
    }

    eth_ohlcv = await svc._fetch_historical_data("ETHUSDT", "30", start, end, market_type="linear")

    import pandas as _pd

    warmup_delta = _pd.Timedelta(minutes=500 * 30)
    btc_start = start - warmup_delta
    btc_ohlcv = await svc._fetch_historical_data("BTCUSDT", "30", btc_start, end, market_type="linear")

    print(f"ETH: {len(eth_ohlcv)} bars, {eth_ohlcv.index[0]} to {eth_ohlcv.index[-1]}")
    print(f"BTC: {len(btc_ohlcv)} bars, {btc_ohlcv.index[0]} to {btc_ohlcv.index[-1]}")

    # Compute BTC RSI manually (same as indicator_handlers)
    btc_close = btc_ohlcv["close"]
    # Normalize tz
    if eth_ohlcv.index.tz is None and btc_close.index.tz is not None:
        btc_close.index = btc_close.index.tz_localize(None)

    btc_rsi_arr = calculate_rsi(btc_close.values, period=14)
    btc_rsi_full = pd.Series(btc_rsi_arr, index=btc_close.index)

    # Reindex to ETH timestamps (as indicator_handlers does)
    rsi_trimmed = btc_rsi_full.reindex(eth_ohlcv.index, method="ffill")
    na_ratio = rsi_trimmed.isna().mean()
    print(f"\nBTC RSI reindexed to ETH bars: na_ratio={na_ratio:.1%}")

    # Fill remaining NaN with ETH RSI
    eth_rsi_arr = calculate_rsi(eth_ohlcv["close"].values, period=14)
    eth_rsi = pd.Series(eth_rsi_arr, index=eth_ohlcv.index)
    rsi = rsi_trimmed.fillna(eth_rsi)

    print("\nRSI values at 2025-01-01 first 20 bars:")
    print(rsi.head(20).to_string())

    # Check conditions at signal bar 13:00
    print("\n--- At bar 13:00 UTC (signal bar) ---")
    bar_13 = pd.Timestamp("2025-01-01 13:00:00")
    bar_12_30 = pd.Timestamp("2025-01-01 12:30:00")

    if bar_13 in rsi.index:
        curr = rsi.loc[bar_13]
        prev = rsi.loc[bar_12_30] if bar_12_30 in rsi.index else float("nan")
        print(f"RSI prev (12:30): {prev:.4f}")
        print(f"RSI curr (13:00): {curr:.4f}")
        print(f"Cross condition (prev>=52 & curr<52): {prev >= 52 and curr < 52}")
        print(f"Range condition (curr>=50 & curr<=70): {curr >= 50 and curr <= 70}")
        print(f"FULL short signal (cross & range): {prev >= 52 and curr < 52 and curr >= 50 and curr <= 70}")

    # Compute cross & range conditions
    rsi_prev = rsi.shift(1)
    cross_short = (rsi_prev >= 52) & (rsi < 52)
    short_range = (rsi >= 50) & (rsi <= 70)
    short_signal = cross_short & short_range

    print(f"\nCross short True bars: {cross_short.sum()}")
    print(f"Short range True bars: {short_range.sum()}")
    print(f"Short signal (both) True bars: {short_signal.sum()}")

    # Show bars where short signal fires
    print("\nBars where short signal fires:")
    for ts in short_signal[short_signal].index:
        print(f"  {ts}: RSI={rsi.loc[ts]:.3f}, prev RSI={rsi_prev.loc[ts]:.3f}")

    # Show all cross_short bars
    print("\nBars where cross_short fires:")
    for ts in cross_short[cross_short].index[:20]:
        print(f"  {ts}: RSI={rsi.loc[ts]:.3f}, prev RSI={rsi_prev.loc[ts]:.3f}, range={short_range.loc[ts]}")


asyncio.run(main())
