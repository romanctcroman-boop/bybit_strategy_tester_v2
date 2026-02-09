"""
Real LLM Deliberation Integration

Connects MultiAgentDeliberation with real LLM APIs (DeepSeek, Qwen, Perplexity).
This module creates an enhanced deliberation system that uses actual AI responses
from 3 specialized agents for robust multi-agent consensus.

Agent Specializations:
- DeepSeek: Quantitative analyst — conservative, data-driven strategies
- Qwen: Technical analyst — momentum, pattern recognition, indicator optimization
- Perplexity: Market researcher — real-time sentiment, macro trends, web-sourced insights

P2 Fix (2026-01-28): Now uses KeyManager for secure API key access instead of os.environ.
P2 Update (2026-02-09): Full 3-agent Qwen integration with specialized system prompts.
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
    QwenClient,
)


class RealLLMDeliberation(MultiAgentDeliberation):
    """
    Multi-Agent Deliberation with real LLM API calls.

    Extends MultiAgentDeliberation to use actual DeepSeek/Qwen/Perplexity APIs
    instead of simulated responses. Each agent has a specialized system prompt
    matching its domain expertise.

    Agent Roles:
        - **deepseek**: Quantitative analyst — risk metrics, statistical validation,
          conservative approach to strategy design.
        - **qwen**: Technical analyst — momentum analysis, indicator optimization,
          pattern recognition, moderate risk tolerance.
        - **perplexity**: Market researcher — real-time sentiment, macro context,
          news-driven insights with web search capability.

    Example:
        deliberation = RealLLMDeliberation()

        result = await deliberation.deliberate(
            question="Should I use RSI or MACD for BTC entry signals?",
            agents=["deepseek", "qwen", "perplexity"],
            max_rounds=2,
        )

        print(f"Decision: {result.decision}")
        print(f"Confidence: {result.confidence:.2%}")
    """

    # Agent-specific system prompts with trading domain specialization
    AGENT_SYSTEM_PROMPTS: dict[str, str] = {
        "deepseek": (
            "You are a quantitative trading analyst participating in a multi-agent deliberation. "
            "Your expertise: statistical analysis, risk management, Sharpe ratio optimization, "
            "drawdown control, and evidence-based decision making. "
            "You prefer conservative, data-validated strategies with strong risk-adjusted returns. "
            "Always consider commission impact (0.07%) and realistic slippage. "
            "Follow the exact format specified in the prompt."
        ),
        "qwen": (
            "You are a technical analysis expert participating in a multi-agent deliberation. "
            "Your expertise: momentum indicators (RSI, MACD, Stochastic), moving average systems, "
            "Bollinger Bands, pattern recognition, and indicator parameter optimization. "
            "You balance signal quality with trade frequency, preferring robust indicator combinations. "
            "Consider timeframe alignment and multi-timeframe confirmation. "
            "Follow the exact format specified in the prompt."
        ),
        "perplexity": (
            "You are a market research analyst participating in a multi-agent deliberation. "
            "Your expertise: market regime analysis, sentiment indicators, macro trends, "
            "volatility cycles, and event-driven strategy adjustments. "
            "You bring real-time market context and broader economic perspective. "
            "Consider market conditions, correlation shifts, and regime changes. "
            "Follow the exact format specified in the prompt."
        ),
    }

    # Default system prompt for unknown agents
    DEFAULT_SYSTEM_PROMPT = (
        "You are an expert AI agent participating in a multi-agent deliberation. "
        "You must analyze the question carefully and provide a well-reasoned response. "
        "Follow the exact format specified in the prompt."
    )

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

        # Qwen - use KeyManager
        qwen_key = _get_api_key("QWEN_API_KEY")
        if qwen_key:
            config = LLMConfig(
                provider=LLMProvider.QWEN,
                api_key=qwen_key,
                model="qwen-plus",
                temperature=0.4,
                max_tokens=2048,
            )
            self._clients["qwen"] = QwenClient(config)
            logger.info("✅ Qwen client ready (via KeyManager)")
        else:
            logger.warning("⚠️ QWEN_API_KEY not found in KeyManager or environment")

    async def _real_ask(self, agent_type: str, prompt: str) -> str:
        """
        Ask real LLM for response with agent-specific system prompt.

        Each agent receives a specialized system prompt matching its domain
        expertise (quantitative, technical, or market research). Falls back
        to simulated response if the client is unavailable.

        Args:
            agent_type: Agent name — "deepseek", "qwen", or "perplexity"
            prompt: The deliberation prompt to send

        Returns:
            LLM response text
        """
        client = self._clients.get(agent_type.lower())

        if not client:
            logger.warning(f"No client for {agent_type}, using fallback")
            return self._simulate_response(agent_type, prompt)

        try:
            # Use agent-specific system prompt for domain specialization
            system_prompt = self.AGENT_SYSTEM_PROMPTS.get(agent_type.lower(), self.DEFAULT_SYSTEM_PROMPT)

            messages = [
                LLMMessage(role="system", content=system_prompt),
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
    agents: list[str] | None = None,
    max_rounds: int = 2,
    min_confidence: float = 0.7,
    voting_strategy: VotingStrategy = VotingStrategy.WEIGHTED,
) -> DeliberationResult:
    """
    Convenience function for real LLM deliberation.

    Automatically uses all available agents (up to 3: deepseek, qwen, perplexity).
    Falls back to deepseek-only if no agents have API keys configured.

    Args:
        question: Question to deliberate
        agents: List of agent types (default: all available agents)
        max_rounds: Max deliberation rounds
        min_confidence: Min confidence for consensus
        voting_strategy: Voting strategy to use

    Returns:
        DeliberationResult with real AI responses
    """
    deliberation = get_real_deliberation()

    # Default to all available agents (up to 3)
    if agents is None:
        available = list(deliberation._clients.keys())
        agents = available if available else ["deepseek"]

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
