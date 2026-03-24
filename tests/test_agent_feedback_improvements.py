"""
Tests for agent feedback improvements (2026-03-23).

Covers:
- ResponseParser.parse_strategy_with_errors(): structured error messages
- RefinementNode: engine warnings (DIRECTION_MISMATCH, NO_TRADES) in feedback
- RefinementNode: sample trades appended when < 10 trades
- RefinementNode: graph conversion warnings in feedback
- OptimizationNode._apply_agent_hints(): agent hint range narrowing
"""

from __future__ import annotations

import pytest

from backend.agents.langgraph_orchestrator import AgentState
from backend.agents.prompts.response_parser import ResponseParser, StrategyDefinition
from backend.agents.trading_strategy_graph import OptimizationNode, RefinementNode

# =============================================================================
# Helpers
# =============================================================================


def _state_with_backtest(
    trades: int = 2,
    sharpe: float = -0.5,
    max_drawdown: float = 40.0,
    engine_warnings: list[str] | None = None,
    sample_trades: list[dict] | None = None,
    graph_warnings: list[str] | None = None,
    refinement_iteration: int = 0,
) -> AgentState:
    state = AgentState()
    state.context["refinement_iteration"] = refinement_iteration
    if graph_warnings:
        state.context["graph_warnings"] = graph_warnings
    state.set_result(
        "backtest",
        {
            "metrics": {
                "total_trades": trades,
                "sharpe_ratio": sharpe,
                "max_drawdown": max_drawdown,
                "total_return": 1.0,
            },
            "engine_warnings": engine_warnings or [],
            "sample_trades": sample_trades or [],
        },
    )
    return state


# =============================================================================
# ResponseParser.parse_strategy_with_errors
# =============================================================================


class TestParseStrategyWithErrors:
    def setup_method(self):
        self.parser = ResponseParser()

    def test_empty_response_returns_none_and_error(self):
        strategy, errors = self.parser.parse_strategy_with_errors("")
        assert strategy is None
        assert len(errors) == 1
        assert "Empty" in errors[0] or "empty" in errors[0].lower()

    def test_no_json_returns_none_and_error(self):
        strategy, errors = self.parser.parse_strategy_with_errors("Here is my analysis but no JSON")
        assert strategy is None
        assert any("JSON" in e or "json" in e.lower() for e in errors)

    def test_invalid_json_returns_error_message(self):
        strategy, errors = self.parser.parse_strategy_with_errors("```json\n{broken json here\n```")
        assert strategy is None
        assert len(errors) >= 1
        assert any("syntax" in e.lower() or "JSON" in e for e in errors)

    def test_missing_signals_returns_critical_error(self):
        response = '{"strategy_name": "Test", "signals": []}'
        strategy, errors = self.parser.parse_strategy_with_errors(response)
        assert strategy is None
        assert any("signal" in e.lower() for e in errors)

    def test_valid_strategy_returns_no_errors(self):
        response = """{
            "strategy_name": "RSI Test",
            "signals": [{"id": "s1", "type": "RSI", "params": {"period": 14}}]
        }"""
        strategy, errors = self.parser.parse_strategy_with_errors(response)
        assert strategy is not None
        assert isinstance(strategy, StrategyDefinition)
        # No critical errors (may have warnings but is_valid=True)
        critical_errors = [e for e in errors if "[CRITICAL]" in e]
        assert len(critical_errors) == 0

    def test_out_of_range_param_returns_warning(self):
        # RSI period > 100 is outside recommended range
        response = """{
            "strategy_name": "RSI Bad Param",
            "signals": [{"id": "s1", "type": "RSI", "params": {"period": 999, "oversold": 30, "overbought": 70}}]
        }"""
        strategy, errors = self.parser.parse_strategy_with_errors(response)
        # Warnings don't block parsing (is_valid can still be True since only "warning" severity)
        # The errors list should contain the range warning
        assert any("period" in e or "range" in e.lower() for e in errors)

    def test_backward_compat_parse_strategy_still_works(self):
        """parse_strategy() is a wrapper — must return same StrategyDefinition."""
        response = """{
            "strategy_name": "Compat Test",
            "signals": [{"id": "s1", "type": "RSI", "params": {"period": 14}}]
        }"""
        result = self.parser.parse_strategy(response)
        assert result is not None
        assert result.strategy_name == "Compat Test"

    def test_errors_list_is_always_returned(self):
        """Even on success, errors list is returned (may be empty or have warnings)."""
        response = """{
            "strategy_name": "OK",
            "signals": [{"id": "s1", "type": "RSI", "params": {"period": 14}}]
        }"""
        result = self.parser.parse_strategy_with_errors(response)
        assert isinstance(result, tuple)
        assert len(result) == 2
        _strat, _errors = result
        assert isinstance(_errors, list)


# =============================================================================
# RefinementNode — engine warnings in feedback
# =============================================================================


