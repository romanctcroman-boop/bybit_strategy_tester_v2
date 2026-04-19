"""Inspect last trade (#129) to understand open vs closed issue."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DATABASE_URL", "sqlite:///data.sqlite3")

from backend.backtesting.engine import BacktestEngine
from backend.backtesting.models import BacktestConfig

cfg = BacktestConfig(
    strategy_id="5a1741ac-ad9e-4285-a9d6-58067c56407a",
    symbol="BTCUSDT",
    timeframe="15",
    start_date="2025-01-01",
    end_date="2025-02-24",
    initial_capital=10000,
    position_size=0.10,
    leverage=10,
    commission_value=0.0007,
    slippage=0.0,
    take_profit=0.015,
    stop_loss=0.032,
    strategy_params={"rsi_period": 14, "rsi_overbought": 70, "rsi_oversold": 30},
)


async def run():
    engine = BacktestEngine()
    result = await engine.run_backtest(cfg)
    trades = result.trades
    print(f"Total trades: {len(trades)}")
    last = trades[-1]
    print("\nTrade #129:")
    print(f"  side={last.side}")
    print(f"  entry_price={last.entry_price}")
    print(f"  exit_price={last.exit_price}")
    exit_reason = getattr(last, "exit_reason", "N/A")
    print(f"  exit_reason={exit_reason}")
    print(f"  exit_time={last.exit_time}")
    print(f"  pnl={last.pnl}")
    # Check all attributes
    attrs = [a for a in dir(last) if not a.startswith("_")]
    print(f"  attrs: {attrs}")
    for a in attrs:
        try:
            val = getattr(last, a)
            if not callable(val):
                print(f"    {a} = {val}")
        except Exception:
            pass


asyncio.run(run())
