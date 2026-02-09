"""
Tests for Agent Performance Tracker (Task 4.3)

Tests AgentPerformanceTracker, AgentProfile, AgentRecord.
"""

from __future__ import annotations

from backend.agents.self_improvement.agent_tracker import (
    AgentPerformanceTracker,
    AgentProfile,
    AgentRecord,
)

# =============================================================================
# Test AgentRecord
# =============================================================================


class TestAgentRecord:
    """Test AgentRecord dataclass."""

    def test_create_record(self):
        """Create a basic record."""
        from datetime import UTC, datetime

        record = AgentRecord(
            agent_name="deepseek",
            timestamp=datetime.now(UTC),
            strategy_type="rsi",
            fitness_score=72.5,
            sharpe_ratio=1.5,
            win_rate=0.55,
            max_drawdown_pct=12.0,
            profit_factor=1.8,
            total_trades=25,
            passed=True,
        )
        assert record.agent_name == "deepseek"
        assert record.fitness_score == 72.5
        assert record.passed is True

    def test_to_dict(self):
        """to_dict should serialize properly."""
        from datetime import UTC, datetime

        record = AgentRecord(
            agent_name="qwen",
            timestamp=datetime.now(UTC),
            strategy_type="macd",
            fitness_score=55.0,
            sharpe_ratio=0.8,
            win_rate=0.45,
            max_drawdown_pct=18.0,
            profit_factor=1.2,
            total_trades=15,
            passed=False,
        )
        d = record.to_dict()
        assert d["agent_name"] == "qwen"
        assert d["passed"] is False
        assert "timestamp" in d


# =============================================================================
# Test AgentProfile
# =============================================================================


class TestAgentProfile:
    """Test AgentProfile dataclass."""

    def test_pass_rate_zero_strategies(self):
        """Pass rate should be 0 with no strategies."""
        profile = AgentProfile(agent_name="test")
        assert profile.pass_rate == 0.0

    def test_pass_rate_calculation(self):
        """Pass rate should be passed/total."""
        profile = AgentProfile(
            agent_name="test",
            total_strategies=10,
            passed_strategies=7,
        )
        assert profile.pass_rate == 0.7

    def test_composite_score_zero(self):
        """Composite score with all zeros."""
        profile = AgentProfile(agent_name="test")
        assert profile.composite_score >= 0
        assert profile.composite_score <= 100

    def test_composite_score_perfect(self):
        """Composite score with great metrics."""
        profile = AgentProfile(
            agent_name="test",
            total_strategies=10,
            passed_strategies=10,
            avg_sharpe=2.5,
            avg_win_rate=0.6,
            avg_drawdown=5.0,
            avg_profit_factor=2.5,
            consistency_score=0.9,
        )
        score = profile.composite_score
        assert score > 60  # Should be high

    def test_composite_score_poor(self):
        """Composite score with poor metrics."""
        profile = AgentProfile(
            agent_name="test",
            total_strategies=10,
            passed_strategies=2,
            avg_sharpe=0.1,
            avg_win_rate=0.3,
            avg_drawdown=40.0,
            avg_profit_factor=0.5,
            consistency_score=0.2,
        )
        score = profile.composite_score
        assert score < 30  # Should be low

    def test_to_dict(self):
        """to_dict should include all fields."""
        profile = AgentProfile(
            agent_name="deepseek",
            total_strategies=5,
            passed_strategies=3,
            avg_sharpe=1.2,
        )
        d = profile.to_dict()
        assert d["agent_name"] == "deepseek"
        assert d["pass_rate"] == 0.6
        assert "composite_score" in d
        assert "last_updated" in d


# =============================================================================
# Test AgentPerformanceTracker
# =============================================================================


