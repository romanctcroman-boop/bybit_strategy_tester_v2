"""
API Helpers Mixin for UnifiedAgentInterface

Extracted from unified_agent_interface.py to reduce file size.
Contains: URL/header builders, content/token extraction, streaming,
           reasoning log management, citation extraction.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import UTC
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING, Any

import httpx
from loguru import logger

from backend.agents.models import AgentChannel, AgentType

if TYPE_CHECKING:
    from backend.agents.key_models import APIKey
    from backend.agents.request_models import AgentRequest, AgentResponse


class APIMixin:
    """Mixin providing API URL/header helpers, content extraction, and streaming."""

    # ------------------------------------------------------------------
    # URL / Header helpers
    # ------------------------------------------------------------------

    def _get_api_url(self, agent_type: AgentType, strict_mode: bool = False) -> str:
        """Get URL for API.

        Qwen uses Singapore (intl) endpoint.
        Available models: qwen-plus, qwen-flash, qwen3-max, qwq-plus, qwen3-coder-plus
        """
        if agent_type == AgentType.DEEPSEEK:
            if strict_mode:
                return "https://api.deepseek.com/beta/chat/completions"
            return "https://api.deepseek.com/v1/chat/completions"
        elif agent_type == AgentType.QWEN:
            # Singapore (International) region — dashscope-intl
            return "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"
        return "https://api.perplexity.ai/chat/completions"

    def _get_headers(self, key: APIKey) -> dict[str, str]:
        """Get headers for API request"""
        return {
            "Authorization": f"Bearer {key.value}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _get_retry_after_seconds(response: httpx.Response) -> float | None:
        header = response.headers.get("Retry-After") if response else None
        if not header:
            return None
        try:
            return float(header)
        except ValueError:
            try:
                retry_dt = parsedate_to_datetime(header)
                if retry_dt.tzinfo is None:
                    retry_dt = retry_dt.replace(tzinfo=UTC)
                from datetime import datetime

                delta = retry_dt - datetime.now(UTC)
                return max(0.0, delta.total_seconds())
            except Exception:
                return None

    def get_key_pool_snapshot(self) -> dict[str, Any]:
        """Export current key pool metrics for monitoring"""
        return {
            "deepseek": self.key_manager.get_pool_metrics(AgentType.DEEPSEEK),
            "qwen": self.key_manager.get_pool_metrics(AgentType.QWEN),
            "perplexity": self.key_manager.get_pool_metrics(AgentType.PERPLEXITY),
            "telemetry": self.key_manager.pool_telemetry.copy(),
        }

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------

    async def stream_request(
        self,
        request: AgentRequest,
        on_reasoning_chunk: Callable | None = None,
        on_content_chunk: Callable | None = None,
    ) -> AgentResponse:
        """
        Stream a request with real-time output.

        DeepSeek V3.2 streaming returns:
        - reasoning_content chunks (Chain-of-Thought)
        - content chunks (Final answer)
        """
        from backend.agents.request_models import AgentResponse

        start_time = time.time()

        key = await self.key_manager.get_active_key(request.agent_type)
        if not key:
            return AgentResponse(
                success=False,
                content="",
                channel=AgentChannel.DIRECT_API,
                error=f"No active {request.agent_type.value} API keys",
            )

        url = self._get_api_url(request.agent_type, strict_mode=request.strict_mode)
        headers = self._get_headers(key)

        payload = request.to_direct_api_format(include_tools=False)
        payload["stream"] = True

        logger.info(f"🌊 Starting streaming request to {request.agent_type.value}")

        full_reasoning = ""
        full_content = ""

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue

                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break

                        try:
                            data = json.loads(data_str)
                            delta = data.get("choices", [{}])[0].get("delta", {})

                            reasoning_chunk = delta.get("reasoning_content", "")
                            if reasoning_chunk:
                                full_reasoning += reasoning_chunk
                                if on_reasoning_chunk:
                                    await on_reasoning_chunk(reasoning_chunk)

                            content_chunk = delta.get("content", "")
                            if content_chunk:
                                full_content += content_chunk
                                if on_content_chunk:
                                    await on_content_chunk(content_chunk)

                        except json.JSONDecodeError:
                            continue

            latency = (time.time() - start_time) * 1000
            self.key_manager.mark_success(key)

            logger.success(
                f"✅ Streaming completed in {latency:.0f}ms "
                f"(reasoning: {len(full_reasoning)}, content: {len(full_content)})"
            )

            if full_reasoning:
                self._save_reasoning_log(full_reasoning)

            return AgentResponse(
                success=True,
                content=full_content,
                channel=AgentChannel.DIRECT_API,
                api_key_index=key.index,
                latency_ms=latency,
                reasoning_content=full_reasoning if full_reasoning else None,
            )

        except httpx.HTTPStatusError as e:
            self.key_manager.mark_rate_limit(key)
            return AgentResponse(
                success=False,
                content="",
                channel=AgentChannel.DIRECT_API,
                latency_ms=(time.time() - start_time) * 1000,
                error=f"HTTP {e.response.status_code}: {e.response.text[:200]}",
            )

        except Exception as e:
            self.key_manager.mark_network_error(key)
            return AgentResponse(
                success=False,
                content="",
                channel=AgentChannel.DIRECT_API,
                latency_ms=(time.time() - start_time) * 1000,
                error=str(e),
            )

    # ------------------------------------------------------------------
    # Content extraction
    # ------------------------------------------------------------------

    def _extract_content(self, data: dict, agent_type: AgentType) -> str:
        """Extract content from API response with fallback strategy"""
        extraction_paths = [
            lambda d: d["choices"][0]["message"]["content"],
            lambda d: d["message"]["content"],
            lambda d: d["content"],
            lambda d: d["text"],
            lambda d: d["response"],
            lambda d: d["choices"][0]["text"],
            lambda d: d["output"]["text"],
        ]

        for path_func in extraction_paths:
            try:
                content = path_func(data)
                if content and isinstance(content, str) and content.strip():
                    return content.strip()
            except (KeyError, IndexError, TypeError):
                continue

        logger.error(f"❌ Failed to extract content from response. Full data: {json.dumps(data, indent=2)[:500]}...")

        for key in ["choices", "message", "content", "text", "response", "output"]:
            if key in data:
                value = data[key]
                if isinstance(value, str) and value.strip():
                    return value.strip()
                if isinstance(value, list) and value:
                    return str(value[0])

        logger.error("❌ No content found in any known field, returning JSON dump")
        return json.dumps(data, indent=2)

    def _extract_reasoning_content(self, data: dict) -> str | None:
        """Extract reasoning_content from DeepSeek V3.2 Thinking Mode response."""
        try:
            message = data.get("choices", [{}])[0].get("message", {})
            reasoning = message.get("reasoning_content")
            if reasoning and isinstance(reasoning, str) and reasoning.strip():
                self._save_reasoning_log(reasoning.strip())
                return reasoning.strip()
        except (KeyError, IndexError, TypeError) as e:
            logger.debug(f"No reasoning_content found: {e}")
        return None

    def _save_reasoning_log(self, reasoning: str) -> None:
        """Save reasoning content to log file for analysis."""
        try:
            from datetime import datetime
            from pathlib import Path

            log_dir = Path("logs/reasoning")
            log_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = log_dir / f"reasoning_{timestamp}.md"

            content = (
                f"# DeepSeek V3.2 Reasoning Log\n"
                f"**Timestamp:** {datetime.now().isoformat()}\n"
                f"**Length:** {len(reasoning)} chars\n\n"
                f"## Chain-of-Thought\n\n{reasoning}\n"
            )
            log_file.write_text(content, encoding="utf-8")
            logger.debug(f"💾 Reasoning saved to {log_file}")
        except Exception as e:
            logger.warning(f"Failed to save reasoning log: {e}")

    def _clear_reasoning_in_messages(self, messages: list[dict]) -> None:
        """Clear reasoning_content from messages to save bandwidth."""
        for msg in messages:
            if isinstance(msg, dict) and "reasoning_content" in msg:
                msg["reasoning_content"] = None
            elif hasattr(msg, "reasoning_content"):
                msg.reasoning_content = None

    def _extract_citations(self, data: dict, agent_type: AgentType) -> list[str] | None:
        """Extract citations from Perplexity API response."""
        if agent_type != AgentType.PERPLEXITY:
            return None

        try:
            citations = data.get("citations", [])
            if citations and isinstance(citations, list):
                valid_citations = [
                    url for url in citations if isinstance(url, str) and url.startswith(("http://", "https://"))
                ]
                if valid_citations:
                    logger.info(f"📚 Extracted {len(valid_citations)} citations from Perplexity")
                    return valid_citations
        except Exception as e:
            logger.debug(f"Failed to extract citations: {e}")

        return None

    def _extract_token_usage(self, data: dict, agent_type: AgentType):
        """Extract token usage from API response."""
        from backend.agents.request_models import TokenUsage

        try:
            usage = data.get("usage", {})
            if not usage:
                return None

            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", 0)

            reasoning_tokens = 0
            if agent_type == AgentType.DEEPSEEK:
                details = usage.get("completion_tokens_details", {})
                reasoning_tokens = details.get("reasoning_tokens", 0)

            cache_hit_tokens = 0
            cache_miss_tokens = 0
            cache_savings_pct = 0.0
            if agent_type == AgentType.DEEPSEEK:
                prompt_details = usage.get("prompt_tokens_details", {})
                cache_hit_tokens = prompt_details.get("cached_tokens", 0)
                if cache_hit_tokens == 0:
                    cache_hit_tokens = usage.get("prompt_cache_hit_tokens", 0)
                    cache_miss_tokens = usage.get("prompt_cache_miss_tokens", 0)
                else:
                    cache_miss_tokens = prompt_tokens - cache_hit_tokens

                if prompt_tokens > 0:
                    cache_savings_pct = round((cache_hit_tokens / prompt_tokens) * 100, 2)

            cost_usd = None
            if agent_type == AgentType.PERPLEXITY:
                cost_info = usage.get("cost", {})
                cost_usd = cost_info.get("total_cost")

            if agent_type == AgentType.DEEPSEEK and cost_usd is None:
                if reasoning_tokens > 0:
                    input_cost = prompt_tokens * 0.55 / 1_000_000
                    output_cost = completion_tokens * 2.19 / 1_000_000
                else:
                    input_cost = prompt_tokens * 0.14 / 1_000_000
                    output_cost = completion_tokens * 0.28 / 1_000_000
                cost_usd = round(input_cost + output_cost, 6)

            token_usage = TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                reasoning_tokens=reasoning_tokens,
                cost_usd=cost_usd,
                cache_hit_tokens=cache_hit_tokens,
                cache_miss_tokens=cache_miss_tokens,
                cache_savings_pct=cache_savings_pct,
            )

            cache_info = ""
            if cache_hit_tokens > 0:
                cache_info = f" | Cache: {cache_savings_pct:.1f}% ({cache_hit_tokens} tokens)"

            logger.debug(
                f"📊 Token usage: {total_tokens} total "
                f"({prompt_tokens} in, {completion_tokens} out"
                f"{f', {reasoning_tokens} reasoning' if reasoning_tokens else ''})"
                f"{cache_info}"
                f" | Cost: ${cost_usd:.4f}"
                if cost_usd
                else ""
            )

            return token_usage

        except Exception as e:
            logger.debug(f"Failed to extract token usage: {e}")
            return None
