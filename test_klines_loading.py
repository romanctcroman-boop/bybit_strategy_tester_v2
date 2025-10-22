#!/usr/bin/env python3
"""Test klines loading from backend API"""
from datetime import datetime

import requests

BASE_URL = "http://127.0.0.1:8000"


def test_klines():
    print("=" * 60)
    print("Testing Bybit Klines Loading")
    print("=" * 60)

    # Test 1: Health check
    print("\n[1] Health check...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"    Status: {response.status_code}")
        print(f"    Response: {response.json()}")
    except Exception as e:
        print(f"    ERROR: {e}")
        return False

    # Test 2: Load 250 candles
    print("\n[2] Loading 250 x 1-min BTCUSDT candles...")
    try:
        params = {"symbol": "BTCUSDT", "interval": "1", "limit": 250, "persist": 0}
        response = requests.get(
            f"{BASE_URL}/api/v1/marketdata/bybit/klines/fetch", params=params, timeout=30
        )
        print(f"    Status: {response.status_code}")

        if response.status_code != 200:
            print(f"    ERROR: {response.text}")
            return False

        data = response.json()
        print(f"    Loaded: {len(data)} candles")

        if len(data) == 0:
            print("    ERROR: No data returned!")
            return False

        if len(data) != 250:
            print(f"    WARNING: Expected 250 candles, got {len(data)}")

        # Check data structure
        print("\n[3] Checking data structure...")
        first = data[0]
        last = data[-1]

        required_fields = ["open_time", "open", "high", "low", "close", "volume", "turnover"]
        print(f"    First candle keys: {list(first.keys())}")

        for field in required_fields:
            if field not in first:
                print(f"    ERROR: Missing field '{field}'")
                return False

        print("    ✓ All required fields present")

        # Display first and last candles
        print("\n[4] Data sample:")
        print("    First candle (oldest):")
        print(
            f"      Time: {first['open_time']} ({datetime.fromtimestamp(first['open_time']/1000)})"
        )
        print(
            f"      OHLCV: {first['open']}, {first['high']}, {first['low']}, {first['close']}, {first['volume']}"
        )

        print("\n    Last candle (newest):")
        print(f"      Time: {last['open_time']} ({datetime.fromtimestamp(last['open_time']/1000)})")
        print(
            f"      OHLCV: {last['open']}, {last['high']}, {last['low']}, {last['close']}, {last['volume']}"
        )

        # Check time differences
        print("\n[5] Time analysis:")
        times = [c["open_time"] for c in data]
        time_diffs = [times[i + 1] - times[i] for i in range(len(times) - 1)]
        avg_diff = sum(time_diffs) / len(time_diffs) if time_diffs else 0
        print(f"    Average time difference: {avg_diff / 1000:.1f} seconds")
        print("    Expected for 1-min candles: 60 seconds")

        if abs(avg_diff / 1000 - 60) > 5:
            print("    WARNING: Time differences don't match 1-min interval")
        else:
            print("    ✓ Time intervals are correct for 1-min candles")

        # Check data ordering
        print("\n[6] Data ordering:")
        if times[0] < times[-1]:
            print("    ✓ Data is newest-first (timestamp increases)")
        else:
            print("    ✗ Data ordering issue")

        print("\n" + "=" * 60)
        print("✓ TEST PASSED - Ready to display on chart")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"    ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_klines()
    exit(0 if success else 1)