class TestAgentPerformanceTracker:
    """Test AgentPerformanceTracker."""

    def test_init(self):
        """Basic initialization."""
        tracker = AgentPerformanceTracker()
        assert tracker.window_size == 100
        assert len(tracker._records) == 0

    def test_init_custom_window(self):
        """Custom window size."""
        tracker = AgentPerformanceTracker(window_size=50)
        assert tracker.window_size == 50

    def test_record_result(self):
        """Record a result and verify profile update."""
        tracker = AgentPerformanceTracker()
        record = tracker.record_result(
            agent_name="deepseek",
            metrics={
                "sharpe_ratio": 1.5,
                "win_rate": 0.55,
                "max_drawdown_pct": 12.0,
                "profit_factor": 1.8,
                "total_trades": 25,
            },
            strategy_type="rsi",
            passed=True,
            fitness_score=72.5,
        )
        assert record.agent_name == "deepseek"
        assert record.sharpe_ratio == 1.5
        assert len(tracker._records["deepseek"]) == 1

    def test_record_multiple_results(self):
        """Record multiple results for same agent."""
        tracker = AgentPerformanceTracker()
        for i in range(5):
            tracker.record_result(
                agent_name="deepseek",
                metrics={
                    "sharpe_ratio": 1.0 + i * 0.2,
                    "win_rate": 0.5,
                    "max_drawdown_pct": 10.0,
                    "profit_factor": 1.5,
                    "total_trades": 20,
                },
                passed=True,
                fitness_score=60 + i * 5,
            )
        assert len(tracker._records["deepseek"]) == 5
        profile = tracker.get_profile("deepseek")
        assert profile.total_strategies == 5
        assert profile.passed_strategies == 5

    def test_record_multiple_agents(self):
        """Record results for different agents."""
        tracker = AgentPerformanceTracker()
        for agent in ["deepseek", "qwen", "perplexity"]:
            tracker.record_result(
                agent_name=agent,
                metrics={"sharpe_ratio": 1.0, "win_rate": 0.5},
                passed=True,
            )
        assert len(tracker._records) == 3

    def test_get_profile_unknown_agent(self):
        """Unknown agent should return empty profile."""
        tracker = AgentPerformanceTracker()
        profile = tracker.get_profile("unknown_agent")
        assert profile.agent_name == "unknown_agent"
        assert profile.total_strategies == 0

    def test_get_profile_averages(self):
        """Profile should compute correct averages."""
        tracker = AgentPerformanceTracker()
        tracker.record_result(
            "deepseek",
            {"sharpe_ratio": 1.0, "win_rate": 0.4},
            passed=True,
            fitness_score=50,
        )
        tracker.record_result(
            "deepseek",
            {"sharpe_ratio": 2.0, "win_rate": 0.6},
            passed=True,
            fitness_score=70,
        )
        profile = tracker.get_profile("deepseek")
        assert abs(profile.avg_sharpe - 1.5) < 0.01
        assert abs(profile.avg_win_rate - 0.5) < 0.01
        assert abs(profile.avg_fitness - 60.0) < 0.01

    def test_compute_dynamic_weights_no_history(self):
        """No history → uniform weights."""
        tracker = AgentPerformanceTracker()
        weights = tracker.compute_dynamic_weights(["deepseek", "qwen", "perplexity"])
        assert len(weights) == 3
        assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_compute_dynamic_weights_default_for_few_records(self):
        """Agents with < MIN_RECORDS should get default weight."""
        tracker = AgentPerformanceTracker()
        tracker.record_result("deepseek", {"sharpe_ratio": 2.0}, passed=True)
        weights = tracker.compute_dynamic_weights(["deepseek", "qwen"])
        # Both should be similar since deepseek has < MIN_RECORDS
        assert abs(weights["deepseek"] - weights["qwen"]) < 0.1

    def test_compute_dynamic_weights_composite(self):
        """Better agent should get higher weight."""
        tracker = AgentPerformanceTracker()

        # DeepSeek: consistently good
        for _ in range(5):
            tracker.record_result(
                "deepseek",
                {
                    "sharpe_ratio": 2.0,
                    "win_rate": 0.6,
                    "max_drawdown_pct": 8.0,
                    "profit_factor": 2.0,
                    "total_trades": 25,
                },
                passed=True,
                fitness_score=80,
            )

        # Qwen: consistently poor
        for _ in range(5):
            tracker.record_result(
                "qwen",
                {
                    "sharpe_ratio": 0.3,
                    "win_rate": 0.35,
                    "max_drawdown_pct": 30.0,
                    "profit_factor": 0.7,
                    "total_trades": 10,
                },
                passed=False,
                fitness_score=25,
            )

        weights = tracker.compute_dynamic_weights(
            ["deepseek", "qwen"],
            method="composite",
        )
        assert weights["deepseek"] > weights["qwen"]

    def test_compute_dynamic_weights_sharpe_method(self):
        """Sharpe method should weight by avg Sharpe."""
        tracker = AgentPerformanceTracker()
        for _ in range(5):
            tracker.record_result("deepseek", {"sharpe_ratio": 2.0}, passed=True, fitness_score=70)
            tracker.record_result("qwen", {"sharpe_ratio": 0.5}, passed=True, fitness_score=40)
        weights = tracker.compute_dynamic_weights(["deepseek", "qwen"], method="sharpe")
        assert weights["deepseek"] > weights["qwen"]

    def test_compute_dynamic_weights_pass_rate_method(self):
        """Pass rate method should weight by pass rate."""
        tracker = AgentPerformanceTracker()
        for _ in range(5):
            tracker.record_result("deepseek", {"sharpe_ratio": 1.0}, passed=True)
            tracker.record_result("qwen", {"sharpe_ratio": 1.0}, passed=False)
        weights = tracker.compute_dynamic_weights(["deepseek", "qwen"], method="pass_rate")
        assert weights["deepseek"] > weights["qwen"]

    def test_compute_dynamic_weights_normalize(self):
        """Weights should sum to 1.0."""
        tracker = AgentPerformanceTracker()
        for _ in range(5):
            tracker.record_result("deepseek", {"sharpe_ratio": 1.5}, passed=True, fitness_score=65)
            tracker.record_result("qwen", {"sharpe_ratio": 1.0}, passed=True, fitness_score=55)
            tracker.record_result("perplexity", {"sharpe_ratio": 0.8}, passed=False, fitness_score=40)

        weights = tracker.compute_dynamic_weights(["deepseek", "qwen", "perplexity"])
        assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_get_leaderboard(self):
        """Leaderboard should be sorted by composite score."""
        tracker = AgentPerformanceTracker()
        for _ in range(5):
            tracker.record_result("deepseek", {"sharpe_ratio": 2.0}, passed=True, fitness_score=80)
            tracker.record_result("qwen", {"sharpe_ratio": 0.5}, passed=False, fitness_score=30)

        leaderboard = tracker.get_leaderboard()
        assert len(leaderboard) == 2
        assert leaderboard[0]["agent_name"] == "deepseek"
        assert leaderboard[0]["composite_score"] > leaderboard[1]["composite_score"]

    def test_get_comparison(self):
        """Comparison should return all agents."""
        tracker = AgentPerformanceTracker()
        tracker.record_result("deepseek", {"sharpe_ratio": 1.5}, passed=True)
        tracker.record_result("qwen", {"sharpe_ratio": 1.0}, passed=True)

        comparison = tracker.get_comparison()
        assert "deepseek" in comparison
        assert "qwen" in comparison

    def test_get_comparison_specific_agents(self):
        """Comparison with specific agents."""
        tracker = AgentPerformanceTracker()
        tracker.record_result("deepseek", {"sharpe_ratio": 1.5}, passed=True)
        tracker.record_result("qwen", {"sharpe_ratio": 1.0}, passed=True)
        tracker.record_result("perplexity", {"sharpe_ratio": 0.8}, passed=True)

        comparison = tracker.get_comparison(["deepseek", "qwen"])
        assert len(comparison) == 2
        assert "perplexity" not in comparison

    def test_get_specialization_analysis(self):
        """Specialization analysis by strategy type."""
        tracker = AgentPerformanceTracker()
        tracker.record_result(
            "deepseek",
            {"sharpe_ratio": 2.0},
            strategy_type="rsi",
            passed=True,
            fitness_score=80,
        )
        tracker.record_result(
            "deepseek",
            {"sharpe_ratio": 0.5},
            strategy_type="macd",
            passed=False,
            fitness_score=30,
        )

        analysis = tracker.get_specialization_analysis("deepseek")
        assert "rsi" in analysis
        assert "macd" in analysis
        assert analysis["rsi"] > analysis["macd"]

    def test_sync_to_consensus_engine(self):
        """Sync should call consensus engine update_performance."""
        from unittest.mock import MagicMock

        tracker = AgentPerformanceTracker()
        for _ in range(3):
            tracker.record_result(
                "deepseek",
                {"sharpe_ratio": 1.5, "win_rate": 0.55, "profit_factor": 1.8},
                passed=True,
            )

        mock_consensus = MagicMock()
        tracker.sync_to_consensus_engine(mock_consensus)
        mock_consensus.update_performance.assert_called_once()

        call_kwargs = mock_consensus.update_performance.call_args
        assert call_kwargs[1]["agent_name"] == "deepseek"

    def test_get_stats(self):
        """Stats should show tracker state."""
        tracker = AgentPerformanceTracker()
        tracker.record_result("deepseek", {"sharpe_ratio": 1.0}, passed=True)
        tracker.record_result("qwen", {"sharpe_ratio": 0.8}, passed=True)

        stats = tracker.get_stats()
        assert stats["tracked_agents"] == 2
        assert stats["total_records"] == 2
        assert "deepseek" in stats["agents"]
        assert "qwen" in stats["agents"]

    def test_reset_specific_agent(self):
        """Reset specific agent should clear only that agent."""
        tracker = AgentPerformanceTracker()
        tracker.record_result("deepseek", {"sharpe_ratio": 1.0}, passed=True)
        tracker.record_result("qwen", {"sharpe_ratio": 0.8}, passed=True)

        tracker.reset("deepseek")
        assert "deepseek" not in tracker._records
        assert "qwen" in tracker._records

    def test_reset_all(self):
        """Reset all should clear everything."""
        tracker = AgentPerformanceTracker()
        tracker.record_result("deepseek", {"sharpe_ratio": 1.0}, passed=True)
        tracker.record_result("qwen", {"sharpe_ratio": 0.8}, passed=True)

        tracker.reset()
        assert len(tracker._records) == 0
        assert len(tracker._profiles) == 0

    def test_window_size_limit(self):
        """Records should be limited by window size."""
        tracker = AgentPerformanceTracker(window_size=5)
        for i in range(10):
            tracker.record_result(
                "deepseek",
                {"sharpe_ratio": float(i)},
                passed=True,
                fitness_score=float(i * 10),
            )
        assert len(tracker._records["deepseek"]) == 5

    def test_sharpe_trend_improving(self):
        """Improving Sharpe should have positive trend."""
        tracker = AgentPerformanceTracker()
        for i in range(6):
            tracker.record_result(
                "deepseek",
                {"sharpe_ratio": 0.5 + i * 0.3},
                passed=True,
                fitness_score=50 + i * 5,
            )
        profile = tracker.get_profile("deepseek")
        assert profile.sharpe_trend > 0

    def test_sharpe_trend_declining(self):
        """Declining Sharpe should have negative trend."""
        tracker = AgentPerformanceTracker()
        for i in range(6):
            tracker.record_result(
                "deepseek",
                {"sharpe_ratio": 2.0 - i * 0.3},
                passed=True,
                fitness_score=80 - i * 5,
            )
        profile = tracker.get_profile("deepseek")
        assert profile.sharpe_trend < 0

    def test_consistency_score_high(self):
        """Consistent results should have high consistency."""
        tracker = AgentPerformanceTracker()
        for _ in range(5):
            tracker.record_result(
                "deepseek",
                {"sharpe_ratio": 1.5},
                passed=True,
                fitness_score=70,
            )
        profile = tracker.get_profile("deepseek")
        assert profile.consistency_score > 0.8

    def test_consistency_score_low(self):
        """Inconsistent results should have lower consistency."""
        tracker = AgentPerformanceTracker()
        sharpes = [0.1, 3.0, 0.5, 2.5, 0.2]
        for s in sharpes:
            tracker.record_result(
                "deepseek",
                {"sharpe_ratio": s},
                passed=True,
                fitness_score=s * 30,
            )
        profile = tracker.get_profile("deepseek")
        assert profile.consistency_score < 0.5

    def test_recency_bonus_in_weights(self):
        """Positive trend should boost weight slightly."""
        tracker = AgentPerformanceTracker()

        # DeepSeek: improving
        for i in range(5):
            tracker.record_result(
                "deepseek",
                {"sharpe_ratio": 1.0 + i * 0.3},
                passed=True,
                fitness_score=50 + i * 10,
            )

        # Qwen: stable
        for _ in range(5):
            tracker.record_result(
                "qwen",
                {"sharpe_ratio": 1.5},
                passed=True,
                fitness_score=65,
            )

        weights = tracker.compute_dynamic_weights(["deepseek", "qwen"])
        # Both should have reasonable weights
        assert weights["deepseek"] > 0.1
        assert weights["qwen"] > 0.1
