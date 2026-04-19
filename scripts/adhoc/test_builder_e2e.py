"""E2E test: AI Agent builds strategy through Strategy Builder API."""

import sys

import requests

BASE = "http://localhost:8000"


def main():
    """Run E2E test for builder workflow."""
    print("=" * 60)
    print("E2E Test: AI Builder → Strategy Builder API")
    print("=" * 60)

    # 1. Health check
    print("\n[1/4] Health check...")
    r = requests.get(f"{BASE}/api/v1/health", timeout=5)
    assert r.status_code == 200, f"Health check failed: {r.status_code}"
    print("  ✅ Server healthy")

    # 2. Block library
    print("\n[2/4] Getting block library...")
    r = requests.get(f"{BASE}/api/v1/agents/advanced/builder/block-library", timeout=10)
    print(f"  Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"  ✅ Block library: {len(data.get('categories', data.get('blocks', [])))} items")
    else:
        print(f"  ⚠️ Block library: {r.text[:200]}")

    # 3. Run builder task with RSI strategy
    print("\n[3/4] Running AI builder task (RSI strategy)...")
    payload = {
        "name": "E2E Test RSI Agent",
        "symbol": "BTCUSDT",
        "timeframe": "15",
        "direction": "both",
        "start_date": "2025-01-01",
        "end_date": "2025-02-01",
        "initial_capital": 10000,
        "leverage": 10,
        "max_iterations": 2,
        "min_sharpe": 0.3,
        "min_win_rate": 0.3,
        "enable_deliberation": False,
        "blocks": [
            {"type": "rsi", "params": {"period": 14, "overbought": 70, "oversold": 30}},
            {"type": "buy"},
            {"type": "sell"},
        ],
        "connections": [],
    }

    r = requests.post(
        f"{BASE}/api/v1/agents/advanced/builder/task",
        json=payload,
        timeout=120,
    )
    print(f"  Status: {r.status_code}")

    if r.status_code != 200:
        print(f"  ❌ Failed: {r.text[:500]}")
        return False

    data = r.json()
    w = data.get("workflow", {})

    print(f"  Success: {data.get('success')}")
    print(f"  Strategy ID: {w.get('strategy_id', '—')}")
    print(f"  Status: {w.get('status', '—')}")
    print(f"  Duration: {w.get('duration_seconds', 0):.1f}s")
    print(f"  Blocks added: {len(w.get('blocks_added', []))}")
    print(f"  Connections: {len(w.get('connections_made', []))}")

    iterations = w.get("iterations", [])
    print(f"  Iterations: {len(iterations)}")
    for it in iterations:
        print(
            f"    Iter {it.get('iteration')}: "
            f"Sharpe={it.get('sharpe_ratio', 0):.3f}, "
            f"WinRate={it.get('win_rate', 0):.1%}, "
            f"Trades={it.get('total_trades', 0)}, "
            f"Profit=${it.get('net_profit', 0):.2f}, "
            f"Acceptable={it.get('acceptable')}"
        )

    errors = w.get("errors", [])
    if errors:
        print(f"  ⚠️ Errors ({len(errors)}):")
        for e in errors:
            print(f"    - {e}")

    if w.get("deliberation"):
        delib = w["deliberation"]
        print(f"  Deliberation: confidence={delib.get('confidence', 0):.2f}")

    # 4. Verify strategy exists
    sid = w.get("strategy_id")
    if sid:
        print(f"\n[4/4] Verifying strategy {sid} exists...")
        r = requests.get(
            f"{BASE}/api/v1/strategy-builder/strategies/{sid}",
            timeout=10,
        )
        if r.status_code == 200:
            s = r.json()
            print(f"  ✅ Strategy found: {s.get('name', '—')}")
            blocks = s.get("blocks", s.get("builder_graph", {}).get("blocks", []))
            print(f"  Blocks in strategy: {len(blocks)}")
        else:
            print(f"  ⚠️ Strategy not found: {r.status_code}")
    else:
        print("\n[4/4] Skipping — no strategy ID returned")

    # Summary
    print("\n" + "=" * 60)
    ok = data.get("success") or w.get("status") == "completed"
    has_iterations = len(iterations) > 0
    has_trades = any(it.get("total_trades", 0) > 0 for it in iterations)
    has_strategy = bool(sid)

    results = [
        ("Workflow completed", ok),
        ("Has iterations", has_iterations),
        ("Has trades", has_trades),
        ("Strategy created", has_strategy),
    ]

    passed = 0
    for name, result in results:
        status = "✅" if result else "❌"
        print(f"  {status} {name}")
        if result:
            passed += 1

    print(f"\nResult: {passed}/{len(results)} checks passed")
    return passed == len(results)


if __name__ == "__main__":
    try:
        ok = main()
        sys.exit(0 if ok else 1)
    except Exception as e:
        print(f"\n❌ E2E test error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
