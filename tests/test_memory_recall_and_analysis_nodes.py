"""
Tests for MemoryRecallNode and BacktestAnalysisNode.

Covers:
- MemoryRecallNode: context injection, non-fatal failure, empty memory
- BacktestAnalysisNode: severity classification, root cause detection, suggestions
- GenerateStrategiesNode: memory_context injected into prompts
- RefinementNode: uses backtest_analysis severity/root_cause
- Graph wiring: new nodes present in build_trading_strategy_graph()
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from unittest.mock import patch as _patch

import pytest

from backend.agents.langgraph_orchestrator import AgentState
from backend.agents.trading_strategy_graph import (
    _MAX_DD_PCT,
    _MIN_TRADES,
    BacktestAnalysisNode,
    MemoryRecallNode,
    RefinementNode,
    _backtest_passes,
    _report_node,
    build_trading_strategy_graph,
    run_strategy_pipeline,
)

# =============================================================================
# Helpers
# =============================================================================


def make_state(**ctx) -> AgentState:
    state = AgentState()
    state.context.update({"symbol": "BTCUSDT", "timeframe": "15", **ctx})
    return state


def make_backtest_result(
    trades: int = 10,
    sharpe: float = 1.2,
    dd: float = 10.0,
    win_rate: float = 0.55,
    engine_warnings: list[str] | None = None,
    sample_trades: list[dict] | None = None,
) -> dict[str, Any]:
    return {
        "metrics": {
            "total_trades": trades,
            "sharpe_ratio": sharpe,
            "max_drawdown": dd,
            "win_rate": win_rate,
            "total_return": 15.0,
        },
        "engine_warnings": engine_warnings or [],
        "sample_trades": sample_trades or [],
    }


# =============================================================================
# BacktestAnalysisNode — severity classification
# =============================================================================


class TestBacktestAnalysisNodeSeverity:
    node = BacktestAnalysisNode()

    def _run(self, state: AgentState) -> AgentState:
        return asyncio.run(self.node.execute(state))

    def test_pass(self):
        state = make_state()
        state.set_result("backtest", make_backtest_result(trades=10, sharpe=1.5, dd=8.0))
        out = self._run(state)
        analysis = out.context["backtest_analysis"]
        assert analysis["passed"] is True
        assert analysis["severity"] == "pass"

    def test_near_miss_low_sharpe(self):
        """sharpe just below 0 → near_miss"""
        state = make_state()
        state.set_result("backtest", make_backtest_result(trades=7, sharpe=-0.1, dd=10.0))
        out = self._run(state)
        analysis = out.context["backtest_analysis"]
        assert analysis["passed"] is False
        assert analysis["severity"] == "near_miss"

    def test_near_miss_few_trades(self):
        """trades=4 (just below MIN_TRADES=5) → near_miss"""
        state = make_state()
        state.set_result("backtest", make_backtest_result(trades=4, sharpe=0.5, dd=15.0))
        out = self._run(state)
        analysis = out.context["backtest_analysis"]
        assert analysis["severity"] == "near_miss"

    def test_catastrophic_zero_trades(self):
        state = make_state()
        state.set_result("backtest", make_backtest_result(trades=0, sharpe=-5.0, dd=80.0))
        out = self._run(state)
        analysis = out.context["backtest_analysis"]
        assert analysis["severity"] == "catastrophic"

    def test_catastrophic_extreme_sharpe(self):
        state = make_state()
        state.set_result("backtest", make_backtest_result(trades=8, sharpe=-2.0, dd=20.0))
        out = self._run(state)
        analysis = out.context["backtest_analysis"]
        assert analysis["severity"] == "catastrophic"

    def test_moderate_failure(self):
        state = make_state()
        state.set_result("backtest", make_backtest_result(trades=2, sharpe=-0.8, dd=20.0))
        out = self._run(state)
        analysis = out.context["backtest_analysis"]
        assert analysis["severity"] == "moderate"


# =============================================================================
# BacktestAnalysisNode — root cause detection
# =============================================================================


class TestBacktestAnalysisNodeRootCause:
    node = BacktestAnalysisNode()

    def _run(self, state: AgentState) -> AgentState:
        return asyncio.run(self.node.execute(state))

    def test_direction_mismatch(self):
        state = make_state()
        state.set_result(
            "backtest", make_backtest_result(trades=0, engine_warnings=["[DIRECTION_MISMATCH] long only vs both"])
        )
        out = self._run(state)
        assert out.context["backtest_analysis"]["root_cause"] == "direction_mismatch"

    def test_no_signal(self):
        state = make_state()
        state.set_result("backtest", make_backtest_result(trades=0, engine_warnings=[]))
        out = self._run(state)
        assert out.context["backtest_analysis"]["root_cause"] == "no_signal"

    def test_signal_connectivity(self):
        state = make_state()
        state.set_result(
            "backtest", make_backtest_result(trades=0, engine_warnings=["[NO_TRADES] signals exist but no executions"])
        )
        out = self._run(state)
        assert out.context["backtest_analysis"]["root_cause"] == "signal_connectivity"

    def test_sl_too_tight(self):
        state = make_state()
        state.set_result("backtest", make_backtest_result(trades=12, sharpe=-1.0, win_rate=0.02))
        out = self._run(state)
        assert out.context["backtest_analysis"]["root_cause"] == "sl_too_tight"

    def test_low_activity(self):
        state = make_state()
        state.set_result("backtest", make_backtest_result(trades=2, sharpe=-0.3, dd=5.0, win_rate=0.5))
        out = self._run(state)
        assert out.context["backtest_analysis"]["root_cause"] == "low_activity"

    def test_poor_risk_reward(self):
        state = make_state()
        state.set_result("backtest", make_backtest_result(trades=20, sharpe=-0.5, dd=10.0, win_rate=0.45))
        out = self._run(state)
        assert out.context["backtest_analysis"]["root_cause"] == "poor_risk_reward"


# =============================================================================
# BacktestAnalysisNode — suggestions and output structure
# =============================================================================


class TestBacktestAnalysisNodeOutput:
    node = BacktestAnalysisNode()

    def _run(self, state: AgentState) -> AgentState:
        return asyncio.run(self.node.execute(state))

    def test_direction_mismatch_suggestion_mentions_port(self):
        state = make_state()
        state.set_result("backtest", make_backtest_result(trades=0, engine_warnings=["[DIRECTION_MISMATCH]"]))
        out = self._run(state)
        suggestions = out.context["backtest_analysis"]["suggestions"]
        assert any("long" in s.lower() or "port" in s.lower() for s in suggestions)

    def test_no_signal_suggestion_mentions_connection(self):
        state = make_state()
        state.set_result("backtest", make_backtest_result(trades=0, engine_warnings=[]))
        out = self._run(state)
        suggestions = out.context["backtest_analysis"]["suggestions"]
        assert any("connect" in s.lower() or "port" in s.lower() for s in suggestions)

    def test_result_stored_in_state_results(self):
        state = make_state()
        state.set_result("backtest", make_backtest_result(trades=5, sharpe=0.8, dd=10.0))
        out = self._run(state)
        result = out.get_result("backtest_analysis")
        assert result is not None
        assert "passed" in result
        assert "severity" in result
        assert "root_cause" in result
        assert "metrics_snapshot" in result

    def test_no_backtest_result_does_not_crash(self):
        """BacktestAnalysisNode must handle missing backtest result gracefully."""
        state = make_state()
        out = self._run(state)
        # Should have some result — severity catastrophic due to zeros
        analysis = out.context.get("backtest_analysis", {})
        assert "severity" in analysis

    def test_none_engine_warnings_does_not_crash(self):
        state = make_state()
        state.set_result(
            "backtest",
            {
                "metrics": {"total_trades": 0, "sharpe_ratio": -1.0, "max_drawdown": 50.0, "win_rate": 0.0},
                "engine_warnings": None,
                "sample_trades": None,
            },
        )
        out = self._run(state)
        assert "backtest_analysis" in out.context


# =============================================================================
# MemoryRecallNode
# =============================================================================


class TestMemoryRecallNode:
    node = MemoryRecallNode()

    def _run(self, state: AgentState) -> AgentState:
        return asyncio.run(self.node.execute(state))

    # Lazy import inside execute() — patch the source module class
    _PATCH_PATH = "backend.agents.memory.hierarchical_memory.HierarchicalMemory"

    def test_no_memory_does_not_crash(self):
        """With no HierarchicalMemory data, node runs without injecting memory_context."""
        state = make_state()
        mock_memory = MagicMock()
        mock_memory.async_load = AsyncMock(return_value=0)
        mock_memory.recall = AsyncMock(return_value=[])
        with patch(self._PATCH_PATH, return_value=mock_memory):
            out = self._run(state)
        # memory_context NOT injected when all recall calls return []
        assert "memory_context" not in out.context

    def test_memory_error_is_non_fatal(self):
        """If HierarchicalMemory raises, node still sets result and doesn't crash."""
        state = make_state()
        with patch(self._PATCH_PATH, side_effect=ImportError("no module")):
            out = self._run(state)
        result = out.get_result("memory_recall")
        assert result is not None
        assert result["memory_context_available"] is False

    @pytest.mark.asyncio
    async def test_wins_inject_memory_context(self):
        """When wins are recalled, memory_context is set in state.context."""
        state = make_state()
        mock_win = MagicMock()
        mock_win.content = "RSI(14) strategy on BTCUSDT — Sharpe=1.5, profitable"
        mock_win.importance = 0.7
        mock_win.tags = ["BTCUSDT", "rsi"]
        mock_win.id = "mem_win_1"
        mock_win.metadata = {}

        mock_memory = MagicMock()
        # async_load must return > 0: SELF-RAG skips recall when count == 0
        mock_memory.async_load = AsyncMock(return_value=1)
        mock_memory.recall = AsyncMock(
            side_effect=[
                [mock_win],  # wins
                [],  # failures
                [],  # regime
            ]
        )

        with patch(self._PATCH_PATH, return_value=mock_memory):
            out = await self.node.execute(state)

        assert "memory_context" in out.context
        assert "Prior Knowledge" in out.context["memory_context"]
        assert "past_attempts" in out.context
        assert len(out.context["past_attempts"]) == 1

    @pytest.mark.asyncio
    async def test_failures_inject_avoid_section(self):
        """When failures are recalled, AVOID section appears in memory_context."""
        state = make_state()
        mock_fail = MagicMock()
        mock_fail.content = "MACD crossover failed — 0 trades generated"
        mock_fail.importance = 0.2
        mock_fail.tags = ["BTCUSDT", "macd", "failed"]
        mock_fail.id = "mem_fail_1"
        mock_fail.metadata = {}

        mock_memory = MagicMock()
        # async_load must return > 0: SELF-RAG skips recall when count == 0
        mock_memory.async_load = AsyncMock(return_value=1)
        mock_memory.recall = AsyncMock(
            side_effect=[
                [],  # wins
                [mock_fail],  # failures
                [],  # regime
            ]
        )

        with patch(self._PATCH_PATH, return_value=mock_memory):
            out = await self.node.execute(state)

        assert "memory_context" in out.context
        assert "AVOID" in out.context["memory_context"]

    def test_result_contains_metadata(self):
        """Result must contain memory_context_available, symbol, timeframe, regime."""
        state = make_state(symbol="ETHUSDT", timeframe="60")
        mock_memory = MagicMock()
        mock_memory.async_load = AsyncMock(return_value=0)
        mock_memory.recall = AsyncMock(return_value=[])
        with patch(self._PATCH_PATH, return_value=mock_memory):
            out = self._run(state)
        result = out.get_result("memory_recall")
        assert result["symbol"] == "ETHUSDT"
        assert result["timeframe"] == "60"
        assert "memory_context_available" in result


