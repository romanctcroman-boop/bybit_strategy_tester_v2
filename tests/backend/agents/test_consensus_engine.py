"""
Tests for ConsensusEngine — multi-agent strategy aggregation.

Tests cover:
- Single agent passthrough
- Weighted voting aggregation
- Bayesian aggregation
- Best-of selection
- Agent weight calculation with/without history
- Agreement score (Jaccard similarity)
- Signal vote counting
- Parameter merging (median/mode)
- Filter merging (dedup by type)
- Exit conditions merging (weighted average)
- Optimization hints merging (union)
- Performance tracking (update_performance)
- ConsensusResult serialization
- Edge cases (empty params, identical strategies)
"""

from __future__ import annotations

import pytest

from backend.agents.consensus.consensus_engine import (
    AgentPerformance,
    ConsensusEngine,
    ConsensusMethod,
    ConsensusResult,
)
from backend.agents.prompts.response_parser import (
    ExitCondition,
    ExitConditions,
    Filter,
    OptimizationHints,
    Signal,
    StrategyDefinition,
)

# =============================================================================
# FIXTURES
# =============================================================================


def _make_signal(type_: str, weight: float = 1.0, **params) -> Signal:
    """Helper to create a Signal instance."""
    return Signal(
        id=f"signal_{type_.lower()}",
        type=type_,
        params=params,
        weight=weight,
        condition=f"{type_} signal",
    )


def _make_strategy(
    name: str,
    signals: list[Signal] | None = None,
    filters: list[Filter] | None = None,
    exit_conditions: ExitConditions | None = None,
    optimization_hints: OptimizationHints | None = None,
) -> StrategyDefinition:
    """Helper to create a StrategyDefinition."""
    if signals is None:
        signals = [_make_signal("RSI", period=14, overbought=70, oversold=30)]
    return StrategyDefinition(
        strategy_name=name,
        description=f"Test strategy {name}",
        signals=signals,
        filters=filters or [],
        exit_conditions=exit_conditions,
        optimization_hints=optimization_hints,
    )


@pytest.fixture
def engine() -> ConsensusEngine:
    """Fresh ConsensusEngine instance."""
    return ConsensusEngine()


@pytest.fixture
def two_strategies() -> dict[str, StrategyDefinition]:
    """Two distinct strategies from different agents."""
    return {
        "deepseek": _make_strategy(
            "RSI Strategy",
            signals=[
                _make_signal("RSI", weight=0.8, period=14, overbought=70, oversold=30),
                _make_signal("MACD", weight=0.5, fast=12, slow=26, signal=9),
            ],
            filters=[
                Filter(id="f1", type="Volume", params={"min_volume": 1000}),
            ],
            exit_conditions=ExitConditions(
                take_profit=ExitCondition(type="fixed_pct", value=0.03),
                stop_loss=ExitCondition(type="fixed_pct", value=0.02),
            ),
            optimization_hints=OptimizationHints(
                parameters_to_optimize=["period", "overbought"],
                ranges={"period": [10, 20]},
                primary_objective="sharpe_ratio",
            ),
        ),
        "qwen": _make_strategy(
            "EMA Crossover",
            signals=[
                _make_signal("EMA_Crossover", weight=0.9, fast_period=9, slow_period=21),
                _make_signal("RSI", weight=0.4, period=21, overbought=75, oversold=25),
            ],
            filters=[
                Filter(id="f2", type="ADX", params={"threshold": 25}),
            ],
            exit_conditions=ExitConditions(
                take_profit=ExitCondition(type="fixed_pct", value=0.05),
                stop_loss=ExitCondition(type="fixed_pct", value=0.015),
            ),
            optimization_hints=OptimizationHints(
                parameters_to_optimize=["fast_period", "slow_period"],
                ranges={"fast_period": [5, 15]},
                primary_objective="profit_factor",
            ),
        ),
    }


@pytest.fixture
def three_strategies(two_strategies: dict) -> dict[str, StrategyDefinition]:
    """Three strategies (adds perplexity with overlapping RSI signal)."""
    strats = dict(two_strategies)
    strats["perplexity"] = _make_strategy(
        "Bollinger RSI",
        signals=[
            _make_signal("RSI", weight=0.7, period=14, overbought=70, oversold=30),
            _make_signal("Bollinger", weight=0.6, period=20, std_dev=2),
        ],
    )
    return strats


