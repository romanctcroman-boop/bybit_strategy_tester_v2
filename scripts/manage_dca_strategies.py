"""
Manage DCA Strategies - Delete old ones, create Long and Short
"""

import builtins
import contextlib

import requests

API_BASE = "http://localhost:8000/api/v1"

def delete_all_dca_strategies():
    """Delete all existing DCA strategies"""
    print("=" * 50)
    print("🗑️  DELETING DCA STRATEGIES")
    print("=" * 50)

    # Get all strategies
    r = requests.get(f"{API_BASE}/strategies")
    if r.status_code != 200:
        print(f"❌ Failed to get strategies: {r.status_code}")
        return False

    data = r.json()

    # Extract strategies list from response
    if isinstance(data, dict):
        strategies = data.get('items', data.get('strategies', []))
        if not isinstance(strategies, list):
            strategies = [s for s in data.values() if isinstance(s, dict) and 'id' in s]
    else:
        strategies = data

    # Find and delete DCA strategies
    dca_strategies = [s for s in strategies if s.get('strategy_type') == 'dca']

    if not dca_strategies:
        print("✅ No DCA strategies found to delete")
        return True

    print(f"Found {len(dca_strategies)} DCA strategies to delete:")

    deleted_count = 0
    for s in dca_strategies:
        strategy_id = s.get('id')
        strategy_name = s.get('name', 'unnamed')
        print(f"  Deleting: {strategy_name} ({strategy_id})...")

        r = requests.delete(f"{API_BASE}/strategies/{strategy_id}")
        if r.status_code in [200, 204]:
            print("    ✅ Deleted")
            deleted_count += 1
        else:
            print(f"    ❌ Failed: {r.status_code}")

    print(f"\n✅ Deleted {deleted_count}/{len(dca_strategies)} DCA strategies")
    return True

def create_dca_strategy(name: str, direction: str):
    """Create a DCA strategy with specified direction"""
    print(f"\n📝 Creating DCA {direction.upper()} strategy: {name}")

    strategy_data = {
        "name": name,
        "strategy_type": "dca",
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "status": "draft",
        "initial_capital": 10000,
        "position_size": 1.0,
        "parameters": {
            # Direction and trading settings
            "_direction": direction,
            "_leverage": 10,
            "_pyramiding": 8,

            # DCA Grid parameters
            "_dca_coverage": 15.0,        # 15% coverage
            "_dca_grid_orders": 8,        # 8 orders in grid
            "_dca_martingale": 25.0,      # 25% martingale
            "_dca_offset_type": "market", # Market entry
            "_dca_offset": 0.0,
            "_dca_logarithmic": True,
            "_dca_log_coefficient": 1.3,
            "_dca_partial_grid": 5,
            "_dca_trailing": 5.0,

            # Stop Loss / Take Profit
            "_stop_loss": 20.0,
            "_take_profit": 10.0,

            # Engine settings
            "_engine_type": "fallback",
            "_market_type": "linear"
        }
    }

    r = requests.post(f"{API_BASE}/strategies", json=strategy_data)

    if r.status_code in [200, 201]:
        data = r.json()
        print(f"  ✅ Created: {data.get('id')}")
        return data
    else:
        print(f"  ❌ Failed: {r.status_code}")
        with contextlib.suppress(builtins.BaseException):
            print(f"     Error: {r.text[:300]}")
        return None

def verify_strategies():
    """List all strategies to verify"""
    print("\n" + "=" * 50)
    print("📋 VERIFYING STRATEGIES")
    print("=" * 50)

    r = requests.get(f"{API_BASE}/strategies")
    if r.status_code != 200:
        print(f"❌ Failed to get strategies: {r.status_code}")
        return

    data = r.json()

    # Extract strategies
    if isinstance(data, dict):
        strategies = data.get('items', data.get('strategies', []))
        if not isinstance(strategies, list):
            strategies = [s for s in data.values() if isinstance(s, dict) and 'id' in s]
    else:
        strategies = data

    print(f"Total strategies: {len(strategies)}")

    for s in strategies:
        stype = s.get('strategy_type', 'unknown')
        direction = s.get('parameters', {}).get('_direction', 'both')
        symbol = s.get('symbol', '?')
        print(f"  • {s.get('name')} | {stype} | {direction} | {symbol}")

def main():
    print("\n🔧 DCA STRATEGY MANAGER")
    print("=" * 50)

    # 1. Delete existing DCA strategies
    delete_all_dca_strategies()

    # 2. Create DCA Long strategy
    dca_long = create_dca_strategy("DCA Long BTCUSDT", "long")

    # 3. Create DCA Short strategy
    dca_short = create_dca_strategy("DCA Short BTCUSDT", "short")

    # 4. Verify
    verify_strategies()

    # Summary
    print("\n" + "=" * 50)
    print("📊 SUMMARY")
    print("=" * 50)

    if dca_long and dca_short:
        print("✅ Successfully created DCA Long and DCA Short strategies!")
        print(f"   Long ID:  {dca_long.get('id')}")
        print(f"   Short ID: {dca_short.get('id')}")
    else:
        print("⚠️  Some strategies failed to create")

    print("\nYou can now run backtests from the frontend!")

if __name__ == "__main__":
    main()
