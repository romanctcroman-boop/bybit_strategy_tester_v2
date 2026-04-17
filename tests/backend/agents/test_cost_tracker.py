# Tests for cost_tracker.py

import time

import pytest

from backend.agents.cost_tracker import (
    COST_TABLE,
    CostRecord,
    CostSummary,
    CostTracker,
)


class TestCostRecord:
    def test_creation(self):
        record = CostRecord(
            agent="claude",
            model="claude-haiku-4-5-20251001",
            prompt_tokens=1000,
            completion_tokens=500,
            total_tokens=1500,
        )
        assert record.agent == "claude"
        assert record.total_tokens == 1500
        assert record.timestamp > 0

    def test_optional_fields(self):
        record = CostRecord(
            agent="claude",
            model="claude-haiku-4-5-20251001",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            reasoning_tokens=30,
            cost_usd=0.01,
            session_id="sess-1",
            task_type="analyze",
        )
        assert record.reasoning_tokens == 30
        assert record.cost_usd == 0.01
        assert record.session_id == "sess-1"


class TestCostTable:
    def test_all_providers_present(self):
        assert "claude" in COST_TABLE
        assert "claude" in COST_TABLE
        assert "perplexity" in COST_TABLE

    def test_claude_models(self):
        assert "claude-haiku-4-5-20251001" in COST_TABLE["claude"]
        assert "claude-sonnet-4-6" in COST_TABLE["claude"]

    def test_rates_are_tuples(self):
        for _provider, models in COST_TABLE.items():
            for _model, rates in models.items():
                assert isinstance(rates, tuple)
                assert len(rates) == 2
                assert rates[0] >= 0
                assert rates[1] >= 0


class TestCostTracker:
    def test_record_basic(self):
        tracker = CostTracker()
        record = tracker.record("claude", "claude-haiku-4-5-20251001", 1000, 500, 1500)
        assert isinstance(record, CostRecord)
        assert record.cost_usd > 0

    def test_record_accumulates(self):
        tracker = CostTracker()
        tracker.record("claude", "claude-haiku-4-5-20251001", 1000, 500, 1500)
        tracker.record("claude", "claude-haiku-4-5-20251001", 2000, 1000, 3000)
        summary = tracker.get_summary()
        assert isinstance(summary, CostSummary)
        assert summary.total_requests == 2
        assert summary.total_tokens == 4500
        assert summary.total_cost_usd > 0

    def test_record_custom_cost(self):
        tracker = CostTracker()
        record = tracker.record("claude", "claude-haiku-4-5-20251001", 1000, 500, 1500, cost_usd=0.05)
        assert record.cost_usd == 0.05

    def test_estimate_cost_known_model(self):
        tracker = CostTracker()
        cost = tracker._estimate_cost("claude", "claude-haiku-4-5-20251001", 1000000, 1000000)
        input_rate, output_rate = COST_TABLE["claude"]["claude-haiku-4-5-20251001"]
        expected = (1000000 * input_rate + 1000000 * output_rate) / 1_000_000
        assert cost == pytest.approx(expected)

    def test_estimate_cost_unknown_model(self):
        tracker = CostTracker()
        cost = tracker._estimate_cost("unknown", "unknown-model", 1000, 500)
        assert cost > 0

    def test_get_summary_structure(self):
        tracker = CostTracker()
        tracker.record("claude", "claude-haiku-4-5-20251001", 1000, 500, 1500)
        summary = tracker.get_summary()
        assert isinstance(summary, CostSummary)
        assert summary.total_cost_usd > 0
        assert summary.total_tokens == 1500
        assert summary.total_requests == 1
        assert "claude" in summary.by_agent
        assert summary.period_start != ""
        assert summary.period_end != ""

    def test_cleanup_old_records(self):
        tracker = CostTracker()
        tracker.record("claude", "claude-haiku-4-5-20251001", 100, 50, 150)
        tracker._records[0].timestamp = time.time() - 200000
        removed = tracker.cleanup_old_records(max_age_seconds=100000)
        assert removed == 1

    def test_per_agent_totals(self):
        tracker = CostTracker()
        tracker.record("claude", "claude-haiku-4-5-20251001", 1000, 500, 1500)
        tracker.record("claude", "claude-haiku-4-5-20251001", 2000, 1000, 3000)
        summary = tracker.get_summary()
        assert "claude" in summary.by_agent
        assert "claude" in summary.by_agent
        assert summary.total_tokens == 4500

    def test_get_summary_period_today(self):
        tracker = CostTracker()
        tracker.record("claude", "claude-haiku-4-5-20251001", 100, 50, 150)
        summary = tracker.get_summary(period="today")
        assert summary.total_requests >= 1

    def test_get_daily_breakdown(self):
        tracker = CostTracker()
        tracker.record("claude", "claude-haiku-4-5-20251001", 100, 50, 150)
        breakdown = tracker.get_daily_breakdown(days=1)
        assert len(breakdown) >= 1
        assert "date" in breakdown[0]
        assert "total_cost" in breakdown[0]

    def test_get_recent_records(self):
        tracker = CostTracker()
        tracker.record("claude", "claude-haiku-4-5-20251001", 100, 50, 150)
        records = tracker.get_recent_records(limit=10)
        assert len(records) == 1
        assert records[0]["agent"] == "claude"

    def test_reset_session(self):
        tracker = CostTracker()
        tracker.record("claude", "claude-haiku-4-5-20251001", 100, 50, 150, session_id="s1")
        tracker.record("claude", "claude-haiku-4-5-20251001", 200, 100, 300, session_id="s2")
        tracker.reset_session("s1")
        remaining = [r for r in tracker._records if r.session_id == "s1"]
        assert len(remaining) == 0
        assert len(tracker._records) == 1