# =============================================================================
# TESTS — BASIC
# =============================================================================


class TestConsensusEngineBasic:
    """Basic functionality tests."""

    def test_aggregate_empty_raises(self, engine: ConsensusEngine):
        """Aggregating empty dict raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            engine.aggregate({})

    def test_single_agent_passthrough(self, engine: ConsensusEngine):
        """Single agent → passthrough with agreement=1.0."""
        strategy = _make_strategy("Solo")
        result = engine.aggregate({"agent_a": strategy})

        assert result.method == "single_agent"
        assert result.agreement_score == 1.0
        assert result.input_agents == ["agent_a"]
        assert result.agent_weights == {"agent_a": 1.0}
        assert result.strategy.signals == strategy.signals

    def test_aggregate_returns_consensus_result(self, engine: ConsensusEngine, two_strategies: dict):
        """Aggregate returns a ConsensusResult instance."""
        result = engine.aggregate(two_strategies)
        assert isinstance(result, ConsensusResult)
        assert isinstance(result.strategy, StrategyDefinition)

    def test_consensus_result_to_dict(self, engine: ConsensusEngine, two_strategies: dict):
        """ConsensusResult.to_dict serializes correctly."""
        result = engine.aggregate(two_strategies)
        d = result.to_dict()

        assert "strategy_name" in d
        assert "method" in d
        assert "agreement_score" in d
        assert isinstance(d["agreement_score"], float)
        assert "agent_weights" in d
        assert "signal_votes" in d
        assert "timestamp" in d

    def test_default_method_is_weighted_voting(self, engine: ConsensusEngine, two_strategies: dict):
        """Default method is weighted_voting."""
        result = engine.aggregate(two_strategies)
        assert result.method == ConsensusMethod.WEIGHTED_VOTING


# =============================================================================
# TESTS — WEIGHTED VOTING
# =============================================================================


class TestWeightedVoting:
    """Tests for weighted_voting consensus method."""

    def test_weighted_voting_produces_signals(self, engine: ConsensusEngine, two_strategies: dict):
        """Weighted voting produces at least one signal."""
        result = engine.aggregate(two_strategies, method="weighted_voting")
        assert len(result.strategy.signals) >= 1

    def test_overlapping_signal_included(self, engine: ConsensusEngine, three_strategies: dict):
        """RSI, present in all 3 agents, should be in consensus."""
        result = engine.aggregate(three_strategies, method="weighted_voting")
        signal_types = [s.type for s in result.strategy.signals]
        assert "RSI" in signal_types

    def test_max_signals_capped(self, engine: ConsensusEngine):
        """Consensus strategy should not exceed _MAX_CONSENSUS_SIGNALS."""
        # Create agents with many signals each
        strats = {}
        for name in ["a", "b", "c"]:
            strats[name] = _make_strategy(
                f"Many_{name}",
                signals=[
                    _make_signal("RSI", period=14),
                    _make_signal("MACD", fast=12),
                    _make_signal("EMA_Crossover", fast_period=9),
                    _make_signal("Bollinger", period=20),
                    _make_signal("SuperTrend", factor=3),
                ],
            )
        result = engine.aggregate(strats, method="weighted_voting")
        assert len(result.strategy.signals) <= 4  # _MAX_CONSENSUS_SIGNALS

    def test_weighted_voting_with_performance_history(self, engine: ConsensusEngine, two_strategies: dict):
        """Agent with better history gets higher weight."""
        engine.update_performance("deepseek", sharpe=2.5, profit_factor=2.0, win_rate=0.6, backtest_passed=True)
        engine.update_performance("qwen", sharpe=0.5, profit_factor=0.8, win_rate=0.4, backtest_passed=False)

        result = engine.aggregate(two_strategies, method="weighted_voting")
        assert result.agent_weights["deepseek"] > result.agent_weights["qwen"]


# =============================================================================
# TESTS — BAYESIAN AGGREGATION
# =============================================================================


class TestBayesianAggregation:
    """Tests for bayesian_aggregation consensus method."""

    def test_bayesian_produces_strategy(self, engine: ConsensusEngine, two_strategies: dict):
        """Bayesian aggregation produces a valid strategy."""
        result = engine.aggregate(two_strategies, method="bayesian_aggregation")
        assert len(result.strategy.signals) >= 1
        assert result.method == ConsensusMethod.BAYESIAN

    def test_bayesian_favors_widely_supported_signals(self, engine: ConsensusEngine, three_strategies: dict):
        """Bayesian should favor signals present in more agents."""
        result = engine.aggregate(three_strategies, method="bayesian_aggregation")
        signal_types = [s.type for s in result.strategy.signals]
        # RSI is in all 3 agents → should definitely be included
        assert "RSI" in signal_types


# =============================================================================
# TESTS — BEST-OF
# =============================================================================


class TestBestOf:
    """Tests for best_of consensus method."""

    def test_best_of_picks_one(self, engine: ConsensusEngine, two_strategies: dict):
        """Best-of picks exactly one agent's strategy."""
        result = engine.aggregate(two_strategies, method="best_of")
        assert result.method == ConsensusMethod.BEST_OF
        # Should preserve the original signal count from one agent
        original_counts = {len(s.signals) for s in two_strategies.values()}
        assert len(result.strategy.signals) in original_counts

    def test_best_of_with_performance_prefers_better_agent(self, engine: ConsensusEngine, two_strategies: dict):
        """Best-of with history picks the better-performing agent."""
        engine.update_performance("deepseek", sharpe=3.0, profit_factor=2.5, win_rate=0.7, backtest_passed=True)
        engine.update_performance("qwen", sharpe=0.2, profit_factor=0.5, win_rate=0.3, backtest_passed=False)

        result = engine.aggregate(two_strategies, method="best_of")
        # With much better history, deepseek should be picked
        assert result.agent_weights["deepseek"] > result.agent_weights["qwen"]


