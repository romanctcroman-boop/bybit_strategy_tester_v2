"""
Tests for Feedback Loop (Task 4.2)

Tests PromptImprovementEngine and FeedbackLoop.
"""

from __future__ import annotations

import pytest

from backend.agents.self_improvement.feedback_loop import (
    FeedbackEntry,
    FeedbackLoop,
    FeedbackLoopResult,
    PromptImprovementEngine,
)

# =============================================================================
# Test FeedbackEntry
# =============================================================================


class TestFeedbackEntry:
    """Test FeedbackEntry dataclass."""

    def test_create_entry(self):
        """Create a basic entry."""
        entry = FeedbackEntry(
            id="fb_test",
            iteration=1,
            strategy_name="rsi_v1",
            strategy_type="rsi",
            strategy_params={"period": 14},
            backtest_metrics={"sharpe_ratio": 1.2},
            fitness_score=65.0,
            reflection_summary=["Good risk management"],
            improvement_actions=["Tighten stop loss"],
            prompt_adjustments={"emphasis_areas": ["risk_management"]},
        )
        assert entry.id == "fb_test"
        assert entry.fitness_score == 65.0

    def test_to_dict(self):
        """to_dict should serialize properly."""
        entry = FeedbackEntry(
            id="fb_test",
            iteration=1,
            strategy_name="rsi_v1",
            strategy_type="rsi",
            strategy_params={"period": 14},
            backtest_metrics={"sharpe_ratio": 1.2345},
            fitness_score=65.0,
            reflection_summary=["lesson1"],
            improvement_actions=["action1"],
            prompt_adjustments={},
        )
        d = entry.to_dict()
        assert d["id"] == "fb_test"
        assert d["backtest_metrics"]["sharpe_ratio"] == 1.2345
        assert "created_at" in d


class TestFeedbackLoopResult:
    """Test FeedbackLoopResult dataclass."""

    def test_create_result(self):
        """Create basic result."""
        result = FeedbackLoopResult(
            loop_id="loop_test",
            total_iterations=3,
            best_fitness=72.5,
        )
        assert result.loop_id == "loop_test"
        assert result.best_fitness == 72.5
        assert result.converged is False

    def test_to_dict(self):
        """to_dict should serialize properly."""
        result = FeedbackLoopResult(
            loop_id="loop_test",
            total_iterations=3,
            best_fitness=72.5,
            fitness_history=[50.0, 65.0, 72.5],
            improvement_trend=11.25,
        )
        d = result.to_dict()
        assert d["loop_id"] == "loop_test"
        assert len(d["fitness_history"]) == 3
        assert d["improvement_trend"] == 11.25


# =============================================================================
# Test PromptImprovementEngine
# =============================================================================


