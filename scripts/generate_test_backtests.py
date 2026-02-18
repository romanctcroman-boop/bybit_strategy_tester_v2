"""
Generate test backtests for Long-only and Short-only directions.
Used to verify chart rendering for different trading directions.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

API_BASE = "http://localhost:8000/api/v1"


def list_strategies():
    """List available strategies."""
    r = requests.get(f"{API_BASE}/strategy-builder/strategies")
    r.raise_for_status()
    strategies = r.json()["strategies"]
    print(f"Total strategies: {len(strategies)}")

    non_dca = [s for s in strategies if "DCA" not in s["name"]]
    print(f"Non-DCA strategies: {len(non_dca)}")
    for s in non_dca[:10]:
        print(f"  {s['id'][:12]}... {s['name']} ({s['block_count']} blocks)")

    return strategies


def find_or_create_strategy():
    """Find existing strategy or create a simple RSI strategy for testing."""
    strategies = list_strategies()

    # Try the strategy from the existing backtest
    target_id = "3340aa1d-a94b-436e-8082-8b4dcb2ddc88"
    found = [s for s in strategies if s["id"] == target_id]
    if found:
        print(f"\nUsing existing strategy: {found[0]['name']} ({target_id})")
        return target_id

    # Try any non-DCA strategy
    non_dca = [s for s in strategies if "DCA" not in s["name"]]
    if non_dca:
        sid = non_dca[0]["id"]
        print(f"\nUsing strategy: {non_dca[0]['name']} ({sid})")
        return sid

    # Use first DCA strategy if nothing else
    if strategies:
        sid = strategies[0]["id"]
        print(f"\nUsing DCA strategy: {strategies[0]['name']} ({sid})")
        return sid

    print("No strategies found! Please create one in the UI first.")
    return None


def run_backtest(
    strategy_id: str,
    direction: str,
    symbol: str = "BTCUSDT",
    interval: str = "60",
    start_date: str = "2025-06-01T00:00:00Z",
    end_date: str = "2025-08-01T00:00:00Z",
):
    """Run a backtest with specific direction."""

    payload = {
        "symbol": symbol,
        "interval": interval,
        "initial_capital": 10000.0,
        "start_date": start_date,
        "end_date": end_date,
        "direction": direction,  # "long", "short", or "both"
        "commission": 0.0007,
        "leverage": 10,
        "slippage": 0.0005,
        "pyramiding": 1,
        "market_type": "linear",
    }

    print(f"\n{'=' * 60}")
    print(f"Running {direction.upper()}-only backtest")
    print(f"  Symbol:   {symbol}")
    print(f"  Interval: {interval}")
    print(f"  Period:   {start_date[:10]} → {end_date[:10]}")
    print(f"  Strategy: {strategy_id[:12]}...")
    print(f"{'=' * 60}")

    url = f"{API_BASE}/strategy-builder/strategies/{strategy_id}/backtest"
    r = requests.post(url, json=payload, timeout=120)

    if r.status_code != 200:
        print(f"  ERROR {r.status_code}: {r.text[:500]}")
        return None

    result = r.json()
    backtest_id = result.get("id") or result.get("backtest_id")
    trade_count = len(result.get("trades", []))
    net_profit = result.get("metrics", {}).get("net_profit", 0)

    print("  ✅ Backtest completed!")
    print(f"  ID:     {backtest_id}")
    print(f"  Trades: {trade_count}")
    print(f"  P&L:    ${net_profit:.2f}")

    return result


def main():
    print("=" * 60)
    print("Generate Test Backtests (Long-only & Short-only)")
    print("=" * 60)

    strategy_id = find_or_create_strategy()
    if not strategy_id:
        sys.exit(1)

    # Parameters for both backtests — use period where kline data exists in DB
    params = {
        "symbol": "BTCUSDT",
        "interval": "15",  # 15m has most data in DB
        "start_date": "2025-01-10T00:00:00Z",
        "end_date": "2025-02-10T00:00:00Z",
    }

    # Run LONG-only backtest
    long_result = run_backtest(strategy_id, direction="long", **params)

    # Run SHORT-only backtest
    short_result = run_backtest(strategy_id, direction="short", **params)

    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    if long_result:
        lt = len(long_result.get("trades", []))
        lp = long_result.get("metrics", {}).get("net_profit", 0)
        lid = long_result.get("id") or long_result.get("backtest_id", "?")
        print(f"  LONG:  {lt} trades, P&L=${lp:.2f}, ID={lid}")
    if short_result:
        st = len(short_result.get("trades", []))
        sp = short_result.get("metrics", {}).get("net_profit", 0)
        sid = short_result.get("id") or short_result.get("backtest_id", "?")
        print(f"  SHORT: {st} trades, P&L=${sp:.2f}, ID={sid}")

    print("\nOpen http://localhost:8000/frontend/backtest-results.html to view")


if __name__ == "__main__":
    main()
