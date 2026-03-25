"""
Tests for HierarchicalMemory system.

Covers:
- MemoryItem creation, serialization, expiration
- HierarchicalMemory store/recall/get/delete
- Memory consolidation (working → episodic → semantic)
- Intelligent forgetting with TTL and importance decay
- Capacity-based eviction
- Persistence to disk (save/load)
- MemoryConsolidator background task
- Statistics tracking
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from backend.agents.memory.hierarchical_memory import (
    HierarchicalMemory,
    MemoryConsolidator,
    MemoryItem,
    MemoryTier,
    MemoryType,
)

# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def memory():
    """In-memory only HierarchicalMemory"""
    return HierarchicalMemory()


@pytest.fixture
def tmp_persist_dir(tmp_path):
    """Temporary directory for persistence tests"""
    return str(tmp_path / "test_memory")


@pytest.fixture
def persistent_memory(tmp_persist_dir):
    """HierarchicalMemory with disk persistence"""
    return HierarchicalMemory(persist_path=tmp_persist_dir)


@pytest.fixture
def dummy_embedding_fn():
    """Simple embedding function for testing"""

    def embed(text: str) -> list[float]:
        # Generate a deterministic 3-element embedding from text hash
        h = hash(text)
        return [
            (h % 100) / 100.0,
            ((h >> 8) % 100) / 100.0,
            ((h >> 16) % 100) / 100.0,
        ]

    return embed


@pytest.fixture
def memory_with_embedding(dummy_embedding_fn):
    """HierarchicalMemory with embedding function"""
    return HierarchicalMemory(embedding_fn=dummy_embedding_fn)


@pytest.fixture
def sample_memory_item():
    """Pre-built MemoryItem for tests"""
    return MemoryItem(
        id="test_item_001",
        content="RSI indicator shows oversold condition at 28",
        memory_type=MemoryType.WORKING,
        importance=0.7,
        tags=["trading", "rsi", "oversold"],
        metadata={"symbol": "BTCUSDT", "timeframe": "15m"},
        source="strategy_analyzer",
    )


# ═══════════════════════════════════════════════════════════════════
# MemoryItem
# ═══════════════════════════════════════════════════════════════════


class TestMemoryItem:
    """Unit tests for MemoryItem dataclass"""

    def test_creation_with_defaults(self):
        """Test creating MemoryItem with minimal fields"""
        item = MemoryItem(
            id="test_1",
            content="Hello world",
            memory_type=MemoryType.WORKING,
        )
        assert item.id == "test_1"
        assert item.content == "Hello world"
        assert item.memory_type == MemoryType.WORKING
        assert item.access_count == 0
        assert item.importance == 0.5
        assert item.embedding is None
        assert item.tags == []
        assert item.metadata == {}
        assert item.source is None
        assert item.related_ids == []

    def test_to_dict_roundtrip(self, sample_memory_item):
        """Test serialization to dict and back"""
        data = sample_memory_item.to_dict()

        assert data["id"] == "test_item_001"
        assert data["content"] == "RSI indicator shows oversold condition at 28"
        assert data["memory_type"] == "working"
        assert data["importance"] == 0.7
        assert "trading" in data["tags"]
        assert data["metadata"]["symbol"] == "BTCUSDT"

        # Roundtrip
        restored = MemoryItem.from_dict(data)
        assert restored.id == sample_memory_item.id
        assert restored.content == sample_memory_item.content
        assert restored.memory_type == sample_memory_item.memory_type
        assert restored.importance == sample_memory_item.importance

    def test_is_expired_within_ttl(self, sample_memory_item):
        """Test item is NOT expired within TTL"""
        ttl = timedelta(hours=1)
        assert not sample_memory_item.is_expired(ttl)

    def test_is_expired_after_ttl(self):
        """Test item IS expired after TTL"""
        item = MemoryItem(
            id="old",
            content="old data",
            memory_type=MemoryType.WORKING,
            created_at=datetime.now(UTC) - timedelta(hours=2),
        )
        ttl = timedelta(hours=1)
        assert item.is_expired(ttl)

    def test_update_access_increments_count(self, sample_memory_item):
        """Test that update_access increments count and importance"""
        old_count = sample_memory_item.access_count
        old_importance = sample_memory_item.importance

        sample_memory_item.update_access()

        assert sample_memory_item.access_count == old_count + 1
        assert sample_memory_item.importance >= old_importance

    def test_update_access_caps_importance_at_1(self):
        """Test that importance doesn't exceed 1.0"""
        item = MemoryItem(
            id="high_imp",
            content="Important",
            memory_type=MemoryType.SEMANTIC,
            importance=0.995,
        )
        item.update_access()
        assert item.importance <= 1.0


