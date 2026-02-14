"""E2E test for AI Build button — tests the full workflow via API."""

import json
import sys

import requests

BASE = "http://localhost:8000"


def test_health():
    """Step 0: Check server is up."""
    r = requests.get(f"{BASE}/api/v1/health", timeout=5)
    assert r.status_code == 200, f"Health check failed: {r.status_code}"
    print("✅ Server is healthy")


def test_ai_build_ema_cross():
    """Step 1: POST /api/v1/agents/advanced/builder/task with EMA Cross config."""
    payload = {
        "name": "AI Test EMA Cross",
        "symbol": "BTCUSDT",
        "timeframe": "15",
        "direction": "both",
        "initial_capital": 10000,
        "leverage": 10,
        "start_date": "2025-01-01",
        "end_date": "2025-02-01",
        "blocks": [
            {
                "type": "ema",
                "id": "ema_fast",
                "name": "EMA Fast",
                "params": {"period": 9, "source": "close"},
            },
            {
                "type": "ema",
                "id": "ema_slow",
                "name": "EMA Slow",
                "params": {"period": 21, "source": "close"},
            },
            {
                "type": "crossover",
                "id": "cross_up",
                "name": "EMA Cross Up",
                "params": {},
            },
            {
                "type": "crossunder",
                "id": "cross_down",
                "name": "EMA Cross Down",
                "params": {},
            },
            {
                "type": "buy",
                "id": "buy_signal",
                "name": "Buy Signal",
                "params": {},
            },
            {
                "type": "sell",
                "id": "sell_signal",
                "name": "Sell Signal",
                "params": {},
            },
        ],
        "connections": [
            {
                "source": "ema_fast",
                "source_port": "value",
                "target": "cross_up",
                "target_port": "a",
            },
            {
                "source": "ema_slow",
                "source_port": "value",
                "target": "cross_up",
                "target_port": "b",
            },
            {
                "source": "ema_fast",
                "source_port": "value",
                "target": "cross_down",
                "target_port": "a",
            },
            {
                "source": "ema_slow",
                "source_port": "value",
                "target": "cross_down",
                "target_port": "b",
            },
            {
                "source": "cross_up",
                "source_port": "result",
                "target": "buy_signal",
                "target_port": "signal",
            },
            {
                "source": "cross_down",
                "source_port": "result",
                "target": "sell_signal",
                "target_port": "signal",
            },
        ],
        "stop_loss": None,
        "take_profit": None,
        "max_iterations": 1,
        "min_sharpe": 0.0,
        "min_win_rate": 0.0,
        "enable_deliberation": False,
    }

    print("\n🔄 Sending POST /api/v1/agents/advanced/builder/task ...")
    print(f"   Payload: {json.dumps(payload, indent=2)[:500]}...")
    r = requests.post(
        f"{BASE}/api/v1/agents/advanced/builder/task",
        json=payload,
        timeout=120,
    )
    print(f"   Status: {r.status_code}")

    if r.status_code != 200:
        print(f"❌ Request failed: {r.status_code}")
        print(f"   Response: {r.text[:2000]}")
        return None

    data = r.json()
    success = data.get("success", False)
    workflow = data.get("workflow", {})

    print(f"\n📊 Result: success={success}")
    print(f"   Status: {workflow.get('status')}")
    print(f"   Strategy ID: {workflow.get('strategy_id')}")
    print(f"   Backtest ID: {workflow.get('backtest_id')}")
    print(f"   Stages: {len(workflow.get('stages', []))}")

    # Print stage details
    for stage in workflow.get("stages", []):
        emoji = "✅" if stage.get("success") else "❌"
        print(f"   {emoji} Stage {stage.get('stage')}: {stage.get('name')} - {stage.get('message', '')[:100]}")

    # Check results
    results = workflow.get("backtest_results", {})
    if results:
        # Backtest endpoint returns metrics under "results" key
        metrics = results.get("results", results.get("metrics", {}))
        print(f"\n📈 Backtest Results:")
        print(f"   Total Trades: {metrics.get('total_trades', 'N/A')}")
        print(f"   Net Profit: {metrics.get('net_profit', 'N/A')}")
        print(f"   Win Rate: {metrics.get('win_rate', 'N/A')}")
        print(f"   Sharpe Ratio: {metrics.get('sharpe_ratio', 'N/A')}")
        print(f"   Max Drawdown: {metrics.get('max_drawdown', 'N/A')}")

    # Check errors
    errors = workflow.get("errors", [])
    if errors:
        print(f"\n⚠️  Errors ({len(errors)}):")
        for err in errors[:5]:
            print(f"   - {err}")

    return data


