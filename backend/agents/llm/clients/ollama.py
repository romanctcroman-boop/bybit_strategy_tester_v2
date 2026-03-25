"""
Ollama LLM Client

Client for local LLM models via Ollama (non-OpenAI-compatible API format).
"""

from __future__ import annotations

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


class OllamaClient(LLMClient):
    """Ollama local LLM client (non-OpenAI API format)."""

    DEFAULT_BASE_URL = "http://localhost:11434"
    DEFAULT_MODEL = "llama2"

    def __init__(self, config: LLMConfig):
        self.config = config
        self.base_url = config.base_url or self.DEFAULT_BASE_URL
        self.model = config.model if config.model != "default" else self.DEFAULT_MODEL
        self.session: aiohttp.ClientSession | None = None

        logger.info(f"🦙 Ollama client initialized: {self.model}")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create session (no auth headers for local)."""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    async def chat(
        self,
        messages: list[LLMMessage],
        **kwargs: Any,
    ) -> LLMResponse:
        """Send chat completion to Ollama."""
        session = await self._get_session()
        start_time = time.time()

        payload = {
            "model": kwargs.get("model", self.model),
            "messages": [m.to_dict() for m in messages],
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", self.config.temperature),
                "num_predict": kwargs.get("max_tokens", self.config.max_tokens),
            },
        }

        try:
            async with session.post(
                f"{self.base_url}/api/chat",
                json=payload,
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()

                latency = (time.time() - start_time) * 1000

                return LLMResponse(
                    content=data["message"]["content"],
                    model=data.get("model", self.model),
                    provider=LLMProvider.OLLAMA,
                    finish_reason="stop",
                    prompt_tokens=data.get("prompt_eval_count", 0),
                    completion_tokens=data.get("eval_count", 0),
                    total_tokens=(data.get("prompt_eval_count", 0) + data.get("eval_count", 0)),
                    latency_ms=latency,
                    raw_response=data,
                )
        except aiohttp.ClientError as e:
            logger.error(f"Ollama request failed: {e}")
            raise

    async def chat_stream(
        self,
        messages: list[LLMMessage],
        **kwargs: Any,
    ) -> AsyncGenerator[str]:
        """Stream chat completion from Ollama."""
        session = await self._get_session()

        payload = {
            "model": kwargs.get("model", self.model),
            "messages": [m.to_dict() for m in messages],
            "stream": True,
        }

        async with session.post(
            f"{self.base_url}/api/chat",
            json=payload,
        ) as resp:
            resp.raise_for_status()

            async for line in resp.content:
                try:
                    data = json.loads(line.decode())
                    if "message" in data and "content" in data["message"]:
                        yield data["message"]["content"]
                except json.JSONDecodeError:
                    continue

    async def close(self) -> None:
        """Close session."""
        if self.session and not self.session.closed:
            await self.session.close()
        logger.info("🦙 Ollama client closed")


__all__ = ["OllamaClient"]
