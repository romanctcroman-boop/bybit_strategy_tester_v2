# Tests for cost_tracker.py

import time

import pytest

from backend.agents.cost_tracker import COST_TABLE, CostRecord, CostTracker


class TestCostRecord:
    def test_creation(self):
        record = CostRecord(
            agent="deepseek",
            model="deepseek-chat",
            prompt_tokens=1000,
            completion_tokens=500,
            total_tokens=1500,
        )
        assert record.agent == "deepseek"
        assert record.total_tokens == 1500
        assert record.timestamp > 0

    def test_optional_fields(self):
        record = CostRecord(
            agent="qwen",
            model="qwen-plus",
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
        assert "deepseek" in COST_TABLE
        assert "qwen" in COST_TABLE
        assert "perplexity" in COST_TABLE

    def test_deepseek_models(self):
        assert "deepseek-chat" in COST_TABLE["deepseek"]
        assert "deepseek-reasoner" in COST_TABLE["deepseek"]

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
        record = tracker.record("deepseek", "deepseek-chat", 1000, 500, 1500)
        assert isinstance(record, CostRecord)
        assert record.cost_usd > 0

    def test_record_accumulates(self):
        tracker = CostTracker()
        tracker.record("deepseek", "deepseek-chat", 1000, 500, 1500)
        tracker.record("deepseek", "deepseek-chat", 2000, 1000, 3000)
        summary = tracker.get_summary()
        assert summary["total_requests"] == 2
        assert summary["total_tokens"] == 4500
        assert summary["total_cost_usd"] > 0

    def test_record_custom_cost(self):
        tracker = CostTracker()
        record = tracker.record("deepseek", "deepseek-chat", 1000, 500, 1500, cost_usd=0.05)
        assert record.cost_usd == 0.05

    def test_estimate_cost_known_model(self):
        tracker = CostTracker()
        cost = tracker._estimate_cost("deepseek", "deepseek-chat", 1000000, 1000000)
        input_rate, output_rate = COST_TABLE["deepseek"]["deepseek-chat"]
        expected = (1000000 * input_rate + 1000000 * output_rate) / 1_000_000
        assert cost == pytest.approx(expected)

    def test_estimate_cost_unknown_model(self):
        tracker = CostTracker()
        cost = tracker._estimate_cost("unknown", "unknown-model", 1000, 500)
        assert cost > 0

    def test_get_summary_structure(self):
        tracker = CostTracker()
        tracker.record("deepseek", "deepseek-chat", 1000, 500, 1500)
        summary = tracker.get_summary()
        assert "total_cost_usd" in summary
        assert "total_tokens" in summary
        assert "total_requests" in summary
        assert "agents" in summary
        assert "deepseek" in summary["agents"]
        agent_data = summary["agents"]["deepseek"]
        assert "hourly_cost_usd" in agent_data
        assert "daily_cost_usd" in agent_data
        assert "hourly_budget_remaining" in agent_data
        assert "daily_budget_remaining" in agent_data

    def test_cleanup_old_records(self):
        tracker = CostTracker()
        tracker.record("deepseek", "deepseek-chat", 100, 50, 150)
        tracker._records[0].timestamp = time.time() - 200000
        removed = tracker.cleanup_old_records(max_age_seconds=100000)
        assert removed == 1

    def test_per_agent_totals(self):
        tracker = CostTracker()
        tracker.record("deepseek", "deepseek-chat", 1000, 500, 1500)
        tracker.record("qwen", "qwen-plus", 2000, 1000, 3000)
        summary = tracker.get_summary()
        assert "deepseek" in summary["agents"]
        assert "qwen" in summary["agents"]
        assert summary["agents"]["deepseek"]["total_tokens"] == 1500
        assert summary["agents"]["qwen"]["total_tokens"] == 3000