# =============================================================================
# RefinementNode uses BacktestAnalysisNode output
# =============================================================================


class TestRefinementNodeUsesAnalysis:
    node = RefinementNode()

    def _run(self, state: AgentState) -> AgentState:
        return asyncio.run(self.node.execute(state))

    def test_uses_analysis_suggestions_in_feedback(self):
        """Suggestions from BacktestAnalysisNode appear in refinement_feedback."""
        state = make_state()
        state.set_result("backtest", make_backtest_result(trades=0, sharpe=-2.0, dd=60.0))
        state.context["backtest_analysis"] = {
            "severity": "catastrophic",
            "root_cause": "direction_mismatch",
            "suggestions": ["Connect BOTH long and short ports to strategy node."],
            "metrics_snapshot": {"total_trades": 0, "sharpe_ratio": -2.0, "max_drawdown": 60.0, "win_rate": 0.0},
            "engine_warnings": ["[DIRECTION_MISMATCH]"],
        }
        out = self._run(state)
        feedback = out.context["refinement_feedback"]
        assert "DIRECTION_MISMATCH" in feedback.upper() or "direction" in feedback.lower()
        assert "Connect" in feedback or "long" in feedback.lower()

    def test_near_miss_uses_refine_instruction(self):
        """Near-miss severity uses softer regeneration instruction."""
        state = make_state()
        state.set_result("backtest", make_backtest_result(trades=4, sharpe=-0.1, dd=10.0))
        state.context["backtest_analysis"] = {
            "severity": "near_miss",
            "root_cause": "low_activity",
            "suggestions": ["Try ±20% on indicator period."],
            "metrics_snapshot": {},
            "engine_warnings": [],
        }
        out = self._run(state)
        feedback = out.context["refinement_feedback"]
        assert "NEAR-MISS" in feedback or "Refine" in feedback

    def test_catastrophic_uses_redesign_instruction(self):
        """Catastrophic severity uses stronger regeneration instruction."""
        state = make_state()
        state.set_result("backtest", make_backtest_result(trades=0, sharpe=-5.0, dd=90.0))
        state.context["backtest_analysis"] = {
            "severity": "catastrophic",
            "root_cause": "no_signal",
            "suggestions": [],
            "metrics_snapshot": {},
            "engine_warnings": [],
        }
        out = self._run(state)
        feedback = out.context["refinement_feedback"]
        assert "CATASTROPHIC" in feedback or "DIFFERENT" in feedback

    def test_no_analysis_still_works(self):
        """RefinementNode must work even if BacktestAnalysisNode was not run."""
        state = make_state()
        state.set_result("backtest", make_backtest_result(trades=2, sharpe=-0.5, dd=10.0))
        # No backtest_analysis in context
        out = self._run(state)
        assert "refinement_feedback" in out.context
        assert len(out.context["refinement_feedback"]) > 0


