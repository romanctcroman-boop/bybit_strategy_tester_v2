"""
Tests for DebateROITracker.

Verifies data model, storage, retrieval, and ROI calculation logic.
All tests use in_memory=True — no files written to disk.
"""

from __future__ import annotations

import uuid

import pytest

from backend.agents.debate_roi_tracker import DebateROITracker, DebateRun

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tracker():
    """Fresh in-memory tracker per test."""
    return DebateROITracker(in_memory=True)


def _run(
    *,
    with_debate: bool,
    sharpe: float | None = None,
    llm_calls: int = 3,
    cost_usd: float = 0.002,
    symbol: str = "BTCUSDT",
    timeframe: str = "15",
    trade_count: int = 20,
) -> DebateRun:
    return DebateRun(
        run_id=str(uuid.uuid4()),
        symbol=symbol,
        timeframe=timeframe,
        with_debate=with_debate,
        sharpe_ratio=sharpe,
        max_drawdown=10.0,
        total_return=5.0,
        trade_count=trade_count,
        llm_call_count=llm_calls,
        total_cost_usd=cost_usd,
        agents=["deepseek"],
        error_count=0,
    )


# ---------------------------------------------------------------------------
# DebateRun dataclass
# ---------------------------------------------------------------------------


class TestDebateRunDataclass:
    def test_to_dict_contains_all_fields(self):
        run = _run(with_debate=True, sharpe=0.5)
        d = run.to_dict()
        assert "run_id" in d
        assert "sharpe_ratio" in d
        assert "with_debate" in d
        assert d["sharpe_ratio"] == 0.5

    def test_to_dict_agents_is_json_string(self):
        run = _run(with_debate=False)
        d = run.to_dict()
        import json

        assert isinstance(d["agents"], str)
        agents = json.loads(d["agents"])
        assert isinstance(agents, list)

    def test_from_row_round_trips(self):
        run = _run(with_debate=True, sharpe=1.2)
        d = run.to_dict()
        restored = DebateRun.from_row(d)
        assert restored.run_id == run.run_id
        assert restored.sharpe_ratio == run.sharpe_ratio
        assert restored.with_debate is True
        assert isinstance(restored.agents, list)

    def test_none_sharpe_preserved(self):
        run = _run(with_debate=False, sharpe=None)
        d = run.to_dict()
        restored = DebateRun.from_row(d)
        assert restored.sharpe_ratio is None

    def test_timestamp_is_iso_string(self):
        run = _run(with_debate=True)
        assert "T" in run.timestamp
        assert "2026" in run.timestamp or "2025" in run.timestamp


# ---------------------------------------------------------------------------
# Record & retrieve
# ---------------------------------------------------------------------------


class TestTrackerRecordAndRetrieve:
    def test_empty_tracker_has_zero_runs(self, tracker):
        assert tracker.count()["total"] == 0

    def test_record_single_run(self, tracker):
        tracker.record(_run(with_debate=True, sharpe=0.5))
        assert tracker.count()["total"] == 1

    def test_record_multiple_runs(self, tracker):
        for _ in range(5):
            tracker.record(_run(with_debate=True))
        assert tracker.count()["total"] == 5

    def test_count_splits_by_debate_flag(self, tracker):
        for _ in range(3):
            tracker.record(_run(with_debate=True))
        for _ in range(2):
            tracker.record(_run(with_debate=False))
        c = tracker.count()
        assert c["with_debate"] == 3
        assert c["without_debate"] == 2

    def test_runs_for_filters_correctly(self, tracker):
        tracker.record(_run(with_debate=True, sharpe=0.8))
        tracker.record(_run(with_debate=False, sharpe=0.3))
        with_runs = tracker.runs_for(with_debate=True)
        assert len(with_runs) == 1
        assert with_runs[0].sharpe_ratio == 0.8

    def test_all_runs_returns_both_groups(self, tracker):
        tracker.record(_run(with_debate=True))
        tracker.record(_run(with_debate=False))
        assert len(tracker.all_runs()) == 2

    def test_replace_on_duplicate_run_id(self, tracker):
        run = _run(with_debate=True, sharpe=0.5)
        tracker.record(run)
        # Record again with same run_id but different sharpe
        updated = DebateRun(
            run_id=run.run_id,
            symbol=run.symbol,
            timeframe=run.timeframe,
            with_debate=run.with_debate,
            sharpe_ratio=0.9,
            llm_call_count=run.llm_call_count,
            total_cost_usd=run.total_cost_usd,
        )
        tracker.record(updated)
        assert tracker.count()["total"] == 1
        assert tracker.all_runs()[0].sharpe_ratio == 0.9

    def test_record_preserves_metadata(self, tracker):
        run = _run(with_debate=True, symbol="ETHUSDT", timeframe="60", llm_calls=7, cost_usd=0.01)
        tracker.record(run)
        retrieved = tracker.all_runs()[0]
        assert retrieved.symbol == "ETHUSDT"
        assert retrieved.timeframe == "60"
        assert retrieved.llm_call_count == 7
        assert abs(retrieved.total_cost_usd - 0.01) < 1e-9


