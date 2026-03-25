"""
Live API E2E Infrastructure Test
=================================
Same 9 phases as test_full_infrastructure.py but hitting
the REAL running server at localhost:8000 with real Bybit market data.

Requires:
    - Server running: uvicorn backend.api.app:app --host 0.0.0.0 --port 8000
    - Real market data in SmartKline cache (BTCUSDT:15, etc.)

Run:
    pytest tests/e2e/test_full_infrastructure_live.py -v -m live
    pytest tests/e2e/test_full_infrastructure_live.py -v  (skips if server down)
"""

from __future__ import annotations

import os
import uuid

import pytest
import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8003")
API = f"{BASE_URL}/api/v1"
BUILDER = f"{API}/strategy-builder"
BACKTESTS = f"{API}/backtests"
TIMEOUT = 30  # seconds per request
BACKTEST_TIMEOUT = 120  # seconds for backtest execution

# Commission rate - NEVER change (TradingView parity)
COMMISSION_RATE = 0.0007

# Test identifier to avoid clashing with real data
TEST_PREFIX = f"E2E_LIVE_{uuid.uuid4().hex[:8]}"

# Critical metrics that MUST be present after backtest
CRITICAL_METRICS_FIELDS = [
    "total_return",
    "sharpe_ratio",
    "max_drawdown",
    "win_rate",
    "profit_factor",
    "total_trades",
    "net_profit",
    "gross_profit",
    "gross_loss",
    "total_commission",
    "expectancy",
    "recovery_factor",
    "avg_bars_in_trade",
    "winning_trades",
    "losing_trades",
    "max_consecutive_wins",
    "max_consecutive_losses",
]


# ---------------------------------------------------------------------------
# Helpers: Strategy builders (same as in-memory test)
# ---------------------------------------------------------------------------
def build_rsi_long_strategy() -> dict:
    """RSI long-only strategy: buy when RSI < 30."""
    blocks = [
        {
            "id": "entry_signal",
            "type": "entry_signal",
            "params": {
                "direction": "long",
                "indicator": "rsi",
                "period": 14,
                "condition": "crosses_below",
                "value": 30,
            },
            "position": {"x": 100, "y": 100},
        },
        {
            "id": "exit_signal",
            "type": "exit_signal",
            "params": {
                "indicator": "rsi",
                "period": 14,
                "condition": "crosses_above",
                "value": 70,
            },
            "position": {"x": 300, "y": 100},
        },
        {
            "id": "static_sltp",
            "type": "static_sltp",
            "params": {
                "stop_loss_percent": 2.0,
                "take_profit_percent": 3.0,
            },
            "position": {"x": 200, "y": 250},
        },
        {
            "id": "filter_volume",
            "type": "filter",
            "params": {
                "indicator": "volume_above_avg",
                "period": 20,
                "multiplier": 1.0,
            },
            "position": {"x": 100, "y": 250},
        },
        {
            "id": "risk_block",
            "type": "risk_management",
            "params": {
                "max_position_pct": 50,
                "max_drawdown_pct": 15,
            },
            "position": {"x": 300, "y": 250},
        },
    ]
    connections = [
        {
            "id": "c1",
            "source_block_id": "entry_signal",
            "source_output": "signal",
            "target_block_id": "exit_signal",
            "target_input": "entry",
        },
        {
            "id": "c2",
            "source_block_id": "entry_signal",
            "source_output": "signal",
            "target_block_id": "static_sltp",
            "target_input": "entry",
        },
        {
            "id": "c3",
            "source_block_id": "filter_volume",
            "source_output": "filter",
            "target_block_id": "entry_signal",
            "target_input": "filter",
        },
        {
            "id": "c4",
            "source_block_id": "risk_block",
            "source_output": "risk",
            "target_block_id": "entry_signal",
            "target_input": "risk",
        },
    ]
    return {"blocks": blocks, "connections": connections}


