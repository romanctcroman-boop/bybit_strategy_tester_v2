"""
CP2 — Phase 2: A2A Strategy Generation

Tests:
  1. seed_mode skips generation entirely
  2. Perplexity key present → 2 parallel LLM calls (Claude + Perplexity)
  3. Perplexity key absent → single Claude call only
  4. A2A synthesis succeeds → response source = "claude+perplexity"
  5. A2A synthesis fails → fallback to raw Claude response
  6. Claude fails + no Perplexity → partial_generation flag set
  7. _synthesis_critic with perplexity_market_analysis builds correct prompt
  8. _synthesis_critic legacy path (no perplexity_market_analysis) unchanged
  9. _build_perplexity_market_prompt contains symbol, timeframe, regime
  10. Perplexity receives the real symbol (not empty string)
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

from backend.agents.langgraph_orchestrator import AgentState
from backend.agents.trading_strategy_graph import GenerateStrategiesNode

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(coro):
    return asyncio.run(coro)


def _make_market_context() -> Any:
    mc = MagicMock()
    mc.summary = "BTC trending upward with high volume"
    return mc


def _state_with_market(
    symbol: str = "BTCUSDT", timeframe: str = "15", seed: bool = False, with_perplexity: bool = True
) -> AgentState:
    state = AgentState()
    state.context["symbol"] = symbol
    state.context["timeframe"] = timeframe
    # A2A tests request both claude + perplexity so Perplexity branch is exercised
    state.context["agents"] = ["claude", "perplexity"] if with_perplexity else ["claude"]
    state.context["regime_classification"] = {"regime": "trending_up"}
    if seed:
        state.context["seed_mode"] = True
    # inject fake analyze_market result
    state.set_result(
        "analyze_market",
        {
            "market_context": _make_market_context(),
            "regime": "trending_up",
        },
    )
    return state


_CLAUDE_STRATEGY_JSON = '{"strategy_name": "RSI Trend", "signals": [], "filters": []}'
_PERPLEXITY_ANALYSIS = "BTC is currently in a strong uptrend with support at 60k."
_SYNTHESIS_JSON = '{"strategy_name": "RSI Trend (synthesised)", "signals": [], "filters": []}'


def _patch_call_llm(node: GenerateStrategiesNode, claude_resp: str | None, perplexity_resp: str | None):
    """Patch _call_llm on the node to return configured responses."""

    async def _mock_call_llm(agent_name, prompt, system_msg, temperature=None, state=None, json_mode=False):
        if agent_name == "perplexity":
            return perplexity_resp
        return claude_resp  # claude-sonnet, claude-opus, claude-haiku

    node._call_llm = _mock_call_llm


def _stub_prompt_engineer(node: GenerateStrategiesNode) -> None:
    """Stub _prompt_engineer to avoid template KeyError in unit tests."""
    node._prompt_engineer = MagicMock(return_value="mock strategy prompt")


# ---------------------------------------------------------------------------
# 1. seed_mode → skip generation
# ---------------------------------------------------------------------------


class TestSeedModeSkip:
    def test_seed_mode_returns_empty_responses(self):
        node = GenerateStrategiesNode()
        state = _state_with_market(seed=True)

        result = _run(node.execute(state))

        gen = result.get_result("generate_strategies")
        assert gen is not None
        assert gen["responses"] == []
        assert gen.get("seed_mode") is True

    def test_seed_mode_no_llm_calls(self):
        node = GenerateStrategiesNode()
        state = _state_with_market(seed=True)
        call_count = {"n": 0}

        async def _counting_llm(*a, **kw):
            call_count["n"] += 1
            return None

        node._call_llm = _counting_llm

        _run(node.execute(state))
        assert call_count["n"] == 0


# ---------------------------------------------------------------------------
# 2 & 3. Perplexity key presence controls parallel vs single call
# ---------------------------------------------------------------------------


class TestCallRouting:
    def test_no_perplexity_key_single_call(self):
        node = GenerateStrategiesNode()
        state = _state_with_market()
        calls = []
        _stub_prompt_engineer(node)

        async def _recording_llm(agent_name, prompt, system_msg, **kw):
            calls.append(agent_name)
            return _CLAUDE_STRATEGY_JSON if agent_name != "perplexity" else None

        node._call_llm = _recording_llm

        with patch(
            "backend.security.key_manager.get_key_manager",
            return_value=MagicMock(get_decrypted_key=lambda k: "" if k == "PERPLEXITY_API_KEY" else "fake-key"),
        ):
            _run(node.execute(state))

        assert "perplexity" not in calls
        assert any(a in ("claude-sonnet", "claude-opus", "claude-haiku") for a in calls)

    def test_perplexity_key_present_two_calls(self):
        node = GenerateStrategiesNode()
        state = _state_with_market()
        calls = []
        _stub_prompt_engineer(node)

        async def _recording_llm(agent_name, prompt, system_msg, **kw):
            calls.append(agent_name)
            if agent_name == "perplexity":
                return _PERPLEXITY_ANALYSIS
            if agent_name == "claude-haiku":
                return _SYNTHESIS_JSON
            return _CLAUDE_STRATEGY_JSON

        node._call_llm = _recording_llm

        with patch(
            "backend.security.key_manager.get_key_manager",
            return_value=MagicMock(get_decrypted_key=lambda k: "fake-key"),
        ):
            _run(node.execute(state))

        assert "perplexity" in calls
        assert any(a in ("claude-sonnet", "claude-opus") for a in calls)


# ---------------------------------------------------------------------------
# 4. A2A synthesis succeeds → source = "claude+perplexity"
# ---------------------------------------------------------------------------


class TestA2ASynthesisSuccess:
    def test_response_source_is_claude_plus_perplexity(self):
        node = GenerateStrategiesNode()
        state = _state_with_market()
        _stub_prompt_engineer(node)

        async def _mock_llm(agent_name, prompt, system_msg, **kw):
            if agent_name == "perplexity":
                return _PERPLEXITY_ANALYSIS
            if agent_name == "claude-haiku":
                return _SYNTHESIS_JSON
            return _CLAUDE_STRATEGY_JSON

        node._call_llm = _mock_llm

        with patch(
            "backend.security.key_manager.get_key_manager",
            return_value=MagicMock(get_decrypted_key=lambda k: "fake-key"),
        ):
            result = _run(node.execute(state))

        gen = result.get_result("generate_strategies")
        assert len(gen["responses"]) == 1
        assert gen["responses"][0]["agent"] == "claude+perplexity"
        assert gen["responses"][0]["response"] == _SYNTHESIS_JSON

    def test_synthesised_response_used_not_raw_claude(self):
        node = GenerateStrategiesNode()
        state = _state_with_market()
        _stub_prompt_engineer(node)

        async def _mock_llm(agent_name, prompt, system_msg, **kw):
            if agent_name == "perplexity":
                return _PERPLEXITY_ANALYSIS
            if agent_name == "claude-haiku":
                return _SYNTHESIS_JSON
            return _CLAUDE_STRATEGY_JSON

        node._call_llm = _mock_llm

        with patch(
            "backend.security.key_manager.get_key_manager",
            return_value=MagicMock(get_decrypted_key=lambda k: "fake-key"),
        ):
            result = _run(node.execute(state))

        response_text = result.get_result("generate_strategies")["responses"][0]["response"]
        assert response_text == _SYNTHESIS_JSON
        assert response_text != _CLAUDE_STRATEGY_JSON


# ---------------------------------------------------------------------------
# 5. Synthesis fails → fallback to raw Claude
# ---------------------------------------------------------------------------


class TestSynthesisFallback:
    def test_haiku_failure_uses_claude_response(self):
        node = GenerateStrategiesNode()
        state = _state_with_market()
        _stub_prompt_engineer(node)

        async def _mock_llm(agent_name, prompt, system_msg, **kw):
            if agent_name == "perplexity":
                return _PERPLEXITY_ANALYSIS
            if agent_name == "claude-haiku":
                return None  # synthesis fails
            return _CLAUDE_STRATEGY_JSON

        node._call_llm = _mock_llm

        with patch(
            "backend.security.key_manager.get_key_manager",
            return_value=MagicMock(get_decrypted_key=lambda k: "fake-key"),
        ):
            result = _run(node.execute(state))

        gen = result.get_result("generate_strategies")
        assert len(gen["responses"]) == 1
        # Fallback: source is just "claude", response is raw Claude output
        assert gen["responses"][0]["agent"] == "claude"
        assert gen["responses"][0]["response"] == _CLAUDE_STRATEGY_JSON


# ---------------------------------------------------------------------------
# 6. Claude fails → partial_generation
# ---------------------------------------------------------------------------


class TestClaudeFailure:
    def test_claude_failure_sets_partial_generation(self):
        node = GenerateStrategiesNode()
        state = _state_with_market()
        _stub_prompt_engineer(node)

        async def _mock_llm(agent_name, prompt, system_msg, **kw):
            if agent_name == "perplexity":
                return None
            raise RuntimeError("API down")

        node._call_llm = _mock_llm

        with patch(
            "backend.security.key_manager.get_key_manager",
            return_value=MagicMock(get_decrypted_key=lambda k: "" if k == "PERPLEXITY_API_KEY" else "fake"),
        ):
            result = _run(node.execute(state))

        assert result.context.get("partial_generation") is True
        assert "claude" in result.context.get("failed_agents", [])
        gen = result.get_result("generate_strategies")
        assert gen["responses"] == []


# ---------------------------------------------------------------------------
# 7 & 8. _synthesis_critic prompt variants
# ---------------------------------------------------------------------------


class TestSynthesisCriticPrompts:
    def test_with_perplexity_analysis_uses_a2a_prompt(self):
        node = GenerateStrategiesNode()
        captured_prompt = {}

        async def _mock_llm(agent_name, prompt, system_msg, **kw):
            captured_prompt["prompt"] = prompt
            return _SYNTHESIS_JSON

        node._call_llm = _mock_llm
        result = _run(
            node._synthesis_critic(
                [_CLAUDE_STRATEGY_JSON],
                _make_market_context(),
                perplexity_market_analysis=_PERPLEXITY_ANALYSIS,
            )
        )

        assert result == _SYNTHESIS_JSON
        # A2A prompt contains both Claude strategy and Perplexity analysis
        assert "Real-time market analysis" in captured_prompt["prompt"]
        assert _PERPLEXITY_ANALYSIS in captured_prompt["prompt"]
        assert _CLAUDE_STRATEGY_JSON in captured_prompt["prompt"]

    def test_without_perplexity_uses_legacy_prompt(self):
        node = GenerateStrategiesNode()
        captured_prompt = {}

        async def _mock_llm(agent_name, prompt, system_msg, **kw):
            captured_prompt["prompt"] = prompt
            return _SYNTHESIS_JSON

        node._call_llm = _mock_llm
        _run(node._synthesis_critic([_CLAUDE_STRATEGY_JSON], _make_market_context()))

        # Legacy prompt uses "strategy critic" language, not A2A language
        assert (
            "multiple strategy proposals" in captured_prompt["prompt"].lower()
            or "variants" in captured_prompt["prompt"].lower()
            or "VARIANT" in captured_prompt["prompt"]
        )
        assert "Real-time market analysis" not in captured_prompt["prompt"]


# ---------------------------------------------------------------------------
# 9. _build_perplexity_market_prompt content
# ---------------------------------------------------------------------------


class TestBuildPerplexityPrompt:
    def test_contains_symbol(self):
        node = GenerateStrategiesNode()
        prompt = node._build_perplexity_market_prompt("ETHUSDT", "60", "ranging", None)
        assert "ETHUSDT" in prompt

    def test_contains_timeframe(self):
        node = GenerateStrategiesNode()
        prompt = node._build_perplexity_market_prompt("BTCUSDT", "15", "trending_up", None)
        assert "15m" in prompt

    def test_contains_regime(self):
        node = GenerateStrategiesNode()
        prompt = node._build_perplexity_market_prompt("BTCUSDT", "15", "volatile", None)
        assert "volatile" in prompt

    def test_non_numeric_timeframe_not_suffixed(self):
        node = GenerateStrategiesNode()
        prompt = node._build_perplexity_market_prompt("BTCUSDT", "D", "ranging", None)
        # "D" is not numeric, should appear as-is
        assert "D" in prompt
        assert "Dm" not in prompt

    def test_no_trading_advice_disclaimer_present(self):
        node = GenerateStrategiesNode()
        prompt = node._build_perplexity_market_prompt("BTCUSDT", "15", "trending_up", None)
        assert "No trading advice" in prompt


# ---------------------------------------------------------------------------
# 10. Perplexity gets real symbol (not empty)
# ---------------------------------------------------------------------------


class TestPerplexityReceivesSymbol:
    def test_perplexity_prompt_contains_real_symbol(self):
        node = GenerateStrategiesNode()
        state = _state_with_market(symbol="SOLUSDT", timeframe="60")
        captured = {}
        _stub_prompt_engineer(node)

        async def _mock_llm(agent_name, prompt, system_msg, **kw):
            if agent_name == "perplexity":
                captured["perplexity_prompt"] = prompt
                return _PERPLEXITY_ANALYSIS
            if agent_name == "claude-haiku":
                return _SYNTHESIS_JSON
            return _CLAUDE_STRATEGY_JSON

        node._call_llm = _mock_llm

        with patch(
            "backend.security.key_manager.get_key_manager",
            return_value=MagicMock(get_decrypted_key=lambda k: "fake-key"),
        ):
            _run(node.execute(state))

        assert "perplexity_prompt" in captured, "Perplexity was not called"
        assert "SOLUSDT" in captured["perplexity_prompt"]
        assert captured["perplexity_prompt"].count("SOLUSDT") >= 1