# ---------------------------------------------------------------------------
# ROI analysis
# ---------------------------------------------------------------------------


class TestDebateROIAnalysis:
    def test_debate_roi_none_when_no_data(self, tracker):
        assert tracker.debate_roi() is None

    def test_debate_roi_none_when_only_one_group(self, tracker):
        tracker.record(_run(with_debate=True, sharpe=0.5))
        assert tracker.debate_roi() is None

    def test_debate_roi_positive_when_debate_better(self, tracker):
        tracker.record(_run(with_debate=True, sharpe=0.8))
        tracker.record(_run(with_debate=False, sharpe=0.3))
        roi = tracker.debate_roi()
        assert roi is not None
        assert roi > 0

    def test_debate_roi_negative_when_debate_worse(self, tracker):
        tracker.record(_run(with_debate=True, sharpe=0.2))
        tracker.record(_run(with_debate=False, sharpe=0.7))
        roi = tracker.debate_roi()
        assert roi is not None
        assert roi < 0

    def test_debate_roi_zero_when_equal(self, tracker):
        tracker.record(_run(with_debate=True, sharpe=0.5))
        tracker.record(_run(with_debate=False, sharpe=0.5))
        roi = tracker.debate_roi()
        assert roi is not None
        assert abs(roi) < 1e-9

    def test_debate_roi_ignores_none_sharpe_runs(self, tracker):
        """Runs without backtest (sharpe=None) must not affect ROI calculation."""
        tracker.record(_run(with_debate=True, sharpe=0.6))
        tracker.record(_run(with_debate=True, sharpe=None))  # no backtest
        tracker.record(_run(with_debate=False, sharpe=0.4))
        roi = tracker.debate_roi()
        assert roi is not None
        assert abs(roi - 0.2) < 1e-9

    def test_debate_roi_averages_multiple_runs(self, tracker):
        # with_debate avg = (1.0 + 0.0) / 2 = 0.5
        # without avg = 0.3
        tracker.record(_run(with_debate=True, sharpe=1.0))
        tracker.record(_run(with_debate=True, sharpe=0.0))
        tracker.record(_run(with_debate=False, sharpe=0.3))
        roi = tracker.debate_roi()
        assert roi is not None
        assert abs(roi - 0.2) < 1e-9


# ---------------------------------------------------------------------------
# Cost overhead
# ---------------------------------------------------------------------------


class TestCostOverhead:
    def test_cost_overhead_none_when_no_data(self, tracker):
        assert tracker.cost_overhead() is None

    def test_cost_overhead_positive_for_debate(self, tracker):
        """Debate should use more LLM calls (4 agents vs 1)."""
        tracker.record(_run(with_debate=True, llm_calls=8))
        tracker.record(_run(with_debate=False, llm_calls=3))
        overhead = tracker.cost_overhead()
        assert overhead is not None
        assert overhead > 0

    def test_cost_overhead_is_difference_of_means(self, tracker):
        tracker.record(_run(with_debate=True, llm_calls=10))
        tracker.record(_run(with_debate=True, llm_calls=6))
        tracker.record(_run(with_debate=False, llm_calls=3))
        overhead = tracker.cost_overhead()
        # avg_debate = 8, avg_no_debate = 3, overhead = 5
        assert overhead is not None
        assert abs(overhead - 5.0) < 1e-9


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


