"""
Tests for P5: Memory ↔ Deliberation Integration.

Covers:
  - P5.1: auto_recall before deliberation (recall_for_deliberation)
  - P5.2: auto_store after consensus (store_deliberation_result)
  - P5.3: build_memory_context in ConsensusEngine
  - P5 integration: deliberate_with_llm with use_memory flag
  - Backward compat: use_memory=False skips all memory ops
  - High confidence → SEMANTIC tier
  - No duplicate injection (current session results excluded)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.agents.consensus.consensus_engine import ConsensusEngine
from backend.agents.consensus.deliberation import (
    AgentVote,
    DeliberationResult,
    DeliberationRound,
    VotingStrategy,
)
from backend.agents.consensus.real_llm_deliberation import (
    RealLLMDeliberation,
)
from backend.agents.memory.hierarchical_memory import (
    HierarchicalMemory,
    MemoryType,
)

# ── Fixtures ───────────────────────────────────────────────────────────


@pytest.fixture()
def memory():
    """Fresh HierarchicalMemory without backend/embeddings."""
    return HierarchicalMemory()


@pytest.fixture()
def mock_delib():
    """RealLLMDeliberation with mocked clients (no real API calls)."""
    with patch.object(RealLLMDeliberation, "_initialize_clients"):
        delib = RealLLMDeliberation(enable_perplexity_enrichment=False)
        delib._clients = {}
        return delib


@pytest.fixture()
def sample_result():
    """A sample DeliberationResult for testing store."""
    return DeliberationResult(
        id="delib_test123",
        question="Should we use RSI or MACD for BTC entries?",
        decision="Use RSI(21) with MACD confirmation",
        confidence=0.85,
        voting_strategy=VotingStrategy.WEIGHTED,
        rounds=[
            DeliberationRound(
                round_number=1,
                phase="initial",
                opinions=[
                    AgentVote(
                        agent_id="deepseek_01",
                        agent_type="deepseek",
                        position="RSI(21)",
                        confidence=0.82,
                        reasoning="Lower noise",
                        evidence=["backtest data"],
                    )
                ],
                critiques=[],
                consensus_emerging=True,
                convergence_score=0.85,
            )
        ],
        final_votes=[
            AgentVote(
                agent_id="deepseek_01",
                agent_type="deepseek",
                position="RSI(21)",
                confidence=0.82,
                reasoning="Lower noise",
                evidence=["backtest data"],
            )
        ],
        dissenting_opinions=[],
        evidence_chain=[],
        duration_seconds=5.0,
        metadata={"agents": ["deepseek", "qwen"]},
    )


@pytest.fixture()
def low_confidence_result(sample_result):
    """A deliberation result with low confidence (stays EPISODIC)."""
    sample_result.confidence = 0.55
    sample_result.id = "delib_low_conf"
    return sample_result


# ── P5.1: Auto-Recall ──────────────────────────────────────────────────


class TestAutoRecall:
    @pytest.mark.asyncio
    async def test_recall_returns_context_when_memories_exist(self, mock_delib):
        """recall_for_deliberation returns formatted context when memories exist."""
        mem = HierarchicalMemory()
        await mem.store(
            "RSI above 70 is overbought on BTCUSDT daily",
            memory_type=MemoryType.SEMANTIC,
            importance=0.8,
            tags=["rsi", "btcusdt"],
        )

        with patch(
            "backend.agents.mcp.tools.memory.get_global_memory",
            return_value=mem,
        ):
            context = await mock_delib.recall_for_deliberation("Should we use RSI for BTC entries?")

        assert context is not None
        assert "Prior Knowledge" in context
        assert "RSI" in context
        assert mock_delib._memory_context == context

    @pytest.mark.asyncio
    async def test_recall_returns_none_when_no_memories(self, mock_delib):
        """recall_for_deliberation returns None for empty memory."""
        mem = HierarchicalMemory()

        with patch(
            "backend.agents.mcp.tools.memory.get_global_memory",
            return_value=mem,
        ):
            context = await mock_delib.recall_for_deliberation("Anything")

        assert context is None
        assert mock_delib._memory_context is None

    @pytest.mark.asyncio
    async def test_recall_graceful_on_error(self, mock_delib):
        """recall_for_deliberation returns None on exception (non-fatal)."""
        with patch(
            "backend.agents.mcp.tools.memory.get_global_memory",
            side_effect=RuntimeError("DB unavailable"),
        ):
            context = await mock_delib.recall_for_deliberation("Anything")

        assert context is None

    @pytest.mark.asyncio
    async def test_recall_formats_multiple_memories(self, mock_delib):
        """Multiple recalled memories appear numbered in the context."""
        mem = HierarchicalMemory()
        await mem.store("RSI analysis result 1", importance=0.7)
        await mem.store("MACD analysis result 2", importance=0.6)
        await mem.store("Bollinger analysis result 3", importance=0.5)

        with patch(
            "backend.agents.mcp.tools.memory.get_global_memory",
            return_value=mem,
        ):
            context = await mock_delib.recall_for_deliberation("indicator analysis")

        assert context is not None
        assert "1." in context
        assert "2." in context


# ── P5.2: Auto-Store ──────────────────────────────────────────────────


class TestAutoStore:
    @pytest.mark.asyncio
    async def test_store_result_in_memory(self, mock_delib, sample_result):
        """store_deliberation_result saves to memory and returns ID."""
        mem = HierarchicalMemory()

        with patch(
            "backend.agents.mcp.tools.memory.get_global_memory",
            return_value=mem,
        ):
            item_id = await mock_delib.store_deliberation_result(sample_result)

        assert item_id is not None
        # Verify stored in memory
        total = sum(len(s) for s in mem.stores.values())
        assert total >= 1

    @pytest.mark.asyncio
    async def test_high_confidence_goes_to_semantic(self, mock_delib, sample_result):
        """Confidence >= 0.8 → SEMANTIC tier."""
        mem = HierarchicalMemory()
        sample_result.confidence = 0.9

        with patch(
            "backend.agents.mcp.tools.memory.get_global_memory",
            return_value=mem,
        ):
            await mock_delib.store_deliberation_result(sample_result)

        assert len(mem.stores[MemoryType.SEMANTIC]) == 1

    @pytest.mark.asyncio
    async def test_low_confidence_goes_to_episodic(self, mock_delib, low_confidence_result):
        """Confidence < 0.8 → EPISODIC tier."""
        mem = HierarchicalMemory()

        with patch(
            "backend.agents.mcp.tools.memory.get_global_memory",
            return_value=mem,
        ):
            await mock_delib.store_deliberation_result(low_confidence_result)

        assert len(mem.stores[MemoryType.EPISODIC]) == 1

    @pytest.mark.asyncio
    async def test_stored_content_includes_decision(self, mock_delib, sample_result):
        """Stored memory content includes the consensus decision."""
        mem = HierarchicalMemory()

        with patch(
            "backend.agents.mcp.tools.memory.get_global_memory",
            return_value=mem,
        ):
            await mock_delib.store_deliberation_result(sample_result)

        # Find the stored item
        items = list(mem.stores[MemoryType.SEMANTIC].values())
        assert len(items) == 1
        assert sample_result.decision in items[0].content
        assert "deliberation" in items[0].tags

    @pytest.mark.asyncio
    async def test_store_graceful_on_error(self, mock_delib, sample_result):
        """store_deliberation_result returns None on exception."""
        with patch(
            "backend.agents.mcp.tools.memory.get_global_memory",
            side_effect=RuntimeError("DB unavailable"),
        ):
            result = await mock_delib.store_deliberation_result(sample_result)

        assert result is None


# ── P5 Prompt Injection ────────────────────────────────────────────────


class TestPromptInjection:
    @pytest.mark.asyncio
    async def test_memory_context_injected_into_prompt(self, mock_delib):
        """When _memory_context is set, it's prepended to the prompt."""
        mock_client = AsyncMock()
        response = MagicMock()
        response.content = "POSITION: Use RSI(21)\nCONFIDENCE: 0.8\nREASONING: Based on data\nEVIDENCE: Backtest"
        response.total_tokens = 50
        response.latency_ms = 100
        mock_client.chat.return_value = response

        mock_delib._clients["deepseek"] = mock_client
        mock_delib._memory_context = "## Relevant Prior Knowledge\n1. RSI insight"

        await mock_delib._real_ask("deepseek", "What indicator to use?")

        # Verify the memory context was injected into the prompt
        call_args = mock_client.chat.call_args
        messages = call_args[0][0]
        user_msg = messages[1].content
        assert "Prior Knowledge" in user_msg
        assert "RSI insight" in user_msg

    @pytest.mark.asyncio
    async def test_no_injection_when_memory_context_none(self, mock_delib):
        """When _memory_context is None, prompt is unchanged."""
        mock_client = AsyncMock()
        response = MagicMock()
        response.content = "POSITION: X\nCONFIDENCE: 0.7\nREASONING: Y\nEVIDENCE: Z"
        response.total_tokens = 30
        response.latency_ms = 80
        mock_client.chat.return_value = response

        mock_delib._clients["deepseek"] = mock_client
        mock_delib._memory_context = None

        await mock_delib._real_ask("deepseek", "Simple question")

        call_args = mock_client.chat.call_args
        messages = call_args[0][0]
        user_msg = messages[1].content
        assert "Prior Knowledge" not in user_msg
        assert user_msg == "Simple question"


