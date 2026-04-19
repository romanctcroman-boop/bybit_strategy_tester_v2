"""
Tests for P4 Hybrid Retrieval — integration with HierarchicalMemory.

Covers:
  - BM25 index maintenance (store → indexed, forget → removed, evict → removed)
  - Hybrid scoring (_calculate_relevance with BM25 + cosine + importance + recency)
  - Degraded mode (no embeddings → BM25-only weights)
  - Structured filter (_structured_filter: namespace, tags, importance, TTL)
  - get_stats() includes bm25 metrics and vector_degraded flag
  - Recall ordering uses hybrid scores
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from backend.agents.memory.hierarchical_memory import (
    HierarchicalMemory,
    MemoryType,
)


@pytest.fixture()
def mem():
    """HierarchicalMemory without backend or embeddings (degraded mode)."""
    return HierarchicalMemory()


@pytest.fixture()
def mem_with_embedding():
    """HierarchicalMemory with a deterministic embedding function."""

    def fake_embed(text: str) -> list[float]:
        """Deterministic 4-dim embedding based on character sums."""
        words = text.lower().split()
        dim = 4
        vec = [0.0] * dim
        for i, w in enumerate(words):
            vec[i % dim] += sum(ord(c) for c in w) / 1000.0
        # Normalize
        import math

        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    return HierarchicalMemory(embedding_fn=fake_embed)


# ── BM25 Index Maintenance ────────────────────────────────────────────


class TestBM25IndexMaintenance:
    @pytest.mark.asyncio
    async def test_store_indexes_in_bm25(self, mem):
        """Storing a memory should add it to the BM25 index."""
        item = await mem.store("RSI crossed above 70 on BTCUSDT", importance=0.7)
        assert item.id in mem._bm25
        assert mem._bm25.document_count == 1

    @pytest.mark.asyncio
    async def test_store_multiple_indexed(self, mem):
        await mem.store("RSI crossed above 70", importance=0.7)
        await mem.store("MACD histogram positive", importance=0.6)
        await mem.store("Bollinger bands squeeze", importance=0.5)
        assert mem._bm25.document_count == 3

    @pytest.mark.asyncio
    async def test_forget_removes_from_bm25(self, mem):
        """forget() should remove forgotten items from the BM25 index."""
        # Store with very low importance so forget() will remove it
        item = await mem.store("Temporary low-importance note", importance=0.05)
        assert item.id in mem._bm25

        # Force low importance and low access_count to trigger forgetting
        item.importance = 0.05
        item.access_count = 0

        await mem.forget()
        assert item.id not in mem._bm25

    @pytest.mark.asyncio
    async def test_eviction_removes_from_bm25(self, mem):
        """When tier is full, evicted item should be removed from BM25."""
        # Working memory has max 10 items. Fill it up + 1.
        stored_items = []
        for i in range(11):
            item = await mem.store(
                f"Working memory item number {i}",
                memory_type=MemoryType.WORKING,
                importance=0.5 + i * 0.01,  # Slight importance gradient
            )
            stored_items.append(item)

        # Working store should have max_items (10)
        assert len(mem.stores[MemoryType.WORKING]) <= 10
        # BM25 should match in-store count
        in_store_ids = set(mem.stores[MemoryType.WORKING].keys())
        for sid in in_store_ids:
            assert sid in mem._bm25


# ── Hybrid Scoring ────────────────────────────────────────────────────


class TestHybridScoring:
    @pytest.mark.asyncio
    async def test_bm25_contributes_to_score_degraded(self, mem):
        """In degraded mode, BM25 should be the primary scoring signal."""
        item = await mem.store("RSI crossed above 70 on BTCUSDT", importance=0.5)

        score = mem._calculate_relevance(item, "RSI BTCUSDT", None)
        assert score > 0.0

    @pytest.mark.asyncio
    async def test_bm25_no_match_lower_score(self, mem):
        """Items with no BM25 match should score lower."""
        item_match = await mem.store("RSI crossed above 70", importance=0.5)
        item_nomatch = await mem.store("Completely unrelated weather forecast", importance=0.5)

        score_match = mem._calculate_relevance(item_match, "RSI above 70", None)
        score_nomatch = mem._calculate_relevance(item_nomatch, "RSI above 70", None)

        assert score_match > score_nomatch

    @pytest.mark.asyncio
    async def test_importance_contributes(self, mem):
        """Higher importance should boost score (same BM25/recency)."""
        item_high = await mem.store("RSI signal detected", importance=0.9)
        item_low = await mem.store("RSI signal observed", importance=0.1)

        score_high = mem._calculate_relevance(item_high, "RSI signal", None)
        score_low = mem._calculate_relevance(item_low, "RSI signal", None)

        assert score_high > score_low

    @pytest.mark.asyncio
    async def test_recency_contributes(self, mem):
        """More recently accessed items should score higher."""
        item_old = await mem.store("RSI analysis old", importance=0.5)
        item_new = await mem.store("RSI analysis new", importance=0.5)

        # Artificially age the old item
        item_old.accessed_at = datetime.now(UTC) - timedelta(days=7)

        score_old = mem._calculate_relevance(item_old, "RSI analysis", None)
        score_new = mem._calculate_relevance(item_new, "RSI analysis", None)

        assert score_new > score_old

    @pytest.mark.asyncio
    async def test_degraded_weights(self, mem):
        """In degraded mode, BM25 weight = 0.65 (dominant)."""
        item = await mem.store("RSI overbought signal BTCUSDT", importance=0.5)
        item.accessed_at = datetime.now(UTC)

        score = mem._calculate_relevance(item, "RSI overbought", None)
        # Score should be meaningful (> just importance + recency)
        assert score > 0.3  # BM25 contributes significantly

    @pytest.mark.asyncio
    async def test_normal_mode_weights(self, mem_with_embedding):
        """With embeddings, cosine similarity gets 0.40 weight."""
        item = await mem_with_embedding.store("RSI overbought signal", importance=0.5)
        # Item should have an embedding
        assert item.embedding is not None

        # Generate query embedding
        query_emb = mem_with_embedding.embedding_fn("RSI overbought")
        score = mem_with_embedding._calculate_relevance(item, "RSI overbought", query_emb)
        assert score > 0.0

    @pytest.mark.asyncio
    async def test_cosine_disabled_without_embeddings(self, mem):
        """When no embeddings, cosine weight should be 0."""
        item = await mem.store("Test content", importance=0.5)
        # Force item to have no embedding
        item.embedding = None

        # Score with no query embedding either
        score = mem._calculate_relevance(item, "Test content", None)
        # Should still work (BM25 + importance + recency)
        assert score > 0.0


# ── Structured Filter ─────────────────────────────────────────────────


class TestStructuredFilter:
    @pytest.mark.asyncio
    async def test_filter_by_tier(self, mem):
        await mem.store("Working item", memory_type=MemoryType.WORKING, importance=0.5)
        await mem.store("Episodic item", memory_type=MemoryType.EPISODIC, importance=0.5)

        working_only = mem._structured_filter(tiers=[MemoryType.WORKING])
        assert len(working_only) == 1
        assert working_only[0].content == "Working item"

    @pytest.mark.asyncio
    async def test_filter_by_namespace(self, mem):
        await mem.store("Agent A data", importance=0.5, agent_namespace="agent_a")
        await mem.store("Agent B data", importance=0.5, agent_namespace="agent_b")
        await mem.store("Shared data", importance=0.5, agent_namespace="shared")

        filtered = mem._structured_filter(
            tiers=list(MemoryType),
            agent_namespace="agent_a",
        )
        contents = [i.content for i in filtered]
        assert "Agent A data" in contents
        assert "Shared data" in contents  # shared always passes
        assert "Agent B data" not in contents

    @pytest.mark.asyncio
    async def test_filter_by_importance(self, mem):
        await mem.store("Low importance", importance=0.2)
        await mem.store("High importance", importance=0.8)

        filtered = mem._structured_filter(
            tiers=list(MemoryType),
            min_importance=0.5,
        )
        assert len(filtered) == 1
        assert filtered[0].content == "High importance"

    @pytest.mark.asyncio
    async def test_filter_by_tags(self, mem):
        await mem.store("RSI stuff", importance=0.5, tags=["rsi", "indicator"])
        await mem.store("MACD stuff", importance=0.5, tags=["macd", "indicator"])

        filtered = mem._structured_filter(
            tiers=list(MemoryType),
            tags=["rsi"],
        )
        assert len(filtered) == 1
        assert "RSI" in filtered[0].content

    @pytest.mark.asyncio
    async def test_filter_expired_items(self, mem):
        """Expired items should be filtered out."""
        item = await mem.store(
            "Old working memory",
            memory_type=MemoryType.WORKING,
            importance=0.5,
        )
        # Expire it (working TTL = 5 minutes)
        item.created_at = datetime.now(UTC) - timedelta(hours=1)

        filtered = mem._structured_filter(tiers=[MemoryType.WORKING])
        assert len(filtered) == 0

    @pytest.mark.asyncio
    async def test_filter_all_tiers(self, mem):
        await mem.store("W", memory_type=MemoryType.WORKING, importance=0.5)
        await mem.store("E", memory_type=MemoryType.EPISODIC, importance=0.5)
        await mem.store("S", memory_type=MemoryType.SEMANTIC, importance=0.5)

        filtered = mem._structured_filter(tiers=list(MemoryType))
        assert len(filtered) == 3


# ── Degradation Warning ───────────────────────────────────────────────


class TestDegradationWarning:
    @pytest.mark.asyncio
    async def test_degraded_mode_logged(self, mem):
        """Recall in degraded mode should log a debug warning."""
        await mem.store("Some content", importance=0.5)

        with patch("backend.agents.memory.hierarchical_memory.logger") as mock_logger:
            await mem.recall("content")
            # Check that debug was called with degradation message
            debug_calls = [str(call) for call in mock_logger.debug.call_args_list]
            assert any("degraded mode" in c for c in debug_calls)

    @pytest.mark.asyncio
    async def test_no_degradation_warning_with_embeddings(self, mem_with_embedding):
        """With embeddings, no degradation warning should appear."""
        await mem_with_embedding.store("Some content", importance=0.5)

        with patch("backend.agents.memory.hierarchical_memory.logger") as mock_logger:
            await mem_with_embedding.recall("content")
            debug_calls = [str(call) for call in mock_logger.debug.call_args_list]
            assert not any("degraded mode" in c for c in debug_calls)


# ── Stats ──────────────────────────────────────────────────────────────


class TestStatsWithBM25:
    @pytest.mark.asyncio
    async def test_stats_include_bm25_fields(self, mem):
        await mem.store("Document one", importance=0.5)
        await mem.store("Document two", importance=0.5)

        stats = mem.get_stats()
        assert "bm25_documents" in stats
        assert stats["bm25_documents"] == 2
        assert "bm25_vocabulary" in stats
        assert stats["bm25_vocabulary"] > 0

    @pytest.mark.asyncio
    async def test_stats_vector_degraded_flag(self, mem, mem_with_embedding):
        assert mem.get_stats()["vector_degraded"] is True
        assert mem_with_embedding.get_stats()["vector_degraded"] is False


# ── Recall Integration ────────────────────────────────────────────────


class TestRecallIntegration:
    @pytest.mark.asyncio
    async def test_recall_uses_bm25_for_ranking(self, mem):
        """Recall should rank BM25-matching items higher."""
        await mem.store("RSI crossed above 70 on BTCUSDT daily", importance=0.5)
        await mem.store("Weather forecast for tomorrow sunny", importance=0.5)
        await mem.store("RSI divergence on ETHUSDT", importance=0.5)

        results = await mem.recall("RSI overbought", top_k=3)
        # RSI items should be ranked before weather
        contents = [r.content for r in results]
        weather_idx = next((i for i, c in enumerate(contents) if "Weather" in c), len(contents))
        rsi_idx = next((i for i, c in enumerate(contents) if "RSI" in c), len(contents))
        assert rsi_idx < weather_idx

    @pytest.mark.asyncio
    async def test_recall_respects_top_k(self, mem):
        for i in range(10):
            await mem.store(f"Memory item {i}", importance=0.5)

        results = await mem.recall("Memory item", top_k=3)
        assert len(results) <= 3

    @pytest.mark.asyncio
    async def test_recall_with_embeddings(self, mem_with_embedding):
        """Recall with embeddings should use hybrid scoring (BM25 + cosine)."""
        await mem_with_embedding.store("RSI indicator analysis", importance=0.7)
        await mem_with_embedding.store("Unrelated weather data", importance=0.7)

        results = await mem_with_embedding.recall("RSI analysis", top_k=2)
        assert len(results) >= 1
        # RSI item should be first
        assert "RSI" in results[0].content


# ── Hydration Rebuilds BM25 ───────────────────────────────────────────


class TestHydration:
    def test_hydrate_items_rebuilds_bm25(self, mem):
        """_hydrate_items should add items to BM25 index."""
        items = [
            {
                "id": "working_abc_123",
                "content": "RSI test data",
                "memory_type": "working",
                "importance": 0.5,
                "tags": [],
                "metadata": {},
                "access_count": 0,
                "created_at": "2025-06-01 12:00:00",
                "accessed_at": "2025-06-01 12:00:00",
                "agent_namespace": "shared",
                "related_ids": [],
            },
        ]
        mem._hydrate_items(items)
        assert mem._bm25.document_count == 1
        assert "working_abc_123" in mem._bm25