class TestPromptImprovementEngine:
    """Test PromptImprovementEngine."""

    def test_init(self):
        """Basic initialization."""
        engine = PromptImprovementEngine()
        assert len(engine._adjustment_history) == 0

    def test_metric_thresholds_defined(self):
        """Thresholds should be defined for key metrics."""
        assert "sharpe_ratio" in PromptImprovementEngine.METRIC_THRESHOLDS
        assert "win_rate" in PromptImprovementEngine.METRIC_THRESHOLDS
        assert "max_drawdown_pct" in PromptImprovementEngine.METRIC_THRESHOLDS
        assert "profit_factor" in PromptImprovementEngine.METRIC_THRESHOLDS

    def test_adjustment_templates_defined(self):
        """Adjustment templates should be defined."""
        templates = PromptImprovementEngine.ADJUSTMENT_TEMPLATES
        assert "high_drawdown" in templates
        assert "low_win_rate" in templates
        assert "low_sharpe" in templates
        assert "low_profit_factor" in templates
        assert "few_trades" in templates

    def test_generate_adjustments_high_drawdown(self):
        """High drawdown should trigger risk management emphasis."""
        engine = PromptImprovementEngine()
        adjustments = engine.generate_adjustments(
            reflection_summary=[],
            improvement_actions=[],
            backtest_metrics={
                "sharpe_ratio": 1.0,
                "win_rate": 0.5,
                "max_drawdown_pct": 35.0,
                "profit_factor": 1.5,
                "total_trades": 20,
            },
        )
        assert "risk_management" in adjustments["emphasis_areas"]

    def test_generate_adjustments_low_win_rate(self):
        """Low win rate should trigger entry quality emphasis."""
        engine = PromptImprovementEngine()
        adjustments = engine.generate_adjustments(
            reflection_summary=[],
            improvement_actions=[],
            backtest_metrics={
                "sharpe_ratio": 1.0,
                "win_rate": 0.25,
                "max_drawdown_pct": 10.0,
                "profit_factor": 1.0,
                "total_trades": 20,
            },
        )
        assert "entry_quality" in adjustments["emphasis_areas"]

    def test_generate_adjustments_low_sharpe(self):
        """Low Sharpe should trigger risk-adjusted returns emphasis."""
        engine = PromptImprovementEngine()
        adjustments = engine.generate_adjustments(
            reflection_summary=[],
            improvement_actions=[],
            backtest_metrics={
                "sharpe_ratio": 0.3,
                "win_rate": 0.5,
                "max_drawdown_pct": 10.0,
                "profit_factor": 1.0,
                "total_trades": 20,
            },
        )
        assert "risk_adjusted_returns" in adjustments["emphasis_areas"]

    def test_generate_adjustments_few_trades(self):
        """Few trades should trigger signal frequency emphasis."""
        engine = PromptImprovementEngine()
        adjustments = engine.generate_adjustments(
            reflection_summary=[],
            improvement_actions=[],
            backtest_metrics={
                "sharpe_ratio": 1.0,
                "win_rate": 0.5,
                "max_drawdown_pct": 10.0,
                "profit_factor": 1.0,
                "total_trades": 5,
            },
        )
        assert "signal_frequency" in adjustments["emphasis_areas"]

    def test_generate_adjustments_good_metrics(self):
        """Good metrics should produce minimal adjustments."""
        engine = PromptImprovementEngine()
        adjustments = engine.generate_adjustments(
            reflection_summary=[],
            improvement_actions=[],
            backtest_metrics={
                "sharpe_ratio": 2.0,
                "win_rate": 0.6,
                "max_drawdown_pct": 8.0,
                "profit_factor": 2.0,
                "total_trades": 30,
            },
        )
        assert len(adjustments["emphasis_areas"]) == 0

    def test_reflection_based_adjustments(self):
        """Reflection summary should influence emphasis areas."""
        engine = PromptImprovementEngine()
        adjustments = engine.generate_adjustments(
            reflection_summary=[
                "Stop loss was too wide leading to large drawdowns",
                "Entry signals need better filtering",
            ],
            improvement_actions=[],
            backtest_metrics={
                "sharpe_ratio": 2.0,
                "win_rate": 0.6,
                "max_drawdown_pct": 8.0,
                "profit_factor": 2.0,
                "total_trades": 30,
            },
        )
        assert "risk_management" in adjustments["emphasis_areas"]
        assert "entry_quality" in adjustments["emphasis_areas"]

    def test_improvement_actions_included(self):
        """Improvement actions should be added to specific_instructions."""
        engine = PromptImprovementEngine()
        adjustments = engine.generate_adjustments(
            reflection_summary=[],
            improvement_actions=["Add ATR trailing stop", "Use volume filter"],
            backtest_metrics={"sharpe_ratio": 1.0, "win_rate": 0.5},
        )
        assert "Add ATR trailing stop" in adjustments["specific_instructions"]
        assert "Use volume filter" in adjustments["specific_instructions"]

    def test_knowledge_gaps_context(self):
        """Knowledge gaps should be added to additional_context."""
        engine = PromptImprovementEngine()
        adjustments = engine.generate_adjustments(
            reflection_summary=[],
            improvement_actions=[],
            backtest_metrics={"sharpe_ratio": 1.0},
            knowledge_gaps=["Bollinger Band squeeze patterns"],
        )
        assert any("Bollinger" in ctx for ctx in adjustments["additional_context"])

    def test_parameter_hints_high_drawdown(self):
        """High drawdown should suggest tighter stop loss."""
        engine = PromptImprovementEngine()
        adjustments = engine.generate_adjustments(
            reflection_summary=[],
            improvement_actions=[],
            backtest_metrics={"max_drawdown_pct": 25.0},
        )
        assert "stop_loss" in adjustments["parameter_hints"]

    def test_parameter_hints_low_win_rate(self):
        """Low win rate should suggest stricter entry."""
        engine = PromptImprovementEngine()
        adjustments = engine.generate_adjustments(
            reflection_summary=[],
            improvement_actions=[],
            backtest_metrics={"win_rate": 0.3},
        )
        assert "entry_threshold" in adjustments["parameter_hints"]

    def test_format_adjustments_for_prompt(self):
        """Format should produce readable text."""
        engine = PromptImprovementEngine()
        adjustments = {
            "emphasis_areas": ["risk_management", "entry_quality"],
            "specific_instructions": ["Tighten stop loss"],
            "parameter_hints": {"stop_loss": "tighter"},
            "avoid_patterns": [],
            "additional_context": [],
        }
        text = engine.format_adjustments_for_prompt(adjustments)
        assert "EMPHASIS" in text
        assert "risk_management" in text
        assert "INSTRUCTIONS" in text
        assert "PARAMETER HINTS" in text

    def test_format_empty_adjustments(self):
        """Empty adjustments should produce empty string."""
        engine = PromptImprovementEngine()
        text = engine.format_adjustments_for_prompt({})
        assert text == ""

    def test_history_tracking(self):
        """Adjustments should be tracked in history."""
        engine = PromptImprovementEngine()
        engine.generate_adjustments([], [], {"sharpe_ratio": 0.3})
        engine.generate_adjustments([], [], {"sharpe_ratio": 1.5})
        assert len(engine.get_history()) == 2


