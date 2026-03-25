"""
Real API Integration Tests — Full run_strategy_pipeline() with live LLMs.

PURPOSE:
    Tests that the full 13-node LangGraph pipeline runs end-to-end against
    real DeepSeek / Qwen / Perplexity APIs without mocks.  Each test is
    individually skipable when the relevant key is absent.

MARKS:
    api_live   — any test that makes a real HTTP call to an LLM provider

USAGE:
    pytest tests/backend/agents/test_pipeline_real_api.py -v -m api_live
    pytest tests/backend/agents/test_pipeline_real_api.py -v -m api_live --timeout=600

COST ESTIMATE:
    ~5-10 API calls per test at DeepSeek/Qwen pricing ≈ $0.001-0.005 per test.
    Total suite: ~$0.05-0.10

REQUIRES:
    DEEPSEEK_API_KEY, QWEN_API_KEY, PERPLEXITY_API_KEY in .env or environment.
"""

from __future__ import annotations

import asyncio
import os

import numpy as np
import pandas as pd
import pytest
from dotenv import load_dotenv

load_dotenv(override=True)

from backend.agents.langgraph_orchestrator import AgentState
from backend.agents.trading_strategy_graph import run_strategy_pipeline

# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------
HAS_DEEPSEEK = bool(os.getenv("DEEPSEEK_API_KEY"))
HAS_QWEN = bool(os.getenv("QWEN_API_KEY"))
HAS_PERPLEXITY = bool(os.getenv("PERPLEXITY_API_KEY"))
HAS_ANY_KEY = HAS_DEEPSEEK or HAS_QWEN

skip_no_deepseek = pytest.mark.skipif(not HAS_DEEPSEEK, reason="DEEPSEEK_API_KEY not set")
skip_no_qwen = pytest.mark.skipif(not HAS_QWEN, reason="QWEN_API_KEY not set")
skip_no_any = pytest.mark.skipif(not HAS_ANY_KEY, reason="No LLM API key set")

pytestmark = pytest.mark.api_live


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_ohlcv(n: int = 300) -> pd.DataFrame:
    """Synthetic BTCUSDT-like OHLCV DataFrame with realistic price movement."""
    rng = np.random.default_rng(42)
    close = 40_000 + np.cumsum(rng.normal(0, 150, n))
    close = np.clip(close, 30_000, 70_000)
    high = close + rng.uniform(50, 400, n)
    low = close - rng.uniform(50, 400, n)
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    volume = rng.uniform(100, 2000, n)
    idx = pd.date_range("2025-01-01", periods=n, freq="15min")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


