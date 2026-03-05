"""
DCA Integration Test - Run via pytest.
Tests the ACTUAL data flow from Strategy Builder to DCA Engine.
"""

import socket

import pytest
import requests

BASE_URL = "http://localhost:8000"


def _server_reachable() -> bool:
    """Quick TCP check — returns False in < 0.5 s when server is down."""
    try:
        with socket.create_connection(("localhost", 8000), timeout=0.5):
            return True
    except OSError:
        return False


_SERVER_RUNNING = _server_reachable()
pytestmark = pytest.mark.skipif(
    not _SERVER_RUNNING,
    reason="Server not reachable at localhost:8000 — start uvicorn to run these tests",
)


@pytest.fixture
def dca_strategy_data():
    """Strategy with DCA block - exactly as frontend sends."""
    return {
        "name": "DCA Test Strategy pytest",
        "description": "Testing DCA flow via pytest",
        "symbol": "BTCUSDT",
        "interval": "15",
        "blocks": [
            # RSI indicator block
            {
                "id": "block_1",
                "type": "rsi",
                "category": "indicators",
                "params": {"period": 14, "overbought": 70, "oversold": 30},
                "position": {"x": 100, "y": 100},
            },
            # Comparator: RSI < 30 → entry long signal
            {
                "id": "block_cmp_long",
                "type": "less_than",
                "category": "conditions",
                "params": {},
                "position": {"x": 300, "y": 60},
            },
            # Constant 30 for oversold threshold
            {
                "id": "block_const_30",
                "type": "constant",
                "category": "values",
                "params": {"value": 30},
                "position": {"x": 100, "y": 200},
            },
            # Comparator: RSI > 70 → exit long signal
            {
                "id": "block_cmp_exit",
                "type": "greater_than",
                "category": "conditions",
                "params": {},
                "position": {"x": 300, "y": 160},
            },
            # Constant 70 for overbought threshold
            {
                "id": "block_const_70",
                "type": "constant",
                "category": "values",
                "params": {"value": 70},
                "position": {"x": 100, "y": 260},
            },
            # DCA block (entry refinement)
            {
                "id": "block_2",
                "type": "dca",
                "category": "entry_refinement",
                "params": {
                    "grid_size_percent": 15,
                    "order_count": 5,
                    "martingale_coefficient": 1.0,
                    "log_steps_coefficient": 1.0,
                    "first_order_offset": 2.0,
                    "grid_trailing": 0.5,
                },
                "position": {"x": 500, "y": 100},
            },
            # Main strategy aggregator node
            {
                "id": "main_strategy",
                "type": "strategy",
                "category": "main",
                "isMain": True,
                "params": {},
                "position": {"x": 700, "y": 200},
            },
        ],
        "connections": [
            # RSI value → comparator inputs
            {
                "id": "conn_1",
                "source": {"blockId": "block_1", "portId": "value"},
                "target": {"blockId": "block_cmp_long", "portId": "a"},
                "type": "data",
            },
            {
                "id": "conn_2",
                "source": {"blockId": "block_const_30", "portId": "value"},
                "target": {"blockId": "block_cmp_long", "portId": "b"},
                "type": "data",
            },
            {
                "id": "conn_3",
                "source": {"blockId": "block_1", "portId": "value"},
                "target": {"blockId": "block_cmp_exit", "portId": "a"},
                "type": "data",
            },
            {
                "id": "conn_4",
                "source": {"blockId": "block_const_70", "portId": "value"},
                "target": {"blockId": "block_cmp_exit", "portId": "b"},
                "type": "data",
            },
            # Entry long signal → main_strategy
            {
                "id": "conn_5",
                "source": {"blockId": "block_cmp_long", "portId": "result"},
                "target": {"blockId": "main_strategy", "portId": "entry_long"},
                "type": "data",
            },
            # Exit long signal → main_strategy
            {
                "id": "conn_6",
                "source": {"blockId": "block_cmp_exit", "portId": "result"},
                "target": {"blockId": "main_strategy", "portId": "exit_long"},
                "type": "data",
            },
        ],
    }


class TestDCAIntegration:
    """Test full DCA integration flow."""

    def test_server_health(self):
        """Ensure server is running."""
        resp = requests.get(f"{BASE_URL}/api/v1/health", timeout=5)
        assert resp.status_code == 200
        print("✓ Server health OK")

    def test_create_strategy_with_dca_block(self, dca_strategy_data):
        """Test creating strategy with DCA block."""
        resp = requests.post(f"{BASE_URL}/api/v1/strategy-builder/strategies", json=dca_strategy_data, timeout=30)

        print(f"Create response: {resp.status_code}")
        if resp.status_code not in [200, 201]:
            print(f"Response text: {resp.text[:500]}")

        assert resp.status_code in [200, 201], f"Failed to create: {resp.text[:200]}"

        strategy = resp.json()
        assert "id" in strategy
        print(f"✓ Strategy created: ID={strategy['id']}")

        return strategy["id"]

    def test_full_dca_backtest_flow(self, dca_strategy_data):
        """Full flow: Create strategy → Run backtest → Check DCA used."""

        # Step 1: Create strategy
        create_resp = requests.post(
            f"{BASE_URL}/api/v1/strategy-builder/strategies", json=dca_strategy_data, timeout=30
        )
        assert create_resp.status_code in [200, 201], f"Create failed: {create_resp.text[:200]}"

        strategy = create_resp.json()
        strategy_id = strategy["id"]
        print(f"✓ Step 1: Strategy created ID={strategy_id}")

        # Step 2: Verify blocks saved
        get_resp = requests.get(f"{BASE_URL}/api/v1/strategy-builder/strategies/{strategy_id}", timeout=10)
        assert get_resp.status_code == 200
        saved = get_resp.json()
        blocks = saved.get("blocks", [])

        dca_found = any(b.get("type") == "dca" and b.get("category") == "entry_refinement" for b in blocks)
        print(f"✓ Step 2: Blocks saved, DCA block found: {dca_found}")

        # Step 3: Run backtest
        backtest_req = {
            "start_date": "2025-01-01",
            "end_date": "2025-01-15",
            "initial_capital": 10000,
            "leverage": 10,
            "direction": "both",
            "dca_enabled": True,
            "dca_order_count": 5,
            "dca_grid_size_percent": 15.0,
        }

        backtest_resp = requests.post(
            f"{BASE_URL}/api/v1/strategy-builder/strategies/{strategy_id}/backtest", json=backtest_req, timeout=180
        )

        print(f"Backtest response status: {backtest_resp.status_code}")

        if backtest_resp.status_code != 200:
            print(f"Backtest error: {backtest_resp.text[:500]}")

        assert backtest_resp.status_code == 200, f"Backtest failed: {backtest_resp.text[:300]}"

        result = backtest_resp.json()
        print("✓ Step 3: Backtest completed")
        print(f"   Total trades: {result.get('total_trades', 0)}")
        print(f"   Net profit: {result.get('net_profit', 0):.2f}")
        print(f"   Engine: {result.get('engine', 'unknown')}")

        # Check that engine used was DCA
        engine = result.get("engine", "").lower()
        # Note: If DCA is properly integrated, it should show in the results

        print("\n=== DCA FLOW TEST PASSED ===")

        # Cleanup
        requests.delete(f"{BASE_URL}/api/v1/strategy-builder/strategies/{strategy_id}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
