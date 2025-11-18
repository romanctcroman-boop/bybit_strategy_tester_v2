"""Seed demo backtest via HTTP API for UI testing.

Requires backend running at http://127.0.0.1:8000

Usage:
    python scripts/seed_demo_via_api.py
"""

import random
import requests
from datetime import datetime, timedelta, UTC

API_BASE = "http://127.0.0.1:8000/api/v1"


def generate_equity_curve(initial_capital: float, days: int = 30):
    """Generate synthetic equity curve with some volatility."""
    equity = []
    pnl_bars = []
    base_time = datetime(2024, 1, 1, tzinfo=UTC)
    current_equity = initial_capital

    for day in range(days):
        time_point = base_time + timedelta(days=day)
        daily_pnl = random.gauss(50, 200)
        current_equity += daily_pnl

        equity.append({"time": time_point.isoformat(), "equity": round(current_equity, 2)})
        pnl_bars.append({"time": time_point.isoformat(), "pnl": round(daily_pnl, 2)})

    return equity, pnl_bars


def seed():
    """Seed demo data via API."""
    # 1. Create or fetch strategy
    print("Creating/fetching demo strategy...")
    import time

    strategy_name = f"Demo MA Strategy {int(time.time())}"
    strategy_payload = {
        "name": strategy_name,
        "description": "Sample strategy for UI testing",
        "strategy_type": "Indicator-Based",
        "config": {"fast_ma": 10, "slow_ma": 30},
    }
    resp = requests.post(f"{API_BASE}/strategies", json=strategy_payload, timeout=10)
    resp.raise_for_status()
    strategy = resp.json()
    print(f"✓ Created strategy #{strategy['id']}")

    # 2. Create backtest then update status to completed
    print("Creating demo backtest...")
    initial_capital = 10000.0
    backtest_payload = {
        "strategy_id": strategy["id"],
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "start_date": "2024-01-01T00:00:00Z",
        "end_date": "2024-01-31T00:00:00Z",
        "initial_capital": initial_capital,
        "leverage": 1,
        "commission": 0.0006,
        "config": {},
    }
    resp = requests.post(f"{API_BASE}/backtests", json=backtest_payload, timeout=10)
    resp.raise_for_status()
    backtest = resp.json()
    backtest_id = backtest["id"]

    # Update status to completed so it validates
    resp = requests.put(
        f"{API_BASE}/backtests/{backtest_id}", json={"status": "completed"}, timeout=10
    )
    resp.raise_for_status()
    backtest = resp.json()
    print(f"✓ Created backtest #{backtest_id}")

    # 3. Generate equity curve
    print("Generating equity curve...")
    equity, pnl_bars = generate_equity_curve(initial_capital, days=30)

    final_equity = equity[-1]["equity"]
    net_pnl = final_equity - initial_capital
    net_pct = (net_pnl / initial_capital) * 100

    # Generate fake trade stats
    total_trades = 25
    wins = 16
    losses = 9
    win_rate = (wins / total_trades) * 100
    gross_profit = 1800.0
    gross_loss = 600.0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

    # Build comprehensive results
    results = {
        "overview": {
            "net_pnl": round(net_pnl, 2),
            "net_pct": round(net_pct, 2),
            "total_trades": total_trades,
            "wins": wins,
            "losses": losses,
            "max_drawdown_abs": 450.0,
            "max_drawdown_pct": -4.5,
            "profit_factor": round(profit_factor, 2),
        },
        "by_side": {
            "all": {
                "total_trades": total_trades,
                "open_trades": 0,
                "wins": wins,
                "losses": losses,
                "win_rate": round(win_rate, 2),
                "avg_pl": round(net_pnl / total_trades, 2),
                "avg_pl_pct": round((net_pnl / initial_capital) / total_trades * 100, 2),
                "avg_win": round(gross_profit / wins, 2),
                "avg_win_pct": round((gross_profit / wins / initial_capital) * 100, 2),
                "avg_loss": round(gross_loss / losses, 2),
                "avg_loss_pct": round((gross_loss / losses / initial_capital) * 100, 2),
                "max_win": 220.0,
                "max_win_pct": 2.2,
                "max_loss": -95.0,
                "max_loss_pct": -0.95,
                "profit_factor": round(profit_factor, 2),
                "avg_bars": 24,
                "avg_bars_win": 28,
                "avg_bars_loss": 18,
            },
            "long": {
                "total_trades": 13,
                "wins": 9,
                "losses": 4,
                "win_rate": 69.2,
                "avg_pl": 60.0,
                "profit_factor": 2.1,
            },
            "short": {
                "total_trades": 12,
                "wins": 7,
                "losses": 5,
                "win_rate": 58.3,
                "avg_pl": 40.0,
                "profit_factor": 1.6,
            },
        },
        "dynamics": {
            "all": {
                "unrealized_abs": 0,
                "unrealized_pct": 0,
                "net_abs": round(net_pnl, 2),
                "net_pct": round(net_pct, 2),
                "gross_profit_abs": gross_profit,
                "gross_profit_pct": round((gross_profit / initial_capital) * 100, 2),
                "gross_loss_abs": gross_loss,
                "gross_loss_pct": round((gross_loss / initial_capital) * 100, 2),
                "fees_abs": round(total_trades * 12, 2),
                "fees_pct": round((total_trades * 12 / initial_capital) * 100, 2),
                "max_runup_abs": 850.0,
                "max_runup_pct": 8.5,
                "max_drawdown_abs": 450.0,
                "max_drawdown_pct": -4.5,
                "buyhold_abs": round(net_pnl * 0.75, 2),
                "buyhold_pct": round(net_pct * 0.75, 2),
                "max_contracts": 5,
            },
            "long": {},
            "short": {},
        },
        "risk": {
            "sharpe": 1.42,
            "sortino": 1.95,
            "profit_factor": round(profit_factor, 2),
        },
        "equity": equity,
        "pnl_bars": pnl_bars,
    }

    # 4. Update backtest results
    print("Updating backtest results...")
    results_payload = {
        "final_capital": final_equity,
        "total_return": net_pct,
        "total_trades": total_trades,
        "winning_trades": wins,
        "losing_trades": losses,
        "win_rate": win_rate,
        "sharpe_ratio": 1.42,
        "max_drawdown": 4.5,
        "results": results,
    }
    resp = requests.post(
        f"{API_BASE}/backtests/{backtest_id}/results", json=results_payload, timeout=10
    )
    resp.raise_for_status()

    print("\n✅ Demo data seeded successfully!")
    print(f"   Strategy ID: {strategy['id']}")
    print(f"   Backtest ID: {backtest_id}")
    print(f"   Final Capital: ${final_equity:,.2f}")
    print(f"   Net PnL: ${net_pnl:,.2f} ({net_pct:.2f}%)")
    print("\nNavigate to:")
    print(f"   http://localhost:5173/backtests/{backtest_id}")


if __name__ == "__main__":
    try:
        seed()
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure the backend is running at http://127.0.0.1:8000")
        print("Start it with: .\\scripts\\start_uvicorn.ps1")
