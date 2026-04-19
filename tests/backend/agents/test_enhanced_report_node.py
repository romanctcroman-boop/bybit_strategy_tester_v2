"""
CP8 — Phase 8: Enhanced ReportNode

Tests:
  1.  report contains "top_trials_table" key
  2.  top_trials_table has up to 20 entries
  3.  each trial entry has rank, sharpe, max_drawdown, trades, params
  4.  top_trials_table empty when no opt result
  5.  report contains "iteration_history" key
  6.  iteration_history has sharpe and params per entry
  7.  iteration_history empty when no opt_iterations
  8.  report contains "opt_insights" key (may be empty dict)
  9.  report contains "debate_outcome" key (may be None)
  10. report contains "comparison" key with sharpe_improvement
  11. sharpe_improvement = final_sharpe - initial_sharpe
  12. comparison.initial_sharpe comes from backtest result
  13. comparison.final_sharpe comes from opt_result.best_sharpe
  14. report contains "pipeline_mode" key
  15. existing fields still present: pipeline_metrics, selected, backtest
"""

from __future__ import annotations

from backend.agents.langgraph_orchestrator import AgentState
from backend.agents.trading_strategy_graph import _report_node

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(
    with_opt: bool = True,
    n_trials: int = 5,
    n_iterations: int = 2,
    with_debate: bool = True,
    with_insights: bool = True,
    initial_sharpe: float = 0.8,
    final_sharpe: float = 1.5,
) -> AgentState:
    state = AgentState()
    state.context["symbol"] = "BTCUSDT"
    state.pipeline_mode = "optimize"

    # backtest result (initial IS run)
    state.set_result(
        "backtest",
        {
            "sharpe_ratio": initial_sharpe,
            "max_drawdown": 15.0,
            "total_trades": 30,
            "win_rate": 0.5,
        },
    )

    if with_opt:
        top_trials = [
            {
                "rank": i + 1,
                "sharpe": final_sharpe - i * 0.05,
                "max_drawdown": 10.0 + i,
                "trades": 40 - i,
                "params": {"rsi_period": 14 + i},
            }
            for i in range(n_trials)
        ]
        state.set_result(
            "optimize_strategy",
            {
                "best_sharpe": final_sharpe,
                "best_drawdown": 10.0,
                "best_trades": 40,
                "best_params": {"rsi_period": 14},
                "top_trials": top_trials,
            },
        )

    if n_iterations > 0:
        state.opt_iterations = [
            {
                "iteration": i + 1,
                "best_sharpe": initial_sharpe + (final_sharpe - initial_sharpe) * (i + 1) / n_iterations,
                "best_params": {"rsi_period": 14 + i},
            }
            for i in range(n_iterations)
        ]

    if with_insights:
        state.opt_insights = {
            "param_clusters": {"rsi_period": [14, 15]},
            "winning_zones": {"rsi_period": {"min": 12, "max": 18}},
            "risks": [],
            "next_ranges": {},
        }

    if with_debate:
        state.debate_outcome = {
            "decision": "proceed",
            "risk_score": 4,
            "conditions": [],
            "rationale": "Strategy looks solid.",
        }

    # Required for select_best / parse_responses
    state.set_result("select_best", {"selected_agent": "claude"})
    state.set_result("parse_responses", {"proposals": []})

    return state


# ---------------------------------------------------------------------------
# 1-4. top_trials_table
# ---------------------------------------------------------------------------


class TestTopTrialsTable:
    def test_top_trials_table_key_present(self):
        state = _make_state()
        result = _report_node(state)
        report = result.get_result("report")
        assert "top_trials_table" in report

    def test_top_trials_table_up_to_20_entries(self):
        state = _make_state(n_trials=25)
        # Add 25 trials to opt result
        state.set_result(
            "optimize_strategy",
            {
                "best_sharpe": 1.5,
                "best_drawdown": 10.0,
                "best_trades": 40,
                "best_params": {},
                "top_trials": [
                    {"rank": i + 1, "sharpe": 1.5, "max_drawdown": 10.0, "trades": 40, "params": {}} for i in range(25)
                ],
            },
        )
        result = _report_node(state)
        table = result.get_result("report")["top_trials_table"]
        assert len(table) <= 20

    def test_trial_entry_has_required_fields(self):
        state = _make_state(n_trials=3)
        result = _report_node(state)
        table = result.get_result("report")["top_trials_table"]
        assert len(table) > 0
        for entry in table:
            for key in ("rank", "sharpe", "max_drawdown", "trades", "params"):
                assert key in entry, f"Missing trial field: {key}"

    def test_top_trials_empty_without_opt_result(self):
        state = _make_state(with_opt=False)
        result = _report_node(state)
        table = result.get_result("report")["top_trials_table"]
        assert table == []


