"""
End-to-end smoke test for Strategy Builder on real DB and historical data.

Usage:
    py -3.14 scripts/strategy_builder_real_e2e_test.py

This script:
- Spins up a TestClient over the real FastAPI app (with real DB config)
- Creates a simple RSI-based strategy via Strategy Builder API
- Runs a backtest via /api/v1/strategy-builder/strategies/{id}/backtest
- Prints key fields from the backtest response

Note:
- Requires network access (for Bybit historical data) OR a pre-populated local DB
- Does NOT use pytest or in-memory SQLite overrides.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from backend.api.app import app


def run_single(direction: str) -> None:
    """Run a single E2E backtest for given direction ('long' or 'short')."""
    client = TestClient(app)

    # Simple RSI-based strategy graph (similar to test fixture)
    strategy_payload = {
        "name": f"Real E2E RSI Strategy ({direction})",
        "description": "E2E test on real DB + historical data",
        "timeframe": "15m",
        "symbol": "BTCUSDT",
        "market_type": "linear",
        "direction": direction,
        "initial_capital": 10_000.0,
        "blocks": [
            {
                "id": "block_rsi",
                "type": "rsi",
                "category": "indicator",
                "name": "RSI",
                "icon": "graph-up",
                "x": 100,
                "y": 200,
                "params": {"period": 14, "overbought": 70, "oversold": 30},
            },
            {
                "id": "block_const_30",
                "type": "constant",
                "category": "input",
                "name": "Constant",
                "icon": "hash",
                "x": 100,
                "y": 300,
                "params": {"value": 30},
            },
            {
                "id": "block_less_than",
                "type": "less_than",
                "category": "condition",
                "name": "Less Than",
                "icon": "chevron-double-down",
                "x": 350,
                "y": 250,
                "params": {},
            },
        ],
        "connections": [
            {
                "id": "conn_1",
                "source": {"blockId": "block_rsi", "portId": "value"},
                "target": {"blockId": "block_less_than", "portId": "a"},
                "type": "data",
            },
            {
                "id": "conn_2",
                "source": {"blockId": "block_const_30", "portId": "value"},
                "target": {"blockId": "block_less_than", "portId": "b"},
                "type": "data",
            },
        ],
    }

    print(f"=== [{direction.upper()}] Creating strategy via Strategy Builder API ===")
    create_resp = client.post(
        "/api/v1/strategy-builder/strategies",
        json=strategy_payload,
    )
    print("Create status:", create_resp.status_code)
    if create_resp.status_code != 200:
        print("Create error payload:", create_resp.json())
        return

    strategy = create_resp.json()
    strategy_id = strategy["id"]
    print("Created strategy_id:", strategy_id)

    # Backtest request: 6 months from 2025-01-01 on 15m
    backtest_payload = {
        "start_date": datetime(2025, 1, 1, tzinfo=UTC).isoformat(),
        "end_date": datetime(2025, 6, 30, 23, 59, 59, tzinfo=UTC).isoformat(),
        "engine": "auto",
        "commission": 0.0007,
        "slippage": 0.0005,
        "leverage": 10,
        "pyramiding": 1,
        "stop_loss": None,
        "take_profit": None,
    }

    print(f"=== [{direction.upper()}] Running backtest on real data (BTCUSDT 15m, 2025-01-01..2025-06-30) ===")
    bt_resp = client.post(
        f"/api/v1/strategy-builder/strategies/{strategy_id}/backtest",
        json=backtest_payload,
    )
    print("Backtest status:", bt_resp.status_code)
    try:
        payload = bt_resp.json()
    except Exception:
        payload = {"raw_text": bt_resp.text}

    if bt_resp.status_code != 200:
        print("Error payload:", payload)
        return

    results = payload.get("results", {})
    summary = {
        k: results.get(k)
        for k in ("total_return", "sharpe_ratio", "win_rate", "total_trades", "max_drawdown")
    }
    print(f"[{direction.upper()}] METRICS:", summary)

    # Persist metrics to JSON for later analysis/audits
    out = {
        "direction": direction,
        "symbol": "BTCUSDT",
        "timeframe": "15m",
        "start_date": "2025-01-01T00:00:00Z",
        "end_date": "2025-06-30T23:59:59Z",
        "results": summary,
    }
    metrics_path = Path("test_metrics/strategy_builder_e2e_2025H1.json")
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    existing = []
    if metrics_path.exists():
        try:
            existing = json.loads(metrics_path.read_text(encoding="utf-8"))
            if not isinstance(existing, list):
                existing = [existing]
        except Exception:
            existing = []
    existing = [e for e in existing if e.get("direction") != direction]
    existing.append(out)
    metrics_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")


def main() -> None:
    # Long-only
    run_single("long")
    print("\n" + "=" * 80 + "\n")
    # Short-only
    run_single("short")


if __name__ == "__main__":
    main()

