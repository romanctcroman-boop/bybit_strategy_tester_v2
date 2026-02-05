"""Test API endpoints directly via TestClient."""


from fastapi.testclient import TestClient

from backend.api.app import app

client = TestClient(app)

# Get strategy ID
response = client.get("/api/v1/strategy-builder/strategies")
print(f"GET /strategies: {response.status_code}")
strategies = response.json().get("strategies", [])
if strategies:
    strategy_id = strategies[0]["id"]
    print(f"Using strategy ID: {strategy_id}")

    # Test PUT
    print("\n" + "=" * 50)
    print("Testing PUT (update strategy)")
    put_data = {
        "name": "Test Update",
        "timeframe": "15m",
        "symbol": "BTCUSDT",
        "market_type": "linear",
        "direction": "both",
        "initial_capital": 10000,
        "description": "",
        "blocks": [],
        "connections": [],
    }
    response = client.put(f"/api/v1/strategy-builder/strategies/{strategy_id}", json=put_data)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:500]}")

    # Test POST generate-code
    print("\n" + "=" * 50)
    print("Testing POST /generate-code")
    code_data = {"template": "backtest", "include_comments": True, "include_logging": True, "async_mode": False}
    response = client.post(f"/api/v1/strategy-builder/strategies/{strategy_id}/generate-code", json=code_data)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:500]}")

    # Test POST backtest
    print("\n" + "=" * 50)
    print("Testing POST /backtest")
    backtest_data = {
        "start_date": "2025-01-01T00:00:00Z",
        "end_date": "2025-01-10T00:00:00Z",
        "commission": 0.0007,
        "slippage": 0.0005,
        "leverage": 10,
    }
    response = client.post(f"/api/v1/strategy-builder/strategies/{strategy_id}/backtest", json=backtest_data)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:500]}")
else:
    print("No strategies found")
