"""Simple test for the API endpoint - writes output to file."""

import sys

import requests

BASE_URL = "http://localhost:8000"
OUTPUT_FILE = r"D:\bybit_strategy_tester_v2\test_output_eval.txt"


def log(msg):
    """Log to both stdout and file."""
    print(msg)
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


# Clear output file
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write("=== Evaluation Criteria Test ===\n\n")

# Test 1: Health check
try:
    r = requests.get(f"{BASE_URL}/api/v1/health", timeout=5)
    log(f"Health: {r.status_code}")
except Exception as e:
    log(f"Health failed: {e}")
    sys.exit(1)

# Test 2: Simple optimization
log("\n--- Test: Basic Optimization ---")
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
    r = requests.post(f"{BASE_URL}/api/v1/optimizations/sync/grid-search", json=payload, timeout=120)
    log(f"Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        log(f"Results: {len(data.get('results', []))}")
        if data.get("results"):
            best = data["results"][0]
            log(f"Best params: {best.get('params')}")
            log(f"Metrics: {best.get('metrics', {})}")
    else:
        log(f"Error: {r.text[:500]}")
except Exception as e:
    log(f"Exception: {e}")

# Test 3: With constraints
log("\n--- Test: With Constraints ---")
payload2 = {
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
    "constraints": [
        {"metric": "max_drawdown", "operator": "<=", "value": 30},
    ],
}

try:
    r = requests.post(f"{BASE_URL}/api/v1/optimizations/sync/grid-search", json=payload2, timeout=120)
    log(f"Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        log(f"Results (with constraints): {len(data.get('results', []))}")
    else:
        log(f"Error: {r.text[:500]}")
except Exception as e:
    log(f"Exception: {e}")

log("\n=== Test Complete ===")