# =============================================================================
# Test FeedbackLoop
# =============================================================================


class TestFeedbackLoop:
    """Test FeedbackLoop."""

    def test_init(self):
        """Basic initialization."""
        loop = FeedbackLoop()
        assert loop.improvement_engine is not None
        assert len(loop._accumulated_insights) == 0

    def test_init_with_custom_engine(self):
        """Initialization with custom improvement engine."""
        custom_engine = PromptImprovementEngine()
        loop = FeedbackLoop(improvement_engine=custom_engine)
        assert loop.improvement_engine is custom_engine

    def test_convergence_constants(self):
        """Convergence constants should be reasonable."""
        assert FeedbackLoop.CONVERGENCE_THRESHOLD > 0
        assert FeedbackLoop.MIN_ITERATIONS >= 2
        assert FeedbackLoop.MAX_STAGNANT >= 2

    def test_create_failed_metrics(self):
        """Failed metrics should have sensible defaults."""
        loop = FeedbackLoop()
        metrics = loop._create_failed_metrics()
        assert metrics["net_profit"] == 0.0
        assert metrics["max_drawdown_pct"] == 100.0
        assert metrics["total_trades"] == 0

    def test_apply_adjustments_tighten_stop_loss(self):
        """Adjustments should tighten stop loss when indicated."""
        loop = FeedbackLoop()
        params = {"period": 14, "stop_loss_pct": 5.0}
        adjustments = {
            "parameter_hints": {"stop_loss": "tighter"},
        }
        new_params = loop._apply_adjustments(params, adjustments, {})
        assert new_params["stop_loss_pct"] < 5.0

    def test_apply_adjustments_entry_threshold(self):
        """Adjustments should modify entry thresholds."""
        loop = FeedbackLoop()
        params = {"period": 14, "oversold": 30, "overbought": 70}
        adjustments = {
            "parameter_hints": {"entry_threshold": "stricter"},
        }
        new_params = loop._apply_adjustments(params, adjustments, {})
        assert new_params["oversold"] < 30
        assert new_params["overbought"] > 70

    def test_apply_adjustments_increase_sensitivity(self):
        """Signal sensitivity increase should reduce period."""
        loop = FeedbackLoop()
        params = {"period": 14}
        adjustments = {
            "parameter_hints": {"signal_sensitivity": "increase (lower thresholds)"},
        }
        new_params = loop._apply_adjustments(params, adjustments, {})
        assert new_params["period"] < 14

    def test_apply_adjustments_decrease_sensitivity(self):
        """Signal sensitivity decrease should increase period."""
        loop = FeedbackLoop()
        params = {"period": 14}
        adjustments = {
            "parameter_hints": {"signal_sensitivity": "decrease (higher thresholds)"},
        }
        new_params = loop._apply_adjustments(params, adjustments, {})
        assert new_params["period"] > 14

    def test_apply_adjustments_no_hints(self):
        """No hints should return same params."""
        loop = FeedbackLoop()
        params = {"period": 14, "oversold": 30}
        adjustments = {"parameter_hints": {}}
        new_params = loop._apply_adjustments(params, adjustments, {})
        assert new_params == params

    def test_build_strategy_definition(self):
        """Should build valid StrategyDefinition."""
        loop = FeedbackLoop()
        strategy = loop._build_strategy_definition("rsi", {"period": 14, "oversold": 25}, 1)
        assert strategy.strategy_name == "rsi_feedback_v1"
        assert len(strategy.signals) == 1
        assert strategy.exit_conditions is not None

    @pytest.mark.asyncio
    async def test_run_single_iteration(self):
        """Run loop with 1 iteration using mocked bridge."""
        from unittest.mock import AsyncMock, patch

        import pandas as pd

        loop = FeedbackLoop()
        df = pd.DataFrame(
            {
                "open": [100.0] * 100,
                "high": [105.0] * 100,
                "low": [95.0] * 100,
                "close": [102.0] * 100,
                "volume": [1000.0] * 100,
            }
        )

        mock_metrics = {
            "net_profit": 500.0,
            "sharpe_ratio": 1.2,
            "win_rate": 0.55,
            "max_drawdown_pct": 12.0,
            "profit_factor": 1.5,
            "total_trades": 20,
        }

        with patch("backend.agents.integration.backtest_bridge.BacktestBridge") as MockBridge:
            mock_bridge = AsyncMock()
            mock_bridge.run_strategy = AsyncMock(return_value=mock_metrics)
            MockBridge.return_value = mock_bridge

            result = await loop.run(
                symbol="BTCUSDT",
                timeframe="15",
                df=df,
                strategy_type="rsi",
                initial_params={"period": 14, "oversold": 30},
                max_iterations=1,
            )

        assert result.total_iterations == 1
        assert result.best_fitness > 0
        assert len(result.fitness_history) == 1

    @pytest.mark.asyncio
    async def test_run_convergence(self):
        """Loop should detect convergence."""
        from unittest.mock import AsyncMock, patch

        import pandas as pd

        loop = FeedbackLoop()
        df = pd.DataFrame(
            {
                "open": [100.0] * 100,
                "high": [105.0] * 100,
                "low": [95.0] * 100,
                "close": [102.0] * 100,
                "volume": [1000.0] * 100,
            }
        )

        # Same metrics each time → should converge
        static_metrics = {
            "net_profit": 500.0,
            "sharpe_ratio": 1.2,
            "win_rate": 0.55,
            "max_drawdown_pct": 12.0,
            "profit_factor": 1.5,
            "total_trades": 20,
        }

        with patch("backend.agents.integration.backtest_bridge.BacktestBridge") as MockBridge:
            mock_bridge = AsyncMock()
            mock_bridge.run_strategy = AsyncMock(return_value=static_metrics)
            MockBridge.return_value = mock_bridge

            result = await loop.run(
                symbol="BTCUSDT",
                timeframe="15",
                df=df,
                max_iterations=10,
            )

        # Should stop before 10 due to stagnation
        assert result.total_iterations < 10

    @pytest.mark.asyncio
    async def test_run_backtest_failure(self):
        """Loop should handle backtest failures gracefully."""
        from unittest.mock import AsyncMock, patch

        import pandas as pd

        loop = FeedbackLoop()
        df = pd.DataFrame(
            {
                "open": [100.0] * 10,
                "high": [105.0] * 10,
                "low": [95.0] * 10,
                "close": [102.0] * 10,
                "volume": [1000.0] * 10,
            }
        )

        with patch("backend.agents.integration.backtest_bridge.BacktestBridge") as MockBridge:
            mock_bridge = AsyncMock()
            mock_bridge.run_strategy = AsyncMock(side_effect=Exception("Backtest error"))
            MockBridge.return_value = mock_bridge

            result = await loop.run(
                symbol="BTCUSDT",
                timeframe="15",
                df=df,
                max_iterations=2,
            )

        assert result.total_iterations >= 1
        # Fitness should be very low for failed backtest
        assert all(f <= 10 for f in result.fitness_history)