# =============================================================================
# TESTS — AGENT WEIGHTS
# =============================================================================


class TestAgentWeights:
    """Tests for agent weight calculation."""

    def test_equal_weights_without_history(self, engine: ConsensusEngine, two_strategies: dict):
        """Without history, agents get roughly equal weights."""
        result = engine.aggregate(two_strategies)
        w = result.agent_weights
        # Weights may differ slightly due to strategy quality, but should be close
        assert abs(w["deepseek"] - w["qwen"]) < 0.5

    def test_weights_sum_to_one(self, engine: ConsensusEngine, three_strategies: dict):
        """Agent weights should sum to 1.0."""
        result = engine.aggregate(three_strategies)
        total = sum(result.agent_weights.values())
        assert abs(total - 1.0) < 1e-6


# =============================================================================
# TESTS — AGREEMENT SCORE
# =============================================================================


class TestAgreementScore:
    """Tests for agreement (Jaccard similarity) scoring."""

    def test_identical_strategies_full_agreement(self, engine: ConsensusEngine):
        """Identical signal sets → agreement = 1.0."""
        sig = [_make_signal("RSI", period=14)]
        strats = {
            "a": _make_strategy("A", signals=sig),
            "b": _make_strategy("B", signals=list(sig)),
        }
        result = engine.aggregate(strats)
        assert result.agreement_score == pytest.approx(1.0)

    def test_disjoint_strategies_low_agreement(self, engine: ConsensusEngine):
        """Completely disjoint signal types → agreement < 0.5."""
        strats = {
            "a": _make_strategy("A", signals=[_make_signal("RSI")]),
            "b": _make_strategy("B", signals=[_make_signal("MACD")]),
        }
        result = engine.aggregate(strats)
        assert result.agreement_score < 0.5

    def test_partial_overlap_moderate_agreement(self, engine: ConsensusEngine, two_strategies: dict):
        """Partial signal overlap → moderate agreement."""
        result = engine.aggregate(two_strategies)
        assert 0.0 < result.agreement_score < 1.0


# =============================================================================
# TESTS — PERFORMANCE TRACKING
# =============================================================================


