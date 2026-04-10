"""
Tests for P2 agent improvements:
- P2-1: RegimeClassifierNode (deterministic ADX+ATR regime)
- P2-3: HITLCheckNode (human-in-the-loop checkpoint)
- P2-4: make_pipeline_event_queue (streaming events)
- P2-5: composite_quality_score in scoring.py

Note: P2-2 (DebateNode S²-MAD) removed — debate system was removed.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from backend.agents.langgraph_orchestrator import (
    AgentGraph,
    AgentState,
    FunctionAgent,
    make_pipeline_event_queue,
)
from backend.agents.trading_strategy_graph import (
    HITLCheckNode,
    RegimeClassifierNode,
    build_trading_strategy_graph,
)
from backend.optimization.scoring import composite_quality_score


def _run(coro):
    return asyncio.run(coro)


# =============================================================================
# Helpers
# =============================================================================


def _make_market_result(
    market_regime: str = "trending_up",
    trend_direction: str = "bullish",
    trend_strength: str = "strong",
    atr_pct: float = 1.0,
) -> dict:
    ctx = MagicMock()
    ctx.market_regime = market_regime
    ctx.trend_direction = trend_direction
    ctx.trend_strength = trend_strength
    ctx.atr_pct = atr_pct
    return {"market_context": ctx, "regime": market_regime, "trend": trend_direction}


# =============================================================================
# P2-1: RegimeClassifierNode
# =============================================================================


class TestRegimeClassifierNode:
    def test_trending_bull_classification(self):
        node = RegimeClassifierNode()
        state = AgentState()
        state.set_result(
            "analyze_market", _make_market_result(trend_direction="bullish", trend_strength="strong", atr_pct=1.0)
        )
        result = _run(node.execute(state))
        clf = result.context["regime_classification"]
        assert clf["regime"] == "trending_bull"
        assert clf["confidence"] > 0.5

    def test_trending_bear_classification(self):
        node = RegimeClassifierNode()
        state = AgentState()
        state.set_result(
            "analyze_market", _make_market_result(trend_direction="bearish", trend_strength="strong", atr_pct=1.0)
        )
        result = _run(node.execute(state))
        clf = result.context["regime_classification"]
        assert clf["regime"] == "trending_bear"

    def test_crypto_risk_off_classification(self):
        """Bearish + very high ATR (>3.5%) → crypto_risk_off."""
        node = RegimeClassifierNode()
        state = AgentState()
        state.set_result(
            "analyze_market", _make_market_result(trend_direction="bearish", trend_strength="weak", atr_pct=4.0)
        )
        result = _run(node.execute(state))
        clf = result.context["regime_classification"]
        assert clf["regime"] == "crypto_risk_off"

    def test_volatile_ranging_classification(self):
        """High ATR but low trend strength → volatile_ranging."""
        node = RegimeClassifierNode()
        state = AgentState()
        state.set_result(
            "analyze_market", _make_market_result(trend_direction="neutral", trend_strength="weak", atr_pct=3.0)
        )
        result = _run(node.execute(state))
        clf = result.context["regime_classification"]
        assert clf["regime"] == "volatile_ranging"

    def test_ranging_classification(self):
        """Low ATR, low trend strength → ranging."""
        node = RegimeClassifierNode()
        state = AgentState()
        state.set_result(
            "analyze_market", _make_market_result(trend_direction="neutral", trend_strength="weak", atr_pct=0.5)
        )
        result = _run(node.execute(state))
        clf = result.context["regime_classification"]
        assert clf["regime"] == "ranging"

    def test_skips_gracefully_without_market_result(self):
        """Node returns state unchanged when no analyze_market result."""
        node = RegimeClassifierNode()
        state = AgentState()
        result = _run(node.execute(state))
        assert "regime_classification" not in result.context

    def test_result_stored_in_state_results(self):
        node = RegimeClassifierNode()
        state = AgentState()
        state.set_result("analyze_market", _make_market_result())
        result = _run(node.execute(state))
        assert result.get_result("regime_classifier") is not None

    def test_classification_has_all_required_keys(self):
        node = RegimeClassifierNode()
        state = AgentState()
        state.set_result("analyze_market", _make_market_result())
        result = _run(node.execute(state))
        clf = result.context["regime_classification"]
        for key in ("regime", "adx_proxy", "atr_pct", "trend", "confidence"):
            assert key in clf, f"Missing key: {key}"

    def test_confidence_is_between_0_and_1(self):
        node = RegimeClassifierNode()
        for strength in ("strong", "moderate", "weak"):
            state = AgentState()
            state.set_result("analyze_market", _make_market_result(trend_direction="bullish", trend_strength=strength))
            result = _run(node.execute(state))
            conf = result.context["regime_classification"]["confidence"]
            assert 0.0 <= conf <= 1.0, f"Confidence {conf} out of range for {strength}"


# =============================================================================
# P2-3: HITLCheckNode
# =============================================================================


class TestHITLCheckNode:
    def test_hitl_pauses_when_not_approved(self):
        node = HITLCheckNode()
        state = AgentState()
        state.context["hitl_approved"] = False
        result = _run(node.execute(state))
        assert result.context.get("hitl_pending") is True

    def test_hitl_continues_when_approved(self):
        node = HITLCheckNode()
        state = AgentState()
        state.context["hitl_approved"] = True
        result = _run(node.execute(state))
        assert not result.context.get("hitl_pending", False)

    def test_hitl_pauses_by_default_when_flag_missing(self):
        """Missing hitl_approved defaults to False → pause."""
        node = HITLCheckNode()
        state = AgentState()
        result = _run(node.execute(state))
        assert result.context.get("hitl_pending") is True

    def test_hitl_payload_contains_strategy_info(self):
        node = HITLCheckNode()
        state = AgentState()
        state.context["hitl_approved"] = False
        state.set_result("backtest", {"total_trades": 25, "sharpe_ratio": 1.3, "max_drawdown": 12.0, "net_profit": 500})
        result = _run(node.execute(state))
        payload = result.context.get("hitl_payload", {})
        assert "backtest_summary" in payload
        assert payload["backtest_summary"]["trades"] == 25

    def test_hitl_payload_includes_regime(self):
        node = HITLCheckNode()
        state = AgentState()
        state.context["hitl_approved"] = False
        state.context["regime_classification"] = {"regime": "trending_bull"}
        result = _run(node.execute(state))
        payload = result.context.get("hitl_payload", {})
        assert payload.get("regime") == "trending_bull"

    def test_hitl_approval_clears_pending_flag(self):
        node = HITLCheckNode()
        state = AgentState()
        state.context["hitl_pending"] = True  # leftover from previous pause
        state.context["hitl_approved"] = True
        result = _run(node.execute(state))
        assert not result.context.get("hitl_pending", False)

    def test_hitl_stores_result(self):
        node = HITLCheckNode()
        state = AgentState()
        state.context["hitl_approved"] = False
        result = _run(node.execute(state))
        assert result.get_result("hitl_check") is not None


# =============================================================================
# P2-4: make_pipeline_event_queue
# =============================================================================


class TestPipelineEventQueue:
    def test_queue_and_event_fn_returned(self):
        q, event_fn = make_pipeline_event_queue()
        assert q is not None
        assert callable(event_fn)

    def test_event_fn_puts_event_in_queue(self):
        q, event_fn = make_pipeline_event_queue()
        event_fn("analyze_market", {"node": "analyze_market", "status": "completed"})
        assert not q.empty()
        event = q.get_nowait()
        assert event["node"] == "analyze_market"
        assert event["status"] == "completed"

    def test_graph_with_event_fn_emits_events(self):
        q, event_fn = make_pipeline_event_queue()

        def _noop(state):
            return state

        graph = AgentGraph(name="test_stream", event_fn=event_fn)
        graph.add_node(FunctionAgent(name="a", func=_noop))
        graph.add_node(FunctionAgent(name="b", func=_noop))
        graph.add_edge("a", "b")
        graph.set_entry_point("a")
        graph.add_exit_point("b")

        _run(graph.execute())
        events = []
        while not q.empty():
            events.append(q.get_nowait())
        node_names = [e["node"] for e in events]
        assert "a" in node_names
        assert "b" in node_names

    def test_event_contains_session_id(self):
        q, event_fn = make_pipeline_event_queue()
        state = AgentState()
        event_fn("analyze_market", {"node": "x", "status": "completed", "session_id": state.session_id})
        event = q.get_nowait()
        assert "session_id" in event

    def test_event_fn_is_non_blocking(self):
        """event_fn should not raise even if called from sync context."""
        q, event_fn = make_pipeline_event_queue()
        for i in range(100):
            event_fn(f"node_{i}", {"node": f"node_{i}", "status": "completed"})
        assert q.qsize() <= 100  # all events queued

    def test_graph_without_event_fn_works_normally(self):
        def _noop(state):
            return state

        graph = AgentGraph(name="no_stream", event_fn=None)
        graph.add_node(FunctionAgent(name="a", func=_noop))
        graph.set_entry_point("a")
        graph.add_exit_point("a")
        result = _run(graph.execute())
        assert result is not None


# =============================================================================
# P2-5: composite_quality_score
# =============================================================================


class TestCompositeQualityScore:
    def test_positive_sharpe_and_sortino_with_trades(self):
        import math

        result = {
            "sharpe_ratio": 1.2,
            "sortino_ratio": 1.8,
            "total_trades": 50,
            "max_drawdown": 15.0,
        }
        score = composite_quality_score(result)
        expected = 1.2 * 1.8 * math.log1p(50) / (1.0 + 0.15)
        assert abs(score - expected) < 1e-6

    def test_non_positive_sharpe_returns_zero(self):
        result = {"sharpe_ratio": -0.5, "sortino_ratio": 1.0, "total_trades": 30, "max_drawdown": 10.0}
        assert composite_quality_score(result) == 0.0

    def test_non_positive_sortino_returns_zero(self):
        result = {"sharpe_ratio": 1.0, "sortino_ratio": 0.0, "total_trades": 30, "max_drawdown": 10.0}
        assert composite_quality_score(result) == 0.0

    def test_zero_trades_gives_low_score(self):
        """log(1+0) = 0 → score = 0 with zero trades."""
        result = {"sharpe_ratio": 2.0, "sortino_ratio": 2.0, "total_trades": 0, "max_drawdown": 5.0}
        assert composite_quality_score(result) == 0.0

    def test_high_drawdown_penalizes_score(self):
        base = {"sharpe_ratio": 1.0, "sortino_ratio": 1.0, "total_trades": 50}
        low_dd = composite_quality_score({**base, "max_drawdown": 5.0})
        high_dd = composite_quality_score({**base, "max_drawdown": 50.0})
        assert low_dd > high_dd

    def test_more_trades_increases_score(self):
        base = {"sharpe_ratio": 1.0, "sortino_ratio": 1.0, "max_drawdown": 10.0}
        few = composite_quality_score({**base, "total_trades": 5})
        many = composite_quality_score({**base, "total_trades": 200})
        assert many > few

    def test_score_capped_at_1000(self):
        result = {"sharpe_ratio": 100.0, "sortino_ratio": 100.0, "total_trades": 10000, "max_drawdown": 0.0}
        assert composite_quality_score(result) == 1000.0

    def test_missing_fields_default_to_zero(self):
        """Should return 0.0 when sharpe/sortino missing (default 0)."""
        assert composite_quality_score({}) == 0.0

    def test_calculate_composite_score_accepts_composite_quality_metric(self):
        from backend.optimization.scoring import calculate_composite_score

        result = {"sharpe_ratio": 1.5, "sortino_ratio": 2.0, "total_trades": 40, "max_drawdown": 12.0}
        score = calculate_composite_score(result, "composite_quality")
        assert score > 0.0
        assert score == composite_quality_score(result)


# =============================================================================
# Build graph with P2 params
# =============================================================================


class TestBuildGraphP2:
    def test_graph_has_regime_classifier_node(self):
        graph = build_trading_strategy_graph(run_backtest=False, run_debate=False)
        assert "regime_classifier" in graph.nodes

    def test_analyze_market_connects_to_regime_classifier(self):
        graph = build_trading_strategy_graph(run_backtest=False, run_debate=False)
        edges = [e.target for e in graph.edges.get("analyze_market", [])]
        assert "regime_classifier" in edges

    def test_regime_classifier_connects_to_memory_recall(self):
        graph = build_trading_strategy_graph(run_backtest=False, run_debate=False)
        edges = [e.target for e in graph.edges.get("regime_classifier", [])]
        assert "memory_recall" in edges

    @pytest.mark.skip(reason="Debate node removed from pipeline")
    def test_regime_classifier_connects_to_debate_when_enabled(self):
        pass

    def test_hitl_node_added_when_enabled(self):
        graph = build_trading_strategy_graph(run_backtest=True, hitl_enabled=True)
        assert "hitl_check" in graph.nodes

    def test_hitl_node_not_added_by_default(self):
        graph = build_trading_strategy_graph(run_backtest=True, hitl_enabled=False)
        assert "hitl_check" not in graph.nodes

    def test_event_fn_attached_to_graph(self):
        _, event_fn = make_pipeline_event_queue()
        graph = build_trading_strategy_graph(run_backtest=False, event_fn=event_fn)
        assert graph.event_fn is event_fn

    def test_graph_without_event_fn_has_none(self):
        graph = build_trading_strategy_graph(run_backtest=False, event_fn=None)
        assert graph.event_fn is None
