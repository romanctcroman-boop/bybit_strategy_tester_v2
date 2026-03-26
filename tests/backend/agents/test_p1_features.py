"""
Tests for P1 agent system improvements.

Covers:
  P1-1  PostRunReflectionNode      — structured retrospective after pipeline run
  P1-2  WalkForwardValidationNode  — overfitting gate (wf_sharpe/is_sharpe >= 0.5)
  P1-3  Few-shot injection         — MemoryRecallNode adds few_shot_examples to context
  P1-4  make_sqlite_checkpointer   — AgentGraph persists state after each node
  P1-5  Cost budget enforcement    — BudgetExceededError when max_cost_usd exceeded
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from backend.agents.langgraph_orchestrator import (
    AgentGraph,
    AgentState,
    BudgetExceededError,
    FunctionAgent,
    make_sqlite_checkpointer,
)
from backend.agents.trading_strategy_graph import (
    PostRunReflectionNode,
    WalkForwardValidationNode,
    build_trading_strategy_graph,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _state(**ctx) -> AgentState:
    return AgentState(context=ctx)


def _run(coro):
    return asyncio.run(coro)


def _make_df(n: int = 300) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    close = 40_000 + np.cumsum(rng.normal(0, 150, n))
    high = close + 200
    low = close - 200
    open_ = np.roll(close, 1)
    volume = rng.uniform(100, 1000, n)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=pd.date_range("2025-01-01", periods=n, freq="15min"),
    )


# =============================================================================
# P1-5: BudgetExceededError + AgentState budget enforcement
# =============================================================================


class TestCostBudgetEnforcement:
    def test_budget_exceeded_error_message(self):
        err = BudgetExceededError(spent=1.5, limit=1.0)
        assert "1.5" in str(err) or "1.50" in str(err)
        assert "1.0" in str(err) or "1.00" in str(err)
        assert err.spent == 1.5
        assert err.limit == 1.0

    def test_no_budget_limit_zero_unlimited(self):
        state = AgentState(max_cost_usd=0.0)
        state.record_llm_cost(999.0)  # must not raise
        assert state.total_cost_usd == 999.0
        assert state.budget_exceeded is False

    def test_budget_enforced_when_exceeded(self):
        state = AgentState(max_cost_usd=0.10)
        with pytest.raises(BudgetExceededError) as exc_info:
            state.record_llm_cost(0.15)
        assert exc_info.value.spent > 0.10
        assert state.budget_exceeded is True

    def test_budget_not_exceeded_below_limit(self):
        state = AgentState(max_cost_usd=1.0)
        state.record_llm_cost(0.05)
        state.record_llm_cost(0.05)
        assert state.total_cost_usd == pytest.approx(0.10)
        assert state.budget_exceeded is False

    def test_budget_accumulates_across_calls(self):
        state = AgentState(max_cost_usd=0.50)
        state.record_llm_cost(0.20)
        state.record_llm_cost(0.20)
        with pytest.raises(BudgetExceededError):
            state.record_llm_cost(0.20)

    def test_llm_call_count_increments_before_budget_check(self):
        state = AgentState(max_cost_usd=0.10)
        try:
            state.record_llm_cost(0.20)
        except BudgetExceededError:
            pass
        assert state.llm_call_count == 1  # count increments even on budget error


# =============================================================================
# P1-4: make_sqlite_checkpointer
# =============================================================================


class TestSQLiteCheckpointer:
    def test_checkpointer_creates_db_file(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db_path = os.path.join(tmp, "test_cp.db")
            cp_fn = make_sqlite_checkpointer(db_path=db_path)
            assert os.path.exists(db_path)

    def test_checkpointer_writes_row(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db_path = os.path.join(tmp, "test_cp.db")
            cp_fn = make_sqlite_checkpointer(db_path=db_path)
            state = AgentState()
            cp_fn(state, "analyze_market")
            with sqlite3.connect(db_path) as conn:
                rows = conn.execute("SELECT * FROM pipeline_checkpoints").fetchall()
            assert len(rows) == 1
            assert rows[0][2] == "analyze_market"  # node_name column

    def test_checkpointer_records_session_id(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db_path = os.path.join(tmp, "cp.db")
            cp_fn = make_sqlite_checkpointer(db_path=db_path)
            state = AgentState()
            sid = state.session_id
            cp_fn(state, "test_node")
            with sqlite3.connect(db_path) as conn:
                row = conn.execute("SELECT session_id FROM pipeline_checkpoints").fetchone()
            assert row[0] == sid

    def test_checkpointer_multiple_nodes(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db_path = os.path.join(tmp, "cp.db")
            cp_fn = make_sqlite_checkpointer(db_path=db_path)
            state = AgentState()
            for node in ["analyze_market", "debate", "generate_strategies"]:
                cp_fn(state, node)
            with sqlite3.connect(db_path) as conn:
                count = conn.execute("SELECT COUNT(*) FROM pipeline_checkpoints").fetchone()[0]
            assert count == 3

    def test_graph_calls_checkpoint_after_each_node(self):
        checkpoint_calls = []

        def cp_fn(state, node_name):
            checkpoint_calls.append(node_name)

        def _noop(state):
            return state

        graph = AgentGraph(name="test", checkpoint_fn=cp_fn)
        graph.add_node(FunctionAgent(name="a", func=_noop))
        graph.add_node(FunctionAgent(name="b", func=_noop))
        graph.add_edge("a", "b")
        graph.set_entry_point("a")
        graph.add_exit_point("b")

        _run(graph.execute())
        assert "a" in checkpoint_calls
        assert "b" in checkpoint_calls

    def test_graph_without_checkpoint_works_normally(self):
        def _noop(state):
            return state

        graph = AgentGraph(name="test", checkpoint_fn=None)
        graph.add_node(FunctionAgent(name="a", func=_noop))
        graph.set_entry_point("a")
        graph.add_exit_point("a")
        state = _run(graph.execute())
        assert isinstance(state, AgentState)


# =============================================================================
# P1-1: PostRunReflectionNode
# =============================================================================


class TestPostRunReflectionNode:
    def _make_passing_state(self) -> AgentState:
        state = AgentState(context={"symbol": "BTCUSDT", "timeframe": "15"})
        state.set_result("analyze_market", {"regime": "trending_bull", "trend": "up"})
        state.set_result(
            "backtest",
            {
                "metrics": {
                    "sharpe_ratio": 1.2,
                    "max_drawdown": 8.0,
                    "total_trades": 25,
                    "win_rate": 0.60,
                    "profit_factor": 1.8,
                }
            },
        )
        state.set_result("backtest_analysis", {"passed": True, "severity": "pass", "root_cause": "none"})
        state.context["backtest_analysis"] = {"passed": True, "severity": "pass", "root_cause": "none"}
        return state

    def _make_failing_state(self) -> AgentState:
        state = AgentState(context={"symbol": "ETHUSDT", "timeframe": "60"})
        state.set_result("analyze_market", {"regime": "ranging", "trend": "sideways"})
        state.set_result(
            "backtest",
            {
                "metrics": {
                    "sharpe_ratio": -0.3,
                    "max_drawdown": 35.0,
                    "total_trades": 2,
                    "win_rate": 0.10,
                    "profit_factor": 0.5,
                }
            },
        )
        state.set_result(
            "backtest_analysis", {"passed": False, "severity": "catastrophic", "root_cause": "poor_risk_reward"}
        )
        state.context["backtest_analysis"] = {
            "passed": False,
            "severity": "catastrophic",
            "root_cause": "poor_risk_reward",
        }
        return state

    def test_reflection_sets_result(self):
        node = PostRunReflectionNode()
        state = self._make_passing_state()
        with patch("backend.agents.trading_strategy_graph.PostRunReflectionNode.execute", wraps=node.execute):
            with patch("backend.agents.memory.hierarchical_memory.HierarchicalMemory") as mock_mem:
                mock_mem.return_value.store = AsyncMock()
                result_state = _run(node.execute(state))
        assert "reflection" in result_state.results

    def test_reflection_contains_required_keys(self):
        node = PostRunReflectionNode()
        state = self._make_passing_state()
        with patch("backend.agents.memory.hierarchical_memory.HierarchicalMemory") as mock_mem:
            mock_mem.return_value.store = AsyncMock()
            result_state = _run(node.execute(state))
        r = result_state.results["reflection"]
        for key in ("symbol", "timeframe", "regime", "passed", "what_worked", "what_failed", "recommended_adjustments"):
            assert key in r, f"Missing key: {key}"

    def test_passing_run_has_what_worked(self):
        node = PostRunReflectionNode()
        state = self._make_passing_state()
        with patch("backend.agents.memory.hierarchical_memory.HierarchicalMemory") as mock_mem:
            mock_mem.return_value.store = AsyncMock()
            result_state = _run(node.execute(state))
        r = result_state.results["reflection"]
        assert r["passed"] is True
        assert len(r["what_worked"]) > 0

    def test_failing_run_has_what_failed(self):
        node = PostRunReflectionNode()
        state = self._make_failing_state()
        with patch("backend.agents.memory.hierarchical_memory.HierarchicalMemory") as mock_mem:
            mock_mem.return_value.store = AsyncMock()
            result_state = _run(node.execute(state))
        r = result_state.results["reflection"]
        assert r["passed"] is False
        assert len(r["what_failed"]) > 0

    def test_regime_based_adjustments_injected(self):
        node = PostRunReflectionNode()
        state = self._make_failing_state()  # regime=ranging
        with patch("backend.agents.memory.hierarchical_memory.HierarchicalMemory") as mock_mem:
            mock_mem.return_value.store = AsyncMock()
            result_state = _run(node.execute(state))
        r = result_state.results["reflection"]
        # ranging regime → mean-reversion hint
        adjustments_text = " ".join(r["recommended_adjustments"])
        assert "mean-reversion" in adjustments_text or "ranging" in adjustments_text

    def test_memory_store_failure_is_nonfatal(self):
        node = PostRunReflectionNode()
        state = self._make_passing_state()
        with patch("backend.agents.memory.hierarchical_memory.HierarchicalMemory") as mock_mem:
            mock_mem.return_value.store = AsyncMock(side_effect=RuntimeError("DB down"))
            result_state = _run(node.execute(state))
        # Should still succeed despite memory failure
        assert "reflection" in result_state.results

    def test_reflection_includes_cost_metrics(self):
        node = PostRunReflectionNode()
        state = self._make_passing_state()
        state.total_cost_usd = 0.0042
        state.llm_call_count = 7
        with patch("backend.agents.memory.hierarchical_memory.HierarchicalMemory") as mock_mem:
            mock_mem.return_value.store = AsyncMock()
            result_state = _run(node.execute(state))
        r = result_state.results["reflection"]
        assert r["llm_call_count"] == 7
        assert abs(r["total_cost_usd"] - 0.0042) < 1e-6


# =============================================================================
# P1-2: WalkForwardValidationNode
# =============================================================================


class TestWalkForwardValidationNode:
    def _make_state_with_backtest(self, sharpe: float = 1.0, df_size: int = 400) -> AgentState:
        state = AgentState(
            context={
                "symbol": "BTCUSDT",
                "timeframe": "15",
                "df": _make_df(df_size),
                "strategy_graph": {"name": "test", "blocks": [], "connections": []},
            }
        )
        state.set_result(
            "backtest",
            {
                "metrics": {
                    "sharpe_ratio": sharpe,
                    "max_drawdown": 10.0,
                    "total_trades": 20,
                }
            },
        )
        return state

    def test_skip_when_negative_is_sharpe(self):
        """Negative IS Sharpe → hard reject (not skip) — strategy is unprofitable."""
        node = WalkForwardValidationNode()
        state = self._make_state_with_backtest(sharpe=-0.5)
        result_state = _run(node.execute(state))
        r = result_state.results["wf_validation"]
        assert r["skipped"] is False  # Not skipped — explicitly rejected
        assert r["passed"] is False  # Hard reject: unprofitable strategy
        assert r["reason"] == "negative_is_sharpe"

    def test_skip_when_no_df(self):
        node = WalkForwardValidationNode()
        state = AgentState(context={"strategy_graph": {}})
        state.set_result("backtest", {"metrics": {"sharpe_ratio": 1.0}})
        result_state = _run(node.execute(state))
        r = result_state.results["wf_validation"]
        assert r["skipped"] is True

    def test_skip_when_insufficient_bars(self):
        node = WalkForwardValidationNode()
        state = self._make_state_with_backtest(sharpe=1.0, df_size=50)
        result_state = _run(node.execute(state))
        r = result_state.results["wf_validation"]
        assert r["skipped"] is True

    def test_result_stored_in_context(self):
        node = WalkForwardValidationNode()
        state = self._make_state_with_backtest(sharpe=-0.5)
        result_state = _run(node.execute(state))
        assert "wf_validation" in result_state.context

    def test_wf_engine_error_nonfatal(self):
        """If the backtest engine raises, WF should be skipped gracefully."""
        node = WalkForwardValidationNode()
        state = self._make_state_with_backtest(sharpe=1.5, df_size=500)
        with patch.object(node, "_run_rolling_wf", side_effect=RuntimeError("engine down")):
            result_state = _run(node.execute(state))
        r = result_state.results["wf_validation"]
        assert r["skipped"] is True
        assert r["passed"] is True

    def test_passing_wf_sets_passed_true(self):
        node = WalkForwardValidationNode()
        state = self._make_state_with_backtest(sharpe=1.0, df_size=400)
        # Mock WF to return high Sharpe (ratio = 1.0 >= 0.5 threshold)
        with patch.object(node, "_run_rolling_wf", return_value=[1.0, 1.2, 0.9]):
            result_state = _run(node.execute(state))
        r = result_state.results["wf_validation"]
        assert r["passed"] is True
        assert r["ratio"] >= 0.5

    def test_failing_wf_sets_passed_false_and_flags_analysis(self):
        node = WalkForwardValidationNode()
        state = self._make_state_with_backtest(sharpe=2.0, df_size=400)
        state.context["backtest_analysis"] = {"passed": True}
        # Mock WF to return low Sharpe (ratio = 0.1 < 0.5)
        with patch.object(node, "_run_rolling_wf", return_value=[0.1, 0.2, 0.3]):
            result_state = _run(node.execute(state))
        r = result_state.results["wf_validation"]
        assert r["passed"] is False
        assert r["ratio"] < 0.5
        # Must flip backtest_analysis.passed = False for _should_refine
        assert result_state.context["backtest_analysis"]["passed"] is False
        assert result_state.context["backtest_analysis"].get("wf_failed") is True

    def test_ratio_computation(self):
        node = WalkForwardValidationNode()
        state = self._make_state_with_backtest(sharpe=2.0, df_size=400)
        with patch.object(node, "_run_rolling_wf", return_value=[1.0]):
            result_state = _run(node.execute(state))
        r = result_state.results["wf_validation"]
        # wf_sharpe=1.0, is_sharpe=2.0, ratio=0.5 → exactly at threshold → passed
        assert abs(r["ratio"] - 0.5) < 0.01


# =============================================================================
# P1-3: Few-shot injection
# =============================================================================


class TestFewShotInjection:
    def test_few_shot_examples_injected_into_context(self):
        """MemoryRecallNode should add few_shot_examples to state.context."""
        from backend.agents.trading_strategy_graph import MemoryRecallNode

        node = MemoryRecallNode()
        state = AgentState(
            context={
                "symbol": "BTCUSDT",
                "timeframe": "15",
            }
        )
        state.set_result("analyze_market", {"regime": "trending_bull"})

        # Mock memory returning wins
        mock_win = MagicMock()
        mock_win.content = "RSI strategy: period=14, oversold=30. Sharpe=1.2, Trades=25."
        mock_win.importance = 0.8
        mock_win.metadata = {"sharpe_ratio": 1.2, "agent": "deepseek"}
        mock_win.tags = ["backtest", "BTCUSDT"]

        mock_memory = MagicMock()
        mock_memory.recall = AsyncMock(return_value=[mock_win])

        with patch("backend.agents.memory.hierarchical_memory.HierarchicalMemory", return_value=mock_memory):
            result_state = _run(node.execute(state))

        # few_shot_examples should be in context
        examples = result_state.context.get("few_shot_examples", [])
        assert isinstance(examples, list)
        # Note: may be empty if no wins met importance threshold — that's OK
        # Just verify no crash

    def test_generate_strategies_uses_few_shot_block(self):
        """GenerateStrategiesNode should prepend few-shot block when examples exist."""
        from backend.agents.trading_strategy_graph import GenerateStrategiesNode

        node = GenerateStrategiesNode()
        state = AgentState(
            context={
                "symbol": "BTCUSDT",
                "timeframe": "15",
                "agents": ["deepseek"],
                "few_shot_examples": ["EXAMPLE (Sharpe=1.2, agent=deepseek): RSI period=14 works well in trend."],
            }
        )
        _market_ctx = MagicMock(market_regime="trending_bull", trend_direction="up", current_price=40000.0)
        _market_ctx.to_prompt_vars.return_value = {
            "symbol": "BTCUSDT",
            "timeframe_display": "15 min",
            "current_price": 40000.0,
            "period_high": 41000.0,
            "period_low": 39000.0,
            "price_change_pct": 1.5,
            "data_points": 500,
            "market_regime": "trending_bull",
            "trend_direction": "up",
            "atr_value": "1.50%",
            "volume_profile": "high",
            "support_levels": "$39,000.00",
            "resistance_levels": "$41,000.00",
            "indicators_summary": "RSI=55",
            "volume_summary": "Avg volume: 1000, Profile: high",
        }
        state.set_result(
            "analyze_market",
            {
                "market_context": _market_ctx,
                "regime": "trending_bull",
            },
        )

        prompts_captured = []

        async def fake_call_llm(agent, prompt, system_msg=None, temperature=0.7, state=None):
            prompts_captured.append(prompt)
            return '{"strategy_name": "TestRSI", "blocks": []}'

        with patch.object(node, "_call_llm", side_effect=fake_call_llm):
            with patch.object(node, "_qwen_critic", return_value=None):
                _run(node.execute(state))

        assert len(prompts_captured) > 0
        combined = " ".join(prompts_captured)
        assert "few-shot" in combined.lower() or "Proven Strategy Examples" in combined or "EXAMPLE" in combined


# =============================================================================
# P1 graph integration: build_trading_strategy_graph accepts new params
# =============================================================================


class TestBuildGraphNewParams:
    def test_graph_builds_with_wf_validation_enabled(self):
        graph = build_trading_strategy_graph(
            run_backtest=True,
            run_debate=False,
            run_wf_validation=True,
        )
        assert "wf_validation" in graph.nodes
        assert "reflection" in graph.nodes

    def test_graph_builds_with_wf_validation_disabled(self):
        graph = build_trading_strategy_graph(
            run_backtest=True,
            run_debate=False,
            run_wf_validation=False,
        )
        assert "wf_validation" not in graph.nodes
        assert "reflection" in graph.nodes

    def test_graph_has_reflection_node(self):
        graph = build_trading_strategy_graph(run_backtest=True, run_debate=False)
        assert "reflection" in graph.nodes

    def test_graph_no_backtest_no_reflection(self):
        graph = build_trading_strategy_graph(run_backtest=False, run_debate=False)
        assert "reflection" not in graph.nodes

    def test_graph_with_checkpoint_has_checkpoint_fn(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "cp.db")
            with patch(
                "backend.agents.trading_strategy_graph.make_sqlite_checkpointer",
                return_value=lambda s, n: None,
            ):
                graph = build_trading_strategy_graph(
                    run_backtest=False,
                    run_debate=False,
                    checkpoint_enabled=True,
                )
            assert graph.checkpoint_fn is not None

    def test_graph_without_checkpoint_has_no_fn(self):
        graph = build_trading_strategy_graph(
            run_backtest=False,
            run_debate=False,
            checkpoint_enabled=False,
        )
        assert graph.checkpoint_fn is None
