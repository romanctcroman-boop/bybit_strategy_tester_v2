"""Quick backend health check"""

import requests

BASE = "http://localhost:8000"


def check():
    endpoints = [
        "/api/v1/health",
        "/api/v1/strategies/",
        "/api/v1/symbols/linear",
    ]

    for ep in endpoints:
        try:
            r = requests.get(f"{BASE}{ep}", timeout=30)
            print(f"{'OK' if r.status_code == 200 else 'FAIL'} [{r.status_code}] {ep}")
        except Exception as e:
            print(f"ERROR {ep}: {e}")

    # Quick backtest test
    try:
        r = requests.post(
            f"{BASE}/api/v1/backtests/",
            json={
                "symbol": "BTCUSDT",
                "interval": "15",
                "start_date": "2025-01-01",
                "end_date": "2025-01-05",
                "initial_capital": 10000,
                "leverage": 10,
                "direction": "both",
                "stop_loss": 0.05,
                "take_profit": 0.02,
                "strategy_type": "rsi",
                "strategy_params": {"period": 14, "overbought": 70, "oversold": 30},
            },
            timeout=60,
        )

        if r.status_code == 200:
            data = r.json()
            trades = data.get("trades", [])
            metrics = data.get("metrics", {})
            print(f"\nBacktest OK: {len(trades)} trades, net_profit=${metrics.get('net_profit', 0):.2f}")
        else:
            print(f"\nBacktest FAIL: {r.status_code}")
    except Exception as e:
        print(f"\nBacktest ERROR: {e}")


if __name__ == "__main__":
    check()