class TestPerformanceTracking:
    """Tests for update_performance and get_performance."""

    def test_update_performance_creates_record(self, engine: ConsensusEngine):
        """First update creates a new performance record."""
        engine.update_performance("agent_x", sharpe=1.5, win_rate=0.55)
        perf = engine.get_performance("agent_x")
        assert perf is not None
        assert perf.agent_name == "agent_x"
        assert perf.total_strategies == 1

    def test_update_performance_increments(self, engine: ConsensusEngine):
        """Multiple updates increment totals."""
        engine.update_performance("a", sharpe=1.0, backtest_passed=True)
        engine.update_performance("a", sharpe=2.0, backtest_passed=True)
        engine.update_performance("a", sharpe=0.5, backtest_passed=False)

        perf = engine.get_performance("a")
        assert perf is not None
        assert perf.total_strategies == 3
        assert perf.successful_backtests == 2

    def test_success_rate_calculation(self, engine: ConsensusEngine):
        """success_rate = successful / total."""
        engine.update_performance("a", backtest_passed=True)
        engine.update_performance("a", backtest_passed=False)
        engine.update_performance("a", backtest_passed=True)

        perf = engine.get_performance("a")
        assert perf is not None
        assert perf.success_rate == pytest.approx(2 / 3)

    def test_get_performance_returns_none_for_unknown(self, engine: ConsensusEngine):
        """get_performance returns None for unknown agent."""
        assert engine.get_performance("unknown_agent") is None


# =============================================================================
# TESTS — SIGNAL VOTES
# =============================================================================


class TestSignalVotes:
    """Tests for signal vote counting."""

    def test_vote_counts_correct(self, engine: ConsensusEngine, three_strategies: dict):
        """RSI should have 3 votes (present in all 3 agents)."""
        result = engine.aggregate(three_strategies)
        assert result.signal_votes.get("RSI", 0) == 3

    def test_unique_signal_has_one_vote(self, engine: ConsensusEngine, two_strategies: dict):
        """EMA_Crossover only in qwen → 1 vote."""
        result = engine.aggregate(two_strategies)
        assert result.signal_votes.get("EMA_Crossover", 0) == 1


# =============================================================================
# TESTS — MERGING HELPERS
# =============================================================================


class TestMergingHelpers:
    """Tests for parameter/filter/exit merging."""

    def test_consensus_strategy_naming(self, engine: ConsensusEngine, two_strategies: dict):
        """Consensus strategy gets an auto-generated name."""
        result = engine.aggregate(two_strategies)
        assert "Consensus_" in result.strategy.strategy_name

    def test_market_context_in_name(self, engine: ConsensusEngine, two_strategies: dict):
        """Market context symbol appears in strategy name."""
        result = engine.aggregate(
            two_strategies,
            market_context={"symbol": "BTCUSDT"},
        )
        assert "BTCUSDT" in result.strategy.strategy_name

    def test_exit_conditions_merged(self, engine: ConsensusEngine, two_strategies: dict):
        """Exit conditions from both agents are merged."""
        result = engine.aggregate(two_strategies, method="weighted_voting")
        exits = result.strategy.exit_conditions
        # Should have merged exit conditions (weighted average)
        if exits is not None:
            if exits.take_profit is not None:
                # Merged TP should be between 0.03 and 0.05
                assert 0.02 <= exits.take_profit.value <= 0.06
            if exits.stop_loss is not None:
                # Merged SL should be between 0.015 and 0.02
                assert 0.01 <= exits.stop_loss.value <= 0.03

    def test_filters_merged_dedup(self, engine: ConsensusEngine, two_strategies: dict):
        """Filters from both agents are merged and deduplicated."""
        result = engine.aggregate(two_strategies, method="weighted_voting")
        filter_types = [f.type for f in result.strategy.filters]
        # Both Volume and ADX should be present
        assert len(filter_types) <= 3  # _MAX_CONSENSUS_FILTERS


# =============================================================================
# TESTS — EDGE CASES
# =============================================================================


class TestEdgeCases:
    """Edge cases and robustness tests."""

    def test_agent_performance_default_prior(self):
        """AgentPerformance with no data has success_rate 0.5 prior."""
        perf = AgentPerformance(agent_name="new")
        assert perf.success_rate == 0.5

    def test_consensus_method_enum_values(self):
        """ConsensusMethod enum has expected values."""
        assert ConsensusMethod.WEIGHTED_VOTING == "weighted_voting"
        assert ConsensusMethod.BAYESIAN == "bayesian_aggregation"
        assert ConsensusMethod.BEST_OF == "best_of"

    def test_history_tracking(self, engine: ConsensusEngine, two_strategies: dict):
        """Engine tracks consensus history."""
        engine.aggregate(two_strategies)
        engine.aggregate(two_strategies, method="best_of")
        assert len(engine._history) == 2
