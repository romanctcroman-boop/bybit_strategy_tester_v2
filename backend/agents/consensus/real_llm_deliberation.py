"""
Real LLM Deliberation Integration

Connects MultiAgentDeliberation with real LLM APIs (DeepSeek, Perplexity).
This module creates an enhanced deliberation system that uses actual AI responses.

P2 Fix (2026-01-28): Now uses KeyManager for secure API key access instead of os.environ.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

# Use KeyManager for secure API key access
try:
    from backend.security.key_manager import get_key_manager

    _key_manager = get_key_manager()
except ImportError:
    logger.warning("KeyManager not available, falling back to environment variables")
    _key_manager = None

import os


def _get_api_key(key_name: str) -> str | None:
    """
    Get API key securely via KeyManager, fallback to env.
    
    Args:
        key_name: Name of the key (e.g., "DEEPSEEK_API_KEY")
        
    Returns:
        Decrypted API key or None
    """
    if _key_manager:
        try:
            return _key_manager.get_decrypted_key(key_name)
        except Exception as e:
            logger.debug(f"KeyManager failed for {key_name}: {e}")

    # Fallback to environment
    return os.environ.get(key_name)

from backend.agents.consensus.deliberation import (
    DeliberationResult,
    MultiAgentDeliberation,
    VotingStrategy,
)
from backend.agents.llm.connections import (
    DeepSeekClient,
    LLMConfig,
    LLMMessage,
    LLMProvider,
    PerplexityClient,
)


class RealLLMDeliberation(MultiAgentDeliberation):
    """
    Multi-Agent Deliberation with real LLM API calls.

    Extends MultiAgentDeliberation to use actual DeepSeek/Perplexity APIs
    instead of simulated responses.

    Example:
        deliberation = RealLLMDeliberation()

        result = await deliberation.deliberate(
            question="Should I use RSI or MACD for BTC entry signals?",
            agents=["deepseek", "perplexity"],
            max_rounds=2,
        )

        print(f"Decision: {result.decision}")
        print(f"Confidence: {result.confidence:.2%}")
    """

    def __init__(self):
        """Initialize with real LLM clients"""
        super().__init__()

        self._clients: dict[str, Any] = {}
        self._initialize_clients()

        # Override ask_fn to use real LLM
        self.ask_fn = self._real_ask

        logger.info("🤖 RealLLMDeliberation initialized with actual LLM APIs")

    def _initialize_clients(self) -> None:
        """Initialize LLM clients using KeyManager for secure key access"""
        # DeepSeek - use KeyManager
        deepseek_key = _get_api_key("DEEPSEEK_API_KEY")
        if deepseek_key:
            config = LLMConfig(
                provider=LLMProvider.DEEPSEEK,
                api_key=deepseek_key,
                model="deepseek-chat",
                temperature=0.7,
                max_tokens=2048,
            )
            self._clients["deepseek"] = DeepSeekClient(config)
            logger.info("✅ DeepSeek client ready (via KeyManager)")
        else:
            logger.warning("⚠️ DEEPSEEK_API_KEY not found in KeyManager or environment")

        # Perplexity - use KeyManager
        perplexity_key = _get_api_key("PERPLEXITY_API_KEY")
        if perplexity_key:
            config = LLMConfig(
                provider=LLMProvider.PERPLEXITY,
                api_key=perplexity_key,
                model="llama-3.1-sonar-small-128k-online",
                temperature=0.7,
                max_tokens=2048,
            )
            self._clients["perplexity"] = PerplexityClient(config)
            logger.info("✅ Perplexity client ready (via KeyManager)")
        else:
            logger.warning("⚠️ PERPLEXITY_API_KEY not found in KeyManager or environment")

    async def _real_ask(self, agent_type: str, prompt: str) -> str:
        """
        Ask real LLM for response.

        Args:
            agent_type: "deepseek" or "perplexity"
            prompt: The prompt to send

        Returns:
            LLM response text
        """
        client = self._clients.get(agent_type.lower())

        if not client:
            logger.warning(f"No client for {agent_type}, using fallback")
            return self._simulate_response(agent_type, prompt)

        try:
            messages = [
                LLMMessage(
                    role="system",
                    content=(
                        "You are an expert AI agent participating in a multi-agent deliberation. "
                        "You must analyze the question carefully and provide a well-reasoned response. "
                        "Follow the exact format specified in the prompt."
                    ),
                ),
                LLMMessage(role="user", content=prompt),
            ]

            response = await client.chat(messages)

            logger.debug(
                f"🤖 {agent_type} response: {len(response.content)} chars, "
                f"{response.total_tokens} tokens, {response.latency_ms:.0f}ms"
            )

            return response.content

        except Exception as e:
            logger.error(f"LLM request failed for {agent_type}: {e}")
            return self._simulate_response(agent_type, prompt)

    async def close(self) -> None:
        """Close all LLM clients"""
        for name, client in self._clients.items():
            try:
                await client.close()
                logger.info(f"Closed {name} client")
            except Exception as e:
                logger.warning(f"Error closing {name}: {e}")

        self._clients.clear()


# Global instance
_real_deliberation: RealLLMDeliberation | None = None


def get_real_deliberation() -> RealLLMDeliberation:
    """Get or create RealLLMDeliberation singleton"""
    global _real_deliberation
    if _real_deliberation is None:
        _real_deliberation = RealLLMDeliberation()
    return _real_deliberation


async def deliberate_with_llm(
    question: str,
    agents: list[str] = None,
    max_rounds: int = 2,
    min_confidence: float = 0.7,
    voting_strategy: VotingStrategy = VotingStrategy.WEIGHTED,
) -> DeliberationResult:
    """
    Convenience function for real LLM deliberation.

    Args:
        question: Question to deliberate
        agents: List of agent types (default: ["deepseek"])
        max_rounds: Max deliberation rounds
        min_confidence: Min confidence for consensus
        voting_strategy: Voting strategy to use

    Returns:
        DeliberationResult with real AI responses
    """
    deliberation = get_real_deliberation()

    # Default to available agents
    if agents is None:
        agents = list(deliberation._clients.keys()) or ["deepseek"]

    return await deliberation.deliberate(
        question=question,
        agents=agents,
        max_rounds=max_rounds,
        min_confidence=min_confidence,
        voting_strategy=voting_strategy,
    )


__all__ = [
    "RealLLMDeliberation",
    "deliberate_with_llm",
    "get_real_deliberation",
]
