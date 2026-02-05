"""
Test DCA parameters through API
"""

import requests

API_BASE = "http://localhost:8000/api/v1"

def test_list_strategies():
    """List all strategies"""
    print("=" * 50)
    print("1. LIST STRATEGIES")
    print("=" * 50)
    r = requests.get(f"{API_BASE}/strategies")
    if r.status_code == 200:
        data = r.json()
        # Handle both dict with 'items'/'strategies' key and direct list
        if isinstance(data, dict):
            # API returns dict - extract strategies list
            strategies = data.get('items', data.get('strategies', list(data.values())))
            if not isinstance(strategies, list):
                # If still not a list, try to get values
                strategies = list(data.values()) if data else []
                # Filter to only dicts (strategy objects)
                strategies = [s for s in strategies if isinstance(s, dict) and 'name' in s]
            print(f"Found {data.get('total', len(strategies))} strategies:")
        else:
            strategies = data
            print(f"Found {len(strategies)} strategies:")

        # Safely iterate
        for s in strategies[:10]:
            if isinstance(s, dict):
                stype = s.get('strategy_type', 'unknown')
                print(f"  - {s.get('name', 'unnamed')} ({stype})")
        return strategies
    else:
        print(f"ERROR: {r.status_code}")
        return []

def test_find_dca_strategy(strategies):
    """Find DCA strategy and check its parameters"""
    print("\n" + "=" * 50)
    print("2. FIND DCA STRATEGY")
    print("=" * 50)

    dca_strategies = [s for s in strategies if s.get('strategy_type') == 'dca']
    if not dca_strategies:
        print("No DCA strategies found!")
        return None

    print(f"Found {len(dca_strategies)} DCA strategies")
    return dca_strategies[0]

def test_get_strategy_details(strategy_id):
    """Get full strategy details"""
    print("\n" + "=" * 50)
    print("3. GET STRATEGY DETAILS")
    print("=" * 50)

    r = requests.get(f"{API_BASE}/strategies/{strategy_id}")
    if r.status_code == 200:
        data = r.json()
        print(f"Strategy: {data['name']}")
        print(f"Type: {data['strategy_type']}")
        print(f"Symbol: {data['symbol']}")
        print(f"Timeframe: {data['timeframe']}")

        params = data.get('parameters', {})
        print("\nDCA Parameters:")
        dca_params = {k: v for k, v in params.items() if k.startswith('_dca_')}
        for k, v in dca_params.items():
            print(f"  {k}: {v}")

        return data
    else:
        print(f"ERROR: {r.status_code} - {r.text}")
        return None

def test_create_dca_strategy():
    """Create a new DCA strategy with all parameters"""
    print("\n" + "=" * 50)
    print("4. CREATE NEW DCA STRATEGY")
    print("=" * 50)

    strategy_data = {
        "name": "API Test DCA",
        "strategy_type": "dca",
        "symbol": "BTCUSDT",
        "timeframe": "15",
        "status": "draft",
        "initial_capital": 10000,
        "position_size": 1.0,
        "parameters": {
            "_direction": "long",
            "_leverage": 5,
            "_pyramiding": 8,
            "_dca_coverage": 15.5,
            "_dca_grid_orders": 8,
            "_dca_martingale": 25.5,
            "_dca_offset_type": "limit",
            "_dca_offset": 0.5,
            "_dca_logarithmic": True,
            "_dca_log_coefficient": 1.4,
            "_dca_partial_grid": 4,
            "_dca_trailing": 7.5
        }
    }

    r = requests.post(f"{API_BASE}/strategies", json=strategy_data)
    if r.status_code in [200, 201]:
        data = r.json()
        print(f"✅ Created strategy: {data['id']}")
        print(f"   Name: {data['name']}")
        return data
    else:
        print(f"❌ ERROR: {r.status_code}")
        print(f"   {r.text[:500]}")
        return None

def test_verify_dca_params(strategy_id):
    """Verify DCA parameters were saved correctly"""
    print("\n" + "=" * 50)
    print("5. VERIFY DCA PARAMETERS")
    print("=" * 50)

    r = requests.get(f"{API_BASE}/strategies/{strategy_id}")
    if r.status_code != 200:
        print(f"ERROR: {r.status_code}")
        return False

    data = r.json()
    params = data.get('parameters', {})

    expected = {
        "_dca_coverage": 15.5,
        "_dca_grid_orders": 8,
        "_dca_martingale": 25.5,
        "_dca_offset_type": "limit",
        "_dca_offset": 0.5,
        "_dca_logarithmic": True,
        "_dca_log_coefficient": 1.4,
        "_dca_partial_grid": 4,
        "_dca_trailing": 7.5
    }

    all_match = True
    for key, expected_value in expected.items():
        actual = params.get(key)
        match = actual == expected_value
        status = "✅" if match else "❌"
        print(f"  {status} {key}: expected={expected_value}, actual={actual}")
        if not match:
            all_match = False

    return all_match

def main():
    print("\n🔍 DCA API VERIFICATION TEST")
    print("=" * 50)

    # 1. List strategies
    strategies = test_list_strategies()

    # 2. Find existing DCA
    dca = test_find_dca_strategy(strategies)
    if dca:
        test_get_strategy_details(dca['id'])

    # 3. Create new DCA
    new_dca = test_create_dca_strategy()

    # 4. Verify parameters
    if new_dca:
        success = test_verify_dca_params(new_dca['id'])
        print("\n" + "=" * 50)
        if success:
            print("✅ ALL DCA PARAMETERS VERIFIED SUCCESSFULLY!")
        else:
            print("❌ SOME PARAMETERS DID NOT MATCH")
        print("=" * 50)

if __name__ == "__main__":
    main()
