"""Run backtest directly (no API) and compare trades with TV reference."""

import asyncio
import json
import sys
from datetime import UTC, datetime, timezone

sys.path.insert(0, "d:\\bybit_strategy_tester_v2")

import pandas as pd

# TV reference trades from q4.csv (UTC time, first 10 trades)
# Entry times are in UTC+3 (MSK), converted to UTC
TV_TRADES = [
    {"n": 1, "side": "short", "entry_utc": "2025-01-01 10:30", "entry_price": 3334.62, "pnl": 21.61},
    {"n": 2, "side": "short", "entry_utc": "2025-01-08 21:30", "entry_price": 3322.53, "pnl": 21.61},
    {"n": 3, "side": "short", "entry_utc": "2025-01-09 17:30", "entry_price": 3285.67, "pnl": 21.59},
    {"n": 4, "side": "short", "entry_utc": "2025-01-10 21:00", "entry_price": 3257.99, "pnl": 21.58},
    {"n": 5, "side": "long", "entry_utc": "2025-01-13 22:00", "entry_price": 3253.57, "pnl": 21.58},
    {"n": 6, "side": "long", "entry_utc": "2025-01-13 22:30", "entry_price": 3226.16, "pnl": 21.56},
    {"n": 7, "side": "short", "entry_utc": "2025-01-16 10:00", "entry_price": 3320.64, "pnl": 21.61},
    {"n": 8, "side": "long", "entry_utc": "2025-01-17 10:30", "entry_price": 3263.98, "pnl": 21.59},
    {"n": 9, "side": "short", "entry_utc": "2025-01-17 13:30", "entry_price": 3329.06, "pnl": 21.62},
    {"n": 10, "side": "short", "entry_utc": "2025-01-19 18:30", "entry_price": 3312.98, "pnl": 21.61},
]


async def main():
    from backend.backtesting.engine import BacktestEngine
    from backend.backtesting.models import BacktestConfig, StrategyType
    from backend.backtesting.service import BacktestService
    from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

    svc = BacktestService()
    start = datetime(2025, 1, 1, tzinfo=UTC)
    end = datetime(2026, 2, 25, tzinfo=UTC)

    # Fetch ETH data
    eth_ohlcv = await svc._fetch_historical_data("ETHUSDT", "30", start, end, market_type="linear")
    print(f"ETH: {len(eth_ohlcv)} bars, {eth_ohlcv.index[0]} to {eth_ohlcv.index[-1]}")

    # Fetch BTC with warmup
    warmup_delta = pd.Timedelta(minutes=500 * 30)
    btc_start = start - warmup_delta
    btc_ohlcv = await svc._fetch_historical_data("BTCUSDT", "30", btc_start, end, market_type="linear")
    print(f"BTC: {len(btc_ohlcv)} bars, {btc_ohlcv.index[0]} to {btc_ohlcv.index[-1]}")

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

    adapter = StrategyBuilderAdapter(strategy_graph, btcusdt_ohlcv=btc_ohlcv)
    signals = adapter.generate_signals(eth_ohlcv)

    # Count signals
    n_long = signals.entries.sum() if signals.entries is not None else 0
    n_short = signals.short_entries.sum() if signals.short_entries is not None else 0
    print(f"\nSignals: {n_long} long entries, {n_short} short entries")

    # Print first 20 entry signals
    print("\nFirst 20 short entry bars (signal -> entry at next open):")
    if signals.short_entries is not None:
        short_bars = eth_ohlcv[signals.short_entries].head(20)
        for ts, row in short_bars.iterrows():
            # Entry will be at next bar open
            next_bar_idx = eth_ohlcv.index.get_loc(ts) + 1
            if next_bar_idx < len(eth_ohlcv):
                next_ts = eth_ohlcv.index[next_bar_idx]
                next_open = eth_ohlcv.iloc[next_bar_idx]["open"]
                print(f"  Signal at {ts} (close={row['close']:.2f}) => Entry at {next_ts} open={next_open:.2f}")
            else:
                print(f"  Signal at {ts} (close={row['close']:.2f}) => End of data")

    print("\nTV first 10 entries (UTC):")
    for t in TV_TRADES[:10]:
        print(f"  #{t['n']:2d} {t['side']:5s} entry={t['entry_utc']} price={t['entry_price']:.2f}")


asyncio.run(main())
