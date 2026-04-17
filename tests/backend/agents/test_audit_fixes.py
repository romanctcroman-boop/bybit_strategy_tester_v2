"""
Tests for the 2026-04-17 audit fixes (9.5/10 → 10/10 push).

Covers:
  • AgentState.check_llm_budget()          — pre-flight budget check
  • BacktestAnalysisNode RiskVetoGuard     — hard-safety integration
  • make_sqlite_checkpointer WAL+timeout   — concurrency hardening
  • PromptLogger._connect() WAL+timeout    — concurrency hardening
"""

from __future__ import annotations

import contextlib
import os
import sqlite3
import tempfile
from unittest.mock import patch

import pytest

from backend.agents.langgraph_orchestrator import (
    AgentState,
    BudgetExceededError,
    make_sqlite_checkpointer,
)

# =============================================================================
# Pre-flight budget check
# =============================================================================


class TestCheckLLMBudgetPreFlight:
    def test_check_raises_when_already_over_budget(self):
        state = AgentState(max_cost_usd=0.10)
        state.total_cost_usd = 0.15  # simulate already over
        with pytest.raises(BudgetExceededError):
            state.check_llm_budget()

    def test_check_raises_when_projected_over_budget(self):
        state = AgentState(max_cost_usd=1.00)
        state.total_cost_usd = 0.90
        # 0.90 + 0.20 = 1.10 > 1.00
        with pytest.raises(BudgetExceededError):
            state.check_llm_budget(estimated_cost_usd=0.20)

    def test_check_passes_when_under_budget(self):
        state = AgentState(max_cost_usd=1.00)
        state.total_cost_usd = 0.10
        state.check_llm_budget(estimated_cost_usd=0.20)  # 0.30 < 1.00 → OK

    def test_check_noop_when_no_budget_limit(self):
        state = AgentState(max_cost_usd=0.0)  # unlimited
        state.total_cost_usd = 1_000_000.0
        state.check_llm_budget(estimated_cost_usd=1_000_000.0)  # must not raise

    def test_check_sets_budget_exceeded_flag(self):
        state = AgentState(max_cost_usd=0.10)
        state.total_cost_usd = 0.05
        with contextlib.suppress(BudgetExceededError):
            state.check_llm_budget(estimated_cost_usd=0.20)
        assert state.budget_exceeded is True

    def test_check_does_NOT_mutate_total_cost(self):
        state = AgentState(max_cost_usd=10.0)
        state.total_cost_usd = 0.5
        state.check_llm_budget(estimated_cost_usd=0.3)
        # pre-flight must not spend money
        assert state.total_cost_usd == 0.5
        assert state.llm_call_count == 0


# =============================================================================
# SQLite checkpointer — WAL + busy_timeout hardening
# =============================================================================


