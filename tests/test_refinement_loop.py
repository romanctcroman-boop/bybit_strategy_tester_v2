"""
Tests for the iterative refinement loop in trading_strategy_graph.py.

Covers:
- RefinementNode.execute(): state mutation, feedback injection, stale result clearing
- _backtest_passes(): acceptance criteria logic
- _should_refine(): guards on iteration count
- build_trading_strategy_graph() wiring: RefinementNode is present, edges correct
- Full loop: simulate 2-iteration refinement until pass
"""

from __future__ import annotations

import asyncio

import pytest

from backend.agents.langgraph_orchestrator import AgentState
from backend.agents.trading_strategy_graph import (
    BacktestAnalysisNode,
    RefinementNode,
    WalkForwardValidationNode,
    _backtest_passes,
    _should_refine,
    build_trading_strategy_graph,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _state_with_backtest(
    trades: int,
    sharpe: float,
    max_drawdown: float,
    refinement_iteration: int = 0,
) -> AgentState:
    state = AgentState()
    state.context["refinement_iteration"] = refinement_iteration
    state.set_result(
        "backtest",
        {
            "metrics": {
                "total_trades": trades,
                "sharpe_ratio": sharpe,
                "max_drawdown": max_drawdown,
                "total_return": 5.0,
            }
        },
    )
    return state


# ---------------------------------------------------------------------------
# _backtest_passes
# ---------------------------------------------------------------------------


class TestBacktestPasses:
    def test_all_criteria_met_returns_true(self):
        state = _state_with_backtest(trades=10, sharpe=1.5, max_drawdown=15.0)
        assert _backtest_passes(state) is True

    def test_too_few_trades_returns_false(self):
        state = _state_with_backtest(trades=3, sharpe=1.5, max_drawdown=15.0)
        assert _backtest_passes(state) is False

    def test_negative_sharpe_returns_false(self):
        state = _state_with_backtest(trades=10, sharpe=-0.1, max_drawdown=15.0)
        assert _backtest_passes(state) is False

    def test_zero_sharpe_returns_false(self):
        state = _state_with_backtest(trades=10, sharpe=0.0, max_drawdown=15.0)
        assert _backtest_passes(state) is False

    def test_high_drawdown_returns_false(self):
        state = _state_with_backtest(trades=10, sharpe=1.5, max_drawdown=30.0)
        assert _backtest_passes(state) is False

    def test_drawdown_exactly_at_limit_fails(self):
        # 30% is >= MAX_DD_PCT so it fails
        state = _state_with_backtest(trades=10, sharpe=1.5, max_drawdown=30.0)
        assert _backtest_passes(state) is False

    def test_no_backtest_result_returns_false(self):
        state = AgentState()
        assert _backtest_passes(state) is False

    def test_exactly_min_trades_passes(self):
        state = _state_with_backtest(trades=5, sharpe=0.1, max_drawdown=29.9)
        assert _backtest_passes(state) is True


# ---------------------------------------------------------------------------
# _should_refine
# ---------------------------------------------------------------------------


class TestShouldRefine:
    def test_failed_no_iterations_should_refine(self):
        state = _state_with_backtest(trades=1, sharpe=-1.0, max_drawdown=50.0, refinement_iteration=0)
        assert _should_refine(state) is True

    def test_failed_iteration_2_should_refine(self):
        # MAX_REFINEMENTS=3, so iteration 2 still has one more attempt left
        state = _state_with_backtest(trades=1, sharpe=-1.0, max_drawdown=50.0, refinement_iteration=2)
        assert _should_refine(state) is True

    def test_failed_max_iterations_no_refine(self):
        # Iteration 3 >= MAX_REFINEMENTS, should NOT refine
        state = _state_with_backtest(trades=1, sharpe=-1.0, max_drawdown=50.0, refinement_iteration=3)
        assert _should_refine(state) is False

    def test_passed_should_not_refine(self):
        state = _state_with_backtest(trades=10, sharpe=1.5, max_drawdown=15.0, refinement_iteration=0)
        assert _should_refine(state) is False

    def test_poor_risk_reward_with_good_signals_skips_refinement(self):
        """poor_risk_reward + ≥50 signals + ≥5 trades → skip refinement (go to optimizer)."""
        state = _state_with_backtest(trades=87, sharpe=-0.09, max_drawdown=35.0, refinement_iteration=0)
        # Set analysis diagnosis
        state.context["backtest_analysis"] = {"root_cause": "poor_risk_reward", "passed": False}
        # Add signal counts to backtest result
        bt = state.get_result("backtest") or {}
        bt["signal_long_count"] = 186
        bt["signal_short_count"] = 154
        state.set_result("backtest", bt)
        assert _should_refine(state) is False  # skip — optimizer handles this better

    def test_poor_risk_reward_sparse_signals_still_refines(self):
        """poor_risk_reward but only 3 total signals → refinement still needed."""
        state = _state_with_backtest(trades=5, sharpe=-0.1, max_drawdown=20.0, refinement_iteration=0)
        state.context["backtest_analysis"] = {"root_cause": "poor_risk_reward", "passed": False}
        bt = state.get_result("backtest") or {}
        bt["signal_long_count"] = 2
        bt["signal_short_count"] = 1
        state.set_result("backtest", bt)
        assert _should_refine(state) is True  # refine — signal generation is the real issue

    def test_poor_risk_reward_no_signal_counts_still_refines(self):
        """poor_risk_reward with no signal_count info → conservative: still refine."""
        state = _state_with_backtest(trades=10, sharpe=-0.5, max_drawdown=20.0, refinement_iteration=0)
        state.context["backtest_analysis"] = {"root_cause": "poor_risk_reward", "passed": False}
        # No signal_long_count / signal_short_count in backtest result
        assert _should_refine(state) is True  # conservative: refine when unknown


# ---------------------------------------------------------------------------
# RefinementNode.execute()
# ---------------------------------------------------------------------------


class TestRefinementNode:
    @pytest.fixture
    def node(self):
        return RefinementNode()

    @pytest.mark.asyncio
    async def test_increments_iteration(self, node):
        state = _state_with_backtest(trades=2, sharpe=-0.5, max_drawdown=40.0, refinement_iteration=0)
        result = await node.execute(state)
        assert result.context["refinement_iteration"] == 1

    @pytest.mark.asyncio
    async def test_increments_from_existing_iteration(self, node):
        state = _state_with_backtest(trades=2, sharpe=-0.5, max_drawdown=40.0, refinement_iteration=2)
        result = await node.execute(state)
        assert result.context["refinement_iteration"] == 3

    @pytest.mark.asyncio
    async def test_injects_refinement_feedback(self, node):
        state = _state_with_backtest(trades=2, sharpe=-0.5, max_drawdown=40.0)
        result = await node.execute(state)
        feedback = result.context.get("refinement_feedback", "")
        assert "REFINEMENT FEEDBACK" in feedback
        assert "too few trades" in feedback
        assert "negative Sharpe" in feedback

    @pytest.mark.asyncio
    async def test_feedback_mentions_high_drawdown(self, node):
        state = _state_with_backtest(trades=10, sharpe=-0.1, max_drawdown=35.0)
        result = await node.execute(state)
        feedback = result.context.get("refinement_feedback", "")
        assert "excessive drawdown" in feedback

    @pytest.mark.asyncio
    async def test_feedback_mentions_few_trades_only(self, node):
        # Only trades fail — drawdown and sharpe are fine
        state = _state_with_backtest(trades=1, sharpe=1.0, max_drawdown=10.0)
        result = await node.execute(state)
        feedback = result.context.get("refinement_feedback", "")
        assert "too few trades" in feedback
        assert "negative Sharpe" not in feedback
        assert "excessive drawdown" not in feedback

    @pytest.mark.asyncio
    async def test_clears_stale_parse_results(self, node):
        state = _state_with_backtest(trades=2, sharpe=-0.5, max_drawdown=40.0)
        # Seed some stale results that should be cleared
        state.set_result("parse_responses", {"proposals": ["stale"]})
        state.set_result("select_best", {"selected": "stale"})
        state.set_result("build_graph", {"blocks": 5})
        state.set_result("backtest", {"metrics": {"total_trades": 2}})

        result = await node.execute(state)

        assert result.get_result("parse_responses") is None
        assert result.get_result("select_best") is None
        assert result.get_result("build_graph") is None

    @pytest.mark.asyncio
    async def test_stores_own_result(self, node):
        state = _state_with_backtest(trades=2, sharpe=-0.5, max_drawdown=40.0)
        result = await node.execute(state)
        refinement_result = result.get_result("refine_strategy")
        assert refinement_result is not None
        assert refinement_result["iteration"] == 1
        assert isinstance(refinement_result["failures"], list)
        assert len(refinement_result["failures"]) > 0

    @pytest.mark.asyncio
    async def test_feedback_contains_previous_metrics(self, node):
        state = _state_with_backtest(trades=3, sharpe=-0.7, max_drawdown=25.0)
        result = await node.execute(state)
        feedback = result.context.get("refinement_feedback", "")
        assert "3 trades" in feedback
        assert "-0.7" in feedback or "−0.7" in feedback or "Sharpe=-0.70" in feedback

    @pytest.mark.asyncio
    async def test_adds_message_to_state(self, node):
        state = _state_with_backtest(trades=1, sharpe=-1.0, max_drawdown=50.0)
        result = await node.execute(state)
        messages = [m["content"] for m in result.messages if m.get("agent") == "refine_strategy"]
        assert len(messages) == 1
        assert "Refinement" in messages[0]


# ---------------------------------------------------------------------------
# Graph wiring
# ---------------------------------------------------------------------------


class TestGraphWiring:
    def test_refinement_node_present_when_backtest_enabled(self):
        graph = build_trading_strategy_graph(run_backtest=True)
        assert "refine_strategy" in graph.nodes

    def test_refinement_node_absent_without_backtest(self):
        graph = build_trading_strategy_graph(run_backtest=False)
        assert "refine_strategy" not in graph.nodes

    def test_conditional_router_registered_on_backtest_analysis(self):
        graph = build_trading_strategy_graph(run_backtest=True)
        # Router now sits on backtest_analysis (after BacktestAnalysisNode was added)
        assert "backtest_analysis" in graph.routers

    def test_refine_routes_to_generate_strategies(self):
        graph = build_trading_strategy_graph(run_backtest=True)
        # RefinementNode has a direct edge back to generate_strategies
        refine_edges = graph.edges.get("refine_strategy", [])
        targets = [e.target for e in refine_edges]
        assert "generate_strategies" in targets

    def test_optimization_is_default_route(self):
        # backtest_analysis → optimize_strategy in both WF and no-WF paths
        # (WF now runs AFTER optimizer, so optimizer is always the next step after backtest_analysis)
        graph = build_trading_strategy_graph(run_backtest=True)
        router = graph.routers["backtest_analysis"]
        assert router.default_route == "optimize_strategy"

        graph_no_wf = build_trading_strategy_graph(run_backtest=True, run_wf_validation=False)
        router_no_wf = graph_no_wf.routers["backtest_analysis"]
        assert router_no_wf.default_route == "optimize_strategy"

    def test_optimization_node_present(self):
        graph = build_trading_strategy_graph(run_backtest=True)
        assert "optimize_strategy" in graph.nodes

    def test_optimization_leads_to_wf_or_analysis_debate(self):
        # With WF enabled: optimize_strategy → wf_validation → analysis_debate
        graph = build_trading_strategy_graph(run_backtest=True)
        opt_edges = graph.edges.get("optimize_strategy", [])
        targets = [e.target for e in opt_edges]
        assert "wf_validation" in targets  # WF validates optimized params

        # Without WF: optimize_strategy → analysis_debate directly
        graph_no_wf = build_trading_strategy_graph(run_backtest=True, run_wf_validation=False)
        opt_edges_no_wf = graph_no_wf.edges.get("optimize_strategy", [])
        targets_no_wf = [e.target for e in opt_edges_no_wf]
        assert "analysis_debate" in targets_no_wf

    def test_analysis_debate_leads_to_ml_validation(self):
        graph = build_trading_strategy_graph(run_backtest=True)
        debate_edges = graph.edges.get("analysis_debate", [])
        targets = [e.target for e in debate_edges]
        assert "ml_validation" in targets

    def test_ml_validation_leads_to_memory_update(self):
        graph = build_trading_strategy_graph(run_backtest=True)
        ml_edges = graph.edges.get("ml_validation", [])
        targets = [e.target for e in ml_edges]
        assert "memory_update" in targets


# ---------------------------------------------------------------------------
# Integration: simulate multi-iteration refinement
# ---------------------------------------------------------------------------


class TestRefinementIntegration:
    """Simulate the refinement loop without real LLM or backtest calls."""

    @pytest.mark.asyncio
    async def test_router_picks_refine_on_failure(self):
        from backend.agents.langgraph_orchestrator import ConditionalRouter

        state = _state_with_backtest(trades=1, sharpe=-1.0, max_drawdown=50.0, refinement_iteration=0)
        graph = build_trading_strategy_graph(run_backtest=True)
        router: ConditionalRouter = graph.routers["backtest_analysis"]
        next_node = router.get_next_node(state)
        assert next_node == "refine_strategy"

    @pytest.mark.asyncio
    async def test_router_picks_optimize_on_pass(self):
        from backend.agents.langgraph_orchestrator import ConditionalRouter

        # Passing path: backtest_analysis → optimize_strategy → wf_validation
        state = _state_with_backtest(trades=10, sharpe=1.5, max_drawdown=15.0, refinement_iteration=0)
        graph = build_trading_strategy_graph(run_backtest=True)
        router: ConditionalRouter = graph.routers["backtest_analysis"]
        next_node = router.get_next_node(state)
        assert next_node == "optimize_strategy"  # optimizer first

        # wf_validation router defaults to analysis_debate (WF validates optimized params)
        wf_router: ConditionalRouter = graph.routers["wf_validation"]
        next_node = wf_router.get_next_node(state)
        assert next_node == "analysis_debate"

    @pytest.mark.asyncio
    async def test_router_picks_optimize_on_max_iterations(self):
        from backend.agents.langgraph_orchestrator import ConditionalRouter

        # Failed strategy, max iterations reached → optimize_strategy (then wf_validation)
        state = _state_with_backtest(trades=1, sharpe=-1.0, max_drawdown=50.0, refinement_iteration=3)
        graph = build_trading_strategy_graph(run_backtest=True)
        router: ConditionalRouter = graph.routers["backtest_analysis"]
        next_node = router.get_next_node(state)
        assert next_node == "optimize_strategy"  # max iter → no refine → optimizer

    @pytest.mark.asyncio
    async def test_two_iterations_then_pass(self):
        """Simulate: fail × 2, then pass. RefinementNode increments counter correctly."""
        node = RefinementNode()

        # Iteration 0 → 1
        state = _state_with_backtest(trades=2, sharpe=-0.5, max_drawdown=40.0, refinement_iteration=0)
        state = await node.execute(state)
        assert state.context["refinement_iteration"] == 1
        assert _should_refine(state) is True  # still has iterations left

        # Simulate another bad backtest result
        state.set_result(
            "backtest",
            {"metrics": {"total_trades": 3, "sharpe_ratio": -0.2, "max_drawdown": 35.0, "total_return": -1.0}},
        )

        # Iteration 1 → 2
        state = await node.execute(state)
        assert state.context["refinement_iteration"] == 2
        assert _should_refine(state) is True

        # Simulate passing backtest
        state.set_result(
            "backtest",
            {"metrics": {"total_trades": 8, "sharpe_ratio": 1.2, "max_drawdown": 18.0, "total_return": 12.0}},
        )
        assert _should_refine(state) is False
        assert _backtest_passes(state) is True


# ---------------------------------------------------------------------------
# WalkForwardValidationNode: acceptance thresholds
# ---------------------------------------------------------------------------


class TestWFThresholds:
    """Unit tests for WalkForwardValidationNode.WF_RATIO_THRESHOLD / WF_MIN_ABS_SHARPE."""

    def test_ratio_threshold_value(self):
        assert WalkForwardValidationNode.WF_RATIO_THRESHOLD == 0.5

    def test_abs_sharpe_floor_value(self):
        assert WalkForwardValidationNode.WF_MIN_ABS_SHARPE == 0.5

    def test_ratio_passes(self):
        """wf=0.6, is=1.0 → ratio=0.6 ≥ 0.5 → passes by ratio."""
        node = WalkForwardValidationNode()
        ratio = 0.6 / 1.0
        ratio_passes = ratio >= node.WF_RATIO_THRESHOLD
        abs_passes = 0.6 >= node.WF_MIN_ABS_SHARPE
        assert ratio_passes is True
        assert (1.0 > 0 and 0.6 > 0 and (ratio_passes or abs_passes)) is True

    def test_abs_floor_passes_when_ratio_fails(self):
        """Run #14 scenario: wf=0.514, is=1.805 → ratio=0.285 < 0.5, but abs≥0.5 → passes."""
        node = WalkForwardValidationNode()
        wf_sharpe, is_sharpe = 0.514, 1.805
        ratio = wf_sharpe / is_sharpe          # 0.285
        ratio_passes = ratio >= node.WF_RATIO_THRESHOLD   # False
        abs_passes = wf_sharpe >= node.WF_MIN_ABS_SHARPE  # True
        passed = is_sharpe > 0 and wf_sharpe > 0 and (ratio_passes or abs_passes)
        assert ratio_passes is False
        assert abs_passes is True
        assert passed is True

    def test_both_fail_when_wf_sharpe_low(self):
        """wf=0.3, is=2.0 → ratio=0.15 < 0.5 AND abs=0.3 < 0.5 → fails."""
        node = WalkForwardValidationNode()
        wf_sharpe, is_sharpe = 0.3, 2.0
        ratio = wf_sharpe / is_sharpe
        ratio_passes = ratio >= node.WF_RATIO_THRESHOLD
        abs_passes = wf_sharpe >= node.WF_MIN_ABS_SHARPE
        passed = is_sharpe > 0 and wf_sharpe > 0 and (ratio_passes or abs_passes)
        assert ratio_passes is False
        assert abs_passes is False
        assert passed is False

    def test_negative_wf_sharpe_always_fails(self):
        """wf=-0.1, is=0.5 → negative OOS → fails regardless."""
        node = WalkForwardValidationNode()
        wf_sharpe, is_sharpe = -0.1, 0.5
        ratio = wf_sharpe / is_sharpe if is_sharpe > 0 else 0.0
        ratio_passes = ratio >= node.WF_RATIO_THRESHOLD
        abs_passes = wf_sharpe >= node.WF_MIN_ABS_SHARPE
        passed = is_sharpe > 0 and wf_sharpe > 0 and (ratio_passes or abs_passes)
        assert passed is False


# ---------------------------------------------------------------------------
# E2E: BacktestAnalysisNode → RefinementNode pipeline integration
# ---------------------------------------------------------------------------


def _make_backtest_result(
    trades: int = 0,
    sharpe: float = -5.0,
    dd: float = 90.0,
    win_rate: float = 0.0,
    engine_warnings: list[str] | None = None,
) -> dict:
    return {
        "metrics": {
            "total_trades": trades,
            "sharpe_ratio": sharpe,
            "max_drawdown": dd,
            "win_rate": win_rate,
            "total_return": -50.0,
        },
        "engine_warnings": engine_warnings or [],
        "sample_trades": [],
    }


class TestRefinementLoopEndToEnd:
    """Integration: BacktestAnalysisNode → RefinementNode working together."""

    _analysis_node = BacktestAnalysisNode()
    _refine_node = RefinementNode()

    def _run(self, coro) -> AgentState:
        return asyncio.run(coro)

    def _run_both(self, state: AgentState) -> AgentState:
        """Run BacktestAnalysisNode then RefinementNode on the same state."""
        state = self._run(self._analysis_node.execute(state))
        state = self._run(self._refine_node.execute(state))
        return state

    def _state(self, **kw) -> AgentState:
        s = AgentState()
        s.context.update({"symbol": "BTCUSDT", "timeframe": "15"})
        s.set_result("backtest", _make_backtest_result(**kw))
        return s

    # ── Severity × feedback instruction ──────────────────────────────────────

    def test_catastrophic_feedback_contains_redesign_keyword(self):
        """trades=0, sharpe=-5 → severity=catastrophic → 'DIFFERENT' or 'redesign' in feedback."""
        state = self._state(trades=0, sharpe=-5.0, dd=90.0)
        state = self._run_both(state)
        feedback = state.context["refinement_feedback"]
        assert "CATASTROPHIC" in feedback or "DIFFERENT" in feedback.upper()

    def test_near_miss_feedback_contains_soft_instruction(self):
        """trades=4, sharpe=-0.1 → severity=near_miss → soft adjustment hint."""
        state = self._state(trades=4, sharpe=-0.1, dd=10.0)
        state = self._run_both(state)
        feedback = state.context["refinement_feedback"]
        assert "NEAR-MISS" in feedback or "Refine" in feedback

    def test_direction_mismatch_feedback_mentions_port_names(self):
        """DIRECTION_MISMATCH warning → feedback explains long/short port fix."""
        state = self._state(trades=0, engine_warnings=["[DIRECTION_MISMATCH]"])
        state = self._run_both(state)
        feedback = state.context["refinement_feedback"]
        assert "long" in feedback.lower() or "short" in feedback.lower()
        assert "port" in feedback.lower() or "DIRECTION" in feedback.upper()

    def test_no_signal_feedback_mentions_connectivity(self):
        """0 trades, no warnings → root_cause=no_signal → feedback mentions entry/connection."""
        state = self._state(trades=0, sharpe=-1.0, engine_warnings=[])
        state = self._run_both(state)
        feedback = state.context["refinement_feedback"]
        assert "entry" in feedback.lower() or "connect" in feedback.lower() or "port" in feedback.lower()

    # ── State mutation ────────────────────────────────────────────────────────

    def test_refinement_clears_stale_state_keys(self):
        """After RefinementNode, stale parse/select/build/backtest results are cleared."""
        state = self._state(trades=0, sharpe=-2.0, dd=60.0)
        for key in ("parse_responses", "select_best", "build_graph", "backtest"):
            state.set_result(key, {"dummy": True})
        state = self._run_both(state)
        for key in ("parse_responses", "select_best", "build_graph"):
            assert key not in state.results, f"Stale key '{key}' should have been cleared"

    def test_iteration_counter_increments_correctly(self):
        """Each RefinementNode.execute() call increments refinement_iteration by 1."""
        state = self._state(trades=0, sharpe=-1.0, dd=50.0)
        assert state.context.get("refinement_iteration", 0) == 0

        state = self._run_both(state)
        assert state.context["refinement_iteration"] == 1

        state.set_result("backtest", _make_backtest_result(trades=0, sharpe=-1.0, dd=50.0))
        state = self._run(self._refine_node.execute(state))
        assert state.context["refinement_iteration"] == 2

    def test_iteration_label_in_feedback(self):
        """Feedback string includes iteration number and max."""
        state = self._state(trades=0, sharpe=-3.0, dd=80.0)
        state = self._run_both(state)
        feedback = state.context["refinement_feedback"]
        assert "1/" in feedback and str(RefinementNode.MAX_REFINEMENTS) in feedback

    # ── Loop exhaustion ───────────────────────────────────────────────────────

    def test_three_iterations_exhaust_loop(self):
        """After 3 RefinementNode runs, _should_refine() returns False."""
        state = self._state(trades=0, sharpe=-2.0, dd=70.0)
        for _ in range(RefinementNode.MAX_REFINEMENTS):
            state.set_result("backtest", _make_backtest_result(trades=0, sharpe=-2.0, dd=70.0))
            state = self._run(self._refine_node.execute(state))
        assert state.context["refinement_iteration"] == RefinementNode.MAX_REFINEMENTS
        assert _should_refine(state) is False

    # ── Root-cause consistency ────────────────────────────────────────────────

    def test_analysis_root_cause_reflected_in_feedback_header(self):
        """Root cause from BacktestAnalysisNode appears in the RefinementNode header."""
        state = self._state(trades=0, engine_warnings=["[NO_TRADES] signals exist"])
        state = self._run(self._analysis_node.execute(state))
        root_cause = state.context["backtest_analysis"]["root_cause"]  # signal_connectivity
        state = self._run(self._refine_node.execute(state))
        feedback = state.context["refinement_feedback"]
        # Root cause should appear (uppercased, underscores replaced with spaces)
        assert root_cause.upper().replace("_", " ") in feedback
