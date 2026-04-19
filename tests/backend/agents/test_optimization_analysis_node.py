"""
CP3 — Phase 3: OptimizationAnalysisNode

Tests:
  1. top_trials forwarded correctly — node receives the full top_trials list
  2. State opt_insights populated after successful analysis
  3. Result keys present: param_clusters, winning_zones, risks, next_ranges
  4. Graceful skip when top_trials is empty
  5. Graceful skip when optimize_strategy result is missing entirely
  6. Claude prompt contains symbol, regime, and trial data
  7. Claude prompt includes sharpe, drawdown, trades, params for each trial
  8. LLM failure → empty opt_insights, result recorded without crash
  9. _parse_insights strips markdown code fences
  10. _parse_insights returns empty dict on invalid JSON
"""

from __future__ import annotations

import asyncio
import json

from backend.agents.langgraph_orchestrator import AgentState
from backend.agents.trading_strategy_graph import OptimizationAnalysisNode

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(coro):
    return asyncio.run(coro)


def _make_top_trials(n: int = 5) -> list[dict]:
    """Return n synthetic trial dicts with the shape OptimizationNode produces."""
    trials = []
    for i in range(n):
        trials.append(
            {
                "rank": i + 1,
                "sharpe": round(1.5 - i * 0.15, 3),
                "max_drawdown": round(8.0 + i * 1.2, 1),
                "trades": 40 - i * 3,
                "params": {"rsi_period": 14 + i, "sl_pct": 0.02 + i * 0.002},
            }
        )
    return trials


_INSIGHTS_JSON = json.dumps(
    {
        "param_clusters": {"rsi_period": [14, 15, 16], "sl_pct": [0.02, 0.022]},
        "winning_zones": {"rsi_period": {"min": 13, "max": 17}, "sl_pct": {"min": 0.018, "max": 0.025}},
        "risks": [{"rank": 4, "issue": "High drawdown despite good Sharpe"}],
        "next_ranges": {"rsi_period": {"min": 13, "max": 18}, "sl_pct": {"min": 0.018, "max": 0.026}},
    }
)


def _make_state_with_opt_result(top_trials: list[dict] | None = None) -> AgentState:
    state = AgentState()
    state.context["symbol"] = "BTCUSDT"
    state.context["timeframe"] = "15"
    state.context["regime_classification"] = {"regime": "trending_up"}

    if top_trials is not None:
        state.set_result(
            "optimize_strategy",
            {
                "tested_combinations": len(top_trials),
                "best_score": 1.2,
                "best_params": {"rsi_period": 14},
                "best_sharpe": 1.5,
                "top_trials": top_trials,
                "param_sensitivity": {},
                "n_positive_sharpe": len(top_trials),
            },
        )
    return state


# ---------------------------------------------------------------------------
# 1. top_trials forwarded correctly
# ---------------------------------------------------------------------------


class TestTopTrialsForwarded:
    def test_n_trials_analysed_matches_input(self):
        node = OptimizationAnalysisNode()
        trials = _make_top_trials(12)
        state = _make_state_with_opt_result(trials)
        captured = {}

        async def _mock_llm(agent_name, prompt, system_msg, **kw):
            captured["prompt"] = prompt
            return _INSIGHTS_JSON

        node._call_llm = _mock_llm
        result = _run(node.execute(state))
        analysis = result.get_result("optimization_analysis")
        assert analysis["n_trials_analysed"] == 12


# ---------------------------------------------------------------------------
# 2. opt_insights populated
# ---------------------------------------------------------------------------


class TestOptInsightsPopulated:
    def test_opt_insights_is_dict_after_run(self):
        node = OptimizationAnalysisNode()
        state = _make_state_with_opt_result(_make_top_trials(5))

        async def _mock_llm(*a, **kw):
            return _INSIGHTS_JSON

        node._call_llm = _mock_llm
        result = _run(node.execute(state))
        assert isinstance(result.opt_insights, dict)
        assert result.opt_insights  # non-empty

    def test_opt_insights_contains_expected_keys(self):
        node = OptimizationAnalysisNode()
        state = _make_state_with_opt_result(_make_top_trials(5))

        async def _mock_llm(*a, **kw):
            return _INSIGHTS_JSON

        node._call_llm = _mock_llm
        result = _run(node.execute(state))
        for key in ("param_clusters", "winning_zones", "risks", "next_ranges"):
            assert key in result.opt_insights, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# 3. Result keys present
# ---------------------------------------------------------------------------


class TestResultKeys:
    def test_all_result_keys_present(self):
        node = OptimizationAnalysisNode()
        state = _make_state_with_opt_result(_make_top_trials(5))

        async def _mock_llm(*a, **kw):
            return _INSIGHTS_JSON

        node._call_llm = _mock_llm
        result = _run(node.execute(state))
        analysis = result.get_result("optimization_analysis")
        for key in ("param_clusters", "winning_zones", "risks", "next_ranges", "n_trials_analysed"):
            assert key in analysis, f"Missing result key: {key}"


# ---------------------------------------------------------------------------
# 4. Graceful skip — empty top_trials
# ---------------------------------------------------------------------------


class TestGracefulSkipEmptyTrials:
    def test_skip_when_top_trials_is_empty(self):
        node = OptimizationAnalysisNode()
        state = _make_state_with_opt_result([])  # empty list
        llm_called = {"n": 0}

        async def _mock_llm(*a, **kw):
            llm_called["n"] += 1
            return _INSIGHTS_JSON

        node._call_llm = _mock_llm
        result = _run(node.execute(state))

        assert llm_called["n"] == 0
        analysis = result.get_result("optimization_analysis")
        assert analysis.get("skipped") is True

    def test_opt_insights_empty_on_skip(self):
        node = OptimizationAnalysisNode()
        state = _make_state_with_opt_result([])

        async def _mock_llm(*a, **kw):
            return _INSIGHTS_JSON

        node._call_llm = _mock_llm
        result = _run(node.execute(state))
        # opt_insights should remain at its default empty dict
        assert result.opt_insights == {}


