"""
Tests for Real LLM Deliberation with 3-agent support.

Tests cover:
- RealLLMDeliberation initialization with DeepSeek, Qwen, Perplexity
- Agent-specific system prompts (specialization)
- _real_ask() dispatching to correct client
- Fallback to simulation when client unavailable
- deliberate_with_llm() convenience function with 3-agent default
- Full 3-agent deliberation flow (mocked LLM calls)
- _ask_agent() Qwen support in base deliberation
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.agents.consensus.deliberation import (
    DeliberationResult,
    MultiAgentDeliberation,
    VotingStrategy,
)
from backend.agents.consensus.real_llm_deliberation import (
    RealLLMDeliberation,
    _get_api_key,
    deliberate_with_llm,
    get_real_deliberation,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_deepseek_client():
    """Mock DeepSeek LLM client."""
    client = AsyncMock()
    response = MagicMock()
    response.content = (
        "POSITION: Use RSI with period 21 for conservative entries\n"
        "CONFIDENCE: 0.82\n"
        "REASONING: RSI(21) reduces noise vs RSI(14), better Sharpe ratio in backtests\n"
        "EVIDENCE: Statistical significance test, lower drawdown, higher risk-adjusted returns"
    )
    response.total_tokens = 150
    response.latency_ms = 450.0
    client.chat.return_value = response
    return client


@pytest.fixture
def mock_qwen_client():
    """Mock Qwen LLM client."""
    client = AsyncMock()
    response = MagicMock()
    response.content = (
        "POSITION: Use RSI(14) with MACD confirmation for momentum entries\n"
        "CONFIDENCE: 0.78\n"
        "REASONING: RSI(14) standard period catches momentum shifts, MACD confirms trend direction\n"
        "EVIDENCE: Multi-indicator confirmation reduces false signals, pattern backtesting shows 65% win rate"
    )
    response.total_tokens = 165
    response.latency_ms = 380.0
    client.chat.return_value = response
    return client


@pytest.fixture
def mock_perplexity_client():
    """Mock Perplexity LLM client."""
    client = AsyncMock()
    response = MagicMock()
    response.content = (
        "POSITION: Use adaptive RSI with volatility-adjusted period\n"
        "CONFIDENCE: 0.75\n"
        "REASONING: Current market regime shows high volatility, fixed periods underperform\n"
        "EVIDENCE: Recent BTC volatility spike, macro uncertainty, regime shift detected"
    )
    response.total_tokens = 140
    response.latency_ms = 520.0
    client.chat.return_value = response
    return client


@pytest.fixture
def deliberation_3agents(mock_deepseek_client, mock_qwen_client, mock_perplexity_client):
    """RealLLMDeliberation with all 3 agents mocked."""
    with patch.object(RealLLMDeliberation, "_initialize_clients"):
        delib = RealLLMDeliberation()
        delib._clients = {
            "deepseek": mock_deepseek_client,
            "qwen": mock_qwen_client,
            "perplexity": mock_perplexity_client,
        }
        return delib


@pytest.fixture
def deliberation_2agents(mock_deepseek_client, mock_qwen_client):
    """RealLLMDeliberation with DeepSeek and Qwen only."""
    with patch.object(RealLLMDeliberation, "_initialize_clients"):
        delib = RealLLMDeliberation()
        delib._clients = {
            "deepseek": mock_deepseek_client,
            "qwen": mock_qwen_client,
        }
        return delib


# =============================================================================
# INITIALIZATION TESTS
# =============================================================================


class TestRealLLMDeliberationInit:
    """Test initialization and client setup."""

    @patch("backend.agents.consensus.real_llm_deliberation._get_api_key")
    def test_init_all_three_clients(self, mock_key):
        """All 3 clients initialized when keys present."""
        mock_key.return_value = "test-key-xxx"

        with (
            patch("backend.agents.consensus.real_llm_deliberation.DeepSeekClient"),
            patch("backend.agents.consensus.real_llm_deliberation.QwenClient"),
            patch("backend.agents.consensus.real_llm_deliberation.PerplexityClient"),
        ):
            delib = RealLLMDeliberation()

        assert "deepseek" in delib._clients
        assert "qwen" in delib._clients
        assert "perplexity" in delib._clients
        assert len(delib._clients) == 3

    @patch("backend.agents.consensus.real_llm_deliberation._get_api_key")
    def test_init_partial_clients(self, mock_key):
        """Only clients with keys are initialized."""

        def side_effect(key_name):
            if key_name == "QWEN_API_KEY":
                return None
            return "test-key"

        mock_key.side_effect = side_effect

        with (
            patch("backend.agents.consensus.real_llm_deliberation.DeepSeekClient"),
            patch("backend.agents.consensus.real_llm_deliberation.PerplexityClient"),
        ):
            delib = RealLLMDeliberation()

        assert "deepseek" in delib._clients
        assert "perplexity" in delib._clients
        assert "qwen" not in delib._clients

    @patch("backend.agents.consensus.real_llm_deliberation._get_api_key")
    def test_init_no_keys(self, mock_key):
        """No clients when no keys configured."""
        mock_key.return_value = None

        delib = RealLLMDeliberation()

        assert len(delib._clients) == 0

    def test_ask_fn_is_real_ask(self):
        """ask_fn is set to _real_ask."""
        with patch.object(RealLLMDeliberation, "_initialize_clients"):
            delib = RealLLMDeliberation()

        assert delib.ask_fn == delib._real_ask


# =============================================================================
# AGENT SYSTEM PROMPT TESTS
# =============================================================================


class TestAgentSystemPrompts:
    """Test agent-specific system prompts."""

    def test_has_three_specializations(self):
        """AGENT_SYSTEM_PROMPTS has all 3 agent types."""
        prompts = RealLLMDeliberation.AGENT_SYSTEM_PROMPTS
        assert "deepseek" in prompts
        assert "qwen" in prompts
        assert "perplexity" in prompts

    def test_deepseek_prompt_quantitative(self):
        """DeepSeek prompt focuses on quantitative analysis."""
        prompt = RealLLMDeliberation.AGENT_SYSTEM_PROMPTS["deepseek"]
        assert "quantitative" in prompt.lower()
        assert "risk" in prompt.lower()
        assert "conservative" in prompt.lower()

    def test_qwen_prompt_technical(self):
        """Qwen prompt focuses on technical analysis."""
        prompt = RealLLMDeliberation.AGENT_SYSTEM_PROMPTS["qwen"]
        assert "technical" in prompt.lower()
        assert "momentum" in prompt.lower() or "indicator" in prompt.lower()
        assert "pattern" in prompt.lower()

    def test_perplexity_prompt_market_research(self):
        """Perplexity prompt focuses on market research."""
        prompt = RealLLMDeliberation.AGENT_SYSTEM_PROMPTS["perplexity"]
        assert "market" in prompt.lower()
        assert "sentiment" in prompt.lower() or "regime" in prompt.lower()

    def test_default_system_prompt_exists(self):
        """Default system prompt for unknown agents."""
        assert len(RealLLMDeliberation.DEFAULT_SYSTEM_PROMPT) > 0
        assert "expert" in RealLLMDeliberation.DEFAULT_SYSTEM_PROMPT.lower()

    def test_all_prompts_require_format(self):
        """All system prompts instruct to follow format."""
        for name, prompt in RealLLMDeliberation.AGENT_SYSTEM_PROMPTS.items():
            assert "format" in prompt.lower(), f"{name} prompt missing format instruction"

    def test_deepseek_mentions_commission(self):
        """DeepSeek prompt mentions commission rate for TradingView parity."""
        prompt = RealLLMDeliberation.AGENT_SYSTEM_PROMPTS["deepseek"]
        assert "0.07%" in prompt or "commission" in prompt.lower()


# =============================================================================
# _real_ask() TESTS
# =============================================================================


class TestRealAsk:
    """Test _real_ask() method."""

    async def test_dispatches_to_deepseek(self, deliberation_3agents, mock_deepseek_client):
        """Calls DeepSeek client when agent_type is deepseek."""
        result = await deliberation_3agents._real_ask("deepseek", "Test prompt")

        mock_deepseek_client.chat.assert_called_once()
        assert "RSI" in result

    async def test_dispatches_to_qwen(self, deliberation_3agents, mock_qwen_client):
        """Calls Qwen client when agent_type is qwen."""
        result = await deliberation_3agents._real_ask("qwen", "Test prompt")

        mock_qwen_client.chat.assert_called_once()
        assert "MACD" in result

    async def test_dispatches_to_perplexity(self, deliberation_3agents, mock_perplexity_client):
        """Calls Perplexity client when agent_type is perplexity."""
        result = await deliberation_3agents._real_ask("perplexity", "Test prompt")

        mock_perplexity_client.chat.assert_called_once()
        assert "adaptive" in result.lower() or "volatility" in result.lower()

    async def test_uses_specialized_system_prompt(self, deliberation_3agents, mock_deepseek_client):
        """System prompt matches agent specialization."""
        await deliberation_3agents._real_ask("deepseek", "Test prompt")

        call_args = mock_deepseek_client.chat.call_args[0][0]
        system_msg = call_args[0]
        assert system_msg.role == "system"
        assert "quantitative" in system_msg.content.lower()

    async def test_qwen_gets_technical_prompt(self, deliberation_3agents, mock_qwen_client):
        """Qwen receives technical analyst system prompt."""
        await deliberation_3agents._real_ask("qwen", "Test prompt")

        call_args = mock_qwen_client.chat.call_args[0][0]
        system_msg = call_args[0]
        assert "technical" in system_msg.content.lower()

    async def test_fallback_for_unknown_agent(self, deliberation_3agents):
        """Unknown agent type falls back to simulation."""
        result = await deliberation_3agents._real_ask("unknown_agent", "Test prompt")

        # Should get a simulated response (not empty)
        assert len(result) > 0

    async def test_fallback_on_client_error(self, deliberation_3agents, mock_deepseek_client):
        """Client error falls back to simulation."""
        mock_deepseek_client.chat.side_effect = RuntimeError("API timeout")

        result = await deliberation_3agents._real_ask("deepseek", "Initial opinion prompt")

        # Should get a simulated response, not raise
        assert len(result) > 0

    async def test_case_insensitive_agent_type(self, deliberation_3agents, mock_qwen_client):
        """Agent type lookup is case-insensitive."""
        result = await deliberation_3agents._real_ask("QWEN", "Test prompt")

        # Should not call qwen (because lookup is .lower() but key is lowercase)
        # Actually it should work: .get("qwen") matches
        mock_qwen_client.chat.assert_called_once()


# =============================================================================
# 3-AGENT DELIBERATION TESTS
# =============================================================================


class TestThreeAgentDeliberation:
    """Test full 3-agent deliberation flow."""

    async def test_deliberate_three_agents(self, deliberation_3agents):
        """3-agent deliberation produces valid result."""
        result = await deliberation_3agents.deliberate(
            question="Which RSI period is best for BTC 15m timeframe?",
            agents=["deepseek", "qwen", "perplexity"],
            max_rounds=1,
        )

        assert isinstance(result, DeliberationResult)
        assert result.decision != ""
        assert 0 <= result.confidence <= 1
        assert len(result.final_votes) == 3
        assert result.duration_seconds > 0

    async def test_deliberate_agent_types_in_votes(self, deliberation_3agents):
        """All 3 agent types appear in votes."""
        result = await deliberation_3agents.deliberate(
            question="Best indicator combination?",
            agents=["deepseek", "qwen", "perplexity"],
            max_rounds=1,
        )

        agent_types = {v.agent_type for v in result.final_votes}
        assert "deepseek" in agent_types
        assert "qwen" in agent_types
        assert "perplexity" in agent_types

    async def test_deliberate_two_agents_subset(self, deliberation_2agents):
        """2-agent subset deliberation works."""
        result = await deliberation_2agents.deliberate(
            question="RSI vs MACD?",
            agents=["deepseek", "qwen"],
            max_rounds=1,
        )

        assert len(result.final_votes) == 2

    async def test_deliberate_weighted_voting(self, deliberation_3agents):
        """Weighted voting works with 3 agents."""
        result = await deliberation_3agents.deliberate(
            question="Trailing vs fixed stop loss?",
            agents=["deepseek", "qwen", "perplexity"],
            max_rounds=1,
            voting_strategy=VotingStrategy.WEIGHTED,
        )

        assert result.voting_strategy == VotingStrategy.WEIGHTED
        assert result.confidence > 0

    async def test_deliberate_multi_round(self, deliberation_3agents):
        """Multi-round deliberation with 3 agents converges."""
        result = await deliberation_3agents.deliberate(
            question="Best entry timing strategy?",
            agents=["deepseek", "qwen", "perplexity"],
            max_rounds=2,
        )

        assert len(result.rounds) >= 1
        assert len(result.rounds) <= 2

    async def test_deliberate_metadata_includes_agents(self, deliberation_3agents):
        """Result metadata records participating agents."""
        result = await deliberation_3agents.deliberate(
            question="Test question",
            agents=["deepseek", "qwen", "perplexity"],
            max_rounds=1,
        )

        assert "agents" in result.metadata
        assert set(result.metadata["agents"]) == {"deepseek", "qwen", "perplexity"}


# =============================================================================
# deliberate_with_llm() TESTS
# =============================================================================


class TestDeliberateWithLlm:
    """Test convenience function."""

    @patch("backend.agents.consensus.real_llm_deliberation.get_real_deliberation")
    async def test_defaults_to_available_agents(self, mock_get):
        """Defaults to all available agents."""
        mock_delib = AsyncMock(spec=RealLLMDeliberation)
        mock_delib._clients = {"deepseek": MagicMock(), "qwen": MagicMock(), "perplexity": MagicMock()}
        mock_delib.deliberate.return_value = MagicMock(spec=DeliberationResult)
        mock_get.return_value = mock_delib

        await deliberate_with_llm("Test question")

        call_kwargs = mock_delib.deliberate.call_args.kwargs
        agents = call_kwargs.get("agents", [])
        assert len(agents) == 3

    @patch("backend.agents.consensus.real_llm_deliberation.get_real_deliberation")
    async def test_defaults_to_deepseek_when_no_clients(self, mock_get):
        """Falls back to deepseek when no clients available."""
        mock_delib = AsyncMock(spec=RealLLMDeliberation)
        mock_delib._clients = {}
        mock_delib.deliberate.return_value = MagicMock(spec=DeliberationResult)
        mock_get.return_value = mock_delib

        await deliberate_with_llm("Test question")

        call_kwargs = mock_delib.deliberate.call_args.kwargs
        assert call_kwargs["agents"] == ["deepseek"]

    @patch("backend.agents.consensus.real_llm_deliberation.get_real_deliberation")
    async def test_explicit_agents_override(self, mock_get):
        """Explicit agents list overrides defaults."""
        mock_delib = AsyncMock(spec=RealLLMDeliberation)
        mock_delib._clients = {"deepseek": MagicMock(), "qwen": MagicMock()}
        mock_delib.deliberate.return_value = MagicMock(spec=DeliberationResult)
        mock_get.return_value = mock_delib

        await deliberate_with_llm("Test", agents=["qwen"])

        call_kwargs = mock_delib.deliberate.call_args.kwargs
        assert call_kwargs["agents"] == ["qwen"]


# =============================================================================
# _ask_agent() QWEN SUPPORT TEST
# =============================================================================


class TestAskAgentQwenSupport:
    """Test _ask_agent() in base MultiAgentDeliberation supports Qwen."""

    async def test_ask_agent_routes_qwen(self):
        """_ask_agent() routes qwen through agent_interface."""
        mock_interface = AsyncMock()
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.content = "POSITION: Use Bollinger Bands\nCONFIDENCE: 0.7"
        mock_interface.send_request.return_value = mock_response

        delib = MultiAgentDeliberation(agent_interface=mock_interface)
        result = await delib._ask_agent("qwen", "Test prompt")

        assert "Bollinger" in result
        # Verify AgentType.QWEN was used
        call_args = mock_interface.send_request.call_args[0][0]
        from backend.agents.models import AgentType

        assert call_args.agent_type == AgentType.QWEN

    async def test_ask_agent_routes_deepseek(self):
        """_ask_agent() still routes deepseek correctly."""
        mock_interface = AsyncMock()
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.content = "POSITION: Use RSI\nCONFIDENCE: 0.8"
        mock_interface.send_request.return_value = mock_response

        delib = MultiAgentDeliberation(agent_interface=mock_interface)
        result = await delib._ask_agent("deepseek", "Test prompt")

        call_args = mock_interface.send_request.call_args[0][0]
        from backend.agents.models import AgentType

        assert call_args.agent_type == AgentType.DEEPSEEK


# =============================================================================
# CLOSE / CLEANUP TESTS
# =============================================================================


class TestCloseCleanup:
    """Test resource cleanup."""

    async def test_close_all_clients(self, deliberation_3agents):
        """close() closes all 3 clients."""
        await deliberation_3agents.close()

        assert len(deliberation_3agents._clients) == 0

    async def test_close_handles_errors(self):
        """close() handles individual client errors gracefully."""
        with patch.object(RealLLMDeliberation, "_initialize_clients"):
            delib = RealLLMDeliberation()

        failing_client = AsyncMock()
        failing_client.close.side_effect = RuntimeError("Connection reset")
        delib._clients = {"deepseek": failing_client}

        # Should not raise
        await delib.close()
        assert len(delib._clients) == 0


# =============================================================================
# _get_api_key() TESTS
# =============================================================================


class TestGetApiKey:
    """Test API key retrieval."""

    @patch("backend.agents.consensus.real_llm_deliberation._key_manager")
    def test_key_from_key_manager(self, mock_km):
        """Key retrieved from KeyManager."""
        mock_km.get_decrypted_key.return_value = "sk-test-123"

        key = _get_api_key("QWEN_API_KEY")
        assert key == "sk-test-123"

    @patch("backend.agents.consensus.real_llm_deliberation._key_manager", None)
    @patch.dict("os.environ", {"QWEN_API_KEY": "env-key-456"})
    def test_key_fallback_to_env(self):
        """Key falls back to environment variable."""
        key = _get_api_key("QWEN_API_KEY")
        assert key == "env-key-456"

    @patch("backend.agents.consensus.real_llm_deliberation._key_manager", None)
    @patch.dict("os.environ", {}, clear=True)
    def test_key_not_found(self):
        """Returns None when key not found anywhere."""
        key = _get_api_key("NONEXISTENT_KEY")
        assert key is None