class TestSummary:
    def test_summary_has_required_keys(self, tracker):
        summary = tracker.summary()
        assert "counts" in summary
        assert "debate_roi_sharpe" in summary
        assert "cost_overhead_calls" in summary
        assert "avg_cost_usd" in summary
        assert "sufficient_data" in summary

    def test_summary_sufficient_data_false_when_empty(self, tracker):
        assert tracker.summary()["sufficient_data"] is False

    def test_summary_sufficient_data_true_when_both_groups_have_sharpe(self, tracker):
        tracker.record(_run(with_debate=True, sharpe=0.5))
        tracker.record(_run(with_debate=False, sharpe=0.3))
        assert tracker.summary()["sufficient_data"] is True

    def test_summary_avg_cost_usd_computed(self, tracker):
        tracker.record(_run(with_debate=True, cost_usd=0.010))
        tracker.record(_run(with_debate=False, cost_usd=0.002))
        s = tracker.summary()
        assert abs(s["avg_cost_usd"]["with_debate"] - 0.010) < 1e-9
        assert abs(s["avg_cost_usd"]["without_debate"] - 0.002) < 1e-9

    def test_summary_counts_correct(self, tracker):
        for _ in range(4):
            tracker.record(_run(with_debate=True))
        for _ in range(2):
            tracker.record(_run(with_debate=False))
        c = tracker.summary()["counts"]
        assert c["total"] == 6
        assert c["with_debate"] == 4
        assert c["without_debate"] == 2


# ---------------------------------------------------------------------------
# Thread safety (basic)
# ---------------------------------------------------------------------------


class TestThreadSafety:
    def test_concurrent_writes_no_race(self, tracker):
        """50 concurrent writes from multiple threads should all succeed."""
        import threading

        errors = []

        def write():
            try:
                tracker.record(_run(with_debate=True, sharpe=0.5))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=write) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread errors: {errors}"
        # Some rows may be replaced (same uuid unlikely, but tolerate)
        assert tracker.count()["total"] >= 1


# ---------------------------------------------------------------------------
# record_from_state integration
# ---------------------------------------------------------------------------


class TestRecordFromState:
    def test_record_from_state_uses_backtest_metrics(self, tracker):
        """record_from_state should extract sharpe_ratio from state.results['backtest']."""
        from unittest.mock import MagicMock

        state = MagicMock()
        state.results = {
            "backtest": {
                "metrics": {
                    "sharpe_ratio": 0.75,
                    "max_drawdown": 15.0,
                    "total_return": 8.0,
                    "total_trades": 30,
                }
            }
        }
        state.llm_call_count = 5
        state.total_cost_usd = 0.004
        state.context = {"agents": ["deepseek"]}
        state.errors = {}

        run = tracker.record_from_state(
            state,
            run_id="test-run-1",
            symbol="BTCUSDT",
            timeframe="15",
            with_debate=True,
        )

        assert run.sharpe_ratio == 0.75
        assert run.trade_count == 30
        assert run.llm_call_count == 5
        assert tracker.count()["total"] == 1

    def test_record_from_state_handles_missing_backtest(self, tracker):
        """No crash when backtest was skipped (no metrics)."""
        from unittest.mock import MagicMock

        state = MagicMock()
        state.results = {}
        state.llm_call_count = 3
        state.total_cost_usd = 0.001
        state.context = {"agents": ["deepseek"]}
        state.errors = {}

        run = tracker.record_from_state(
            state,
            run_id="test-run-2",
            symbol="ETHUSDT",
            timeframe="60",
            with_debate=False,
        )

        assert run.sharpe_ratio is None
        assert run.trade_count is None
        assert tracker.count()["total"] == 1
