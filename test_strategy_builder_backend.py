#!/usr/bin/env python3
"""
Test Strategy Builder Backend Integration
Tests the mapping from Strategy Builder blocks to backend API
"""

import json
from datetime import datetime

import requests

BASE_URL = "http://localhost:8000"


def test_create_strategy():
    """Test creating a strategy via API"""
    print("\n" + "=" * 60)
    print("1. Testing Strategy Creation")
    print("=" * 60)

    strategy_data = {
        "name": f"Test Strategy {datetime.now().strftime('%H:%M:%S')}",
        "description": "Test strategy from Strategy Builder",
        "direction": "both",
        "market_type": "linear",
        "blocks": [
            {
                "id": "block_1",
                "type": "rsi",
                "name": "RSI Indicator",
                "params": {"period": 14, "overbought": 70, "oversold": 30, "source": "close"},
                "position": {"x": 100, "y": 100},
            },
            {
                "id": "block_2",
                "type": "rsi_filter",
                "name": "RSI Filter",
                "params": {
                    "use_rsi": True,
                    "rsi_period": 14,
                    "rsi_timeframe": "Chart",
                    "long_rsi_more": 0,
                    "long_rsi_less": 30,
                    "short_rsi_more": 70,
                    "short_rsi_less": 100,
                },
                "position": {"x": 300, "y": 100},
            },
        ],
        "connections": [{"from_block": "block_1", "from_port": "output", "to_block": "block_2", "to_port": "input"}],
    }

    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/strategy-builder/strategies",
            json=strategy_data,
            headers={"Content-Type": "application/json"},
        )

        print(f"Status: {response.status_code}")

        if response.ok:
            data = response.json()
            print(f"✅ Strategy created: ID={data.get('id')}")
            print(f"   Name: {data.get('name')}")
            return data.get("id")
        else:
            print(f"❌ Error: {response.text}")
            return None

    except Exception as e:
        print(f"❌ Connection error: {e}")
        return None


def test_run_backtest(strategy_id: str):
    """Test running a backtest for a strategy"""
    print("\n" + "=" * 60)
    print("2. Testing Backtest Execution")
    print("=" * 60)

    if not strategy_id:
        print("⚠️ No strategy ID, skipping backtest test")
        return None

    backtest_params = {
        "symbol": "BTCUSDT",
        "interval": "15m",
        "start_date": "2024-01-01",
        "end_date": "2024-01-31",
        "initial_capital": 10000,
        "leverage": 10,
        "direction": "both",
        "commission": 0.0007,
        "slippage": 0.0005,
        "strategy_type": "rsi",
        "strategy_params": {"period": 14, "overbought": 70, "oversold": 30},
        "filters": [
            {
                "type": "rsi_filter",
                "enabled": True,
                "params": {
                    "use_rsi": True,
                    "rsi_period": 14,
                    "long_rsi_more": 0,
                    "long_rsi_less": 30,
                    "short_rsi_more": 70,
                    "short_rsi_less": 100,
                },
            }
        ],
    }

    try:
        url = f"{BASE_URL}/api/v1/strategy-builder/strategies/{strategy_id}/backtest"
        print(f"POST {url}")
        print(f"Params: {json.dumps(backtest_params, indent=2)[:500]}...")

        response = requests.post(url, json=backtest_params, headers={"Content-Type": "application/json"}, timeout=120)

        print(f"Status: {response.status_code}")

        if response.ok:
            data = response.json()
            print("✅ Backtest completed!")

            if "backtest_id" in data:
                print(f"   Backtest ID: {data['backtest_id']}")
            if "metrics" in data:
                metrics = data["metrics"]
                print(f"   Total Return: {metrics.get('total_return', 'N/A')}%")
                print(f"   Win Rate: {metrics.get('win_rate', 'N/A')}%")
                print(f"   Sharpe Ratio: {metrics.get('sharpe_ratio', 'N/A')}")
                print(f"   Max Drawdown: {metrics.get('max_drawdown', 'N/A')}%")
                print(f"   Total Trades: {metrics.get('total_trades', 'N/A')}")
            return data
        else:
            print(f"❌ Error: {response.text[:500]}")
            return None

    except requests.Timeout:
        print("❌ Timeout - backtest taking too long")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def test_direct_backtest():
    """Test direct backtest API (without strategy builder)"""
    print("\n" + "=" * 60)
    print("3. Testing Direct Backtest API")
    print("=" * 60)

    backtest_data = {
        "symbol": "BTCUSDT",
        "interval": "15m",
        "start_date": "2024-01-01",
        "end_date": "2024-01-15",
        "initial_capital": 10000,
        "leverage": 10,
        "direction": "both",
        "stop_loss": 0.02,
        "take_profit": 0.03,
        "strategy_type": "rsi",
        "strategy_params": {"period": 14, "overbought": 70, "oversold": 30},
    }

    try:
        url = f"{BASE_URL}/api/v1/backtests/"
        print(f"POST {url}")

        response = requests.post(url, json=backtest_data, headers={"Content-Type": "application/json"}, timeout=60)

        print(f"Status: {response.status_code}")

        if response.ok:
            data = response.json()
            print("✅ Direct backtest completed!")

            metrics = data.get("metrics", {})
            print(f"   Total Return: {metrics.get('total_return', data.get('total_return', 'N/A'))}%")
            print(f"   Win Rate: {metrics.get('win_rate', data.get('win_rate', 'N/A'))}%")
            print(f"   Total Trades: {metrics.get('total_trades', data.get('total_trades', 'N/A'))}")
            print(f"   Max Drawdown: {metrics.get('max_drawdown', data.get('max_drawdown', 'N/A'))}%")
            return data
        else:
            print(f"❌ Error: {response.text[:500]}")
            return None

    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def test_list_strategies():
    """Test listing strategies"""
    print("\n" + "=" * 60)
    print("4. Testing List Strategies")
    print("=" * 60)

    try:
        response = requests.get(f"{BASE_URL}/api/v1/strategy-builder/strategies")
        print(f"Status: {response.status_code}")

        if response.ok:
            data = response.json()
            strategies = data if isinstance(data, list) else data.get("items", [])
            print(f"✅ Found {len(strategies)} strategies")

            for s in strategies[:5]:
                print(f"   - {s.get('name')} (ID: {s.get('id')})")
            return strategies
        else:
            print(f"❌ Error: {response.text}")
            return []

    except Exception as e:
        print(f"❌ Error: {e}")
        return []


def main():
    print("\n" + "=" * 60)
    print("🧪 STRATEGY BUILDER BACKEND INTEGRATION TEST")
    print("=" * 60)
    print(f"Target: {BASE_URL}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        if response.ok:
            print("✅ Server is running")
        else:
            print(f"⚠️ Server responded with: {response.status_code}")
    except:
        print("❌ Server is not running! Start with: uvicorn backend.api.app:app --reload")
        return

    # Run tests
    test_list_strategies()
    test_direct_backtest()
    strategy_id = test_create_strategy()
    test_run_backtest(strategy_id)

    print("\n" + "=" * 60)
    print("✅ TESTS COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    main()
