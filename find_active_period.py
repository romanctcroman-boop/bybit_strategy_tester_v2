"""Find active period for RSI strategy testing."""

import json

import requests

BASE_URL = "http://localhost:8000"
OUTPUT = r"D:\bybit_strategy_tester_v2\find_data_result.txt"

with open(OUTPUT, "w", encoding="utf-8") as f:
    # Check server
    try:
        r = requests.get(f"{BASE_URL}/api/v1/health", timeout=5)
        f.write(f"Server: {r.status_code}\n\n")
    except Exception as e:
        f.write(f"Server DOWN: {e}\n")
        exit(1)

    # Try a quick backtest to see if we get trades
    # Use more aggressive RSI params
    f.write("Testing RSI with aggressive params (period=7, ob=65, os=35)...\n")

    test_configs = [
        {"start": "2025-01-01", "end": "2025-01-31", "name": "January 2025"},
        {"start": "2025-01-15", "end": "2025-02-04", "name": "Late Jan - Feb 2025"},
    ]

    for cfg in test_configs:
        f.write(f"\n--- {cfg['name']} ---\n")
        try:
            r = requests.post(
                f"{BASE_URL}/api/v1/backtests/",
                json={
                    "symbol": "BTCUSDT",
                    "interval": "15m",
                    "start_date": cfg["start"],
                    "end_date": cfg["end"],
                    "initial_capital": 10000,
                    "leverage": 10,
                    "direction": "both",
                    "strategy_type": "rsi",
                    "strategy_params": {"period": 7, "overbought": 65, "oversold": 35},
                },
                timeout=60,
            )
            f.write(f"Status: {r.status_code}\n")
            if r.status_code == 200:
                data = r.json()
                trades = len(data.get("trades", []))
                metrics = data.get("metrics", {})
                f.write(f"Trades: {trades}\n")
                if trades > 0:
                    f.write(f"Total Return: {metrics.get('total_return', 0):.2f}%\n")
                    f.write(f"Max Drawdown: {metrics.get('max_drawdown', 0):.2f}%\n")
                    f.write(f"Sharpe: {metrics.get('sharpe_ratio', 0):.3f}\n")
                    f.write(f"Win Rate: {metrics.get('win_rate', 0):.2f}%\n")
                    f.write("GOOD - Use this period!\n")
            else:
                f.write(f"Error: {r.text[:200]}\n")
        except Exception as e:
            f.write(f"Exception: {e}\n")
        f.flush()