class TestRefinementNodeEngineWarnings:
    @pytest.mark.asyncio
    async def test_direction_mismatch_warning_included(self):
        state = _state_with_backtest(
            trades=0,
            sharpe=-1.0,
            engine_warnings=["[DIRECTION_MISMATCH] direction filter dropped all signals"],
        )
        node = RefinementNode()
        new_state = await node.execute(state)
        feedback = new_state.context.get("refinement_feedback", "")
        assert "DIRECTION_MISMATCH" in feedback
        assert "long" in feedback.lower() and "short" in feedback.lower()

    @pytest.mark.asyncio
    async def test_no_trades_warning_included(self):
        state = _state_with_backtest(
            trades=0,
            sharpe=0.0,
            engine_warnings=["[NO_TRADES] Signals generated but no trades executed"],
        )
        node = RefinementNode()
        new_state = await node.execute(state)
        feedback = new_state.context.get("refinement_feedback", "")
        assert "NO_TRADES" in feedback
        assert "port" in feedback.lower() or "SL/TP" in feedback

    @pytest.mark.asyncio
    async def test_irrelevant_warnings_not_included(self):
        """Only DIRECTION_MISMATCH / NO_TRADES / INVALID_OHLC / BAR_MAGNIFIER are shown."""
        state = _state_with_backtest(
            trades=2,
            sharpe=-0.5,
            engine_warnings=["[SOME_OTHER_WARNING] something happened"],
        )
        node = RefinementNode()
        new_state = await node.execute(state)
        feedback = new_state.context.get("refinement_feedback", "")
        # SOME_OTHER_WARNING should not appear in ENGINE WARNINGS section
        assert "ENGINE WARNINGS" not in feedback

    @pytest.mark.asyncio
    async def test_no_warnings_no_engine_section(self):
        """If no relevant engine warnings, ENGINE WARNINGS block is absent."""
        state = _state_with_backtest(trades=2, sharpe=-0.3)
        node = RefinementNode()
        new_state = await node.execute(state)
        feedback = new_state.context.get("refinement_feedback", "")
        assert "ENGINE WARNINGS" not in feedback


# =============================================================================
# RefinementNode — sample trades in feedback
# =============================================================================


class TestRefinementNodeSampleTrades:
    @pytest.mark.asyncio
    async def test_sample_trades_shown_when_few_trades(self):
        trades_data = [
            {"entry_price": 100.0, "exit_price": 98.0, "pnl": -2.0, "direction": "long"},
            {"entry_price": 102.0, "exit_price": 105.0, "pnl": 3.0, "direction": "long"},
        ]
        state = _state_with_backtest(trades=2, sharpe=-0.3, sample_trades=trades_data)
        node = RefinementNode()
        new_state = await node.execute(state)
        feedback = new_state.context.get("refinement_feedback", "")
        assert "SAMPLE TRADES" in feedback
        assert "100.0" in feedback or "entry" in feedback.lower()

    @pytest.mark.asyncio
    async def test_sample_trades_not_shown_when_many_trades(self):
        """With >= 10 trades, SAMPLE TRADES block is suppressed."""
        trades_data = [{"entry_price": 100.0, "exit_price": 98.0, "pnl": -2.0}]
        state = _state_with_backtest(trades=15, sharpe=-0.1, sample_trades=trades_data)
        node = RefinementNode()
        new_state = await node.execute(state)
        feedback = new_state.context.get("refinement_feedback", "")
        assert "SAMPLE TRADES" not in feedback

    @pytest.mark.asyncio
    async def test_sample_trades_capped_at_five(self):
        """Even if 9 trades exist, we only show first 5 in feedback."""
        trades_data = [{"entry_price": float(100 + i), "exit_price": float(99 + i), "pnl": -1.0} for i in range(9)]
        state = _state_with_backtest(trades=9, sharpe=-0.2, sample_trades=trades_data)
        node = RefinementNode()
        new_state = await node.execute(state)
        feedback = new_state.context.get("refinement_feedback", "")
        if "SAMPLE TRADES" in feedback:
            # Count how many "#N:" entries appear
            import re

            trade_lines = re.findall(r"#\d+:", feedback)
            assert len(trade_lines) <= 5


# =============================================================================
# RefinementNode — graph conversion warnings
# =============================================================================


class TestRefinementNodeGraphWarnings:
    @pytest.mark.asyncio
    async def test_graph_warnings_included(self):
        state = _state_with_backtest(
            trades=0,
            sharpe=-1.0,
            graph_warnings=["Unknown block type: 'custom_indicator'", "Port 'go_long' not found"],
        )
        node = RefinementNode()
        new_state = await node.execute(state)
        feedback = new_state.context.get("refinement_feedback", "")
        assert "GRAPH CONVERSION WARNINGS" in feedback
        assert "Unknown block type" in feedback or "go_long" in feedback

    @pytest.mark.asyncio
    async def test_graph_warnings_capped_at_three(self):
        """Only first 3 graph warnings are shown."""
        state = _state_with_backtest(
            trades=0,
            sharpe=-1.0,
            graph_warnings=[f"Warning {i}" for i in range(6)],
        )
        node = RefinementNode()
        new_state = await node.execute(state)
        feedback = new_state.context.get("refinement_feedback", "")
        # Verify at most 3 of the 6 warnings are present in feedback
        shown = sum(1 for i in range(6) if f"Warning {i}" in feedback)
        assert shown <= 3


