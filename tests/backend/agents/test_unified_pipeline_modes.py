"""
CP1 — Phase 1: Unified Pipeline Modes

Tests:
  1. AgentState new fields — default values and explicit set
  2. _load_strategy_graph_from_db — success, API error, builder_graph fallback
  3. run_strategy_pipeline() CREATE mode — pipeline_mode="create", no seed_mode
  4. run_strategy_pipeline() OPTIMIZE mode via seed_graph — pipeline_mode="optimize"
  5. run_strategy_pipeline() OPTIMIZE mode via existing_strategy_id — DB load + mode
  6. run_strategy_pipeline() existing_strategy_id DB load failure — fallback to CREATE
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd

from backend.agents.langgraph_orchestrator import AgentState
from backend.agents.trading_strategy_graph import _load_strategy_graph_from_db

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(coro):
    return asyncio.run(coro)


def _make_df(n: int = 100) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    close = 40_000 + np.cumsum(rng.normal(0, 150, n))
    return pd.DataFrame(
        {
            "open": np.roll(close, 1),
            "high": close + 200,
            "low": close - 200,
            "close": close,
            "volume": rng.uniform(100, 1000, n),
        },
        index=pd.date_range("2025-01-01", periods=n, freq="15min"),
    )


_SAMPLE_STRATEGY_RESPONSE = {
    "id": "abc-123",
    "name": "RSI Test Strategy",
    "blocks": [
        {"id": "b1", "type": "rsi", "params": {"period": 14}},
        {"id": "b2", "type": "strategy", "params": {}},
    ],
    "connections": [{"from": "b1", "to": "b2"}],
    "builder_graph": {},
}

_SAMPLE_SEED_GRAPH = {
    "blocks": _SAMPLE_STRATEGY_RESPONSE["blocks"],
    "connections": _SAMPLE_STRATEGY_RESPONSE["connections"],
    "name": "RSI Test Strategy",
    "id": "abc-123",
}


# ---------------------------------------------------------------------------
# 1. AgentState new fields
# ---------------------------------------------------------------------------


class TestAgentStateNewFields:
    def test_pipeline_mode_default_is_create(self):
        state = AgentState()
        assert state.pipeline_mode == "create"

    def test_pipeline_mode_explicit_optimize(self):
        state = AgentState(pipeline_mode="optimize")
        assert state.pipeline_mode == "optimize"

    def test_opt_iterations_default_empty_list(self):
        state = AgentState()
        assert state.opt_iterations == []
        assert isinstance(state.opt_iterations, list)

    def test_opt_insights_default_empty_dict(self):
        state = AgentState()
        assert state.opt_insights == {}
        assert isinstance(state.opt_insights, dict)

    def test_debate_outcome_default_none(self):
        state = AgentState()
        assert state.debate_outcome is None

    def test_new_fields_independent_across_instances(self):
        """Mutable defaults must not be shared between instances."""
        s1 = AgentState()
        s2 = AgentState()
        s1.opt_iterations.append({"iteration": 1})
        s1.opt_insights["key"] = "value"
        assert s2.opt_iterations == []
        assert s2.opt_insights == {}


# ---------------------------------------------------------------------------
# 2. _load_strategy_graph_from_db
# ---------------------------------------------------------------------------


class TestLoadStrategyGraphFromDb:
    def test_success_returns_seed_graph(self):
        with patch(
            "backend.agents.trading_strategy_graph._load_strategy_graph_from_db",
        ):
            pass  # tested via direct call below

        async def _run_async():
            with patch(
                "backend.agents.mcp.tools.strategy_builder.builder_get_strategy",
                new=AsyncMock(return_value=_SAMPLE_STRATEGY_RESPONSE),
            ):
                result = await _load_strategy_graph_from_db("abc-123")
            return result

        result = _run(_run_async())
        assert result is not None
        assert result["name"] == "RSI Test Strategy"
        assert result["id"] == "abc-123"
        assert len(result["blocks"]) == 2
        assert len(result["connections"]) == 1

    def test_api_error_returns_none(self):
        async def _run_async():
            with patch(
                "backend.agents.mcp.tools.strategy_builder.builder_get_strategy",
                new=AsyncMock(return_value={"error": "Not found"}),
            ):
                return await _load_strategy_graph_from_db("bad-id")

        assert _run(_run_async()) is None

    def test_exception_returns_none(self):
        async def _run_async():
            with patch(
                "backend.agents.mcp.tools.strategy_builder.builder_get_strategy",
                new=AsyncMock(side_effect=ConnectionError("DB down")),
            ):
                return await _load_strategy_graph_from_db("any-id")

        assert _run(_run_async()) is None

    def test_fallback_to_builder_graph_blocks_when_top_level_sparse(self):
        """When top-level blocks have no params, fall back to builder_graph.blocks."""
        response = {
            "id": "xyz",
            "name": "Sparse Strategy",
            "blocks": [{"id": "b1", "type": "rsi"}],  # no params key
            "connections": [],
            "builder_graph": {
                "blocks": [{"id": "b1", "type": "rsi", "params": {"period": 21}}],
                "connections": [{"from": "b1", "to": "b2"}],
            },
        }

        async def _run_async():
            with patch(
                "backend.agents.mcp.tools.strategy_builder.builder_get_strategy",
                new=AsyncMock(return_value=response),
            ):
                return await _load_strategy_graph_from_db("xyz")

        result = _run(_run_async())
        assert result is not None
        # Should use builder_graph.blocks (richer)
        assert result["blocks"][0].get("params") == {"period": 21}
        # Should use builder_graph.connections (top-level was empty)
        assert len(result["connections"]) == 1

    def test_name_fallback_when_missing(self):
        response = {"id": "abc-123", "blocks": [], "connections": []}

        async def _run_async():
            with patch(
                "backend.agents.mcp.tools.strategy_builder.builder_get_strategy",
                new=AsyncMock(return_value=response),
            ):
                return await _load_strategy_graph_from_db("abc-123")

        result = _run(_run_async())
        assert result is not None
        assert "abc-123"[:8] in result["name"]


# ---------------------------------------------------------------------------
# 3-6. run_strategy_pipeline() mode detection
# ---------------------------------------------------------------------------


def _make_pipeline_state_spy(expected_pipeline_mode: str, expected_seed_mode: bool):
    """
    Returns a mock graph whose execute() captures the initial AgentState and
    asserts the expected mode fields, then returns the state unchanged.
    """
    captured = {}

    async def fake_execute(state: AgentState) -> AgentState:
        captured["state"] = state
        return state

    mock_graph = MagicMock()
    mock_graph.execute = fake_execute
    return mock_graph, captured


class TestRunStrategyPipelineMode:
    """
    These tests intercept build_trading_strategy_graph() and graph.execute()
    to inspect the initial AgentState without running the full pipeline.
    """

    _df = _make_df()

    def _run_pipeline(self, mock_graph, **kwargs):
        """Patch build_trading_strategy_graph and preflight, then run pipeline."""
        from backend.agents.trading_strategy_graph import run_strategy_pipeline

        async def _inner():
            with (
                patch(
                    "backend.agents.trading_strategy_graph.build_trading_strategy_graph",
                    return_value=mock_graph,
                ),
                patch(
                    "backend.agents.monitoring.provider_health.get_health_monitor",
                    return_value=MagicMock(preflight_check=AsyncMock()),
                ),
            ):
                return await run_strategy_pipeline(
                    symbol="BTCUSDT",
                    timeframe="15",
                    df=self._df,
                    **kwargs,
                )

        return _run(_inner())

    # ── 3. CREATE mode (no existing_strategy_id, no seed_graph) ──────────────

    def test_create_mode_default(self):
        mock_graph, captured = _make_pipeline_state_spy("create", False)
        self._run_pipeline(mock_graph)
        state: AgentState = captured["state"]
        assert state.pipeline_mode == "create"
        assert not state.context.get("seed_mode")

    def test_create_mode_agents_default_to_claude(self):
        mock_graph, captured = _make_pipeline_state_spy("create", False)
        self._run_pipeline(mock_graph)
        assert captured["state"].context["agents"] == ["claude"]

    # ── 4. OPTIMIZE mode via explicit seed_graph ──────────────────────────────

    def test_optimize_mode_via_seed_graph(self):
        mock_graph, captured = _make_pipeline_state_spy("optimize", True)
        self._run_pipeline(mock_graph, seed_graph=_SAMPLE_SEED_GRAPH)
        state: AgentState = captured["state"]
        assert state.pipeline_mode == "optimize"
        assert state.context.get("seed_mode") is True
        assert state.context["seed_strategy_name"] == "RSI Test Strategy"
        assert state.context["strategy_graph"] is _SAMPLE_SEED_GRAPH

    # ── 5. OPTIMIZE mode via existing_strategy_id (DB load success) ──────────

    def test_optimize_mode_via_existing_strategy_id(self):
        mock_graph, captured = _make_pipeline_state_spy("optimize", True)

        async def _inner():
            from backend.agents.trading_strategy_graph import run_strategy_pipeline

            with (
                patch(
                    "backend.agents.trading_strategy_graph.build_trading_strategy_graph",
                    return_value=mock_graph,
                ),
                patch(
                    "backend.agents.monitoring.provider_health.get_health_monitor",
                    return_value=MagicMock(preflight_check=AsyncMock()),
                ),
                patch(
                    "backend.agents.trading_strategy_graph._load_strategy_graph_from_db",
                    new=AsyncMock(return_value=_SAMPLE_SEED_GRAPH),
                ),
            ):
                return await run_strategy_pipeline(
                    symbol="BTCUSDT",
                    timeframe="15",
                    df=self._df,
                    existing_strategy_id="abc-123",
                )

        _run(_inner())
        state: AgentState = captured["state"]
        assert state.pipeline_mode == "optimize"
        assert state.context.get("seed_mode") is True
        assert state.context["existing_strategy_id"] == "abc-123"
        assert state.context["strategy_graph"]["name"] == "RSI Test Strategy"

    # ── 6. DB load failure → fallback to CREATE mode ─────────────────────────

    def test_optimize_mode_db_failure_falls_back_to_create(self):
        mock_graph, captured = _make_pipeline_state_spy("create", False)

        async def _inner():
            from backend.agents.trading_strategy_graph import run_strategy_pipeline

            with (
                patch(
                    "backend.agents.trading_strategy_graph.build_trading_strategy_graph",
                    return_value=mock_graph,
                ),
                patch(
                    "backend.agents.monitoring.provider_health.get_health_monitor",
                    return_value=MagicMock(preflight_check=AsyncMock()),
                ),
                patch(
                    "backend.agents.trading_strategy_graph._load_strategy_graph_from_db",
                    new=AsyncMock(return_value=None),  # DB load failed
                ),
            ):
                return await run_strategy_pipeline(
                    symbol="BTCUSDT",
                    timeframe="15",
                    df=self._df,
                    existing_strategy_id="bad-id",
                )

        _run(_inner())
        state: AgentState = captured["state"]
        # Fallback: no strategy loaded → create mode, no seed_mode
        assert state.pipeline_mode == "create"
        assert not state.context.get("seed_mode")

    # ── existing_strategy_id stored in context ───────────────────────────────

    def test_existing_strategy_id_stored_in_context(self):
        mock_graph, captured = _make_pipeline_state_spy("optimize", True)

        async def _inner():
            from backend.agents.trading_strategy_graph import run_strategy_pipeline

            with (
                patch(
                    "backend.agents.trading_strategy_graph.build_trading_strategy_graph",
                    return_value=mock_graph,
                ),
                patch(
                    "backend.agents.monitoring.provider_health.get_health_monitor",
                    return_value=MagicMock(preflight_check=AsyncMock()),
                ),
                patch(
                    "backend.agents.trading_strategy_graph._load_strategy_graph_from_db",
                    new=AsyncMock(return_value=_SAMPLE_SEED_GRAPH),
                ),
            ):
                return await run_strategy_pipeline(
                    symbol="ETHUSDT",
                    timeframe="60",
                    df=self._df,
                    existing_strategy_id="abc-123",
                )

        _run(_inner())
        ctx = captured["state"].context
        assert ctx["existing_strategy_id"] == "abc-123"
        assert ctx["symbol"] == "ETHUSDT"
        assert ctx["timeframe"] == "60"
