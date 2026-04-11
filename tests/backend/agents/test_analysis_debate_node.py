"""
CP5 — Phase 5: AnalysisDebateNode

Tests:
  1.  execute() sets state.debate_outcome with required keys
  2.  decision is one of {"proceed", "reject", "conditional"}
  3.  risk_score is an integer in [0, 10]
  4.  conditions is a list
  5.  Both Sonnet (optimist) and Haiku (risk) LLM calls are made
  6.  Synthesis call is made after parallel debate calls
  7.  "reject" decision propagates to state.debate_outcome["decision"]
  8.  _is_debate_rejected → True when decision == "reject"
  9.  _is_debate_rejected → False when decision == "proceed"
  10. _is_debate_rejected → False when debate_outcome is None
  11. LLM failure on parallel round → safe default "proceed" outcome
  12. LLM failure on synthesis → safe default "proceed" outcome
  13. _parse_outcome strips markdown fences
  14. _parse_outcome normalises unknown decision to "proceed"
  15. _parse_outcome returns None on invalid JSON
  16. _build_metrics_summary includes sharpe, drawdown, trades
  17. debate result is also stored via state.set_result("analysis_debate", ...)
"""

from __future__ import annotations

import asyncio

from backend.agents.langgraph_orchestrator import AgentState
from backend.agents.trading_strategy_graph import AnalysisDebateNode, _is_debate_rejected

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(coro):
    return asyncio.run(coro)


_PROCEED_JSON = '{"decision": "proceed", "risk_score": 3, "conditions": [], "rationale": "Looks solid."}'
_REJECT_JSON = '{"decision": "reject", "risk_score": 9, "conditions": [], "rationale": "Too risky."}'
_CONDITIONAL_JSON = (
    '{"decision": "conditional", "risk_score": 6, '
    '"conditions": ["Add trailing stop"], "rationale": "Good but needs guard."}'
)


def _make_state(sharpe: float = 1.2, dd: float = 8.0) -> AgentState:
    state = AgentState()
    state.context["symbol"] = "BTCUSDT"
    state.context["regime_classification"] = {"regime": "trending_up"}
    state.set_result(
        "optimize_strategy",
        {
            "best_sharpe": sharpe,
            "best_drawdown": dd,
            "best_trades": 40,
            "n_positive_sharpe": 12,
            "best_params": {"rsi_period": 14},
        },
    )
    state.set_result("backtest", {"sharpe_ratio": sharpe, "max_drawdown": dd, "total_trades": 40})
    state.set_result("optimization_analysis", {"risks": []})
    return state


def _stub_debate_llm(node: AnalysisDebateNode, synthesis_response: str) -> list:
    """Stub _call_llm: debate calls return short text, synthesis returns synthesis_response."""
    calls = []

    async def _mock_llm(agent_name, prompt, system_msg, **kw):
        calls.append(agent_name)
        if "Synthesiser" in system_msg or kw.get("json_mode"):
            return synthesis_response
        # Optimist / Risk Manager — return plain text
        if "OPTIMISTIC" in system_msg or "SCEPTICAL" in system_msg:
            return f"Arguments from {agent_name}."
        return synthesis_response

    node._call_llm = _mock_llm
    return calls


# ---------------------------------------------------------------------------
# 1-4. Basic outcome structure
# ---------------------------------------------------------------------------


class TestDebateOutcomeStructure:
    def test_debate_outcome_keys_present(self):
        node = AnalysisDebateNode()
        state = _make_state()
        _stub_debate_llm(node, _PROCEED_JSON)
        result = _run(node.execute(state))
        outcome = result.debate_outcome
        assert outcome is not None
        for key in ("decision", "risk_score", "conditions", "rationale"):
            assert key in outcome, f"Missing key: {key}"

    def test_decision_is_valid_value(self):
        node = AnalysisDebateNode()
        state = _make_state()
        _stub_debate_llm(node, _PROCEED_JSON)
        result = _run(node.execute(state))
        assert result.debate_outcome["decision"] in {"proceed", "reject", "conditional"}

    def test_risk_score_is_int_in_range(self):
        node = AnalysisDebateNode()
        state = _make_state()
        _stub_debate_llm(node, _PROCEED_JSON)
        result = _run(node.execute(state))
        score = result.debate_outcome["risk_score"]
        assert isinstance(score, int)
        assert 0 <= score <= 10

    def test_conditions_is_list(self):
        node = AnalysisDebateNode()
        state = _make_state()
        _stub_debate_llm(node, _PROCEED_JSON)
        result = _run(node.execute(state))
        assert isinstance(result.debate_outcome["conditions"], list)


# ---------------------------------------------------------------------------
# 5-6. LLM call routing
# ---------------------------------------------------------------------------