# =============================================================================
# Graph wiring
# =============================================================================


def _edge_pairs(g) -> set[tuple[str, str]]:
    """Extract (source, target) pairs from AgentGraph.edges dict."""
    pairs: set[tuple[str, str]] = set()
    for source, edge_list in g.edges.items():
        for edge in edge_list:
            target = edge.target
            if isinstance(target, list):
                for t in target:
                    pairs.add((source, t))
            else:
                pairs.add((source, target))
    return pairs


class TestGraphWiringWithNewNodes:
    def test_memory_recall_node_in_graph(self):
        g = build_trading_strategy_graph(run_backtest=False, run_debate=False)
        assert "memory_recall" in g.nodes

    def test_memory_recall_wired_before_generate(self):
        g = build_trading_strategy_graph(run_backtest=False, run_debate=False)
        # analyze_market → regime_classifier → memory_recall → grounding → generate_strategies
        edges = _edge_pairs(g)
        assert ("regime_classifier", "memory_recall") in edges
        assert ("memory_recall", "grounding") in edges
        assert ("grounding", "generate_strategies") in edges

    @pytest.mark.skip(reason="Debate node removed from pipeline")
    def test_debate_and_memory_recall_run_in_parallel(self):
        # P3-1: debate and memory_recall ran in parallel after regime_classifier (debate removed)
        pass

    def test_backtest_analysis_node_in_graph(self):
        g = build_trading_strategy_graph(run_backtest=True, run_debate=False)
        assert "backtest_analysis" in g.nodes

    def test_backtest_analysis_wired_after_backtest(self):
        g = build_trading_strategy_graph(run_backtest=True, run_debate=False)
        edges = _edge_pairs(g)
        assert ("backtest", "backtest_analysis") in edges

    def test_conditional_router_on_backtest_analysis(self):
        g = build_trading_strategy_graph(run_backtest=True, run_debate=False)
        # The conditional router should be on backtest_analysis, not backtest
        assert "backtest_analysis" in g.routers
        # backtest should NOT have a conditional router anymore
        assert "backtest" not in g.routers

    def test_all_nodes_present(self):
        g = build_trading_strategy_graph(run_backtest=True)
        expected = {
            "analyze_market",
            "memory_recall",
            "generate_strategies",
            "parse_responses",
            "select_best",
            "build_graph",
            "backtest",
            "backtest_analysis",
            "refine_strategy",
            "optimize_strategy",
            "ml_validation",
            "memory_update",
            "report",
        }
        assert expected.issubset(set(g.nodes.keys()))