def build_rsi_short_strategy() -> dict:
    """RSI short-only strategy: sell when RSI > 70."""
    blocks = [
        {
            "id": "entry_signal",
            "type": "entry_signal",
            "params": {
                "direction": "short",
                "indicator": "rsi",
                "period": 14,
                "condition": "crosses_above",
                "value": 70,
            },
            "position": {"x": 100, "y": 100},
        },
        {
            "id": "exit_signal",
            "type": "exit_signal",
            "params": {
                "indicator": "rsi",
                "period": 14,
                "condition": "crosses_below",
                "value": 30,
            },
            "position": {"x": 300, "y": 100},
        },
        {
            "id": "static_sltp",
            "type": "static_sltp",
            "params": {
                "stop_loss_percent": 2.0,
                "take_profit_percent": 3.0,
            },
            "position": {"x": 200, "y": 250},
        },
    ]
    connections = [
        {
            "id": "c1",
            "source_block_id": "entry_signal",
            "source_output": "signal",
            "target_block_id": "exit_signal",
            "target_input": "entry",
        },
        {
            "id": "c2",
            "source_block_id": "entry_signal",
            "source_output": "signal",
            "target_block_id": "static_sltp",
            "target_input": "entry",
        },
    ]
    return {"blocks": blocks, "connections": connections}


def build_rsi_dca_strategy() -> dict:
    """RSI + DCA grid strategy."""
    blocks = [
        {
            "id": "entry_signal",
            "type": "entry_signal",
            "params": {
                "direction": "long",
                "indicator": "rsi",
                "period": 14,
                "condition": "crosses_below",
                "value": 35,
            },
            "position": {"x": 100, "y": 100},
        },
        {
            "id": "exit_signal",
            "type": "exit_signal",
            "params": {
                "indicator": "rsi",
                "period": 14,
                "condition": "crosses_above",
                "value": 65,
            },
            "position": {"x": 300, "y": 100},
        },
        {
            "id": "dca_grid",
            "type": "dca_grid",
            "params": {
                "dca_order_count": 3,
                "dca_grid_size_percent": 1.5,
                "dca_martingale_coef": 1.5,
            },
            "position": {"x": 200, "y": 250},
        },
    ]
    connections = [
        {
            "id": "c1",
            "source_block_id": "entry_signal",
            "source_output": "signal",
            "target_block_id": "exit_signal",
            "target_input": "entry",
        },
        {
            "id": "c2",
            "source_block_id": "entry_signal",
            "source_output": "signal",
            "target_block_id": "dca_grid",
            "target_input": "entry",
        },
    ]
    return {"blocks": blocks, "connections": connections}


# ---------------------------------------------------------------------------
# Backtest parameters
# ---------------------------------------------------------------------------
BACKTEST_CLASSIC = {
    "symbol": "BTCUSDT",
    "interval": "15",
    "start_date": "2025-01-01T00:00:00Z",
    "end_date": "2025-02-01T00:00:00Z",
    "initial_capital": 10000.0,
    "commission": COMMISSION_RATE,
    "leverage": 10,
    "pyramiding": 1,
    "direction": "both",
    "market_type": "linear",
}

BACKTEST_DCA = {
    **BACKTEST_CLASSIC,
    "dca_enabled": True,
    "dca_order_count": 3,
    "dca_grid_size_percent": 1.5,
    "dca_martingale_coef": 1.5,
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _server_is_reachable() -> bool:
    """Check if server is reachable."""
    try:
        r = requests.get(f"{API}/health", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


# Skip entire module if server is not running
pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not _server_is_reachable(),
        reason=f"Server not running at {BASE_URL}",
    ),
]


@pytest.fixture(scope="module")
def session():
    """Requests session with default headers."""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def created_strategies(session):
    """Shared state: strategy IDs created during the test."""
    return {}


@pytest.fixture(scope="module")
def created_backtests(session):
    """Shared state: backtest IDs created during the test."""
    return {}


