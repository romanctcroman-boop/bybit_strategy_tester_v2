"""Test PUT request to strategy builder."""

import json

import requests

strategy_id = "4a9f2d78-b85d-4eb3-afb0-28a8c57b5396"
url = f"http://localhost:8000/api/v1/strategy-builder/strategies/{strategy_id}"

payload = {
    "name": "Test Strategy Update",
    "timeframe": "15m",
    "symbol": "BTCUSDT",
    "market_type": "linear",
    "direction": "both",
    "initial_capital": 10000,
    "description": "",
    "blocks": [],
    "connections": [],
}

print(f"Testing PUT {url}")
print(f"Payload: {json.dumps(payload, indent=2)}")

response = requests.put(url, json=payload)
print(f"\nStatus: {response.status_code}")
print(f"Headers: {dict(response.headers)}")
print(f"Response: {response.text}")

# Test POST generate-code
print("\n" + "=" * 50)
print("Testing POST /generate-code")
code_url = f"http://localhost:8000/api/v1/strategy-builder/strategies/{strategy_id}/generate-code"
code_payload = {"template": "backtest", "include_comments": True, "include_logging": True, "async_mode": False}
print(f"URL: {code_url}")
response = requests.post(code_url, json=code_payload)
print(f"Status: {response.status_code}")
print(f"Response: {response.text[:500] if len(response.text) > 500 else response.text}")

# Test POST backtest
print("\n" + "=" * 50)
print("Testing POST /backtest")
backtest_url = f"http://localhost:8000/api/v1/strategy-builder/strategies/{strategy_id}/backtest"
backtest_payload = {
    "start_date": "2025-01-01T00:00:00Z",
    "end_date": "2025-01-10T00:00:00Z",
    "commission": 0.0007,
    "slippage": 0.0005,
    "leverage": 10,
}
print(f"URL: {backtest_url}")
response = requests.post(backtest_url, json=backtest_payload)
print(f"Status: {response.status_code}")
print(f"Response: {response.text[:500] if len(response.text) > 500 else response.text}")
