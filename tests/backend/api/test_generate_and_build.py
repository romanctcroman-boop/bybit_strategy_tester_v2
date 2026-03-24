"""
Integration tests for POST /ai-strategy-generator/generate-and-build endpoint.

Tests cover:
- Happy path: correct response shape
- Empty OHLCV → 404
- DB failure → 503
- Pipeline error → 500
- Graph warnings passed through
- Request params forwarded to pipeline
- Execution path in response
- Edge: no selected strategy name, no backtest result

Patch strategy:
- `asyncio.to_thread` → patched at module level (asyncio is top-level import)
- `run_strategy_pipeline` → lazy-imported inside the endpoint function →
  must be patched at SOURCE: backend.agents.trading_strategy_graph.run_strategy_pipeline
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.agents.langgraph_orchestrator import AgentState
from backend.api.routers.ai_strategy_generator import router

# Patch targets
_PIPELINE = "backend.agents.trading_strategy_graph.run_strategy_pipeline"
_TO_THREAD = "backend.api.routers.ai_strategy_generator.asyncio.to_thread"


# =============================================================================
# Helpers
# =============================================================================


def _make_ohlcv(n: int = 200) -> pd.DataFrame:
    """Return a minimal OHLCV DataFrame with DatetimeIndex."""
    np.random.seed(0)
    prices = 50_000.0 * np.cumprod(1 + np.random.randn(n) * 0.002)
    idx = pd.date_range("2025-01-01", periods=n, freq="15min", tz="UTC")
    idx.name = "open_time"
    return pd.DataFrame(
        {
            "open": prices,
            "high": prices * 1.002,
            "low": prices * 0.998,
            "close": prices,
            "volume": np.random.uniform(10, 100, n),
        },
        index=idx,
    )


def _make_state(
    *,
    symbol: str = "BTCUSDT",
    timeframe: str = "15",
    backtest_metrics: dict | None = None,
    strategy_graph: dict | None = None,
    graph_warnings: list | None = None,
    saved_strategy_id: int | None = 42,
    errors: list | None = None,
) -> AgentState:
    """Build a realistic AgentState as returned by run_strategy_pipeline()."""
    state = AgentState()
    state.execution_path = [
        ("analyze_market", 0.5),
        ("memory_recall", 0.1),
        ("generate_strategies", 2.3),
        ("parse_responses", 0.2),
        ("select_best", 0.1),
        ("build_graph", 0.3),
        ("backtest", 1.4),
        ("backtest_analysis", 0.1),
        ("memory_update", 0.2),
        ("report", 0.05),
    ]

    # Report node result
    state.set_result(
        "report",
        {
            "symbol": symbol,
            "timeframe": timeframe,
            "proposals_count": 3,
            "pipeline_metrics": {
                "total_cost_usd": 0.0042,
                "llm_call_count": 4,
                "total_wall_time_s": 5.25,
            },
        },
    )

    # Strategy selection result
    mock_strategy = MagicMock()
    mock_strategy.strategy_name = "AI RSI Momentum"
    state.set_result("select_best", {"selected_strategy": mock_strategy})

    # Backtest result
    state.set_result(
        "backtest",
        {
            "metrics": backtest_metrics
            or {
                "total_return": 12.5,
                "sharpe_ratio": 1.23,
                "max_drawdown": 8.4,
                "total_trades": 47,
            }
        },
    )

    # Context
    state.context["strategy_graph"] = strategy_graph or {
        "blocks": [{"id": "rsi_1", "type": "rsi"}, {"id": "strategy_node", "type": "strategy"}],
        "connections": [
            {"from": "rsi_1", "fromPort": "long", "to": "strategy_node", "toPort": "entry_long"}
        ],
        "name": "AI RSI Momentum",
    }
    state.context["graph_warnings"] = graph_warnings if graph_warnings is not None else []
    state.context["saved_strategy_id"] = saved_strategy_id

    if errors:
        state.errors = errors

    return state


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def app() -> FastAPI:
    _app = FastAPI()
    _app.include_router(router)
    return _app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture
def ohlcv() -> pd.DataFrame:
    return _make_ohlcv()


# =============================================================================
# Happy path
# =============================================================================


class TestGenerateAndBuildHappyPath:
    def test_returns_200_with_expected_keys(self, client: TestClient, ohlcv: pd.DataFrame):
        state = _make_state()
        with (
            patch(_TO_THREAD, new=AsyncMock(return_value=ohlcv)),
            patch(_PIPELINE, new=AsyncMock(return_value=state)),
        ):
            resp = client.post("/ai-strategy-generator/generate-and-build", json={"symbol": "BTCUSDT", "timeframe": "15", "days": 90})

        assert resp.status_code == 200
        body = resp.json()
        required_keys = {
            "strategy_name",
            "strategy_graph",
            "graph_warnings",
            "backtest_metrics",
            "saved_strategy_id",
            "proposals_count",
            "execution_path",
            "errors",
            "symbol",
            "timeframe",
        }
        missing = required_keys - set(body.keys())
        assert not missing, f"Missing keys: {missing}"

    def test_strategy_name_from_selected_strategy(self, client: TestClient, ohlcv: pd.DataFrame):
        state = _make_state()
        with (
            patch(_TO_THREAD, new=AsyncMock(return_value=ohlcv)),
            patch(_PIPELINE, new=AsyncMock(return_value=state)),
        ):
            resp = client.post("/ai-strategy-generator/generate-and-build", json={"symbol": "BTCUSDT"})

        assert resp.json()["strategy_name"] == "AI RSI Momentum"

    def test_backtest_metrics_in_response(self, client: TestClient, ohlcv: pd.DataFrame):
        state = _make_state(backtest_metrics={"sharpe_ratio": 1.5, "total_trades": 30})
        with (
            patch(_TO_THREAD, new=AsyncMock(return_value=ohlcv)),
            patch(_PIPELINE, new=AsyncMock(return_value=state)),
        ):
            resp = client.post("/ai-strategy-generator/generate-and-build", json={"symbol": "BTCUSDT"})

        metrics = resp.json()["backtest_metrics"]
        assert metrics["sharpe_ratio"] == 1.5
        assert metrics["total_trades"] == 30

    def test_strategy_graph_passed_through(self, client: TestClient, ohlcv: pd.DataFrame):
        graph = {"blocks": [{"id": "b1", "type": "macd"}], "connections": [], "name": "Test MACD"}
        state = _make_state(strategy_graph=graph)
        with (
            patch(_TO_THREAD, new=AsyncMock(return_value=ohlcv)),
            patch(_PIPELINE, new=AsyncMock(return_value=state)),
        ):
            resp = client.post("/ai-strategy-generator/generate-and-build", json={"symbol": "BTCUSDT"})

        assert resp.json()["strategy_graph"]["name"] == "Test MACD"

    def test_saved_strategy_id_in_response(self, client: TestClient, ohlcv: pd.DataFrame):
        state = _make_state(saved_strategy_id=99)
        with (
            patch(_TO_THREAD, new=AsyncMock(return_value=ohlcv)),
            patch(_PIPELINE, new=AsyncMock(return_value=state)),
        ):
            resp = client.post("/ai-strategy-generator/generate-and-build", json={"symbol": "BTCUSDT"})

        assert resp.json()["saved_strategy_id"] == 99

    def test_execution_path_non_empty(self, client: TestClient, ohlcv: pd.DataFrame):
        state = _make_state()
        with (
            patch(_TO_THREAD, new=AsyncMock(return_value=ohlcv)),
            patch(_PIPELINE, new=AsyncMock(return_value=state)),
        ):
            resp = client.post("/ai-strategy-generator/generate-and-build", json={"symbol": "BTCUSDT"})

        path = resp.json()["execution_path"]
        assert len(path) > 0
        # Each entry is [node_name, elapsed_s]
        assert len(path[0]) == 2

    def test_symbol_and_timeframe_echoed_in_response(self, client: TestClient, ohlcv: pd.DataFrame):
        state = _make_state(symbol="ETHUSDT", timeframe="60")
        with (
            patch(_TO_THREAD, new=AsyncMock(return_value=ohlcv)),
            patch(_PIPELINE, new=AsyncMock(return_value=state)),
        ):
            resp = client.post("/ai-strategy-generator/generate-and-build", json={"symbol": "ETHUSDT", "timeframe": "60"})

        body = resp.json()
        assert body["symbol"] == "ETHUSDT"
        assert body["timeframe"] == "60"

    def test_graph_warnings_passed_through(self, client: TestClient, ohlcv: pd.DataFrame):
        warnings = ["Block 'rsi_1' has no connections to strategy node"]
        state = _make_state(graph_warnings=warnings)
        with (
            patch(_TO_THREAD, new=AsyncMock(return_value=ohlcv)),
            patch(_PIPELINE, new=AsyncMock(return_value=state)),
        ):
            resp = client.post("/ai-strategy-generator/generate-and-build", json={"symbol": "BTCUSDT"})

        assert resp.json()["graph_warnings"] == warnings

    def test_proposals_count_from_report(self, client: TestClient, ohlcv: pd.DataFrame):
        state = _make_state()
        with (
            patch(_TO_THREAD, new=AsyncMock(return_value=ohlcv)),
            patch(_PIPELINE, new=AsyncMock(return_value=state)),
        ):
            resp = client.post("/ai-strategy-generator/generate-and-build", json={"symbol": "BTCUSDT"})

        assert resp.json()["proposals_count"] == 3

    def test_pipeline_errors_surface_in_response(self, client: TestClient, ohlcv: pd.DataFrame):
        error = {"node": "backtest", "error_type": "ValueError", "error_message": "no trades", "timestamp": "..."}
        state = _make_state(errors=[error])
        with (
            patch(_TO_THREAD, new=AsyncMock(return_value=ohlcv)),
            patch(_PIPELINE, new=AsyncMock(return_value=state)),
        ):
            resp = client.post("/ai-strategy-generator/generate-and-build", json={"symbol": "BTCUSDT"})

        assert resp.status_code == 200  # partial state still returns 200
        assert len(resp.json()["errors"]) == 1
        assert resp.json()["errors"][0]["node"] == "backtest"


# =============================================================================
# Request parameter forwarding
# =============================================================================


class TestGenerateAndBuildRequestForwarding:
    def test_request_params_forwarded_to_pipeline(self, client: TestClient, ohlcv: pd.DataFrame):
        state = _make_state()
        pipeline_mock = AsyncMock(return_value=state)
        with (
            patch(_TO_THREAD, new=AsyncMock(return_value=ohlcv)),
            patch(_PIPELINE, new=pipeline_mock),
        ):
            resp = client.post(
                "/ai-strategy-generator/generate-and-build",
                json={
                    "symbol": "SOLUSDT",
                    "timeframe": "240",
                    "agents": ["deepseek", "qwen"],
                    "run_backtest": False,
                    "run_debate": False,
                    "initial_capital": 50000.0,
                    "leverage": 5,
                },
            )

        assert resp.status_code == 200
        pipeline_mock.assert_awaited_once()
        call_kwargs = pipeline_mock.call_args.kwargs
        assert call_kwargs["symbol"] == "SOLUSDT"
        assert call_kwargs["timeframe"] == "240"
        assert call_kwargs["agents"] == ["deepseek", "qwen"]
        assert call_kwargs["run_backtest"] is False
        assert call_kwargs["run_debate"] is False
        assert call_kwargs["initial_capital"] == 50000.0
        assert call_kwargs["leverage"] == 5

    def test_default_agents_is_deepseek(self, client: TestClient, ohlcv: pd.DataFrame):
        state = _make_state()
        pipeline_mock = AsyncMock(return_value=state)
        with (
            patch(_TO_THREAD, new=AsyncMock(return_value=ohlcv)),
            patch(_PIPELINE, new=pipeline_mock),
        ):
            client.post("/ai-strategy-generator/generate-and-build", json={"symbol": "BTCUSDT"})

        assert pipeline_mock.call_args.kwargs["agents"] == ["deepseek"]

    def test_symbol_forwarded_as_provided(self, client: TestClient, ohlcv: pd.DataFrame):
        """Pipeline receives symbol exactly as sent (not uppercased by router)."""
        state = _make_state()
        pipeline_mock = AsyncMock(return_value=state)
        with (
            patch(_TO_THREAD, new=AsyncMock(return_value=ohlcv)),
            patch(_PIPELINE, new=pipeline_mock),
        ):
            client.post("/ai-strategy-generator/generate-and-build", json={"symbol": "ETHUSDT"})

        assert pipeline_mock.call_args.kwargs["symbol"] == "ETHUSDT"

    def test_pipeline_called_exactly_once(self, client: TestClient, ohlcv: pd.DataFrame):
        state = _make_state()
        pipeline_mock = AsyncMock(return_value=state)
        with (
            patch(_TO_THREAD, new=AsyncMock(return_value=ohlcv)),
            patch(_PIPELINE, new=pipeline_mock),
        ):
            client.post("/ai-strategy-generator/generate-and-build", json={"symbol": "BTCUSDT"})

        pipeline_mock.assert_awaited_once()


# =============================================================================
# Error paths
# =============================================================================


class TestGenerateAndBuildErrorPaths:
    def test_empty_dataframe_returns_404(self, client: TestClient):
        empty_df = pd.DataFrame()
        with patch(_TO_THREAD, new=AsyncMock(return_value=empty_df)):
            resp = client.post("/ai-strategy-generator/generate-and-build", json={"symbol": "UNKNSYM"})

        assert resp.status_code == 404
        assert "No OHLCV" in resp.json()["detail"]

    def test_db_exception_returns_503(self, client: TestClient):
        with patch(_TO_THREAD, new=AsyncMock(side_effect=Exception("sqlite3 disk I/O error"))):
            resp = client.post("/ai-strategy-generator/generate-and-build", json={"symbol": "BTCUSDT"})

        assert resp.status_code == 503
        assert "Failed to load OHLCV" in resp.json()["detail"]

    def test_pipeline_exception_returns_500(self, client: TestClient, ohlcv: pd.DataFrame):
        with (
            patch(_TO_THREAD, new=AsyncMock(return_value=ohlcv)),
            patch(_PIPELINE, new=AsyncMock(side_effect=RuntimeError("LLM timeout"))),
        ):
            resp = client.post("/ai-strategy-generator/generate-and-build", json={"symbol": "BTCUSDT"})

        assert resp.status_code == 500
        assert "Strategy pipeline failed" in resp.json()["detail"]

    def test_none_dataframe_returns_404(self, client: TestClient):
        """asyncio.to_thread returning None is treated as empty."""
        with patch(_TO_THREAD, new=AsyncMock(return_value=None)):
            resp = client.post("/ai-strategy-generator/generate-and-build", json={"symbol": "BTCUSDT"})

        assert resp.status_code == 404

    def test_pipeline_error_message_in_detail(self, client: TestClient, ohlcv: pd.DataFrame):
        with (
            patch(_TO_THREAD, new=AsyncMock(return_value=ohlcv)),
            patch(_PIPELINE, new=AsyncMock(side_effect=ValueError("invalid strategy graph"))),
        ):
            resp = client.post("/ai-strategy-generator/generate-and-build", json={"symbol": "BTCUSDT"})

        assert resp.status_code == 500
        assert "invalid strategy graph" in resp.json()["detail"]


# =============================================================================
# Edge cases
# =============================================================================


class TestGenerateAndBuildEdgeCases:
    def test_no_selected_strategy_name_defaults_to_ai_strategy(self, client: TestClient, ohlcv: pd.DataFrame):
        """If select_best result is missing, strategy_name defaults to 'AI Strategy'."""
        state = AgentState()
        state.execution_path = []
        with (
            patch(_TO_THREAD, new=AsyncMock(return_value=ohlcv)),
            patch(_PIPELINE, new=AsyncMock(return_value=state)),
        ):
            resp = client.post("/ai-strategy-generator/generate-and-build", json={"symbol": "BTCUSDT"})

        assert resp.status_code == 200
        assert resp.json()["strategy_name"] == "AI Strategy"

    def test_no_backtest_result_returns_empty_metrics(self, client: TestClient, ohlcv: pd.DataFrame):
        """If backtest node did not run, backtest_metrics is {}."""
        state = AgentState()
        state.execution_path = []
        with (
            patch(_TO_THREAD, new=AsyncMock(return_value=ohlcv)),
            patch(_PIPELINE, new=AsyncMock(return_value=state)),
        ):
            resp = client.post("/ai-strategy-generator/generate-and-build", json={"symbol": "BTCUSDT"})

        assert resp.json()["backtest_metrics"] == {}

    def test_no_graph_warnings_returns_empty_list(self, client: TestClient, ohlcv: pd.DataFrame):
        state = _make_state(graph_warnings=[])
        with (
            patch(_TO_THREAD, new=AsyncMock(return_value=ohlcv)),
            patch(_PIPELINE, new=AsyncMock(return_value=state)),
        ):
            resp = client.post("/ai-strategy-generator/generate-and-build", json={"symbol": "BTCUSDT"})

        assert resp.json()["graph_warnings"] == []

    def test_no_strategy_graph_in_context_returns_none(self, client: TestClient, ohlcv: pd.DataFrame):
        """If BuildGraphNode did not run, strategy_graph is None."""
        state = AgentState()
        state.execution_path = []
        # context["strategy_graph"] not set → None
        with (
            patch(_TO_THREAD, new=AsyncMock(return_value=ohlcv)),
            patch(_PIPELINE, new=AsyncMock(return_value=state)),
        ):
            resp = client.post("/ai-strategy-generator/generate-and-build", json={"symbol": "BTCUSDT"})

        assert resp.status_code == 200
        assert resp.json()["strategy_graph"] is None

    def test_request_with_empty_body_uses_defaults(self, client: TestClient, ohlcv: pd.DataFrame):
        """Empty body is valid: all fields have defaults. symbol defaults to BTCUSDT."""
        state = _make_state()
        with (
            patch(_TO_THREAD, new=AsyncMock(return_value=ohlcv)),
            patch(_PIPELINE, new=AsyncMock(return_value=state)),
        ):
            resp = client.post("/ai-strategy-generator/generate-and-build", json={})
        # All defaults used — should succeed
        assert resp.status_code == 200
        assert resp.json()["symbol"] == "BTCUSDT"

    def test_multiple_graph_warnings_preserved(self, client: TestClient, ohlcv: pd.DataFrame):
        warnings = [
            "Block 'ma_1': slow period smaller than fast period",
            "Block 'rsi_1': oversold threshold above overbought",
        ]
        state = _make_state(graph_warnings=warnings)
        with (
            patch(_TO_THREAD, new=AsyncMock(return_value=ohlcv)),
            patch(_PIPELINE, new=AsyncMock(return_value=state)),
        ):
            resp = client.post("/ai-strategy-generator/generate-and-build", json={"symbol": "BTCUSDT"})

        assert resp.json()["graph_warnings"] == warnings
        assert len(resp.json()["graph_warnings"]) == 2
