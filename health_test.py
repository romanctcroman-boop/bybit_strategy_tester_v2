"""Test server health only."""

import requests

with open(r"D:\bybit_strategy_tester_v2\health_result.txt", "w") as f:
    try:
        r = requests.get("http://localhost:8000/api/v1/health", timeout=5)
        f.write(f"Health Status: {r.status_code}\n")
        f.write(f"Response: {r.text}\n")
    except Exception as e:
        f.write(f"Error: {e}\n")
