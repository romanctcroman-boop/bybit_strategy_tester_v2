import sys

import requests

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

STRATEGY_ID = "f46c7cc3-1098-483a-a177-67b7867dd72e"
BASE_URL = "http://localhost:8000"

payload = {
    "symbol": "ETHUSDT",
    "interval": "30",
    "start_date": "2025-01-01T00:00:00Z",
    "end_date": "2025-03-01T00:00:00Z",
    "initial_capital": 10000.0,
    "position_size": 0.1,
    "leverage": 1,
    "direction": "both",
    "commission": 0.0007,
    "slippage": 0.0,
    "pyramiding": 1,
    "market_type": "linear",
}

print("Sending backtest request...")
r = requests.post(f"{BASE_URL}/api/v1/strategy-builder/strategies/{STRATEGY_ID}/backtest", json=payload, timeout=120)
print(f"Status: {r.status_code}")

if r.status_code == 200:
    data = r.json()
    metrics = data.get("metrics", {})
    trades = data.get("trades", [])

    print(f"\n=== METRICS RAW VALUES ===")
    print(f"total_trades: {metrics.get('total_trades')}")
    print(f"winning_trades: {metrics.get('winning_trades')}")
    print(f"win_rate (raw): {metrics.get('win_rate')}")  # Should be 0-100
    print(f"net_profit: {metrics.get('net_profit')}")
    print(f"final_equity: {metrics.get('final_equity')}")  # From data root, not metrics
    print(f"initial_capital: {metrics.get('initial_capital')}")
    print(f"sharpe_ratio: {metrics.get('sharpe_ratio')}")
    print(f"sortino_ratio: {metrics.get('sortino_ratio')}")
    print(f"max_drawdown: {metrics.get('max_drawdown')}")
    print(f"profit_factor: {metrics.get('profit_factor')}")
    print(f"long_trades: {metrics.get('long_trades')}")
    print(f"short_trades: {metrics.get('short_trades')}")
    print(f"long_win_rate: {metrics.get('long_win_rate')}")
    print(f"short_win_rate: {metrics.get('short_win_rate')}")

    print(f"\n=== DATA ROOT ===")
    print(f"final_equity (root): {data.get('final_equity')}")
    print(f"final_pnl (root): {data.get('final_pnl')}")
    print(f"status: {data.get('status')}")

    if trades:
        print(f"\n=== FIRST 5 TRADES (DCA order numbers) ===")
        for i, t in enumerate(trades[:5]):
            print(
                f"Trade {i}: trade_number={t.get('trade_number')} grid_level={t.get('grid_level')} "
                f"dca_orders_filled={t.get('dca_orders_filled')} "
                f"entry={t.get('entry_price'):.2f}, pnl={t.get('pnl'):.4f}, comment={t.get('exit_comment')}"
            )
else:
    print(f"Error: {r.text[:500]}")
