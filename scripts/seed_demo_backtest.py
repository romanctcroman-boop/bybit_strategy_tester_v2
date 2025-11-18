"""Seed demo backtest with equity curve and trades for UI testing.

Usage:
    python scripts/seed_demo_backtest.py
"""

import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Ensure DATABASE_URL is set (fallback to local sqlite for demo)
if not os.environ.get("DATABASE_URL"):
    db_path = project_root / "demo.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    print(f"Using demo database: {db_path}")

from backend.database import Base, engine
from backend.services.data_service import DataService


def generate_equity_curve(initial_capital: float, days: int = 30):
    """Generate synthetic equity curve with some volatility."""
    import random

    equity = []
    pnl_bars = []
    base_time = datetime(2024, 1, 1, tzinfo=UTC)
    current_equity = initial_capital

    for day in range(days):
        time_point = base_time + timedelta(days=day)
        # Simulate daily PnL: random walk with slight upward bias
        daily_pnl = random.gauss(50, 200)  # mean=50, stddev=200
        current_equity += daily_pnl

        equity.append({"time": time_point.isoformat(), "equity": round(current_equity, 2)})
        pnl_bars.append({"time": time_point.isoformat(), "pnl": round(daily_pnl, 2)})

    return equity, pnl_bars


def generate_trades(backtest_id: int, num_trades: int = 20):
    """Generate synthetic trades."""
    import random

    trades = []
    base_time = datetime(2024, 1, 1, tzinfo=UTC)
    cumulative_pnl = 0.0

    for i in range(num_trades):
        entry_time = base_time + timedelta(days=i, hours=random.randint(0, 23))
        exit_time = entry_time + timedelta(hours=random.randint(1, 48))
        side = random.choice(["LONG", "SHORT"])
        entry_price = round(random.uniform(40000, 50000), 2)
        quantity = round(random.uniform(0.01, 0.1), 4)
        # Simulate PnL: 60% win rate
        is_win = random.random() < 0.6
        if is_win:
            pnl = round(random.uniform(10, 100), 2)
        else:
            pnl = -round(random.uniform(5, 80), 2)

        cumulative_pnl += pnl

        trades.append(
            {
                "backtest_id": backtest_id,
                "entry_time": entry_time,
                "exit_time": exit_time,
                "side": side,
                "entry_price": entry_price,
                "quantity": quantity,
                "pnl": pnl,
            }
        )

    return trades


