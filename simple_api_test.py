"""Simple test for the API endpoint."""

import sys

import requests

BASE_URL = "http://localhost:8000"

# Test 1: Health check
try:
    r = requests.get(f"{BASE_URL}/api/v1/health", timeout=5)
    print(f"Health: {r.status_code}")
except Exception as e:
    print(f"Health failed: {e}")
    sys.exit(1)

# Test 2: Simple optimization
payload = {
    "symbol": "BTCUSDT",
    "interval": "15",
    "start_date": "2025-01-01",
    "end_date": "2025-01-10",
    "initial_capital": 10000,
    "leverage": 10,
    "direction": "both",
    "strategy_type": "rsi",
    "param_ranges": {"period": [10, 15, 5], "overbought": [70, 75, 5], "oversold": [25, 30, 5]},
    "primary_metric": "profit_factor",
}

try:
    r = requests.post(f"{BASE_URL}/api/v1/optimizations/sync/grid-search", json=payload, timeout=60)
    print(f"Optimization: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"Results: {len(data.get('results', []))}")
    else:
        print(f"Error: {r.text[:300]}")
except Exception as e:
    print(f"Optimization failed: {e}")
