"""
Claude (Anthropic) LLM Client

Native Anthropic Messages API client.
NOT OpenAI-compatible — uses x-api-key header and a different message/response format.

Supported models (as of April 2026):
  claude-haiku-4-5-20251001  — fastest, cheapest ($1/$5 per 1M tok) — DEFAULT
  claude-sonnet-4-6          — best balance of quality/cost ($3/$15 per 1M tok)
  claude-opus-4-6            — most capable ($5/$25 per 1M tok)  ← significantly cheaper than opus-4

Key differences from OpenAI format:
  - Endpoint: POST /v1/messages  (not /v1/chat/completions)
  - Auth header: x-api-key  (not Authorization: Bearer)
  - system message is a top-level field, NOT inside messages[]
  - Response content: data["content"][0]["text"]  (not choices[0].message.content)
  - Token fields: input_tokens / output_tokens  (not prompt_tokens / completion_tokens)

JSON output modes (in order of reliability):
  1. tool_use + strict schema (kwarg: tools=[...], tool_choice={"type":"tool",...}) → ~100%
  2. Prompt engineering OUTPUT RULES (default) → ~95%
  Note: response_format / json_mode is NOT a field in the Anthropic Messages API.

Prompt caching (enabled by default via anthropic-beta header):
  - Static system message parts get cache_control: {"type": "ephemeral"} (5-min TTL)
  - Cache hit cost: 10% of normal input price (90% savings on repeated calls)
  - Minimum cacheable block: 2048 tokens (Sonnet/Opus), 2048 (Haiku)
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncGenerator
from typing import Any

import aiohttp
from loguru import logger

from backend.agents.llm.base_client import (
    LLMClient,
    LLMConfig,
    LLMMessage,
    LLMProvider,
    LLMResponse,
)
from backend.agents.llm.rate_limiter import TokenAwareRateLimiter, TokenBudget

_ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"


class ClaudeClient(LLMClient):
    """
    Anthropic Claude client using the native Messages API.

    Usage:
        config = LLMConfig(
            provider=LLMProvider.ANTHROPIC,
            api_key=os.environ["ANTHROPIC_API_KEY"],
            model="claude-haiku-4-5-20251001",
            temperature=0.7,
            max_tokens=4096,
        )
        client = ClaudeClient(config)
        response = await client.chat([
            LLMMessage(role="system", content="You are a trading strategy expert."),
            LLMMessage(role="user", content="Generate an RSI strategy."),
        ])
        print(response.content)
        await client.close()
    """

    DEFAULT_MODEL = "claude-haiku-4-5-20251001"
    PROVIDER = LLMProvider.ANTHROPIC
    BREAKER_NAME = "claude_llm_client"
    EMOJI = "🟠"  # Anthropic orange; 🟣 is reserved for Perplexity

    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self.model = config.model if config.model != "default" else self.DEFAULT_MODEL
        self.session: aiohttp.ClientSession | None = None

        self.rate_limiter = TokenAwareRateLimiter(
            provider=self.PROVIDER.value,
            budget=TokenBudget(max_tokens_per_minute=config.rate_limit_rpm * 1000),
        )

        self.total_requests = 0
        self.total_tokens = 0
        self.total_cost = 0.0

        self._init_circuit_breaker(self.BREAKER_NAME)
        logger.info(f"{self.EMOJI} ClaudeClient initialized: {self.model}")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create persistent aiohttp session with Anthropic headers."""
        if self.session is None or self.session.closed:
            headers = {
                "x-api-key": self.config.api_key or "",
                "anthropic-version": _ANTHROPIC_VERSION,
                "anthropic-beta": "prompt-caching-2024-07-31",
                "content-type": "application/json",
            }
            timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
            self.session = aiohttp.ClientSession(headers=headers, timeout=timeout)
        return self.session

    def _build_payload(self, messages: list[LLMMessage], **kwargs: Any) -> dict[str, Any]:
        """Build Anthropic Messages API payload.

        Extracts 'system' role messages to the top-level 'system' field
        (Anthropic requirement — system may not appear inside messages[]).
        The json_mode kwarg is intentionally ignored: Claude follows JSON
        instructions reliably via prompt, no response_format field is needed.

        Prompt caching: the first (static) system block gets
        cache_control={"type":"ephemeral"} so repeated calls reuse the KV cache.
        Minimum cacheable block: 2048 tokens — smaller blocks are silently skipped.

        Structured outputs (tool use, ~100% reliability):
          Pass tools=[...] and tool_choice={...} as kwargs to opt in.
          _parse_response() will auto-extract JSON from the tool_use content block.
        """
        system_parts: list[str] = []
        user_messages: list[dict[str, str]] = []

        for m in messages:
            if m.role == "system":
                system_parts.append(m.content)
            else:
                user_messages.append({"role": m.role, "content": m.content})

        payload: dict[str, Any] = {
            "model": kwargs.get("model", self.model),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature),
            "messages": user_messages,
        }

        if system_parts:
            # Build structured system list so the first (static) block gets cached.
            # Last block is dynamic market context — no cache_control.
            if len(system_parts) == 1:
                payload["system"] = [
                    {
                        "type": "text",
                        "text": system_parts[0],
                        "cache_control": {"type": "ephemeral"},
                    }
                ]
            else:
                blocks: list[dict[str, Any]] = [
                    {
                        "type": "text",
                        "text": system_parts[0],
                        "cache_control": {"type": "ephemeral"},  # static specialization
                    }
                ]
                for part in system_parts[1:-1]:
                    blocks.append({"type": "text", "text": part, "cache_control": {"type": "ephemeral"}})
                blocks.append({"type": "text", "text": system_parts[-1]})  # dynamic — no cache
                payload["system"] = blocks

        # Optional structured-output tool use (П1: ~100% JSON reliability)
        if "tools" in kwargs:
            payload["tools"] = kwargs["tools"]
        if "tool_choice" in kwargs:
            payload["tool_choice"] = kwargs["tool_choice"]

        return payload

    def _parse_response(self, data: dict[str, Any], latency: float) -> LLMResponse:
        """Parse Anthropic Messages API response.

        Handles both plain text and tool_use content blocks.
        When a tool_use block is present its ``input`` dict is serialised to
        JSON and returned as the response content (structured-output path).
        Cache token counters are forwarded to LLMResponse for cost tracking.
        """
        content_blocks = data.get("content", [])
        text = ""
        for b in content_blocks:
            if b.get("type") == "text":
                text += b.get("text", "")
            elif b.get("type") == "tool_use":
                # Structured output: serialise the tool input as JSON string
                tool_input = b.get("input", {})
                text = json.dumps(tool_input, ensure_ascii=False)
                break  # first tool_use block wins

        usage = data.get("usage", {})
        prompt_tokens = usage.get("input_tokens", 0)
        completion_tokens = usage.get("output_tokens", 0)
        cache_hit = usage.get("cache_read_input_tokens", 0)
        cache_miss = usage.get("cache_creation_input_tokens", 0)

        return LLMResponse(
            content=text,
            model=data.get("model", self.model),
            provider=self.PROVIDER,
            finish_reason=data.get("stop_reason"),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=latency,
            raw_response=data,
            prompt_cache_hit_tokens=cache_hit,
            prompt_cache_miss_tokens=cache_miss,
        )

    async def chat(self, messages: list[LLMMessage], **kwargs: Any) -> LLMResponse:
        """Send chat completion with retry, rate limiting, and usage tracking."""
        estimated_tokens = kwargs.pop("estimated_tokens", 1000)
        kwargs.pop("json_mode", None)  # Anthropic has no response_format — ignore

        await self.rate_limiter.acquire(estimated_tokens=estimated_tokens)

        session = await self._get_session()
        start_time = time.time()
        payload = self._build_payload(messages, **kwargs)

        for attempt in range(self.config.max_retries):
            try:
                async with session.post(_ANTHROPIC_API_URL, json=payload) as resp:
                    if resp.status == 429:
                        try:
                            retry_after = min(float(resp.headers.get("retry-after", 5)), 30.0)
                        except (ValueError, TypeError):
                            retry_after = min(5.0 * (2**attempt), 30.0)
                        logger.warning(
                            f"{self.EMOJI} Rate limited, waiting {retry_after}s "
                            f"(attempt {attempt + 1}/{self.config.max_retries})"
                        )
                        if attempt < self.config.max_retries - 1:
                            await asyncio.sleep(retry_after)
                            continue
                        raise RuntimeError(
                            f"ClaudeClient: rate limit exceeded after {self.config.max_retries} attempts"
                        )

                    resp.raise_for_status()
                    data = await resp.json()
                    latency = (time.time() - start_time) * 1000
                    response = self._parse_response(data, latency)

                    self.total_requests += 1
                    self.total_tokens += response.total_tokens
                    self.total_cost += response.estimated_cost
                    self.rate_limiter.record_usage(
                        tokens=response.total_tokens,
                        cost_usd=response.estimated_cost,
                    )
                    return response

            except aiohttp.ClientError as e:
                logger.warning(f"{self.EMOJI} Request failed (attempt {attempt + 1}): {e}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay_seconds * (2**attempt))
                else:
                    raise

        raise RuntimeError("ClaudeClient: max retries exceeded")

    async def chat_stream(
        self,
        messages: list[LLMMessage],
        **kwargs: Any,
    ) -> AsyncGenerator[str]:
        """Stream via Anthropic SSE (content_block_delta / text_delta events)."""
        kwargs.pop("json_mode", None)
        estimated_tokens = kwargs.pop("estimated_tokens", 1000)
        await self.rate_limiter.acquire(estimated_tokens=estimated_tokens)

        session = await self._get_session()
        payload = self._build_payload(messages, **kwargs)
        payload["stream"] = True

        async with session.post(_ANTHROPIC_API_URL, json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.content:
                decoded = line.decode().strip()
                if not decoded.startswith("data: "):
                    continue
                data_str = decoded[6:]
                if data_str == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                    if data.get("type") == "content_block_delta":
                        delta = data.get("delta", {})
                        if delta.get("type") == "text_delta":
                            yield delta.get("text", "")
                except json.JSONDecodeError:
                    continue

    async def close(self) -> None:
        """Close persistent session."""
        if self.session and not self.session.closed:
            await self.session.close()
        logger.info(f"{self.EMOJI} ClaudeClient closed")


__all__ = ["ClaudeClient"]