# ---------------------------------------------------------------------------
# 5-7. iteration_history
# ---------------------------------------------------------------------------


class TestIterationHistory:
    def test_iteration_history_key_present(self):
        state = _make_state()
        result = _report_node(state)
        assert "iteration_history" in result.get_result("report")

    def test_iteration_history_entries_have_sharpe_and_params(self):
        state = _make_state(n_iterations=3)
        result = _report_node(state)
        history = result.get_result("report")["iteration_history"]
        assert len(history) == 3
        for entry in history:
            assert "sharpe" in entry
            assert "params" in entry

    def test_iteration_history_empty_without_iterations(self):
        state = _make_state(n_iterations=0)
        result = _report_node(state)
        assert result.get_result("report")["iteration_history"] == []


# ---------------------------------------------------------------------------
# 8-9. opt_insights and debate_outcome
# ---------------------------------------------------------------------------


class TestInsightsAndDebate:
    def test_opt_insights_key_present(self):
        state = _make_state(with_insights=True)
        result = _report_node(state)
        report = result.get_result("report")
        assert "opt_insights" in report
        assert "param_clusters" in report["opt_insights"]

    def test_opt_insights_empty_dict_when_no_insights(self):
        state = _make_state(with_insights=False)
        result = _report_node(state)
        assert result.get_result("report")["opt_insights"] == {}

    def test_debate_outcome_key_present(self):
        state = _make_state(with_debate=True)
        result = _report_node(state)
        assert "debate_outcome" in result.get_result("report")
        assert result.get_result("report")["debate_outcome"]["decision"] == "proceed"

    def test_debate_outcome_none_when_no_debate(self):
        state = _make_state(with_debate=False)
        result = _report_node(state)
        assert result.get_result("report")["debate_outcome"] is None


# ---------------------------------------------------------------------------
# 10-13. comparison
# ---------------------------------------------------------------------------


class TestComparison:
    def test_comparison_key_present(self):
        state = _make_state()
        result = _report_node(state)
        assert "comparison" in result.get_result("report")

    def test_sharpe_improvement_calculated_correctly(self):
        state = _make_state(initial_sharpe=0.8, final_sharpe=1.5)
        result = _report_node(state)
        comp = result.get_result("report")["comparison"]
        assert abs(comp["sharpe_improvement"] - 0.7) < 0.01

    def test_initial_sharpe_from_backtest(self):
        state = _make_state(initial_sharpe=0.6, final_sharpe=1.2)
        result = _report_node(state)
        comp = result.get_result("report")["comparison"]
        assert abs(comp["initial_sharpe"] - 0.6) < 0.01

    def test_final_sharpe_from_opt_result(self):
        state = _make_state(initial_sharpe=0.6, final_sharpe=1.8)
        result = _report_node(state)
        comp = result.get_result("report")["comparison"]
        assert abs(comp["final_sharpe"] - 1.8) < 0.01


# ---------------------------------------------------------------------------
# 14-15. pipeline_mode and legacy fields
# ---------------------------------------------------------------------------


class TestLegacyFields:
    def test_pipeline_mode_present(self):
        state = _make_state()
        state.pipeline_mode = "optimize"
        result = _report_node(state)
        assert result.get_result("report")["pipeline_mode"] == "optimize"

    def test_pipeline_metrics_still_present(self):
        state = _make_state()
        result = _report_node(state)
        report = result.get_result("report")
        assert "pipeline_metrics" in report
        assert "total_cost_usd" in report["pipeline_metrics"]
        assert "llm_call_count" in report["pipeline_metrics"]

    def test_backtest_field_still_present(self):
        state = _make_state()
        result = _report_node(state)
        assert "backtest" in result.get_result("report")

    def test_selected_field_still_present(self):
        state = _make_state()
        result = _report_node(state)
        assert "selected" in result.get_result("report")
