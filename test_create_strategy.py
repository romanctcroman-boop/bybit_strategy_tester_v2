"""Create a new builder strategy and test the API."""

import json

import requests

# 1. Create a new strategy
print("=== Creating new Strategy Builder strategy ===")
create_url = "http://localhost:8000/api/v1/strategy-builder/strategies"
create_payload = {
    "name": "Test RSI Strategy",
    "timeframe": "15m",
    "symbol": "BTCUSDT",
    "market_type": "linear",
    "direction": "both",
    "initial_capital": 10000,
    "description": "Test strategy for API validation",
    "blocks": [
        {
            "id": "rsi_1",
            "type": "rsi",
            "name": "RSI Indicator",
            "position_x": 100,
            "position_y": 100,
            "params": {"period": 14, "source": "close"},
            "inputs": [],
            "outputs": [{"id": "value", "name": "RSI Value", "type": "number"}],
        },
        {
            "id": "const_30",
            "type": "constant",
            "name": "Oversold Level",
            "position_x": 100,
            "position_y": 200,
            "params": {"value": 30},
            "inputs": [],
            "outputs": [{"id": "value", "name": "Value", "type": "number"}],
        },
        {
            "id": "less_than_1",
            "type": "less_than",
            "name": "RSI < 30",
            "position_x": 300,
            "position_y": 150,
            "params": {},
            "inputs": [
                {"id": "left", "name": "Left", "type": "number"},
                {"id": "right", "name": "Right", "type": "number"},
            ],
            "outputs": [{"id": "result", "name": "Result", "type": "boolean"}],
        },
    ],
    "connections": [
        {
            "id": "conn_1",
            "source_block": "rsi_1",
            "source_output": "value",
            "target_block": "less_than_1",
            "target_input": "left",
        },
        {
            "id": "conn_2",
            "source_block": "const_30",
            "source_output": "value",
            "target_block": "less_than_1",
            "target_input": "right",
        },
    ],
}

response = requests.post(create_url, json=create_payload)
print(f"Create Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")

if response.status_code == 200:
    strategy_id = response.json().get("id")
    print(f"\n✅ Strategy created with ID: {strategy_id}")

    # 2. Test GET
    print("\n=== Testing GET ===")
    get_url = f"http://localhost:8000/api/v1/strategy-builder/strategies/{strategy_id}"
    response = requests.get(get_url)
    print(f"GET Status: {response.status_code}")

    # 3. Test PUT (update)
    print("\n=== Testing PUT (update) ===")
    update_payload = create_payload.copy()
    update_payload["name"] = "Updated RSI Strategy"
    response = requests.put(get_url, json=update_payload)
    print(f"PUT Status: {response.status_code}")
    if response.status_code == 200:
        print(f"Updated name: {response.json().get('name')}")
    else:
        print(f"Response: {response.text}")

    # 4. Test generate-code
    print("\n=== Testing POST /generate-code ===")
    code_url = f"http://localhost:8000/api/v1/strategy-builder/strategies/{strategy_id}/generate-code"
    code_payload = {
        "template": "backtest",
        "include_comments": True,
        "include_logging": True,
        "async_mode": False,
    }
    response = requests.post(code_url, json=code_payload)
    print(f"Generate Code Status: {response.status_code}")
    if response.status_code == 200:
        code = response.json().get("code", "")
        print(f"Generated code length: {len(code)} chars")
        print(f"First 200 chars:\n{code[:200]}...")
    else:
        print(f"Response: {response.text[:300]}")

    # 5. Test backtest
    print("\n=== Testing POST /backtest ===")
    backtest_url = f"http://localhost:8000/api/v1/strategy-builder/strategies/{strategy_id}/backtest"
    backtest_payload = {
        "start_date": "2025-01-01T00:00:00Z",
        "end_date": "2025-01-10T00:00:00Z",
        "commission": 0.0007,
        "slippage": 0.0005,
        "leverage": 10,
    }
    response = requests.post(backtest_url, json=backtest_payload)
    print(f"Backtest Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print("Backtest completed!")
        print(f"Total trades: {result.get('total_trades', 'N/A')}")
    else:
        print(f"Response: {response.text[:500]}")

    print(f"\n🎉 All API tests completed! Strategy ID: {strategy_id}")
    print(f"Use this ID in frontend: http://localhost:8000/frontend/strategy-builder.html?id={strategy_id}")
else:
    print(f"❌ Failed to create strategy: {response.text}")