# ═══════════════════════════════════════════════════════════════════
# MemoryTier
# ═══════════════════════════════════════════════════════════════════


class TestMemoryTier:
    """Tests for MemoryTier configuration"""

    def test_tier_creation(self):
        """Test creating a memory tier"""
        tier = MemoryTier(
            name="Working Memory",
            memory_type=MemoryType.WORKING,
            max_items=10,
            ttl=timedelta(minutes=5),
            priority=1,
            consolidation_threshold=0.7,
        )
        assert tier.name == "Working Memory"
        assert tier.max_items == 10
        assert tier.priority == 1

    def test_default_consolidation_threshold(self):
        """Test default consolidation threshold"""
        tier = MemoryTier(
            name="Test",
            memory_type=MemoryType.EPISODIC,
            max_items=100,
            ttl=timedelta(days=7),
            priority=2,
        )
        assert tier.consolidation_threshold == 0.5


# ═══════════════════════════════════════════════════════════════════
# HierarchicalMemory — Store
# ═══════════════════════════════════════════════════════════════════


class TestHierarchicalMemoryStore:
    """Tests for storing memories"""

    @pytest.mark.asyncio
    async def test_store_working_memory(self, memory):
        """Test storing to working memory"""
        item = await memory.store(
            content="BTC is trending up",
            memory_type=MemoryType.WORKING,
            importance=0.8,
            tags=["btc", "trend"],
        )
        assert item.id is not None
        assert item.content == "BTC is trending up"
        assert item.memory_type == MemoryType.WORKING
        assert item.importance == 0.8
        assert "btc" in item.tags

    @pytest.mark.asyncio
    async def test_store_increments_stats(self, memory):
        """Test that store increments total_stored stat"""
        assert memory.stats["total_stored"] == 0

        await memory.store(content="test 1", memory_type=MemoryType.WORKING)
        assert memory.stats["total_stored"] == 1

        await memory.store(content="test 2", memory_type=MemoryType.EPISODIC)
        assert memory.stats["total_stored"] == 2

    @pytest.mark.asyncio
    async def test_store_clamps_importance(self, memory):
        """Test that importance is clamped to [0, 1]"""
        item1 = await memory.store(content="high", importance=2.0)
        assert item1.importance == 1.0

        item2 = await memory.store(content="low", importance=-0.5)
        assert item2.importance == 0.0

    @pytest.mark.asyncio
    async def test_store_with_embedding(self, memory_with_embedding):
        """Test storing with embedding function"""
        item = await memory_with_embedding.store(
            content="RSI is below 30",
            memory_type=MemoryType.SEMANTIC,
        )
        assert item.embedding is not None
        assert len(item.embedding) == 3  # dummy embedding is 3-element

    @pytest.mark.asyncio
    async def test_store_with_metadata_and_source(self, memory):
        """Test storing with metadata and source"""
        item = await memory.store(
            content="Market analysis",
            metadata={"symbol": "ETHUSDT"},
            source="market_analyzer",
        )
        assert item.metadata["symbol"] == "ETHUSDT"
        assert item.source == "market_analyzer"

    @pytest.mark.asyncio
    async def test_store_evicts_on_capacity(self, memory):
        """Test that low-importance items get evicted when at capacity"""
        # Working memory max is 10
        for i in range(10):
            await memory.store(
                content=f"Item {i}",
                memory_type=MemoryType.WORKING,
                importance=0.5,
            )
        assert len(memory.stores[MemoryType.WORKING]) == 10

        # Store 11th item — should evict one
        await memory.store(
            content="Item 10 (overflow)",
            memory_type=MemoryType.WORKING,
            importance=0.9,
        )
        assert len(memory.stores[MemoryType.WORKING]) == 10

    @pytest.mark.asyncio
    async def test_store_all_memory_types(self, memory):
        """Test storing to all four memory types"""
        for mem_type in MemoryType:
            item = await memory.store(
                content=f"Content for {mem_type.value}",
                memory_type=mem_type,
            )
            assert item.memory_type == mem_type
            assert len(memory.stores[mem_type]) == 1