def verify_strategy(strategy_id: str):
    """Step 2: Verify the strategy was created correctly in the DB."""
    print(f"\n🔍 Verifying strategy {strategy_id}...")
    r = requests.get(
        f"{BASE}/api/v1/strategy-builder/strategies/{strategy_id}",
        timeout=10,
    )
    if r.status_code != 200:
        print(f"❌ Strategy not found: {r.status_code}")
        return

    strat = r.json()
    blocks = strat.get("blocks", [])
    connections = strat.get("connections", [])
    print(f"   Name: {strat.get('name')}")
    print(f"   Blocks: {len(blocks)}")
    print(f"   Connections: {len(connections)}")

    # Check each block has category
    missing_cat = []
    for b in blocks:
        cat = b.get("category", "")
        btype = b.get("type", "unknown")
        bid = b.get("id", "")
        is_main = b.get("isMain", False)
        print(f"   - Block '{bid}' type='{btype}' category='{cat}' isMain={is_main}")
        if not cat:
            missing_cat.append(bid)

    if missing_cat:
        print(f"   ⚠️  Blocks WITHOUT category: {missing_cat}")
    else:
        print(f"   ✅ All blocks have category field")

    # Check connections
    print(f"\n   Connections:")
    for c in connections:
        src = c.get("source", {})
        tgt = c.get("target", {})
        if isinstance(src, dict):
            print(f"   - {src.get('blockId')}:{src.get('portId')} → {tgt.get('blockId')}:{tgt.get('portId')}")
        else:
            print(f"   - {c}")

    # Check for main_strategy node
    main_nodes = [b for b in blocks if b.get("isMain") or b.get("type") == "strategy"]
    if main_nodes:
        print(f"   ✅ Main strategy node found: {main_nodes[0].get('id')}")
    else:
        print(f"   ❌ No main strategy node found!")

    return strat


def cleanup_strategy(strategy_id: str):
    """Step 3: Cleanup test strategy."""
    print(f"\n🧹 Cleaning up strategy {strategy_id}...")
    r = requests.delete(
        f"{BASE}/api/v1/strategy-builder/strategies/{strategy_id}",
        timeout=10,
    )
    if r.status_code == 200:
        print("   ✅ Strategy deleted")
    else:
        print(f"   ⚠️ Delete returned {r.status_code}: {r.text[:200]}")


if __name__ == "__main__":
    print("=" * 60)
    print("🤖 AI Build E2E Test")
    print("=" * 60)

    try:
        test_health()
    except Exception as e:
        print(f"❌ Server not available: {e}")
        sys.exit(1)

    result = test_ai_build_ema_cross()
    if result is None:
        print("\n❌ TEST FAILED - API request failed")
        sys.exit(1)

    workflow = result.get("workflow", {})
    strategy_id = workflow.get("strategy_id")

    if strategy_id:
        verify_strategy(strategy_id)

    success = result.get("success", False)
    # Backtest results are in workflow.backtest_results.results
    bt_results = workflow.get("backtest_results", {})
    bt_metrics = bt_results.get("results", bt_results.get("metrics", {}))
    total_trades = bt_metrics.get("total_trades", 0)

    print("\n" + "=" * 60)
    if success and total_trades and total_trades > 0:
        print(f"🎉 TEST PASSED! Strategy created, {total_trades} trades generated")
    elif success:
        print(f"⚠️  TEST PARTIAL - Strategy created but total_trades={total_trades}")
    else:
        print(f"❌ TEST FAILED - success={success}, trades={total_trades}")

    # Don't cleanup on failure so we can inspect
    if strategy_id and success:
        cleanup_strategy(strategy_id)

    sys.exit(0 if success else 1)
