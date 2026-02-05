"""Debug: Compare backtest vs grid-search."""

import requests

BASE_URL = "http://localhost:8000"
OUTPUT = r"D:\bybit_strategy_tester_v2\debug_compare.txt"

with open(OUTPUT, "w", encoding="utf-8") as f:
    # Direct backtest
    f.write("=== Direct Backtest ===\n")
    r = requests.post(
        f"{BASE_URL}/api/v1/backtests/",
        json={
            "symbol": "BTCUSDT",
            "interval": "15m",  # Note: 15m
            "start_date": "2025-01-01",
            "end_date": "2025-01-31",
            "initial_capital": 10000,
            "leverage": 10,
            "direction": "both",
            "strategy_type": "rsi",
            "strategy_params": {"period": 7, "overbought": 65, "oversold": 35},
        },
        timeout=60,
    )
    data = r.json()
    f.write(f"Status: {r.status_code}\n")
    f.write(f"Trades: {len(data.get('trades', []))}\n")
    f.write(f"Net Profit: {data.get('metrics', {}).get('net_profit', 0)}\n\n")

    # Grid search with same params
    f.write("=== Grid Search (single combo) ===\n")
    r = requests.post(
        f"{BASE_URL}/api/v1/optimizations/sync/grid-search",
        json={
            "symbol": "BTCUSDT",
            "interval": "15",  # Note: 15 (without m)
            "start_date": "2025-01-01",
            "end_date": "2025-01-31",
            "initial_capital": 10000,
            "leverage": 10,
            "direction": "both",
            "strategy_type": "rsi",
            "param_ranges": {"period": [7, 7, 1], "overbought": [65, 65, 1], "oversold": [35, 35, 1]},
            "primary_metric": "profit_factor",
        },
        timeout=120,
    )
    f.write(f"Status: {r.status_code}\n")
    if r.status_code == 200:
        data = r.json()
        f.write(f"Results: {len(data.get('results', []))}\n")
        f.write(f"Total combinations: {data.get('total_combinations', 0)}\n")
        f.write(f"Tested combinations: {data.get('tested_combinations', 0)}\n")
        if data.get("results"):
            best = data["results"][0]
            f.write(f"Best result: {best}\n")
        else:
            f.write("No results!\n")
        f.write(f"\nFull response keys: {list(data.keys())}\n")
    else:
        f.write(f"Error: {r.text[:500]}\n")