# ═══════════════════════════════════════════════════════════════════
# HierarchicalMemory — Recall
# ═══════════════════════════════════════════════════════════════════


class TestHierarchicalMemoryRecall:
    """Tests for recalling memories"""

    @pytest.mark.asyncio
    async def test_recall_by_keyword(self, memory):
        """Test keyword-based recall"""
        await memory.store(content="RSI is at 25, oversold", memory_type=MemoryType.SEMANTIC)
        await memory.store(content="MACD crossover detected", memory_type=MemoryType.SEMANTIC)
        await memory.store(content="Volume spike on BTC", memory_type=MemoryType.SEMANTIC)

        results = await memory.recall(query="RSI oversold", use_semantic=False)
        assert len(results) > 0
        # The RSI item should have the highest relevance
        assert "RSI" in results[0].content

    @pytest.mark.asyncio
    async def test_recall_updates_access(self, memory):
        """Test that recalled items get their access updated"""
        item = await memory.store(content="Important fact", memory_type=MemoryType.SEMANTIC)
        original_count = item.access_count

        results = await memory.recall(query="Important fact", use_semantic=False)
        assert len(results) > 0
        assert results[0].access_count > original_count

    @pytest.mark.asyncio
    async def test_recall_filters_by_memory_type(self, memory):
        """Test filtering recall by memory type"""
        await memory.store(content="Working data", memory_type=MemoryType.WORKING)
        await memory.store(content="Episodic event", memory_type=MemoryType.EPISODIC)

        working_only = await memory.recall(
            query="data event",
            memory_type=MemoryType.WORKING,
            use_semantic=False,
        )
        # Only working memory items
        for item in working_only:
            assert item.memory_type == MemoryType.WORKING

    @pytest.mark.asyncio
    async def test_recall_filters_by_min_importance(self, memory):
        """Test filtering by minimum importance"""
        await memory.store(content="Low importance", importance=0.1)
        await memory.store(content="High importance", importance=0.9)

        results = await memory.recall(
            query="importance",
            min_importance=0.5,
            use_semantic=False,
        )
        for item in results:
            assert item.importance >= 0.5

    @pytest.mark.asyncio
    async def test_recall_filters_by_tags(self, memory):
        """Test filtering by tags"""
        await memory.store(content="RSI analysis", tags=["rsi", "indicator"])
        await memory.store(content="Volume analysis", tags=["volume"])

        results = await memory.recall(
            query="analysis",
            tags=["rsi"],
            use_semantic=False,
        )
        assert len(results) >= 1
        assert all("rsi" in item.tags for item in results)

    @pytest.mark.asyncio
    async def test_recall_top_k_limit(self, memory):
        """Test that recall respects top_k"""
        for i in range(10):
            await memory.store(
                content=f"Memory item {i} about trading",
                memory_type=MemoryType.SEMANTIC,
            )

        results = await memory.recall(query="trading", top_k=3, use_semantic=False)
        assert len(results) <= 3

    @pytest.mark.asyncio
    async def test_recall_empty_store(self, memory):
        """Test recall on empty store returns empty list"""
        results = await memory.recall(query="anything")
        assert results == []

    @pytest.mark.asyncio
    async def test_recall_with_semantic_search(self, memory_with_embedding):
        """Test recall with embedding-based semantic search"""
        await memory_with_embedding.store(
            content="RSI indicates oversold",
            memory_type=MemoryType.SEMANTIC,
        )
        await memory_with_embedding.store(
            content="Volume is above average",
            memory_type=MemoryType.SEMANTIC,
        )

        results = await memory_with_embedding.recall(
            query="RSI oversold signal",
            use_semantic=True,
        )
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_recall_skips_expired_items(self, memory):
        """Test that expired items are skipped in recall"""
        # Manually create an expired item in working memory
        expired_item = MemoryItem(
            id="expired_1",
            content="Old data about trading",
            memory_type=MemoryType.WORKING,
            created_at=datetime.now(UTC) - timedelta(hours=1),  # Working TTL is 5 min
            importance=0.9,
        )
        memory.stores[MemoryType.WORKING]["expired_1"] = expired_item

        results = await memory.recall(
            query="trading",
            memory_type=MemoryType.WORKING,
            use_semantic=False,
        )
        assert all(r.id != "expired_1" for r in results)

    @pytest.mark.asyncio
    async def test_recall_increments_stats(self, memory):
        """Test that recall increments total_recalled stat"""
        await memory.store(content="Test data", memory_type=MemoryType.SEMANTIC)
        assert memory.stats["total_recalled"] == 0

        await memory.recall(query="Test", use_semantic=False)
        assert memory.stats["total_recalled"] > 0