# =============================================================================
# RefinementNode — None/missing safety (BUG #3 regression tests)
# =============================================================================


class TestRefinementNodeSafety:
    @pytest.mark.asyncio
    async def test_engine_warnings_none_does_not_crash(self):
        """engine_warnings=None in backtest result must not raise TypeError."""
        state = AgentState()
        state.context["refinement_iteration"] = 0
        state.set_result(
            "backtest",
            {
                "metrics": {"total_trades": 0, "sharpe_ratio": -1.0, "max_drawdown": 50.0, "total_return": -5.0},
                "engine_warnings": None,  # simulate missing/None
                "sample_trades": None,
            },
        )
        node = RefinementNode()
        new_state = await node.execute(state)  # must not raise
        assert new_state is not None

    @pytest.mark.asyncio
    async def test_missing_backtest_result_does_not_crash(self):
        """If 'backtest' result is missing entirely, RefinementNode should still run."""
        state = AgentState()
        state.context["refinement_iteration"] = 0
        # No backtest result set — simulates interrupted pipeline
        node = RefinementNode()
        new_state = await node.execute(state)
        assert new_state is not None

    @pytest.mark.asyncio
    async def test_no_trades_generates_warning_in_feedback(self):
        """When total_trades=0, feedback should reference NO_TRADES or port names."""
        state = _state_with_backtest(
            trades=0,
            sharpe=-1.0,
            engine_warnings=["[NO_TRADES] Signals generated but no trades executed"],
        )
        node = RefinementNode()
        new_state = await node.execute(state)
        feedback = new_state.context.get("refinement_feedback", "")
        assert "NO_TRADES" in feedback or "port" in feedback.lower()

    @pytest.mark.asyncio
    async def test_metrics_dict_passthrough(self):
        """Metrics stored as plain dict (from mocked state) work correctly."""
        state = _state_with_backtest(trades=2, sharpe=-0.5, max_drawdown=25.0)
        node = RefinementNode()
        new_state = await node.execute(state)
        feedback = new_state.context.get("refinement_feedback", "")
        # Should contain trade count and Sharpe from the dict metrics
        assert "2 trades" in feedback or "2" in feedback


# =============================================================================
# OptimizationNode._apply_agent_hints
# =============================================================================


class TestApplyAgentHints:
    def test_hints_narrow_param_range(self):
        param_specs = [
            {"param_key": "block_1.period", "low": 5, "high": 50, "step": 1},
        ]
        hints = {"optimizationParams": {"period": {"enabled": True, "min": 10, "max": 20, "step": 2}}}
        result = OptimizationNode._apply_agent_hints(param_specs, hints)
        assert result[0]["low"] == 10
        assert result[0]["high"] == 20
        assert result[0]["step"] == 2

    def test_hints_leave_unmatched_params_unchanged(self):
        param_specs = [
            {"param_key": "block_1.period", "low": 5, "high": 50, "step": 1},
            {"param_key": "block_2.multiplier", "low": 1.0, "high": 5.0, "step": 0.5},
        ]
        hints = {"optimizationParams": {"period": {"enabled": True, "min": 10, "max": 20, "step": 1}}}
        result = OptimizationNode._apply_agent_hints(param_specs, hints)
        # multiplier should be unchanged
        mult_spec = next(s for s in result if "multiplier" in s["param_key"])
        assert mult_spec["low"] == 1.0
        assert mult_spec["high"] == 5.0

    def test_disabled_hint_not_applied(self):
        param_specs = [
            {"param_key": "period", "low": 5, "high": 50, "step": 1},
        ]
        hints = {"optimizationParams": {"period": {"enabled": False, "min": 10, "max": 20}}}
        result = OptimizationNode._apply_agent_hints(param_specs, hints)
        # Disabled hint — original range kept
        assert result[0]["low"] == 5
        assert result[0]["high"] == 50

    def test_empty_hints_returns_unchanged_specs(self):
        param_specs = [{"param_key": "period", "low": 5, "high": 50, "step": 1}]
        result = OptimizationNode._apply_agent_hints(param_specs, {})
        assert result == param_specs

    def test_simple_ranges_dict_format(self):
        """Fallback format: hints = {"ranges": {"period": [10, 25]}}"""
        param_specs = [{"param_key": "period", "low": 5, "high": 50, "step": 1}]
        hints = {"ranges": {"period": [10, 25]}}
        result = OptimizationNode._apply_agent_hints(param_specs, hints)
        assert result[0]["low"] == 10
        assert result[0]["high"] == 25

    def test_dotted_param_key_matched_by_bare_key(self):
        """'block_1.period' should match hint key 'period'."""
        param_specs = [{"param_key": "block_rsi.period", "low": 5, "high": 50, "step": 1}]
        hints = {"optimizationParams": {"period": {"enabled": True, "min": 7, "max": 21, "step": 1}}}
        result = OptimizationNode._apply_agent_hints(param_specs, hints)
        assert result[0]["low"] == 7
        assert result[0]["high"] == 21
