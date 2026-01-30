"""Test Strategy Builder API endpoints."""

import requests

BASE_URL = "http://localhost:8000/api/v1/strategy-builder"


def test_all_endpoints():
    print("=" * 60)
    print("Testing Strategy Builder API")
    print("=" * 60)

    # 1. List strategies
    print("\n1. GET /strategies")
    try:
        r = requests.get(f"{BASE_URL}/strategies", timeout=10)
        print(f"   Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"   Strategies found: {len(data.get('strategies', []))}")
            if data.get("strategies"):
                for s in data["strategies"][:3]:
                    print(f"     - {s.get('id')}: {s.get('name')}")
        else:
            print(f"   Response: {r.text[:200]}")
    except Exception as e:
        print(f"   Error: {e}")

    # 2. Create a new strategy
    print("\n2. POST /strategies (Create)")
    strategy_data = {
        "name": "Test API Strategy",
        "description": "Created via API test",
        "symbol": "BTCUSDT",
        "interval": "15m",
    }
    try:
        r = requests.post(f"{BASE_URL}/strategies", json=strategy_data, timeout=10)
        print(f"   Status: {r.status_code}")
        if r.status_code in (200, 201):
            data = r.json()
            strategy_id = data.get("id")
            print(f"   Created strategy ID: {strategy_id}")

            if strategy_id:
                # 3. GET the strategy
                print(f"\n3. GET /strategies/{strategy_id}")
                r = requests.get(f"{BASE_URL}/strategies/{strategy_id}", timeout=10)
                print(f"   Status: {r.status_code}")
                if r.status_code == 200:
                    print(f"   Strategy name: {r.json().get('name')}")

                # 4. PUT update the strategy
                print(f"\n4. PUT /strategies/{strategy_id}")
                update_data = {"name": "Updated Test Strategy", "description": "Updated via API"}
                r = requests.put(f"{BASE_URL}/strategies/{strategy_id}", json=update_data, timeout=10)
                print(f"   Status: {r.status_code}")
                print(f"   Allow header: {r.headers.get('allow', 'N/A')}")
                if r.status_code in (200, 201):
                    print(f"   Updated: {r.json().get('name')}")
                else:
                    print(f"   Response: {r.text[:300]}")

                # 5. POST validate
                print(f"\n5. POST /validate/{strategy_id}")
                r = requests.post(f"{BASE_URL}/validate/{strategy_id}", timeout=10)
                print(f"   Status: {r.status_code}")
                if r.status_code == 200:
                    print(f"   Valid: {r.json().get('valid')}")

                # 6. POST generate code
                print(f"\n6. POST /strategies/{strategy_id}/generate-code")
                r = requests.post(f"{BASE_URL}/strategies/{strategy_id}/generate-code", timeout=10)
                print(f"   Status: {r.status_code}")
                if r.status_code == 200:
                    data = r.json()
                    code_len = len(data.get("code", ""))
                    print(f"   Generated code length: {code_len} chars")
                else:
                    print(f"   Response: {r.text[:300]}")

                # 7. POST backtest
                print(f"\n7. POST /strategies/{strategy_id}/backtest")
                backtest_params = {
                    "start_date": "2025-01-01",
                    "end_date": "2025-01-15",
                    "initial_capital": 10000,
                    "leverage": 10,
                }
                r = requests.post(f"{BASE_URL}/strategies/{strategy_id}/backtest", json=backtest_params, timeout=30)
                print(f"   Status: {r.status_code}")
                if r.status_code == 200:
                    data = r.json()
                    print(f"   Trades: {data.get('total_trades', 'N/A')}")
                    print(f"   Net PnL: {data.get('net_pnl', 'N/A')}")
                else:
                    print(f"   Response: {r.text[:300]}")

                # 8. DELETE the strategy
                print(f"\n8. DELETE /strategies/{strategy_id}")
                r = requests.delete(f"{BASE_URL}/strategies/{strategy_id}", timeout=10)
                print(f"   Status: {r.status_code}")
        else:
            print(f"   Response: {r.text[:300]}")
    except Exception as e:
        print(f"   Error: {e}")

    print("\n" + "=" * 60)
    print("Test complete")
    print("=" * 60)


if __name__ == "__main__":
    test_all_endpoints()