# ═══════════════════════════════════════════════════════════════════
# HierarchicalMemory — Get / Delete
# ═══════════════════════════════════════════════════════════════════


class TestHierarchicalMemoryGetDelete:
    """Tests for get and delete operations"""

    @pytest.mark.asyncio
    async def test_get_existing_item(self, memory):
        """Test getting an item by ID"""
        stored = await memory.store(content="Findable", memory_type=MemoryType.EPISODIC)

        found = await memory.get(stored.id)
        assert found is not None
        assert found.content == "Findable"

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self, memory):
        """Test getting a non-existent item returns None"""
        result = await memory.get("nonexistent_id")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_existing_item(self, memory):
        """Test deleting an item"""
        stored = await memory.store(content="Deletable", memory_type=MemoryType.WORKING)

        deleted = await memory.delete(stored.id)
        assert deleted is True

        # Should not be found anymore
        found = await memory.get(stored.id)
        assert found is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_false(self, memory):
        """Test deleting a non-existent item returns False"""
        result = await memory.delete("nonexistent_id")
        assert result is False


# ═══════════════════════════════════════════════════════════════════
# HierarchicalMemory — Consolidation
# ═══════════════════════════════════════════════════════════════════


class TestHierarchicalMemoryConsolidation:
    """Tests for memory consolidation"""

    @pytest.mark.asyncio
    async def test_consolidate_working_to_episodic(self, memory):
        """Test that high-importance working memories consolidate to episodic"""
        # Store items with high importance (above threshold 0.7)
        await memory.store(
            content="Important signal detected",
            memory_type=MemoryType.WORKING,
            importance=0.9,
        )

        working_count_before = len(memory.stores[MemoryType.WORKING])
        assert working_count_before == 1

        result = await memory.consolidate()
        assert result["working_to_episodic"] >= 1

        # Working memory should be emptied
        assert len(memory.stores[MemoryType.WORKING]) == 0
        # Episodic should have the consolidated item
        assert len(memory.stores[MemoryType.EPISODIC]) >= 1

    @pytest.mark.asyncio
    async def test_consolidate_keeps_low_importance_in_working(self, memory):
        """Test that low-importance items stay in working memory"""
        await memory.store(
            content="Low importance item",
            memory_type=MemoryType.WORKING,
            importance=0.3,  # Below threshold 0.7
        )

        result = await memory.consolidate()
        assert result["working_to_episodic"] == 0
        assert len(memory.stores[MemoryType.WORKING]) == 1

    @pytest.mark.asyncio
    async def test_consolidate_episodic_to_semantic(self, memory):
        """Test pattern extraction from episodic to semantic"""
        # Store 3+ items with same tag (needed for pattern extraction)
        for i in range(4):
            await memory.store(
                content=f"RSI was oversold on day {i}",
                memory_type=MemoryType.EPISODIC,
                importance=0.8,  # Above threshold 0.6
                tags=["rsi_pattern"],
            )

        result = await memory.consolidate()
        assert result["episodic_to_semantic"] >= 1

    @pytest.mark.asyncio
    async def test_consolidate_increments_stats(self, memory):
        """Test that consolidation increments stats"""
        assert memory.stats["consolidations"] == 0

        await memory.consolidate()
        assert memory.stats["consolidations"] == 1


# ═══════════════════════════════════════════════════════════════════
# HierarchicalMemory — Forgetting
# ═══════════════════════════════════════════════════════════════════