# =============================================================================
# Module-level constants and _backtest_passes / _report_node
# =============================================================================


class TestModuleLevelConstants:
    def test_min_trades_value(self):
        assert _MIN_TRADES == 5

    def test_max_dd_value(self):
        assert _MAX_DD_PCT == 30.0

    def test_refinement_node_uses_module_constants(self):
        assert RefinementNode.MIN_TRADES == _MIN_TRADES
        assert RefinementNode.MAX_DD_PCT == _MAX_DD_PCT

    def test_backtest_analysis_node_uses_module_constants(self):
        node = BacktestAnalysisNode()
        assert node.MIN_TRADES == _MIN_TRADES
        assert node.MAX_DD_PCT == _MAX_DD_PCT


class TestBacktestPassesHelper:
    def test_reads_from_backtest_analysis_when_present(self):
        """_backtest_passes uses BacktestAnalysisNode output (no recomputation)."""
        state = make_state()
        state.context["backtest_analysis"] = {"passed": True}
        assert _backtest_passes(state) is True

    def test_reads_false_from_backtest_analysis(self):
        state = make_state()
        state.context["backtest_analysis"] = {"passed": False}
        assert _backtest_passes(state) is False

    def test_fallback_when_no_analysis(self):
        """Without BacktestAnalysisNode, falls back to direct metric computation."""
        state = make_state()
        state.set_result("backtest", make_backtest_result(trades=10, sharpe=1.0, dd=10.0))
        assert _backtest_passes(state) is True

    def test_fallback_fails_correctly(self):
        state = make_state()
        state.set_result("backtest", make_backtest_result(trades=0, sharpe=-1.0, dd=80.0))
        assert _backtest_passes(state) is False