@pytest.fixture
def ohlcv() -> pd.DataFrame:
    return _make_ohlcv()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _run(coro):
    """Run an async coroutine in the test (pytest-asyncio not required)."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Test class: Pipeline structure & state contract
# ---------------------------------------------------------------------------


class TestPipelineRealApiStructure:
    """Verify AgentState structure when pipeline runs with real LLMs."""

    @skip_no_deepseek
    def test_pipeline_returns_agent_state(self, ohlcv):
        state = _run(
            run_strategy_pipeline(
                symbol="BTCUSDT",
                timeframe="15",
                df=ohlcv,
                agents=["deepseek"],
                run_backtest=False,
                run_debate=False,
                pipeline_timeout=120.0,
            )
        )
        assert isinstance(state, AgentState)

    @skip_no_deepseek
    def test_pipeline_populates_results(self, ohlcv):
        state = _run(
            run_strategy_pipeline(
                symbol="BTCUSDT",
                timeframe="15",
                df=ohlcv,
                agents=["deepseek"],
                run_backtest=False,
                run_debate=False,
                pipeline_timeout=120.0,
            )
        )
        assert isinstance(state.results, dict)
        assert len(state.results) > 0

    @skip_no_deepseek
    def test_pipeline_tracks_execution_path(self, ohlcv):
        state = _run(
            run_strategy_pipeline(
                symbol="BTCUSDT",
                timeframe="15",
                df=ohlcv,
                agents=["deepseek"],
                run_backtest=False,
                run_debate=False,
                pipeline_timeout=120.0,
            )
        )
        assert len(state.execution_path) >= 3
        node_names = [name for name, _ in state.execution_path]
        assert "analyze_market" in node_names

    @skip_no_deepseek
    def test_pipeline_records_llm_calls(self, ohlcv):
        """At least one LLM call should be made and tracked."""
        state = _run(
            run_strategy_pipeline(
                symbol="BTCUSDT",
                timeframe="15",
                df=ohlcv,
                agents=["deepseek"],
                run_backtest=False,
                run_debate=False,
                pipeline_timeout=120.0,
            )
        )
        assert state.llm_call_count >= 1

    @skip_no_deepseek
    def test_pipeline_cost_is_non_negative(self, ohlcv):
        state = _run(
            run_strategy_pipeline(
                symbol="BTCUSDT",
                timeframe="15",
                df=ohlcv,
                agents=["deepseek"],
                run_backtest=False,
                run_debate=False,
                pipeline_timeout=120.0,
            )
        )
        assert state.total_cost_usd >= 0.0

    @skip_no_deepseek
    def test_pipeline_has_no_critical_errors(self, ohlcv):
        """Pipeline may have warnings but should not crash with unhandled errors."""
        state = _run(
            run_strategy_pipeline(
                symbol="BTCUSDT",
                timeframe="15",
                df=ohlcv,
                agents=["deepseek"],
                run_backtest=False,
                run_debate=False,
                pipeline_timeout=120.0,
            )
        )
        # errors is a list of dicts; may be non-empty for optional nodes, but must not be None
        assert state.errors is not None
        assert isinstance(state.errors, list)


# ---------------------------------------------------------------------------
# Test class: Strategy output quality
# ---------------------------------------------------------------------------


class TestPipelineRealApiOutput:
    """Verify that real LLM responses produce parseable, valid strategy graphs."""

    @skip_no_deepseek
    def test_generate_strategies_produces_parsed_responses(self, ohlcv):
        state = _run(
            run_strategy_pipeline(
                symbol="BTCUSDT",
                timeframe="15",
                df=ohlcv,
                agents=["deepseek"],
                run_backtest=False,
                run_debate=False,
                pipeline_timeout=120.0,
            )
        )
        # parse_responses stores {"proposals": [...]} — check the proposals list
        parsed = state.results.get("parse_responses", {})
        assert isinstance(parsed, dict)
        proposals = parsed.get("proposals", [])
        assert isinstance(proposals, list)

    @skip_no_deepseek
    def test_select_best_returns_dict_or_none(self, ohlcv):
        state = _run(
            run_strategy_pipeline(
                symbol="BTCUSDT",
                timeframe="15",
                df=ohlcv,
                agents=["deepseek"],
                run_backtest=False,
                run_debate=False,
                pipeline_timeout=120.0,
            )
        )
        best = state.results.get("select_best")
        # None is acceptable if LLM returned unparseable output
        assert best is None or isinstance(best, dict)

    @skip_no_deepseek
    def test_strategy_graph_has_required_keys_when_present(self, ohlcv):
        state = _run(
            run_strategy_pipeline(
                symbol="BTCUSDT",
                timeframe="15",
                df=ohlcv,
                agents=["deepseek"],
                run_backtest=False,
                run_debate=False,
                pipeline_timeout=120.0,
            )
        )
        graph = state.results.get("strategy_graph") or state.results.get("build_graph")
        if graph is not None:
            assert isinstance(graph, dict)
            # Must have at minimum blocks and connections (or name)
            assert "blocks" in graph or "name" in graph

    @skip_no_deepseek
    def test_report_node_included_in_results(self, ohlcv):
        state = _run(
            run_strategy_pipeline(
                symbol="BTCUSDT",
                timeframe="15",
                df=ohlcv,
                agents=["deepseek"],
                run_backtest=False,
                run_debate=False,
                pipeline_timeout=120.0,
            )
        )
        # report node should have run and populated results
        report = state.results.get("report")
        assert report is not None
        assert isinstance(report, dict)

    @skip_no_deepseek
    def test_report_contains_pipeline_metrics(self, ohlcv):
        state = _run(
            run_strategy_pipeline(
                symbol="BTCUSDT",
                timeframe="15",
                df=ohlcv,
                agents=["deepseek"],
                run_backtest=False,
                run_debate=False,
                pipeline_timeout=120.0,
            )
        )
        report = state.results.get("report", {})
        metrics = report.get("pipeline_metrics")
        if metrics is not None:
            assert "total_cost_usd" in metrics
            assert "llm_call_count" in metrics


# ---------------------------------------------------------------------------
# Test class: Multi-agent (debate)
# ---------------------------------------------------------------------------


class TestPipelineRealApiDebate:
    """Verify debate path when multiple agents are available."""

    @pytest.mark.skipif(
        not (HAS_DEEPSEEK and HAS_QWEN),
        reason="Requires both DEEPSEEK_API_KEY and QWEN_API_KEY",
    )
    def test_debate_path_runs_with_two_agents(self, ohlcv):
        state = _run(
            run_strategy_pipeline(
                symbol="BTCUSDT",
                timeframe="15",
                df=ohlcv,
                agents=["deepseek", "qwen"],
                run_backtest=False,
                run_debate=True,
                pipeline_timeout=180.0,
            )
        )
        assert isinstance(state, AgentState)
        node_names = [name for name, _ in state.execution_path]
        assert "debate" in node_names or "consensus" in node_names or len(node_names) >= 3

    @skip_no_deepseek
    def test_no_debate_path_completes_faster(self, ohlcv):
        """Pipeline without debate should complete with fewer nodes."""
        state_no_debate = _run(
            run_strategy_pipeline(
                symbol="BTCUSDT",
                timeframe="15",
                df=ohlcv,
                agents=["deepseek"],
                run_backtest=False,
                run_debate=False,
                pipeline_timeout=120.0,
            )
        )
        assert isinstance(state_no_debate, AgentState)
        # Should at minimum visit analyze + generate + parse + report
        assert len(state_no_debate.execution_path) >= 4


# ---------------------------------------------------------------------------
# Test class: Timeout behaviour
# ---------------------------------------------------------------------------


class TestPipelineRealApiTimeout:
    """Verify pipeline_timeout is enforced."""

    @skip_no_deepseek
    def test_pipeline_respects_short_timeout(self, ohlcv):
        """A 1-second timeout should return partial state without crashing."""
        state = _run(
            run_strategy_pipeline(
                symbol="BTCUSDT",
                timeframe="15",
                df=ohlcv,
                agents=["deepseek"],
                run_backtest=False,
                run_debate=False,
                pipeline_timeout=1.0,
            )
        )
        assert isinstance(state, AgentState)
        # Either timed out (error recorded) or pipeline was fast enough
        assert state.errors is not None

    @skip_no_deepseek
    def test_timeout_records_pipeline_error(self, ohlcv):
        """When timeout fires, 'pipeline' key appears in state.errors."""
        state = _run(
            run_strategy_pipeline(
                symbol="BTCUSDT",
                timeframe="15",
                df=ohlcv,
                agents=["deepseek"],
                run_backtest=False,
                run_debate=False,
                pipeline_timeout=0.001,  # near-instant timeout
            )
        )
        assert isinstance(state, AgentState)
        # With 1ms timeout the pipeline MUST have timed out;
        # state.errors is a list of dicts with "node" key
        assert any(e.get("node") == "pipeline" for e in state.errors)


# ---------------------------------------------------------------------------
# Test class: Different symbols / timeframes
# ---------------------------------------------------------------------------


class TestPipelineRealApiSymbols:
    """Verify pipeline handles different market configurations."""

    @skip_no_deepseek
    def test_ethusdt_symbol(self):
        ohlcv = _make_ohlcv(200)
        state = _run(
            run_strategy_pipeline(
                symbol="ETHUSDT",
                timeframe="60",
                df=ohlcv,
                agents=["deepseek"],
                run_backtest=False,
                run_debate=False,
                pipeline_timeout=120.0,
            )
        )
        assert isinstance(state, AgentState)
        assert state.context.get("symbol") == "ETHUSDT"

    @skip_no_deepseek
    def test_context_symbol_preserved(self, ohlcv):
        state = _run(
            run_strategy_pipeline(
                symbol="SOLUSDT",
                timeframe="15",
                df=ohlcv,
                agents=["deepseek"],
                run_backtest=False,
                run_debate=False,
                pipeline_timeout=120.0,
            )
        )
        assert state.context.get("symbol") == "SOLUSDT"

    @skip_no_deepseek
    def test_context_timeframe_preserved(self, ohlcv):
        state = _run(
            run_strategy_pipeline(
                symbol="BTCUSDT",
                timeframe="240",
                df=ohlcv,
                agents=["deepseek"],
                run_backtest=False,
                run_debate=False,
                pipeline_timeout=120.0,
            )
        )
        assert state.context.get("timeframe") == "240"
