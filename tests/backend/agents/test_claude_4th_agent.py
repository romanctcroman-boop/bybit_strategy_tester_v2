"""
Tests for Claude as 4th agent in the LangGraph pipeline.

Coverage (18 tests):
  A. Specialization in templates.py (4 tests)
  B. _call_llm routing for "claude" (5 tests)
  C. GenerateStrategiesNode with Claude as generator (5 tests)
  D. DebateNode / AnalysisDebateNode agent filters (4 tests)

These tests complement test_claude_client.py (18 tests for ClaudeClient itself
and _synthesis_critic). Together they cover the full integration surface.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.agents.langgraph_orchestrator import AgentState

# ============================================================================
# A. Specialization in templates.py
# ============================================================================


class TestClaudeAgentSpecialization:
    """Claude must have a complete entry in AGENT_SPECIALIZATIONS."""

    def _spec(self):
        from backend.agents.prompts.templates import AGENT_SPECIALIZATIONS

        return AGENT_SPECIALIZATIONS["claude"]

    def test_specialization_exists_with_required_fields(self):
        spec = self._spec()
        for field in ("primary_role", "description", "strengths", "style"):
            assert field in spec, f"Missing field: {field}"

    def test_primary_role_is_strategy_synthesizer(self):
        assert self._spec()["primary_role"] == "strategy_synthesizer"

    def test_get_system_message_claude_nonempty(self):
        from backend.agents.prompts.prompt_engineer import PromptEngineer

        msg = PromptEngineer().get_system_message("claude")
        assert isinstance(msg, str) and len(msg) > 20

    def test_get_system_message_claude_contains_specialization_text(self):
        from backend.agents.prompts.prompt_engineer import PromptEngineer

        msg = PromptEngineer().get_system_message("claude")
        # Should reference the description from AGENT_SPECIALIZATIONS["claude"]
        assert "systematic trader" in msg.lower() or "synthesiz" in msg.lower()


# ============================================================================
# B. _call_llm routing for "claude"
# ============================================================================


class TestCallLlmClaudeRouting:
    """
    _call_llm("claude", ...) must:
    - Return None when ANTHROPIC_API_KEY is missing
    - Create a ClaudeClient (ANTHROPIC provider) when key present
    - NOT forward json_mode to ClaudeClient
    - Record cost to state on success
    - Return response content on success

    Note: get_key_manager and LLMClientFactory are lazy-imported inside _call_llm().
    Patch at their source modules, not at trading_strategy_graph.
    """

    def _make_node(self):
        from backend.agents.trading_strategy_graph import GenerateStrategiesNode

        return GenerateStrategiesNode()

    def _mock_km(self, key: str | None = "sk-ant-test"):
        km = MagicMock()
        km.get_decrypted_key.return_value = key
        return km

    @pytest.mark.asyncio
    async def test_returns_none_when_no_anthropic_key(self):
        node = self._make_node()
        with patch("backend.security.key_manager.get_key_manager", return_value=self._mock_km(None)):
            result = await node._call_llm("claude", "prompt", "sys")
        assert result is None

    @pytest.mark.asyncio
    async def test_creates_claude_client_with_anthropic_provider(self):
        from backend.agents.llm.base_client import LLMProvider

        node = self._make_node()

        mock_client = AsyncMock()
        mock_client.chat = AsyncMock(
            return_value=MagicMock(
                content="strategy json",
                estimated_cost=0.001,
            )
        )
        mock_client.close = AsyncMock()

        created_configs: list = []

        def capture_create(config):
            created_configs.append(config)
            return mock_client

        with patch("backend.security.key_manager.get_key_manager", return_value=self._mock_km("sk-ant-test")):
            with patch("backend.agents.llm.base_client.LLMClientFactory.create", side_effect=capture_create):
                await node._call_llm("claude", "prompt", "sys")

        assert len(created_configs) == 1
        assert created_configs[0].provider == LLMProvider.ANTHROPIC

    @pytest.mark.asyncio
    async def test_json_mode_not_forwarded_to_claude_client(self):
        """json_mode must be False in client.chat() even when json_mode=True passed."""
        node = self._make_node()
        chat_kwargs: list[dict] = []

        mock_client = AsyncMock()

        async def capture_chat(messages, **kwargs):
            chat_kwargs.append(kwargs)
            return MagicMock(content="ok", estimated_cost=0.0)

        mock_client.chat = capture_chat
        mock_client.close = AsyncMock()

        with (
            patch("backend.security.key_manager.get_key_manager", return_value=self._mock_km()),
            patch("backend.agents.llm.base_client.LLMClientFactory.create", return_value=mock_client),
        ):
            await node._call_llm("claude", "p", "s", json_mode=True)

        assert chat_kwargs, "client.chat was never called"
        assert chat_kwargs[0].get("json_mode") is False

    @pytest.mark.asyncio
    async def test_records_cost_to_state(self):
        node = self._make_node()
        state = AgentState()

        mock_client = AsyncMock()
        mock_client.chat = AsyncMock(
            return_value=MagicMock(
                content="ok",
                estimated_cost=0.0042,
            )
        )
        mock_client.close = AsyncMock()

        with (
            patch("backend.security.key_manager.get_key_manager", return_value=self._mock_km()),
            patch("backend.agents.llm.base_client.LLMClientFactory.create", return_value=mock_client),
        ):
            await node._call_llm("claude", "p", "s", state=state)

        assert state.llm_call_count == 1
        assert abs(state.total_cost_usd - 0.0042) < 1e-9

    @pytest.mark.asyncio
    async def test_returns_content_on_success(self):
        node = self._make_node()
        mock_client = AsyncMock()
        mock_client.chat = AsyncMock(
            return_value=MagicMock(
                content='{"strategy_name":"test"}',
                estimated_cost=0.0,
            )
        )
        mock_client.close = AsyncMock()

        with (
            patch("backend.security.key_manager.get_key_manager", return_value=self._mock_km()),
            patch("backend.agents.llm.base_client.LLMClientFactory.create", return_value=mock_client),
        ):
            result = await node._call_llm("claude", "p", "s")

        assert result == '{"strategy_name":"test"}'


# ============================================================================
# C. GenerateStrategiesNode with Claude as generator (via for-loop)
# ============================================================================


def _make_state_with_market(agents: list[str]) -> AgentState:
    """Return a minimal AgentState ready for GenerateStrategiesNode.execute()."""
    state = AgentState()
    state.context["agents"] = agents
    state.context["platform_config"] = {"commission": 0.0007, "leverage": 10}
    state.set_result("analyze_market", {"market_context": MagicMock()})
    return state


def _patch_prompt_engineer(node: object) -> None:
    """Replace _prompt_engineer with a stub that returns simple strings.

    create_strategy_prompt() calls context.to_prompt_vars() then fills
    STRATEGY_GENERATION_TEMPLATE — too many required vars to mock. Stub
    the entire PromptEngineer instead so tests stay focused on Claude routing.
    """
    pe = MagicMock()
    pe.create_strategy_prompt.return_value = "Generate a trading strategy."
    pe.get_system_message.return_value = "You are a trading expert."
    node._prompt_engineer = pe  # type: ignore[attr-defined]


class TestGenerateStrategiesNodeWithClaude:
    """Claude goes through the single-call path (not Claude MoA) as primary generator."""

    @pytest.mark.asyncio
    async def test_claude_only_calls_claude_via_for_loop(self):
        """agents=['claude'] → _call_llm called once with a Claude tier name."""
        from backend.agents.trading_strategy_graph import GenerateStrategiesNode

        node = GenerateStrategiesNode()
        _patch_prompt_engineer(node)
        state = _make_state_with_market(["claude"])

        called_agents: list[str] = []

        async def fake_call_llm(agent_name, *args, **kwargs):
            called_agents.append(agent_name)
            return '{"strategy_name":"Claude Strategy"}'

        node._call_llm = fake_call_llm
        await node.execute(state)
        assert len(called_agents) == 1
        assert called_agents[0].startswith("claude")

    @pytest.mark.asyncio
    async def test_claude_only_response_stored_in_results(self):
        from backend.agents.trading_strategy_graph import GenerateStrategiesNode

        node = GenerateStrategiesNode()
        _patch_prompt_engineer(node)
        state = _make_state_with_market(["claude"])

        async def fake_call_llm(agent_name, *args, **kwargs):
            return '{"strategy_name":"Claude Strategy"}'

        node._call_llm = fake_call_llm
        await node.execute(state)

        result = state.get_result("generate_strategies")
        assert result is not None
        responses = result.get("responses", [])
        assert len(responses) == 1
        assert responses[0]["agent"] == "claude"

    @pytest.mark.asyncio
    async def test_claude_and_claude_produce_one_response(self):
        """agents=['claude','claude'] → 1 response: all agent names route to Claude Sonnet."""
        from backend.agents.trading_strategy_graph import GenerateStrategiesNode

        node = GenerateStrategiesNode()
        _patch_prompt_engineer(node)
        state = _make_state_with_market(["claude", "perplexity"])

        async def fake_call_llm(agent_name, *args, **kwargs):
            return f'{{"strategy_name":"{agent_name} strategy"}}'

        async def fake_critic(moa_texts, market_context, **kwargs):
            return None

        node._call_llm = fake_call_llm
        node._synthesis_critic = fake_critic

        await node.execute(state)

        result = state.get_result("generate_strategies") or {}
        responses = result.get("responses", [])
        # New architecture: single Claude call regardless of agents list
        assert len(responses) == 1
        assert responses[0]["agent"] == "claude"

    @pytest.mark.asyncio
    async def test_claude_failure_handled_gracefully(self):
        """Claude raises → partial_generation flag set, no exception propagated."""
        from backend.agents.trading_strategy_graph import GenerateStrategiesNode

        node = GenerateStrategiesNode()
        _patch_prompt_engineer(node)
        state = _make_state_with_market(["claude"])

        async def fake_call_llm(agent_name, *args, **kwargs):
            raise RuntimeError("Claude API down")

        node._call_llm = fake_call_llm
        await node.execute(state)  # must not raise

        assert state.context.get("partial_generation") is True
        assert "claude" in state.context.get("failed_agents", [])

    @pytest.mark.asyncio
    async def test_claude_only_no_extra_agents_moa_triggered(self):
        """agents=['claude'] → synthesis_critic never called (no MoA needed)."""
        from backend.agents.trading_strategy_graph import GenerateStrategiesNode

        node = GenerateStrategiesNode()
        _patch_prompt_engineer(node)
        state = _make_state_with_market(["claude"])

        critic_called = []

        async def fake_call_llm(agent_name, *args, **kwargs):
            return '{"strategy_name":"Claude"}'

        async def fake_critic(*args, **kwargs):
            critic_called.append(True)
            return None

        node._call_llm = fake_call_llm
        node._synthesis_critic = fake_critic

        await node.execute(state)
        assert critic_called == [], "synthesis_critic should not be called with single agent"


# ============================================================================
# D. (removed) Debate agent filters — debate system removed
# ============================================================================
