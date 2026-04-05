"""
Tests for ClaudeClient and _synthesis_critic in GenerateStrategiesNode.

Coverage:
  - ClaudeClient._build_payload: system extraction, json_mode ignored
  - ClaudeClient._parse_response: Anthropic response format
  - ClaudeClient.chat: retry on 429, raise on network error
  - GenerateStrategiesNode._synthesis_critic:
      Claude succeeds → returns result
      Claude fails → QWEN fallback succeeds
      Both fail → returns None
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.agents.llm.base_client import LLMConfig, LLMMessage, LLMProvider
from backend.agents.llm.clients.claude import ClaudeClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(**kwargs) -> LLMConfig:
    return LLMConfig(
        provider=LLMProvider.ANTHROPIC,
        api_key="sk-ant-test",
        model="claude-haiku-4-5-20251001",
        temperature=0.7,
        max_tokens=256,
        **kwargs,
    )


def _anthropic_response(text: str = "hello") -> dict:
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": text}],
        "model": "claude-haiku-4-5-20251001",
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }


# ---------------------------------------------------------------------------
# ClaudeClient unit tests
# ---------------------------------------------------------------------------

class TestClaudeBuildPayload:
    def setup_method(self):
        self.client = ClaudeClient(_make_config())

    def test_system_extracted_to_top_level(self):
        messages = [
            LLMMessage(role="system", content="Be concise."),
            LLMMessage(role="user", content="Hello"),
        ]
        payload = self.client._build_payload(messages)
        assert payload["system"] == "Be concise."
        assert all(m["role"] != "system" for m in payload["messages"])
        assert payload["messages"][0] == {"role": "user", "content": "Hello"}

    def test_no_system_message(self):
        messages = [LLMMessage(role="user", content="Hi")]
        payload = self.client._build_payload(messages)
        assert "system" not in payload
        assert len(payload["messages"]) == 1

    def test_json_mode_kwarg_ignored(self):
        """json_mode must NOT produce a response_format field."""
        messages = [LLMMessage(role="user", content="Give JSON")]
        payload = self.client._build_payload(messages, json_mode=True)
        assert "response_format" not in payload

    def test_multiple_system_messages_joined(self):
        messages = [
            LLMMessage(role="system", content="Part 1."),
            LLMMessage(role="system", content="Part 2."),
            LLMMessage(role="user", content="Go"),
        ]
        payload = self.client._build_payload(messages)
        assert "Part 1." in payload["system"]
        assert "Part 2." in payload["system"]

    def test_temperature_and_max_tokens_passed(self):
        messages = [LLMMessage(role="user", content="x")]
        payload = self.client._build_payload(messages, temperature=0.3, max_tokens=512)
        assert payload["temperature"] == 0.3
        assert payload["max_tokens"] == 512


class TestClaudeParseResponse:
    def setup_method(self):
        self.client = ClaudeClient(_make_config())

    def test_extracts_text_content(self):
        data = _anthropic_response("strategy JSON here")
        resp = self.client._parse_response(data, latency=123.0)
        assert resp.content == "strategy JSON here"
        assert resp.model == "claude-haiku-4-5-20251001"
        assert resp.finish_reason == "end_turn"

    def test_token_counts(self):
        data = _anthropic_response()
        resp = self.client._parse_response(data, latency=50.0)
        assert resp.prompt_tokens == 10
        assert resp.completion_tokens == 5
        assert resp.total_tokens == 15

    def test_multiple_text_blocks_concatenated(self):
        data = {
            "id": "msg_x",
            "type": "message",
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Part A"},
                {"type": "thinking", "thinking": "..."},  # non-text block ignored
                {"type": "text", "text": "Part B"},
            ],
            "model": "claude-haiku-4-5-20251001",
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 5, "output_tokens": 3},
        }
        resp = self.client._parse_response(data, latency=0.0)
        assert resp.content == "Part APart B"

    def test_provider_is_anthropic(self):
        resp = self.client._parse_response(_anthropic_response(), latency=0.0)
        assert resp.provider == LLMProvider.ANTHROPIC


class TestClaudeChatRetry:
    """Test retry and rate-limit handling via mocked aiohttp session."""

    def setup_method(self):
        self.client = ClaudeClient(_make_config(max_retries=3, retry_delay_seconds=0.0))

    @pytest.mark.asyncio
    async def test_chat_success(self):
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=_anthropic_response("ok"))
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)
        mock_resp.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_resp)
        mock_session.closed = False

        with patch.object(self.client, "_get_session", return_value=mock_session):
            with patch.object(self.client.rate_limiter, "acquire", new_callable=AsyncMock):
                result = await self.client.chat([LLMMessage(role="user", content="hi")])

        assert result.content == "ok"

    @pytest.mark.asyncio
    async def test_json_mode_not_in_payload(self):
        """Confirm json_mode kwarg never reaches the HTTP request body."""
        captured_payload: list[dict] = []

        # session.post must return a synchronous context manager (MagicMock),
        # whose __aenter__ resolves to the mock response.
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=_anthropic_response("x"))
        mock_resp.raise_for_status = MagicMock()
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        def mock_post(url, json=None, **kwargs):
            captured_payload.append(json or {})
            return mock_resp

        mock_session = MagicMock()
        mock_session.post = mock_post
        mock_session.closed = False

        with patch.object(self.client, "_get_session", return_value=mock_session):
            with patch.object(self.client.rate_limiter, "acquire", new_callable=AsyncMock):
                await self.client.chat(
                    [LLMMessage(role="user", content="json?")],
                    json_mode=True,
                )

        assert captured_payload, "No payload captured"
        assert "response_format" not in captured_payload[0]


# ---------------------------------------------------------------------------
# _synthesis_critic tests
# ---------------------------------------------------------------------------

class TestSynthesisCritic:
    """Tests for GenerateStrategiesNode._synthesis_critic."""

    def _make_node(self):
        from backend.agents.trading_strategy_graph import GenerateStrategiesNode
        node = GenerateStrategiesNode.__new__(GenerateStrategiesNode)
        node._MOA_TEMPERATURES = [0.3, 0.7, 1.1]
        return node

    @pytest.mark.asyncio
    async def test_returns_claude_result_when_available(self):
        """Claude succeeds → result returned immediately, QWEN not called."""
        node = self._make_node()
        call_log: list[str] = []

        async def fake_call_llm(agent_name, prompt, system_msg, temperature=None, state=None, json_mode=False):
            call_log.append(agent_name)
            if agent_name == "claude":
                return '{"strategy_name": "Claude strategy"}'
            return None

        node._call_llm = fake_call_llm
        result = await node._synthesis_critic(["variant1", "variant2", "variant3"], market_context=None)

        assert result == '{"strategy_name": "Claude strategy"}'
        assert call_log == ["claude"]  # QWEN never called

    @pytest.mark.asyncio
    async def test_falls_back_to_qwen_when_claude_fails(self):
        """Claude raises → QWEN fallback invoked."""
        node = self._make_node()
        call_log: list[str] = []

        async def fake_call_llm(agent_name, prompt, system_msg, temperature=None, state=None, json_mode=False):
            call_log.append(agent_name)
            if agent_name == "claude":
                raise RuntimeError("Claude unavailable")
            return '{"strategy_name": "QWEN strategy"}'

        node._call_llm = fake_call_llm
        result = await node._synthesis_critic(["v1", "v2"], market_context=None)

        assert result == '{"strategy_name": "QWEN strategy"}'
        assert call_log == ["claude", "qwen"]

    @pytest.mark.asyncio
    async def test_falls_back_to_qwen_when_claude_returns_none(self):
        """Claude returns None (key missing) → QWEN fallback."""
        node = self._make_node()

        async def fake_call_llm(agent_name, prompt, system_msg, temperature=None, state=None, json_mode=False):
            if agent_name == "claude":
                return None
            return '{"strategy_name": "QWEN"}'

        node._call_llm = fake_call_llm
        result = await node._synthesis_critic(["v1"], market_context=None)
        assert result == '{"strategy_name": "QWEN"}'

    @pytest.mark.asyncio
    async def test_returns_none_when_both_fail(self):
        """Both Claude and QWEN fail → None (caller uses T=0.7 raw variant)."""
        node = self._make_node()

        async def fake_call_llm(agent_name, prompt, system_msg, temperature=None, state=None, json_mode=False):
            raise RuntimeError("all down")

        node._call_llm = fake_call_llm
        result = await node._synthesis_critic(["v1", "v2"], market_context=None)
        assert result is None

    @pytest.mark.asyncio
    async def test_critic_uses_deterministic_temperature(self):
        """Critic must call with temperature=0.3 regardless of agent."""
        node = self._make_node()
        temps_seen: list[float] = []

        async def fake_call_llm(agent_name, prompt, system_msg, temperature=None, state=None, json_mode=False):
            temps_seen.append(temperature)
            if agent_name == "claude":
                return '{"ok": true}'
            return None

        node._call_llm = fake_call_llm
        await node._synthesis_critic(["v1"], market_context=None)
        assert temps_seen[0] == 0.3


# ---------------------------------------------------------------------------
# LLMClientFactory registration
# ---------------------------------------------------------------------------

class TestClaudeClientFactory:
    def test_factory_creates_claude_client(self):
        from backend.agents.llm.base_client import LLMClientFactory, LLMConfig, LLMProvider

        config = LLMConfig(provider=LLMProvider.ANTHROPIC, api_key="test", model="default")
        client = LLMClientFactory.create(config)
        assert isinstance(client, ClaudeClient)

    def test_anthropic_in_provider_enum(self):
        assert LLMProvider.ANTHROPIC.value == "anthropic"