class TestHierarchicalMemoryForgetting:
    """Tests for intelligent forgetting"""

    @pytest.mark.asyncio
    async def test_forget_expired_items(self, memory):
        """Test that expired items are forgotten"""
        # Manually add an expired working memory item
        expired_item = MemoryItem(
            id="expired_work",
            content="Old working memory",
            memory_type=MemoryType.WORKING,
            created_at=datetime.now(UTC) - timedelta(hours=1),
        )
        memory.stores[MemoryType.WORKING]["expired_work"] = expired_item

        result = await memory.forget()
        assert result["working"] >= 1
        assert "expired_work" not in memory.stores[MemoryType.WORKING]

    @pytest.mark.asyncio
    async def test_forget_low_importance_items(self, memory):
        """Test that very low importance items get forgotten"""
        low_imp = MemoryItem(
            id="low_imp",
            content="Irrelevant data",
            memory_type=MemoryType.EPISODIC,
            importance=0.05,
            access_count=0,
            created_at=datetime.now(UTC) - timedelta(hours=12),
            accessed_at=datetime.now(UTC) - timedelta(hours=12),
        )
        memory.stores[MemoryType.EPISODIC]["low_imp"] = low_imp

        result = await memory.forget()
        assert result["episodic"] >= 1

    @pytest.mark.asyncio
    async def test_forget_increments_stats(self, memory):
        """Test that forgetting increments stats"""
        expired = MemoryItem(
            id="exp",
            content="Expired",
            memory_type=MemoryType.WORKING,
            created_at=datetime.now(UTC) - timedelta(hours=1),
        )
        memory.stores[MemoryType.WORKING]["exp"] = expired

        await memory.forget()
        assert memory.stats["forgettings"] > 0

    @pytest.mark.asyncio
    async def test_forget_preserves_important_items(self, memory):
        """Test that important items are NOT forgotten"""
        important = await memory.store(
            content="Critical trading signal",
            memory_type=MemoryType.SEMANTIC,
            importance=0.95,
        )

        await memory.forget()
        found = await memory.get(important.id)
        assert found is not None


# ═══════════════════════════════════════════════════════════════════
# HierarchicalMemory — Persistence
# ═══════════════════════════════════════════════════════════════════


class TestHierarchicalMemoryPersistence:
    """Tests for disk persistence"""

    @pytest.mark.asyncio
    async def test_persist_and_load(self, tmp_persist_dir):
        """Test that stored items persist to disk and can be reloaded"""
        # Store with persistence
        mem1 = HierarchicalMemory(persist_path=tmp_persist_dir)
        item = await mem1.store(
            content="Persistent memory",
            memory_type=MemoryType.SEMANTIC,
            importance=0.8,
            tags=["persistent"],
        )

        # Create new instance from same path
        mem2 = HierarchicalMemory(persist_path=tmp_persist_dir)

        # Should find the persisted item
        found = await mem2.get(item.id)
        assert found is not None
        assert found.content == "Persistent memory"
        # importance may increase by 0.01 per access() call
        assert abs(found.importance - 0.8) <= 0.02

    @pytest.mark.asyncio
    async def test_delete_removes_from_disk(self, tmp_persist_dir):
        """Test that delete removes the file from disk"""
        mem = HierarchicalMemory(persist_path=tmp_persist_dir)
        item = await mem.store(
            content="Will be deleted",
            memory_type=MemoryType.EPISODIC,
        )

        # File should exist
        file_path = Path(tmp_persist_dir) / "episodic" / f"{item.id}.json"
        assert file_path.exists()

        await mem.delete(item.id)
        assert not file_path.exists()

    @pytest.mark.asyncio
    async def test_persist_multiple_types(self, tmp_persist_dir):
        """Test persisting across multiple memory types"""
        mem = HierarchicalMemory(persist_path=tmp_persist_dir)

        await mem.store(content="Working", memory_type=MemoryType.WORKING)
        await mem.store(content="Episodic", memory_type=MemoryType.EPISODIC)
        await mem.store(content="Semantic", memory_type=MemoryType.SEMANTIC)
        await mem.store(content="Procedural", memory_type=MemoryType.PROCEDURAL)

        # Reload
        mem2 = HierarchicalMemory(persist_path=tmp_persist_dir)
        total = sum(len(store) for store in mem2.stores.values())
        assert total == 4


# ═══════════════════════════════════════════════════════════════════
# HierarchicalMemory — Cosine Similarity & Relevance
# ═══════════════════════════════════════════════════════════════════