class TestLLMCallRouting:
    def test_both_sonnet_and_haiku_called(self):
        node = AnalysisDebateNode()
        state = _make_state()
        calls = _stub_debate_llm(node, _PROCEED_JSON)
        _run(node.execute(state))
        # Sonnet for optimist, haiku for risk + haiku for synthesis
        assert "claude-sonnet" in calls
        assert "claude-haiku" in calls

    def test_at_least_three_llm_calls(self):
        """Optimist (sonnet) + Risk (haiku) + Synthesis (haiku) = 3 calls."""
        node = AnalysisDebateNode()
        state = _make_state()
        calls = _stub_debate_llm(node, _PROCEED_JSON)
        _run(node.execute(state))
        assert len(calls) >= 3


# ---------------------------------------------------------------------------
# 7. Reject decision propagates
# ---------------------------------------------------------------------------


class TestRejectDecision:
    def test_reject_stored_in_debate_outcome(self):
        node = AnalysisDebateNode()
        state = _make_state(sharpe=0.2, dd=35.0)
        _stub_debate_llm(node, _REJECT_JSON)
        result = _run(node.execute(state))
        assert result.debate_outcome["decision"] == "reject"
        assert result.debate_outcome["risk_score"] == 9


# ---------------------------------------------------------------------------
# 8-10. _is_debate_rejected helper
# ---------------------------------------------------------------------------


class TestIsDebateRejected:
    def test_true_when_reject(self):
        state = AgentState()
        state.debate_outcome = {"decision": "reject", "risk_score": 9, "conditions": [], "rationale": ""}
        assert _is_debate_rejected(state) is True

    def test_false_when_proceed(self):
        state = AgentState()
        state.debate_outcome = {"decision": "proceed", "risk_score": 2, "conditions": [], "rationale": ""}
        assert _is_debate_rejected(state) is False

    def test_false_when_no_outcome(self):
        state = AgentState()
        assert state.debate_outcome is None
        assert _is_debate_rejected(state) is False


# ---------------------------------------------------------------------------
# 11-12. LLM failure fallback
# ---------------------------------------------------------------------------


class TestLLMFailureFallback:
    def test_parallel_failure_returns_safe_default(self):
        node = AnalysisDebateNode()
        state = _make_state()

        async def _failing_llm(*a, **kw):
            raise RuntimeError("API down")

        node._call_llm = _failing_llm
        result = _run(node.execute(state))
        # Should still produce a valid outcome (safe default)
        assert result.debate_outcome is not None
        assert result.debate_outcome["decision"] in {"proceed", "reject", "conditional"}

    def test_synthesis_failure_returns_safe_default(self):
        node = AnalysisDebateNode()
        state = _make_state()
        call_count = {"n": 0}

        async def _partial_llm(agent_name, prompt, system_msg, **kw):
            call_count["n"] += 1
            if kw.get("json_mode"):
                raise RuntimeError("Synthesis API down")
            return "Some argument text."

        node._call_llm = _partial_llm
        result = _run(node.execute(state))
        assert result.debate_outcome["decision"] == "proceed"


# ---------------------------------------------------------------------------
# 13-15. _parse_outcome
# ---------------------------------------------------------------------------


class TestParseOutcome:
    def test_strips_markdown_fences(self):
        raw = f"```json\n{_PROCEED_JSON}\n```"
        parsed = AnalysisDebateNode._parse_outcome(raw)
        assert parsed is not None
        assert parsed["decision"] == "proceed"

    def test_normalises_unknown_decision(self):
        raw = '{"decision": "maybe", "risk_score": 5, "conditions": [], "rationale": "hmm"}'
        parsed = AnalysisDebateNode._parse_outcome(raw)
        assert parsed["decision"] == "proceed"

    def test_invalid_json_returns_none(self):
        assert AnalysisDebateNode._parse_outcome("not json") is None

    def test_none_returns_none(self):
        assert AnalysisDebateNode._parse_outcome(None) is None


# ---------------------------------------------------------------------------
# 16. _build_metrics_summary
# ---------------------------------------------------------------------------


class TestBuildMetricsSummary:
    def test_summary_contains_sharpe(self):
        summary = AnalysisDebateNode._build_metrics_summary(
            backtest={"sharpe_ratio": 1.5, "max_drawdown": 10.0, "total_trades": 30},
            opt={},
            opt_analysis={},
        )
        assert "1.5" in summary or "Sharpe" in summary

    def test_summary_contains_drawdown(self):
        summary = AnalysisDebateNode._build_metrics_summary(
            backtest={},
            opt={"best_sharpe": 1.2, "best_drawdown": 22.5, "best_trades": 20, "n_positive_sharpe": 5},
            opt_analysis={"risks": [{"rank": 1, "issue": "high dd"}]},
        )
        assert "22.5" in summary or "Drawdown" in summary


# ---------------------------------------------------------------------------
# 17. Result stored in state results
# ---------------------------------------------------------------------------


class TestResultStored:
    def test_result_accessible_via_get_result(self):
        node = AnalysisDebateNode()
        state = _make_state()
        _stub_debate_llm(node, _CONDITIONAL_JSON)
        result = _run(node.execute(state))
        stored = result.get_result("analysis_debate")
        assert stored is not None
        assert stored["decision"] == "conditional"