class TestReportNodeIncludesAnalysis:
    def test_report_contains_backtest_analysis_key(self):
        state = make_state()
        analysis = {"passed": True, "severity": "pass", "root_cause": "unknown"}
        state.set_result("backtest_analysis", analysis)
        out = _report_node(state)
        report = out.get_result("report")
        assert "backtest_analysis" in report
        assert report["backtest_analysis"] == analysis

    def test_report_backtest_analysis_none_when_not_run(self):
        """If BacktestAnalysisNode was skipped, key exists but value is None."""
        state = make_state()
        out = _report_node(state)
        report = out.get_result("report")
        assert "backtest_analysis" in report
        assert report["backtest_analysis"] is None

    def test_report_contains_pipeline_metrics_key(self):
        """pipeline_metrics must be in report with cost + timing fields."""
        state = make_state()
        state.total_cost_usd = 0.042
        state.llm_call_count = 7
        state.execution_path = [("analyze_market", 1.2), ("generate_strategies", 3.5)]
        out = _report_node(state)
        report = out.get_result("report")
        assert "pipeline_metrics" in report
        pm = report["pipeline_metrics"]
        assert pm["total_cost_usd"] == pytest.approx(0.042, abs=1e-6)
        assert pm["llm_call_count"] == 7
        assert pm["total_wall_time_s"] == pytest.approx(4.7, abs=0.01)
        assert "analyze_market" in pm["node_timing_s"]