# ---------------------------------------------------------------------------
# 5. Graceful skip — optimize_strategy result missing
# ---------------------------------------------------------------------------


class TestGracefulSkipNoOptResult:
    def test_skip_when_no_optimize_result(self):
        node = OptimizationAnalysisNode()
        state = _make_state_with_opt_result(None)  # no set_result call
        llm_called = {"n": 0}

        async def _mock_llm(*a, **kw):
            llm_called["n"] += 1
            return _INSIGHTS_JSON

        node._call_llm = _mock_llm
        result = _run(node.execute(state))
        assert llm_called["n"] == 0
        assert result.get_result("optimization_analysis").get("skipped") is True


# ---------------------------------------------------------------------------
# 6. Prompt contains symbol and regime
# ---------------------------------------------------------------------------


class TestPromptContent:
    def test_prompt_contains_symbol(self):
        node = OptimizationAnalysisNode()
        state = _make_state_with_opt_result(_make_top_trials(3))
        state.context["symbol"] = "ETHUSDT"
        captured = {}

        async def _mock_llm(agent_name, prompt, system_msg, **kw):
            captured["prompt"] = prompt
            return _INSIGHTS_JSON

        node._call_llm = _mock_llm
        _run(node.execute(state))
        assert "ETHUSDT" in captured["prompt"]

    def test_prompt_contains_regime(self):
        node = OptimizationAnalysisNode()
        state = _make_state_with_opt_result(_make_top_trials(3))
        state.context["regime_classification"] = {"regime": "volatile"}
        captured = {}

        async def _mock_llm(agent_name, prompt, system_msg, **kw):
            captured["prompt"] = prompt
            return _INSIGHTS_JSON

        node._call_llm = _mock_llm
        _run(node.execute(state))
        assert "volatile" in captured["prompt"]


# ---------------------------------------------------------------------------
# 7. Prompt includes trial metrics
# ---------------------------------------------------------------------------


class TestPromptTrialMetrics:
    def test_prompt_includes_sharpe(self):
        node = OptimizationAnalysisNode()
        trials = _make_top_trials(3)
        state = _make_state_with_opt_result(trials)
        captured = {}

        async def _mock_llm(agent_name, prompt, system_msg, **kw):
            captured["prompt"] = prompt
            return _INSIGHTS_JSON

        node._call_llm = _mock_llm
        _run(node.execute(state))
        assert "sharpe" in captured["prompt"].lower()

    def test_prompt_includes_drawdown(self):
        node = OptimizationAnalysisNode()
        state = _make_state_with_opt_result(_make_top_trials(3))
        captured = {}

        async def _mock_llm(agent_name, prompt, system_msg, **kw):
            captured["prompt"] = prompt
            return _INSIGHTS_JSON

        node._call_llm = _mock_llm
        _run(node.execute(state))
        assert "drawdown" in captured["prompt"].lower()

    def test_prompt_includes_params(self):
        node = OptimizationAnalysisNode()
        state = _make_state_with_opt_result(_make_top_trials(3))
        captured = {}

        async def _mock_llm(agent_name, prompt, system_msg, **kw):
            captured["prompt"] = prompt
            return _INSIGHTS_JSON

        node._call_llm = _mock_llm
        _run(node.execute(state))
        assert "rsi_period" in captured["prompt"]


# ---------------------------------------------------------------------------
# 8. LLM failure → empty insights, no crash
# ---------------------------------------------------------------------------


class TestLLMFailure:
    def test_llm_exception_sets_empty_insights(self):
        node = OptimizationAnalysisNode()
        state = _make_state_with_opt_result(_make_top_trials(5))

        async def _mock_llm(*a, **kw):
            raise RuntimeError("API timeout")

        node._call_llm = _mock_llm
        result = _run(node.execute(state))
        assert result.opt_insights == {}
        # Node should still record a result (not crash)
        analysis = result.get_result("optimization_analysis")
        assert analysis is not None

    def test_llm_returns_none_gives_empty_insights(self):
        node = OptimizationAnalysisNode()
        state = _make_state_with_opt_result(_make_top_trials(5))

        async def _mock_llm(*a, **kw):
            return None

        node._call_llm = _mock_llm
        result = _run(node.execute(state))
        assert result.opt_insights == {}


# ---------------------------------------------------------------------------
# 9. _parse_insights strips markdown fences
# ---------------------------------------------------------------------------


class TestParseInsights:
    def test_strips_markdown_fences(self):
        raw = f"```json\n{_INSIGHTS_JSON}\n```"
        parsed = OptimizationAnalysisNode._parse_insights(raw)
        assert "param_clusters" in parsed

    def test_strips_plain_fences(self):
        raw = f"```\n{_INSIGHTS_JSON}\n```"
        parsed = OptimizationAnalysisNode._parse_insights(raw)
        assert "winning_zones" in parsed


# ---------------------------------------------------------------------------
# 10. _parse_insights returns {} on invalid JSON
# ---------------------------------------------------------------------------


class TestParseInsightsInvalidJson:
    def test_invalid_json_returns_empty_dict(self):
        assert OptimizationAnalysisNode._parse_insights("not json at all") == {}

    def test_none_returns_empty_dict(self):
        assert OptimizationAnalysisNode._parse_insights(None) == {}

    def test_empty_string_returns_empty_dict(self):
        assert OptimizationAnalysisNode._parse_insights("") == {}