def seed():
    """Seed demo data."""
    print("Creating database schema...")
    Base.metadata.create_all(bind=engine)

    with DataService() as ds:
        # Create demo strategy
        print("Creating demo strategy...")
        strategy = ds.create_strategy(
            name="Demo Moving Average Strategy",
            description="Sample strategy for UI testing",
            strategy_type="Indicator-Based",
            config={"fast_ma": 10, "slow_ma": 30},
        )
        print(f"✓ Created strategy #{strategy.id}")

        # Create backtest
        print("Creating demo backtest...")
        initial_capital = 10000.0
        backtest = ds.create_backtest(
            strategy_id=strategy.id,
            symbol="BTCUSDT",
            timeframe="1h",
            start_date=datetime(2024, 1, 1, tzinfo=UTC),
            end_date=datetime(2024, 1, 31, tzinfo=UTC),
            initial_capital=initial_capital,
            leverage=1,
            commission=0.0006,
            status="completed",
        )
        print(f"✓ Created backtest #{backtest.id}")

        # Generate equity curve
        print("Generating equity curve...")
        equity, pnl_bars = generate_equity_curve(initial_capital, days=30)

        # Calculate metrics
        final_equity = equity[-1]["equity"]
        net_pnl = final_equity - initial_capital
        net_pct = (net_pnl / initial_capital) * 100

        # Generate trades
        print("Generating trades...")
        trades_data = generate_trades(backtest.id, num_trades=25)

        # Calculate trade stats
        wins = sum(1 for t in trades_data if t["pnl"] > 0)
        losses = sum(1 for t in trades_data if t["pnl"] <= 0)
        total_trades = len(trades_data)
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        total_pnl = sum(t["pnl"] for t in trades_data)
        gross_profit = sum(t["pnl"] for t in trades_data if t["pnl"] > 0)
        gross_loss = abs(sum(t["pnl"] for t in trades_data if t["pnl"] < 0))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0
        avg_win = (gross_profit / wins) if wins > 0 else 0
        avg_loss = (gross_loss / losses) if losses > 0 else 0

        # Build comprehensive results object
        results = {
            "overview": {
                "net_pnl": round(net_pnl, 2),
                "net_pct": round(net_pct, 2),
                "total_trades": total_trades,
                "wins": wins,
                "losses": losses,
                "max_drawdown_abs": round(abs(min(pnl_bars, key=lambda x: x["pnl"])["pnl"]), 2),
                "max_drawdown_pct": -15.5,
                "profit_factor": round(profit_factor, 2),
            },
            "by_side": {
                "all": {
                    "total_trades": total_trades,
                    "open_trades": 0,
                    "wins": wins,
                    "losses": losses,
                    "win_rate": round(win_rate, 2),
                    "avg_pl": round(total_pnl / total_trades, 2) if total_trades > 0 else 0,
                    "avg_pl_pct": round((total_pnl / initial_capital) / total_trades * 100, 2)
                    if total_trades > 0
                    else 0,
                    "avg_win": round(avg_win, 2),
                    "avg_win_pct": round((avg_win / initial_capital) * 100, 2) if avg_win > 0 else 0,
                    "avg_loss": round(avg_loss, 2),
                    "avg_loss_pct": round((avg_loss / initial_capital) * 100, 2)
                    if avg_loss > 0
                    else 0,
                    "max_win": round(max(t["pnl"] for t in trades_data), 2),
                    "max_win_pct": 2.5,
                    "max_loss": round(min(t["pnl"] for t in trades_data), 2),
                    "max_loss_pct": -1.8,
                    "profit_factor": round(profit_factor, 2),
                    "avg_bars": 24,
                    "avg_bars_win": 28,
                    "avg_bars_loss": 18,
                },
                "long": {
                    "total_trades": sum(1 for t in trades_data if t["side"] == "LONG"),
                    "wins": sum(1 for t in trades_data if t["side"] == "LONG" and t["pnl"] > 0),
                    "losses": sum(1 for t in trades_data if t["side"] == "LONG" and t["pnl"] <= 0),
                    "win_rate": 65.0,
                    "avg_pl": 35.0,
                    "profit_factor": 1.8,
                },
                "short": {
                    "total_trades": sum(1 for t in trades_data if t["side"] == "SHORT"),
                    "wins": sum(1 for t in trades_data if t["side"] == "SHORT" and t["pnl"] > 0),
                    "losses": sum(
                        1 for t in trades_data if t["side"] == "SHORT" and t["pnl"] <= 0
                    ),
                    "win_rate": 55.0,
                    "avg_pl": 25.0,
                    "profit_factor": 1.4,
                },
            },
            "dynamics": {
                "all": {
                    "unrealized_abs": 0,
                    "unrealized_pct": 0,
                    "net_abs": round(net_pnl, 2),
                    "net_pct": round(net_pct, 2),
                    "gross_profit_abs": round(gross_profit, 2),
                    "gross_profit_pct": round((gross_profit / initial_capital) * 100, 2),
                    "gross_loss_abs": round(gross_loss, 2),
                    "gross_loss_pct": round((gross_loss / initial_capital) * 100, 2),
                    "fees_abs": round(total_trades * 10, 2),
                    "fees_pct": round((total_trades * 10 / initial_capital) * 100, 2),
                    "max_runup_abs": round(max(pnl_bars, key=lambda x: x["pnl"])["pnl"], 2),
                    "max_runup_pct": 18.5,
                    "max_drawdown_abs": round(abs(min(pnl_bars, key=lambda x: x["pnl"])["pnl"]), 2),
                    "max_drawdown_pct": -15.5,
                    "buyhold_abs": round(net_pnl * 0.8, 2),
                    "buyhold_pct": round(net_pct * 0.8, 2),
                    "max_contracts": 5,
                },
                "long": {},
                "short": {},
            },
            "risk": {
                "sharpe": 1.35,
                "sortino": 1.85,
                "profit_factor": round(profit_factor, 2),
            },
            "equity": equity,
            "pnl_bars": pnl_bars,
        }

        # Update backtest with results
        print("Updating backtest results...")
        ds.update_backtest_results(
            backtest.id,
            final_capital=final_equity,
            total_return=net_pct,
            total_trades=total_trades,
            winning_trades=wins,
            losing_trades=losses,
            win_rate=win_rate,
            sharpe_ratio=1.35,
            max_drawdown=15.5,
            results=results,
        )

        # Insert trades
        print(f"Inserting {len(trades_data)} trades...")
        for trade in trades_data:
            ds.create_trade(**trade)

        print("\n✅ Demo data seeded successfully!")
        print(f"   Strategy ID: {strategy.id}")
        print(f"   Backtest ID: {backtest.id}")
        print(f"   Trades: {total_trades}")
        print(f"   Final Capital: ${final_equity:,.2f}")
        print(f"   Net PnL: ${net_pnl:,.2f} ({net_pct:.2f}%)")
        print("\nStart the backend and navigate to:")
        print(f"   http://localhost:5173/backtests/{backtest.id}")


if __name__ == "__main__":
    seed()