class TestCheckpointerConcurrency:
    def test_checkpointer_enables_wal_mode(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db_path = os.path.join(tmp, "cp_wal.db")
            _ = make_sqlite_checkpointer(db_path=db_path)
            # Verify WAL was enabled
            with sqlite3.connect(db_path) as conn:
                mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
                assert mode.lower() == "wal", f"Expected WAL journal mode, got {mode}"

    def test_checkpointer_accepts_timeout_arg(self):
        # Regression test: connect() must be called with timeout to avoid
        # "database is locked" under concurrent pipelines.
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db_path = os.path.join(tmp, "cp_to.db")
            cp = make_sqlite_checkpointer(db_path=db_path)
            state = AgentState()
            state.visited_nodes = ["a", "b"]
            cp(state, "node_x")  # must not raise
            # Table should have one row
            with sqlite3.connect(db_path) as conn:
                count = conn.execute("SELECT COUNT(*) FROM pipeline_checkpoints").fetchone()[0]
                assert count == 1


# =============================================================================
# PromptLogger — WAL + busy_timeout
# =============================================================================


class TestPromptLoggerConcurrency:
    def test_prompt_logger_enables_wal(self):
        from backend.agents.prompts.prompt_logger import PromptLogger

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db_path = os.path.join(tmp, "prompts.db")
            _ = PromptLogger(db_path=db_path)
            with sqlite3.connect(db_path) as conn:
                mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
                assert mode.lower() == "wal"

    def test_prompt_logger_connect_helper_sets_busy_timeout(self):
        from backend.agents.prompts.prompt_logger import PromptLogger

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db_path = os.path.join(tmp, "prompts_to.db")
            logger_obj = PromptLogger(db_path=db_path)
            conn = logger_obj._connect()
            try:
                # busy_timeout is in ms; we set 10000
                bt = conn.execute("PRAGMA busy_timeout").fetchone()[0]
                assert bt == 10000
            finally:
                conn.close()


# =============================================================================
# BacktestAnalysisNode — RiskVetoGuard integration
# =============================================================================


class TestBacktestAnalysisNodeVetoIntegration:
    """Verify the 2026-04-17 RiskVetoGuard hook inside BacktestAnalysisNode.

    These tests exercise the node in isolation by feeding it a state with a
    synthetic backtest result and asserting the veto branch populates the
    analysis dict correctly.
    """

    @pytest.mark.asyncio
    async def test_veto_block_populates_analysis(self):
        from backend.agents.langgraph_orchestrator import AgentState
        from backend.agents.trading_strategy_graph import BacktestAnalysisNode

        node = BacktestAnalysisNode()
        state = AgentState()
        # Simulate a backtest with catastrophic drawdown (triggers DD veto)
        state.set_result(
            "backtest",
            {
                "metrics": {
                    "total_trades": 20,
                    "sharpe_ratio": 0.2,
                    "max_drawdown": 95.0,  # 95% drawdown → catastrophic
                    "win_rate": 0.4,
                    "open_trades": 0,
                    "long_trades": 20,
                    "short_trades": 0,
                },
                "warnings": [],
            },
        )
        state.set_result(
            "consensus",
            {"agreement_score": 0.9},
        )
        state.context["initial_capital"] = 10_000.0

        result = await node.execute(state)
        analysis = result.context.get("backtest_analysis")
        assert analysis is not None, "analysis must be populated"
        # With 95% DD, veto should fire and force passed=False
        assert analysis["passed"] is False
        assert "veto" in analysis, "veto decision must be attached"

    @pytest.mark.asyncio
    async def test_veto_skipped_when_metrics_healthy(self):
        from backend.agents.langgraph_orchestrator import AgentState
        from backend.agents.trading_strategy_graph import BacktestAnalysisNode

        node = BacktestAnalysisNode()
        state = AgentState()
        state.set_result(
            "backtest",
            {
                "metrics": {
                    "total_trades": 120,
                    "sharpe_ratio": 1.8,
                    "max_drawdown": 12.0,  # healthy
                    "win_rate": 0.58,
                    "open_trades": 0,
                    "long_trades": 70,
                    "short_trades": 50,
                },
                "warnings": [],
            },
        )
        state.set_result("consensus", {"agreement_score": 0.85})
        state.context["initial_capital"] = 10_000.0

        result = await node.execute(state)
        analysis = result.context.get("backtest_analysis")
        assert analysis is not None
        assert "veto" in analysis
        veto_dict = analysis["veto"]
        # Healthy metrics → no veto reasons / is_vetoed False
        assert veto_dict.get("is_vetoed") is False, f"expected no veto, got {veto_dict}"

    @pytest.mark.asyncio
    async def test_veto_error_is_captured_not_silent(self):
        """If RiskVetoGuard import or check fails, the error must be recorded in state.errors."""
        from backend.agents.langgraph_orchestrator import AgentState
        from backend.agents.trading_strategy_graph import BacktestAnalysisNode

        node = BacktestAnalysisNode()
        state = AgentState()
        state.set_result(
            "backtest",
            {
                "metrics": {
                    "total_trades": 50,
                    "sharpe_ratio": 1.0,
                    "max_drawdown": 10.0,
                    "win_rate": 0.55,
                },
                "warnings": [],
            },
        )
        state.context["initial_capital"] = 10_000.0

        # Patch get_risk_veto_guard to raise so we hit the except branch
        with patch(
            "backend.agents.consensus.risk_veto_guard.get_risk_veto_guard",
            side_effect=RuntimeError("synthetic failure"),
        ):
            result = await node.execute(state)

        # Error must be logged (not silently swallowed) — stored via state.add_error
        assert result.errors, "veto failure must be captured in state.errors"
        assert any(
            e.get("error_type") == "RuntimeError" and "synthetic" in e.get("error_message", "") for e in result.errors
        ), f"expected RuntimeError('synthetic ...') in errors, got {result.errors}"