class TestHierarchicalMemoryRelevance:
    """Tests for relevance calculation helpers"""

    def test_cosine_similarity_identical(self):
        """Test cosine similarity of identical vectors"""
        sim = HierarchicalMemory._cosine_similarity([1, 0, 0], [1, 0, 0])
        assert abs(sim - 1.0) < 0.001

    def test_cosine_similarity_orthogonal(self):
        """Test cosine similarity of orthogonal vectors"""
        sim = HierarchicalMemory._cosine_similarity([1, 0, 0], [0, 1, 0])
        assert abs(sim) < 0.001

    def test_cosine_similarity_opposite(self):
        """Test cosine similarity of opposite vectors"""
        sim = HierarchicalMemory._cosine_similarity([1, 0], [-1, 0])
        assert abs(sim - (-1.0)) < 0.001

    def test_cosine_similarity_zero_vector(self):
        """Test cosine similarity with zero vector"""
        sim = HierarchicalMemory._cosine_similarity([0, 0, 0], [1, 2, 3])
        assert sim == 0.0

    def test_cosine_similarity_different_lengths(self):
        """Test cosine similarity with different length vectors"""
        sim = HierarchicalMemory._cosine_similarity([1, 2], [1, 2, 3])
        assert sim == 0.0


# ═══════════════════════════════════════════════════════════════════
# HierarchicalMemory — Statistics
# ═══════════════════════════════════════════════════════════════════


class TestHierarchicalMemoryStats:
    """Tests for statistics reporting"""

    @pytest.mark.asyncio
    async def test_get_stats_initial(self, memory):
        """Test initial stats"""
        stats = memory.get_stats()
        assert stats["total_stored"] == 0
        assert stats["total_recalled"] == 0
        assert stats["consolidations"] == 0
        assert stats["forgettings"] == 0
        assert "tiers" in stats

    @pytest.mark.asyncio
    async def test_get_stats_after_operations(self, memory):
        """Test stats after various operations"""
        await memory.store(content="item 1", memory_type=MemoryType.WORKING)
        await memory.store(content="item 2", memory_type=MemoryType.SEMANTIC)
        await memory.recall(query="item", use_semantic=False)

        stats = memory.get_stats()
        assert stats["total_stored"] == 2
        assert stats["total_recalled"] > 0
        assert stats["tiers"]["working"]["count"] == 1
        assert stats["tiers"]["semantic"]["count"] == 1

    @pytest.mark.asyncio
    async def test_tier_utilization(self, memory):
        """Test tier utilization calculation"""
        for i in range(5):
            await memory.store(
                content=f"Working item {i}",
                memory_type=MemoryType.WORKING,
            )

        stats = memory.get_stats()
        # 5 items / 10 max = 0.5 utilization
        assert stats["tiers"]["working"]["utilization"] == 0.5


# ═══════════════════════════════════════════════════════════════════
# MemoryConsolidator
# ═══════════════════════════════════════════════════════════════════


class TestMemoryConsolidator:
    """Tests for background MemoryConsolidator"""

    @pytest.mark.asyncio
    async def test_consolidator_start_stop(self, memory):
        """Test starting and stopping the consolidator"""
        consolidator = MemoryConsolidator(
            memory=memory,
            consolidation_interval=timedelta(seconds=1),
            forgetting_interval=timedelta(seconds=1),
        )

        await consolidator.start()
        assert consolidator._running is True
        assert consolidator._task is not None

        await consolidator.stop()
        assert consolidator._running is False

    @pytest.mark.asyncio
    async def test_consolidator_double_start(self, memory):
        """Test that double start doesn't create duplicate tasks"""
        consolidator = MemoryConsolidator(memory=memory)

        await consolidator.start()
        task1 = consolidator._task

        await consolidator.start()  # Should be no-op
        task2 = consolidator._task

        assert task1 is task2
        await consolidator.stop()

    @pytest.mark.asyncio
    async def test_consolidator_stop_when_not_started(self, memory):
        """Test that stopping a non-started consolidator is safe"""
        consolidator = MemoryConsolidator(memory=memory)
        await consolidator.stop()  # Should not raise


# ═══════════════════════════════════════════════════════════════════
# MemoryType enum
# ═══════════════════════════════════════════════════════════════════


class TestMemoryType:
    """Tests for MemoryType enum"""

    def test_all_types_exist(self):
        """Test that all 4 memory types exist"""
        assert MemoryType.WORKING.value == "working"
        assert MemoryType.EPISODIC.value == "episodic"
        assert MemoryType.SEMANTIC.value == "semantic"
        assert MemoryType.PROCEDURAL.value == "procedural"

    def test_enum_length(self):
        """Test that there are exactly 4 memory types"""
        assert len(MemoryType) == 4
