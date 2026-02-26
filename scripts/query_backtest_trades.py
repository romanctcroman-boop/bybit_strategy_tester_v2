"""Query the latest backtest trades from DB directly."""

import sys

sys.path.insert(0, "d:\\bybit_strategy_tester_v2")

import json

from backend.database import SessionLocal
from backend.models.backtest import Backtest

with SessionLocal() as s:
    # Get the most recent backtest for RSI_LS_11 strategy
    bt = (
        s.query(Backtest)
        .filter(Backtest.strategy_id == "01cd8861-60eb-40dd-a9a9-8baa6f2db0fa")
        .order_by(Backtest.created_at.desc())
        .first()
    )

    if bt:
        print(f"Backtest ID: {bt.id}")
        print(f"Status: {bt.status}")
        print(f"Total trades: {bt.total_trades}")
        print(f"Created: {bt.created_at}")

        # Get trades
        trades = bt.trades or []
        print(f"Stored trades: {len(trades)}")

        if trades:
            print("\nFirst 10 trades:")
            for i, t in enumerate(trades[:10], 1):
                side = t.get("side", t.get("direction", "?"))
                entry_time = t.get("entry_time", t.get("entry_date", "?"))
                entry_price = t.get("entry_price", t.get("open_price", 0))
                pnl = t.get("pnl", t.get("profit", t.get("net_pnl", 0)))
                exit_reason = t.get("exit_reason", t.get("close_reason", "?"))
                print(
                    f"  {i}. {side} entry={entry_time} ep={float(entry_price):.2f} pnl={float(pnl):.2f} exit={exit_reason}"
                )
    else:
        print("No backtest found")

        # List recent backtests
        recent = s.query(Backtest).order_by(Backtest.created_at.desc()).limit(5).all()
        for b in recent:
            print(f"  {b.id} strategy={b.strategy_id} trades={b.total_trades} {b.created_at}")