# =============================================================================
# AgentState — cost accumulator
# =============================================================================


class TestAgentStateCostAccumulator:
    def test_initial_cost_is_zero(self):
        state = AgentState()
        assert state.total_cost_usd == 0.0
        assert state.llm_call_count == 0

    def test_record_llm_cost_accumulates(self):
        state = AgentState()
        state.record_llm_cost(0.01)
        state.record_llm_cost(0.02)
        state.record_llm_cost(0.03)
        assert state.total_cost_usd == pytest.approx(0.06, abs=1e-9)
        assert state.llm_call_count == 3

    def test_record_llm_cost_zero_does_not_break(self):
        state = AgentState()
        state.record_llm_cost(0.0)
        assert state.total_cost_usd == 0.0
        assert state.llm_call_count == 1  # call counted even if free


# =============================================================================
# AgentGraph — get_metrics() timing + cost aggregation
# =============================================================================


class TestAgentGraphMetrics:
    def test_get_metrics_without_last_state_omits_timing(self):
        g = build_trading_strategy_graph(run_backtest=False, run_debate=False)
        metrics = g.get_metrics()
        # Without a completed run, timing keys absent
        assert "node_timing_s" not in metrics

    def test_get_metrics_with_last_state_includes_timing_and_cost(self):
        g = build_trading_strategy_graph(run_backtest=False, run_debate=False)
        fake_state = AgentState()
        fake_state.execution_path = [("analyze_market", 1.5), ("memory_recall", 0.3)]
        fake_state.total_cost_usd = 0.055
        fake_state.llm_call_count = 4
        g._last_state = fake_state

        metrics = g.get_metrics()
        assert "node_timing_s" in metrics
        assert metrics["slowest_node"] == "analyze_market"
        assert metrics["total_wall_time_s"] == pytest.approx(1.8, abs=0.01)
        assert metrics["total_cost_usd"] == pytest.approx(0.055, abs=1e-6)
        assert metrics["llm_call_count"] == 4


# =============================================================================
# run_strategy_pipeline — global timeout
# =============================================================================


class TestPipelineTimeout:
    def test_timeout_default_is_300s(self):
        """Default pipeline_timeout parameter value must be 300 seconds."""
        import inspect

        sig = inspect.signature(run_strategy_pipeline)
        assert sig.parameters["pipeline_timeout"].default == 300.0

    def test_timeout_returns_partial_state_with_error(self):
        """When pipeline times out, a partial AgentState is returned with 'pipeline' error."""
        import pandas as pd

        async def _slow_execute(initial_state):
            await asyncio.sleep(10)  # hangs forever in test context
            return initial_state

        # Minimal OHLCV dataframe (won't actually run LLM)
        df = pd.DataFrame(
            {"open": [1.0], "high": [2.0], "low": [0.5], "close": [1.5], "volume": [100.0]},
        )

        async def _run():
            with _patch(
                "backend.agents.langgraph_orchestrator.AgentGraph.execute",
                side_effect=_slow_execute,
            ):
                return await run_strategy_pipeline(
                    symbol="BTCUSDT",
                    timeframe="15",
                    df=df,
                    pipeline_timeout=0.05,  # 50 ms — will always time out
                )

        state = asyncio.run(_run())
        assert any(e["node"] == "pipeline" for e in state.errors), (
            f"Expected pipeline error in state.errors, got: {state.errors}"
        )