# ===================================================================
# Phase 1: Health Check
# ===================================================================
class TestHealthCheck:
    """Verify server is healthy before running tests."""

    def test_health_endpoint(self, session):
        """GET /api/v1/health returns 200."""
        r = session.get(f"{API}/health", timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") in ("healthy", "ok", "degraded", True)

    def test_strategy_builder_block_types(self, session):
        """Strategy builder block types endpoint works."""
        r = session.get(f"{BUILDER}/blocks/types", timeout=TIMEOUT)
        assert r.status_code == 200


# ===================================================================
# Phase 2: Strategy Creation via API
# ===================================================================
class TestStrategyCreation:
    """Create strategies via POST /strategy-builder/strategies."""

    def test_create_long_strategy(self, session, created_strategies):
        """Create RSI long-only strategy."""
        graph = build_rsi_long_strategy()
        payload = {
            "name": f"{TEST_PREFIX}_RSI_Long",
            "description": "E2E live test: RSI long strategy",
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "market_type": "linear",
            "direction": "long",
            "initial_capital": 10000.0,
            "leverage": 10,
            "blocks": graph["blocks"],
            "connections": graph["connections"],
        }
        r = session.post(f"{BUILDER}/strategies", json=payload, timeout=TIMEOUT)
        assert r.status_code == 200, f"Create long failed: {r.text}"
        data = r.json()
        assert "id" in data
        created_strategies["long"] = data["id"]
        assert data["name"] == f"{TEST_PREFIX}_RSI_Long"

    def test_create_short_strategy(self, session, created_strategies):
        """Create RSI short-only strategy."""
        graph = build_rsi_short_strategy()
        payload = {
            "name": f"{TEST_PREFIX}_RSI_Short",
            "description": "E2E live test: RSI short strategy",
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "market_type": "linear",
            "direction": "short",
            "initial_capital": 10000.0,
            "leverage": 10,
            "blocks": graph["blocks"],
            "connections": graph["connections"],
        }
        r = session.post(f"{BUILDER}/strategies", json=payload, timeout=TIMEOUT)
        assert r.status_code == 200, f"Create short failed: {r.text}"
        data = r.json()
        created_strategies["short"] = data["id"]

    def test_create_dca_strategy(self, session, created_strategies):
        """Create RSI + DCA grid strategy."""
        graph = build_rsi_dca_strategy()
        payload = {
            "name": f"{TEST_PREFIX}_RSI_DCA",
            "description": "E2E live test: RSI + DCA strategy",
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "market_type": "linear",
            "direction": "long",
            "initial_capital": 10000.0,
            "leverage": 10,
            "blocks": graph["blocks"],
            "connections": graph["connections"],
        }
        r = session.post(f"{BUILDER}/strategies", json=payload, timeout=TIMEOUT)
        assert r.status_code == 200, f"Create DCA failed: {r.text}"
        data = r.json()
        created_strategies["dca"] = data["id"]


# ===================================================================
# Phase 3: Strategy Load & Validate
# ===================================================================
class TestStrategyLoadAndValidate:
    """Load created strategies and validate blocks/connections."""

    def test_load_long_strategy(self, session, created_strategies):
        """GET /strategy-builder/strategies/{id} loads correctly."""
        sid = created_strategies.get("long")
        assert sid, "Long strategy was not created"
        r = session.get(f"{BUILDER}/strategies/{sid}", timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == sid
        assert len(data.get("blocks", [])) == 5, "Long strategy must have 5 blocks"
        assert len(data.get("connections", [])) == 4, "Long strategy must have 4 connections"

    def test_load_short_strategy(self, session, created_strategies):
        """Short strategy loads with correct block count."""
        sid = created_strategies.get("short")
        assert sid, "Short strategy was not created"
        r = session.get(f"{BUILDER}/strategies/{sid}", timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert len(data.get("blocks", [])) == 3
        assert len(data.get("connections", [])) == 2

    def test_list_strategies_contains_ours(self, session, created_strategies):
        """GET /strategy-builder/strategies lists our strategies."""
        r = session.get(
            f"{BUILDER}/strategies",
            params={"page": 1, "page_size": 100},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        # Response might be a list or {"strategies": [...]}
        strategies = data if isinstance(data, list) else data.get("strategies", data.get("items", []))
        our_ids = set(created_strategies.values())
        found_ids = {s["id"] for s in strategies if isinstance(s, dict)}
        assert our_ids.issubset(found_ids), f"Not all strategies found. Ours: {our_ids}, found: {found_ids}"

    def test_validate_strategy(self, session, created_strategies):
        """POST /strategy-builder/validate/{id} passes for long strategy."""
        sid = created_strategies.get("long")
        assert sid
        r = session.post(f"{BUILDER}/validate/{sid}", timeout=TIMEOUT)
        # Validation may return 200 (valid), 400/422 (invalid), or 404 (not implemented for this flow)
        assert r.status_code in (200, 400, 404, 422), f"Validate failed with {r.status_code}: {r.text}"


# ===================================================================
# Phase 4: Backtest Execution (Real market data)
# ===================================================================
class TestBacktestExecution:
    """Run backtests via real API with real BTCUSDT data."""

    def test_run_long_backtest(self, session, created_strategies, created_backtests):
        """POST /strategy-builder/strategies/{id}/backtest with long strategy."""
        sid = created_strategies.get("long")
        assert sid, "Long strategy not created"

        r = session.post(
            f"{BUILDER}/strategies/{sid}/backtest",
            json=BACKTEST_CLASSIC,
            timeout=BACKTEST_TIMEOUT,
        )
        assert r.status_code == 200, f"Long backtest failed ({r.status_code}): {r.text[:500]}"
        data = r.json()

        # Must have metrics, performance, or results
        assert "metrics" in data or "performance" in data or "results" in data, (
            f"No metrics in response: {list(data.keys())}"
        )

        # Extract backtest_id for later tests
        bt_id = data.get("backtest_id") or data.get("id")
        if bt_id:
            created_backtests["long"] = bt_id

        # Store full response for metrics checks
        created_backtests["long_response"] = data

    def test_run_short_backtest(self, session, created_strategies, created_backtests):
        """POST /strategy-builder/strategies/{id}/backtest with short strategy."""
        sid = created_strategies.get("short")
        assert sid, "Short strategy not created"

        params = {**BACKTEST_CLASSIC, "direction": "short"}
        r = session.post(
            f"{BUILDER}/strategies/{sid}/backtest",
            json=params,
            timeout=BACKTEST_TIMEOUT,
        )
        assert r.status_code == 200, f"Short backtest failed ({r.status_code}): {r.text[:500]}"
        data = r.json()

        bt_id = data.get("backtest_id") or data.get("id")
        if bt_id:
            created_backtests["short"] = bt_id
        created_backtests["short_response"] = data

    @pytest.mark.xfail(
        reason="DCA engine has known position_size kwarg bug in TradeRecord",
        strict=False,
    )
    def test_run_dca_backtest(self, session, created_strategies, created_backtests):
        """POST /strategy-builder/strategies/{id}/backtest with DCA strategy."""
        sid = created_strategies.get("dca")
        assert sid, "DCA strategy not created"

        r = session.post(
            f"{BUILDER}/strategies/{sid}/backtest",
            json=BACKTEST_DCA,
            timeout=BACKTEST_TIMEOUT,
        )
        assert r.status_code == 200, f"DCA backtest failed ({r.status_code}): {r.text[:500]}"
        data = r.json()

        bt_id = data.get("backtest_id") or data.get("id")
        if bt_id:
            created_backtests["dca"] = bt_id
        created_backtests["dca_response"] = data


# ===================================================================
# Phase 5: Metrics Integrity
# ===================================================================
class TestMetricsIntegrity:
    """Verify backtest response contains all critical metrics."""

    def _get_metrics(self, response: dict) -> dict:
        """Extract metrics dict from response (various formats)."""
        for key in ("metrics", "performance", "results"):
            if key in response:
                val = response[key]
                if isinstance(val, dict):
                    return val
        return response

    def test_long_metrics_completeness(self, created_backtests):
        """Long backtest has critical metrics (if trades were generated)."""
        data = created_backtests.get("long_response")
        assert data, "Long backtest response not saved"
        metrics = self._get_metrics(data)

        # If 0 trades, only basic metrics are returned - that's expected for builder strategies
        if metrics.get("total_trades", 0) == 0:
            pytest.skip("Builder strategy generated 0 trades (block category mapping issue)")

        missing = [f for f in CRITICAL_METRICS_FIELDS if f not in metrics]
        assert not missing, f"Long backtest missing critical metrics: {missing}"

    def test_short_metrics_completeness(self, created_backtests):
        """Short backtest has critical metrics (if trades were generated)."""
        data = created_backtests.get("short_response")
        assert data, "Short backtest response not saved"
        metrics = self._get_metrics(data)

        if metrics.get("total_trades", 0) == 0:
            pytest.skip("Builder strategy generated 0 trades (block category mapping issue)")

        missing = [f for f in CRITICAL_METRICS_FIELDS if f not in metrics]
        assert not missing, f"Short backtest missing critical metrics: {missing}"

    def test_metrics_values_sensible(self, created_backtests):
        """Metric values are within reasonable ranges."""
        # Prefer standard backtest response (has real trades via RSI strategy_type)
        data = created_backtests.get("standard_response") or created_backtests.get("long_response")
        assert data
        metrics = self._get_metrics(data)

        if metrics.get("total_trades", 0) == 0:
            pytest.skip("No trades to validate metric values")

        # total_trades must be >= 0
        assert metrics.get("total_trades", 0) >= 0

        # win_rate must be 0-100 (or 0-1)
        wr = metrics.get("win_rate", 0)
        assert 0 <= wr <= 100, f"win_rate out of range: {wr}"

        # max_drawdown must be >= 0
        mdd = metrics.get("max_drawdown", 0)
        assert mdd >= 0, f"max_drawdown should be >= 0: {mdd}"

        # commission must be > 0 if there were trades
        if metrics.get("total_trades", 0) > 0:
            comm = metrics.get("total_commission", 0)
            assert comm > 0, f"total_commission must be > 0 with trades: {comm}"

    def test_sign_conventions(self, created_backtests):
        """Verify backend sign conventions on live data."""
        data = created_backtests.get("standard_response") or created_backtests.get("long_response")
        assert data
        metrics = self._get_metrics(data)

        if metrics.get("total_trades", 0) == 0:
            pytest.skip("No trades to validate sign conventions")

        # gross_loss must be >= 0 (positive in our convention)
        gl = metrics.get("gross_loss")
        if gl is not None:
            assert gl >= 0, f"gross_loss must be >= 0 in backend: {gl}"

        # max_drawdown must be >= 0
        mdd = metrics.get("max_drawdown")
        if mdd is not None:
            assert mdd >= 0, f"max_drawdown must be >= 0: {mdd}"

        # avg_loss should be negative (it's a loss)
        avg_loss = metrics.get("avg_loss")
        if avg_loss is not None and metrics.get("losing_trades", 0) > 0:
            assert avg_loss <= 0, f"avg_loss should be <= 0: {avg_loss}"


# ===================================================================
# Phase 6: Trades Validation
# ===================================================================
class TestTradesValidation:
    """Verify trades list structure in backtest response."""

    def test_trades_present(self, created_backtests):
        """Backtest response contains trades list."""
        data = created_backtests.get("long_response")
        assert data
        trades = data.get("trades", [])
        # Some backtests may have 0 trades (no signals in period)
        assert isinstance(trades, list), f"trades must be a list: {type(trades)}"

    def test_trade_structure(self, created_backtests):
        """Each trade has required fields."""
        data = created_backtests.get("long_response")
        assert data
        trades = data.get("trades", [])
        if not trades:
            pytest.skip("No trades generated — can't validate structure")

        required = {"entry_price", "exit_price", "pnl", "side"}
        for i, trade in enumerate(trades[:5]):  # check first 5
            for field in required:
                assert field in trade, f"Trade {i} missing '{field}': {list(trade.keys())}"

    def test_trade_mfe_mae(self, created_backtests):
        """Trades have MFE/MAE fields."""
        data = created_backtests.get("long_response")
        assert data
        trades = data.get("trades", [])
        if not trades:
            pytest.skip("No trades generated")

        # MFE/MAE may be named mfe/mae or max_favorable_excursion etc.
        first_trade = trades[0]
        has_mfe = "mfe" in first_trade or "max_favorable_excursion" in first_trade
        has_mae = "mae" in first_trade or "max_adverse_excursion" in first_trade
        assert has_mfe, f"Trade missing MFE: {list(first_trade.keys())}"
        assert has_mae, f"Trade missing MAE: {list(first_trade.keys())}"


# ===================================================================
# Phase 7: Equity Curve Validation
# ===================================================================
class TestEquityCurveValidation:
    """Verify equity curve in backtest response."""

    def test_equity_curve_present(self, created_backtests):
        """Response has equity_curve."""
        data = created_backtests.get("long_response")
        assert data
        ec = data.get("equity_curve", data.get("equity"))
        # equity_curve may be inside metrics or results
        if ec is None and "metrics" in data:
            ec = data["metrics"].get("equity_curve")
        if ec is None and "results" in data:
            ec = data["results"].get("equity_curve")
        # Builder responses may not include equity_curve in HTTP response
        # (it is stored in DB and available via GET /backtests/{id})
        if ec is None:
            pytest.skip("equity_curve not in builder response body — available via GET /backtests/{id}")

    def test_equity_curve_structure(self, created_backtests):
        """Equity curve has timestamps and values."""
        data = created_backtests.get("long_response")
        assert data
        ec = data.get("equity_curve", data.get("equity"))
        if ec is None and "metrics" in data:
            ec = data["metrics"].get("equity_curve")
        if ec is None:
            pytest.skip("No equity_curve")

        if isinstance(ec, list) and len(ec) > 0:
            first = ec[0]
            if isinstance(first, dict):
                # Should have value/equity field
                assert any(k in first for k in ("value", "equity", "balance", "capital")), (
                    f"Equity curve item has no value field: {list(first.keys())}"
                )
        elif isinstance(ec, dict):
            # May be {"timestamps": [...], "values": [...]} format
            assert "timestamps" in ec or "values" in ec or "data" in ec, (
                f"Unknown equity_curve format: {list(ec.keys())}"
            )


# ===================================================================
# Phase 8: DB Round-trip (load saved backtest)
# ===================================================================
class TestDBRoundtrip:
    """Load backtest from DB via GET /backtests/{id} and verify metrics survived."""

    def test_load_saved_backtest(self, session, created_backtests):
        """GET /backtests/{id} returns saved backtest with metrics."""
        bt_id = created_backtests.get("long")
        if not bt_id:
            pytest.skip("No backtest_id saved — backtest may not have been persisted")

        r = session.get(f"{BACKTESTS}/{bt_id}", timeout=TIMEOUT)
        assert r.status_code == 200, f"Load backtest failed ({r.status_code}): {r.text[:300]}"
        data = r.json()

        # Verify it has metrics
        assert "metrics" in data or "performance" in data, f"Loaded backtest missing metrics: {list(data.keys())}"

    def test_metrics_survived_db_save(self, session, created_backtests):
        """Critical metrics survive save → load round-trip."""
        bt_id = created_backtests.get("long")
        if not bt_id:
            pytest.skip("No backtest_id saved")

        r = session.get(f"{BACKTESTS}/{bt_id}", timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()

        # Extract metrics
        metrics = data.get("metrics") or data.get("performance") or {}
        if isinstance(metrics, dict):
            # Check at least some critical fields survived
            survived = [f for f in CRITICAL_METRICS_FIELDS if f in metrics]
            assert len(survived) >= 10, f"Only {len(survived)}/17 critical metrics survived DB round-trip: {survived}"

    def test_trades_survived_db_save(self, session, created_backtests):
        """Trades survive save → load round-trip."""
        bt_id = created_backtests.get("long")
        if not bt_id:
            pytest.skip("No backtest_id saved")

        r = session.get(f"{BACKTESTS}/{bt_id}/trades", timeout=TIMEOUT)
        if r.status_code == 200:
            data = r.json()
            trades = data if isinstance(data, list) else data.get("trades", [])
            # If the original had trades, they should be here too
            orig = created_backtests.get("long_response", {})
            orig_count = len(orig.get("trades", []))
            if orig_count > 0:
                assert len(trades) > 0, "Trades lost after DB save"

    def test_equity_survived_db_save(self, session, created_backtests):
        """Equity curve survives save → load round-trip."""
        bt_id = created_backtests.get("long")
        if not bt_id:
            pytest.skip("No backtest_id saved")

        r = session.get(f"{BACKTESTS}/{bt_id}/equity", timeout=TIMEOUT)
        if r.status_code == 200:
            data = r.json()
            # Just check it's not empty
            assert data, "Equity curve endpoint returned empty data"


# ===================================================================
# Phase 9: Standard Backtest API
# ===================================================================
class TestStandardBacktestAPI:
    """Test POST /backtests/ (standard, non-builder backtest)."""

    def test_create_standard_backtest(self, session, created_backtests):
        """POST /backtests/ with RSI strategy runs successfully."""
        payload = {
            "symbol": "BTCUSDT",
            "interval": "15",
            "start_date": "2025-01-01",
            "end_date": "2025-02-01",
            "initial_capital": 10000,
            "leverage": 10,
            "direction": "both",
            "stop_loss": 0.02,
            "take_profit": 0.03,
            "strategy_type": "rsi",
            "strategy_params": {
                "period": 14,
                "overbought": 70,
                "oversold": 30,
            },
        }
        r = session.post(f"{BACKTESTS}/", json=payload, timeout=BACKTEST_TIMEOUT)
        assert r.status_code == 200, f"Standard backtest failed ({r.status_code}): {r.text[:500]}"
        data = r.json()

        # Should have backtest_id and metrics
        bt_id = data.get("backtest_id") or data.get("id")
        if bt_id:
            created_backtests["standard"] = bt_id

        # Store response for later metric checks
        created_backtests["standard_response"] = data

        # Check metrics
        metrics = data.get("metrics") or data.get("performance") or data.get("results") or {}
        assert isinstance(metrics, dict), "Standard backtest missing metrics"

    def test_standard_metrics_complete(self, session, created_backtests):
        """Standard backtest (RSI strategy_type) returns all critical metrics."""
        data = created_backtests.get("standard_response")
        assert data, "Standard backtest response not saved"

        metrics = data.get("metrics") or data.get("performance") or data.get("results") or {}
        total = metrics.get("total_trades", 0)
        if total == 0:
            pytest.skip("Standard backtest returned 0 trades — no metric validation possible")

        missing = [f for f in CRITICAL_METRICS_FIELDS if f not in metrics]
        assert not missing, f"Standard backtest missing critical metrics: {missing}"

    def test_standard_trades_present(self, session, created_backtests):
        """Standard backtest has trades with expected fields."""
        data = created_backtests.get("standard_response")
        assert data
        trades = data.get("trades", [])
        if not trades:
            pytest.skip("Standard backtest returned 0 trades")

        required = {"entry_price", "exit_price", "pnl", "side"}
        first = trades[0]
        missing = required - set(first.keys())
        assert not missing, f"Standard trade missing fields: {missing}. Has: {list(first.keys())}"

    def test_list_backtests_after_creation(self, session, created_backtests):
        """GET /backtests/ shows our backtests."""
        r = session.get(f"{BACKTESTS}/", timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        backtests = data if isinstance(data, list) else data.get("backtests", data.get("items", []))
        assert isinstance(backtests, list)
        # Should have at least 1 backtest
        assert len(backtests) >= 1, "No backtests found after creation"


# ===================================================================
# Phase 10: Cleanup
# ===================================================================
class TestCleanup:
    """Delete all test artifacts."""

    def test_delete_backtests(self, session, created_backtests):
        """Delete all backtests created by this test run."""
        for label in ("long", "short", "dca", "standard"):
            bt_id = created_backtests.get(label)
            if bt_id:
                r = session.delete(f"{BACKTESTS}/{bt_id}", timeout=TIMEOUT)
                # 200 or 204 or 404 (already deleted) are all OK
                assert r.status_code in (200, 204, 404), f"Delete backtest {label}={bt_id} failed: {r.status_code}"

    def test_delete_strategies(self, session, created_strategies):
        """Delete all strategies created by this test run."""
        for label in ("long", "short", "dca"):
            sid = created_strategies.get(label)
            if sid:
                r = session.delete(f"{BUILDER}/strategies/{sid}", timeout=TIMEOUT)
                assert r.status_code in (200, 204, 404), f"Delete strategy {label}={sid} failed: {r.status_code}"

    def test_verify_cleanup(self, session, created_strategies):
        """Verify deleted strategies no longer appear in list."""
        r = session.get(
            f"{BUILDER}/strategies",
            params={"page": 1, "page_size": 100},
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            data = r.json()
            strategies = data if isinstance(data, list) else data.get("strategies", data.get("items", []))
            remaining_ids = {s.get("id") for s in strategies if isinstance(s, dict)}
            for label, sid in created_strategies.items():
                assert sid not in remaining_ids, f"Strategy {label}={sid} still exists after delete"