# ── P5.3: ConsensusEngine Memory Context ──────────────────────────────


class TestConsensusEngineMemoryContext:
    @pytest.mark.asyncio
    async def test_build_memory_context_returns_prior_results(self):
        """build_memory_context returns formatted prior consensus results."""
        mem = HierarchicalMemory()
        item = await mem.store(
            "Deliberation consensus: Use RSI(21) with MACD",
            memory_type=MemoryType.SEMANTIC,
            importance=0.8,
            tags=["deliberation", "consensus"],
            source="deliberation",
        )
        # Backdate so it's not excluded by the 5-min dedup
        item.created_at = datetime.now(UTC) - timedelta(hours=1)

        engine = ConsensusEngine()
        with patch(
            "backend.agents.mcp.tools.memory.get_global_memory",
            return_value=mem,
        ):
            context = await engine.build_memory_context("RSI vs MACD")

        assert context is not None
        assert "Prior Consensus Results" in context
        assert "RSI" in context

    @pytest.mark.asyncio
    async def test_build_memory_context_excludes_recent(self):
        """Items created in the last 5 min are excluded (deduplication)."""
        mem = HierarchicalMemory()
        await mem.store(
            "Very recent deliberation result",
            importance=0.9,
            tags=["deliberation"],
        )
        # created_at is now — within 5 min cutoff

        engine = ConsensusEngine()
        with patch(
            "backend.agents.mcp.tools.memory.get_global_memory",
            return_value=mem,
        ):
            context = await engine.build_memory_context("deliberation topic")

        assert context is None  # Excluded because too recent

    @pytest.mark.asyncio
    async def test_build_memory_context_returns_none_when_empty(self):
        """Returns None when no matching deliberation memories exist."""
        mem = HierarchicalMemory()
        engine = ConsensusEngine()
        with patch(
            "backend.agents.mcp.tools.memory.get_global_memory",
            return_value=mem,
        ):
            context = await engine.build_memory_context("any topic")

        assert context is None

    @pytest.mark.asyncio
    async def test_build_memory_context_graceful_on_error(self):
        """Returns None on exception (non-fatal)."""
        engine = ConsensusEngine()
        with patch(
            "backend.agents.mcp.tools.memory.get_global_memory",
            side_effect=RuntimeError("DB down"),
        ):
            context = await engine.build_memory_context("topic")

        assert context is None


