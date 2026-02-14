"""
Qwen LLM Client

OpenAI-compatible API client for Alibaba Cloud Model Studio (Qwen) models.

Supported models (International / Singapore region):
  Commercial:
    - qwen-plus          Best balance (1M ctx, $0.40/$1.20 per 1M tok)
    - qwen-flash         Fastest & cheapest (1M ctx, $0.05/$0.40 per 1M tok)
    - qwen3-max          Most powerful (262K ctx, $1.20/$6.00 per 1M tok)
  Reasoning:
    - qwq-plus           Chain-of-thought reasoning ($0.80/$2.40 per 1M tok)
  Code:
    - qwen3-coder-plus   Code generation & tool calling (1M ctx)

Regional endpoints (API keys are NOT interchangeable between regions):
  - Singapore:   https://dashscope-intl.aliyuncs.com/compatible-mode/v1
  - US:          https://dashscope-us.aliyuncs.com/compatible-mode/v1
  - China:       https://dashscope.aliyuncs.com/compatible-mode/v1

API docs: https://www.alibabacloud.com/help/en/model-studio/
"""

from __future__ import annotations

from typing import Any

from backend.agents.llm.base_client import (
    LLMMessage,
    LLMProvider,
    LLMResponse,
    OpenAICompatibleClient,
)


class QwenClient(OpenAICompatibleClient):
    """
    Qwen API client with hybrid thinking mode support.

    Pass enable_thinking=True in chat() kwargs to enable CoT reasoning.
    Thinking output is returned in LLMResponse.reasoning_content.
    """

    DEFAULT_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    DEFAULT_MODEL = "qwen-plus"
    PROVIDER = LLMProvider.QWEN
    BREAKER_NAME = "qwen_llm_client"
    EMOJI = "🟢"

    # Models that support hybrid thinking mode (enable_thinking parameter)
    THINKING_MODELS = {
        "qwen-plus",
        "qwen-plus-latest",
        "qwen-flash",
        "qwen-flash-latest",
        "qwen3-max",
        "qwen3-max-preview",
        "qwen-turbo",
        "qwen-turbo-latest",
        "qwen3-235b-a22b",
        "qwen3-32b",
        "qwen3-30b-a3b",
        "qwen3-14b",
        "qwen3-8b",
        "qwen3-4b",
    }

    def _build_payload(self, messages: list[LLMMessage], **kwargs: Any) -> dict[str, Any]:
        """Build payload with optional thinking mode parameters."""
        payload = super()._build_payload(messages, **kwargs)

        model = kwargs.get("model", self.model)
        enable_thinking = kwargs.get("enable_thinking")
        if enable_thinking is not None and model in self.THINKING_MODELS:
            payload["enable_thinking"] = enable_thinking
            thinking_budget = kwargs.get("thinking_budget")
            if thinking_budget and enable_thinking:
                payload["thinking_budget"] = thinking_budget

        return payload

    def _parse_response(self, data: dict[str, Any], latency: float) -> LLMResponse:
        """Parse response with reasoning_content extraction."""
        message = data["choices"][0]["message"]
        reasoning = message.get("reasoning_content")

        return LLMResponse(
            content=message["content"],
            model=data.get("model", self.model),
            provider=self.PROVIDER,
            finish_reason=data["choices"][0].get("finish_reason"),
            prompt_tokens=data.get("usage", {}).get("prompt_tokens", 0),
            completion_tokens=data.get("usage", {}).get("completion_tokens", 0),
            total_tokens=data.get("usage", {}).get("total_tokens", 0),
            latency_ms=latency,
            raw_response=data,
            reasoning_content=reasoning,
        )


__all__ = ["QwenClient"]