# ── Clear Session ─────────────────────────────────────────────────────


class TestClearSession:
    def test_clear_session_clears_memory_context(self, mock_delib):
        """clear_session() resets _memory_context to None."""
        mock_delib._memory_context = "Some prior knowledge"
        mock_delib.clear_session()
        assert mock_delib._memory_context is None


# ── deliberate_with_llm Integration ───────────────────────────────────


class TestDeliberateWithLLMMemory:
    @pytest.mark.asyncio
    async def test_use_memory_true_calls_recall_and_store(self):
        """deliberate_with_llm with use_memory=True calls recall + store."""
        mock_recall = AsyncMock(return_value="## Prior Knowledge\n1. RSI data")
        mock_store = AsyncMock(return_value="mem_id_123")

        mock_delib = MagicMock()
        mock_delib._clients = {"deepseek": MagicMock()}
        mock_delib.clear_session = MagicMock()
        mock_delib.recall_for_deliberation = mock_recall
        mock_delib.store_deliberation_result = mock_store
        mock_delib.cross_validate = MagicMock(return_value=None)

        # Create a mock result
        mock_result = MagicMock()
        mock_result.metadata = {"agents": ["deepseek"]}
        mock_delib.deliberate = AsyncMock(return_value=mock_result)

        with patch(
            "backend.agents.consensus.real_llm_deliberation.get_real_deliberation",
            return_value=mock_delib,
        ):
            from backend.agents.consensus.real_llm_deliberation import (
                deliberate_with_llm,
            )

            result = await deliberate_with_llm(
                "RSI question",
                agents=["deepseek"],
                use_memory=True,
                enrich_with_perplexity=False,
            )

        mock_recall.assert_awaited_once()
        mock_store.assert_awaited_once()
        assert result.metadata.get("memory_id") == "mem_id_123"

    @pytest.mark.asyncio
    async def test_use_memory_false_skips_recall_and_store(self):
        """deliberate_with_llm with use_memory=False does not touch memory."""
        mock_recall = AsyncMock()
        mock_store = AsyncMock()

        mock_delib = MagicMock()
        mock_delib._clients = {"deepseek": MagicMock()}
        mock_delib.clear_session = MagicMock()
        mock_delib.recall_for_deliberation = mock_recall
        mock_delib.store_deliberation_result = mock_store
        mock_delib.cross_validate = MagicMock(return_value=None)

        mock_result = MagicMock()
        mock_result.metadata = {"agents": ["deepseek"]}
        mock_delib.deliberate = AsyncMock(return_value=mock_result)

        with patch(
            "backend.agents.consensus.real_llm_deliberation.get_real_deliberation",
            return_value=mock_delib,
        ):
            from backend.agents.consensus.real_llm_deliberation import (
                deliberate_with_llm,
            )

            await deliberate_with_llm(
                "RSI question",
                agents=["deepseek"],
                use_memory=False,
                enrich_with_perplexity=False,
            )

        mock_recall.assert_not_awaited()
        mock_store.assert_not_awaited()


# ── E2E: 2 Rounds Reuse ──────────────────────────────────────────────


class TestTwoRoundsReuse:
    @pytest.mark.asyncio
    async def test_second_recall_finds_first_result(self, mock_delib):
        """After storing a result, subsequent recall finds it."""
        mem = HierarchicalMemory()

        with patch(
            "backend.agents.mcp.tools.memory.get_global_memory",
            return_value=mem,
        ):
            # First round: store a deliberation result
            result = DeliberationResult(
                id="delib_round1",
                question="Best RSI period for BTC?",
                decision="RSI(21) optimal for BTCUSDT",
                confidence=0.85,
                voting_strategy=VotingStrategy.WEIGHTED,
                rounds=[],
                final_votes=[],
                dissenting_opinions=[],
                evidence_chain=[],
                duration_seconds=3.0,
                metadata={"agents": ["deepseek", "qwen"]},
            )
            item_id = await mock_delib.store_deliberation_result(result)
            assert item_id is not None

            # Second round: recall should find the prior result
            context = await mock_delib.recall_for_deliberation("What RSI period should we use for BTC?")

        assert context is not None
        assert "RSI" in context
        assert "21" in context
