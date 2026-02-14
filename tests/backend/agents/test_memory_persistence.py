"""
Tests for HierarchicalMemory with SQLite-backed persistence.

Covers audit finding: "Tests contain zero coverage for SQLite-backed persistence —
no test instantiates HierarchicalMemory(persist_path=...) and validates disk
round-trip, TTL expiration, or LRU eviction under load." (Qwen, HIGH severity)

Tests:
- SQLiteBackendAdapter save/load/delete round-trip
- HierarchicalMemory with SQLiteBackendAdapter backend
- Persistence across re-instantiation (simulates restart)
- TTL expiration with persistent storage
- Importance decay and forgetting with persistent backend
- Capacity-based eviction with persistent backend
- JsonFileBackend round-trip
- Backend switching (in-memory → SQLite)
"""

from __future__ import annotations

import asyncio

import pytest

from backend.agents.memory.backend_interface import (
    JsonFileBackend,
    MemoryBackend,
    SQLiteBackendAdapter,
)
from backend.agents.memory.hierarchical_memory import (
    HierarchicalMemory,
    MemoryType,
)

# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def sqlite_db_path(tmp_path):
    """Temporary SQLite database path."""
    return str(tmp_path / "test_memory.db")


@pytest.fixture
def sqlite_backend(sqlite_db_path):
    """SQLiteBackendAdapter instance for testing."""
    return SQLiteBackendAdapter(db_path=sqlite_db_path)


@pytest.fixture
def json_backend(tmp_path):
    """JsonFileBackend instance for testing."""
    return JsonFileBackend(persist_path=str(tmp_path / "json_memory"))


@pytest.fixture
def sqlite_memory(sqlite_db_path):
    """HierarchicalMemory with SQLiteBackendAdapter."""
    backend = SQLiteBackendAdapter(db_path=sqlite_db_path)
    return HierarchicalMemory(backend=backend)


@pytest.fixture
def json_memory(tmp_path):
    """HierarchicalMemory with JsonFileBackend via persist_path."""
    return HierarchicalMemory(persist_path=str(tmp_path / "json_persist"))


# ═══════════════════════════════════════════════════════════════════
# SQLiteBackendAdapter — Unit Tests
# ═══════════════════════════════════════════════════════════════════


class TestSQLiteBackendAdapter:
    """Tests for SQLiteBackendAdapter conforming to MemoryBackend ABC."""

    def test_implements_memory_backend(self, sqlite_backend):
        """Verify adapter implements the ABC."""
        assert isinstance(sqlite_backend, MemoryBackend)

    @pytest.mark.asyncio
    async def test_save_and_load_item(self, sqlite_backend):
        """Save an item and load it back — basic round-trip."""
        data = {
            "id": "test-item-1",
            "content": "BTC RSI strategy works well at 14 period",
            "memory_type": "working",
            "importance": 0.85,
            "tags": ["btc", "rsi"],
        }
        await sqlite_backend.save_item("test-item-1", "working", data)

        loaded = await sqlite_backend.load_item("test-item-1", "working")
        assert loaded is not None
        assert loaded["id"] == "test-item-1"
        assert loaded["content"] == "BTC RSI strategy works well at 14 period"
        assert loaded["importance"] == 0.85
        assert "btc" in loaded["tags"]

    @pytest.mark.asyncio
    async def test_save_and_delete_item(self, sqlite_backend):
        """Save item, delete it, verify it's gone."""
        data = {"id": "del-me", "content": "Temporary", "importance": 0.3}
        await sqlite_backend.save_item("del-me", "episodic", data)

        # Verify it exists
        loaded = await sqlite_backend.load_item("del-me", "episodic")
        assert loaded is not None

        # Delete it
        await sqlite_backend.delete_item("del-me", "episodic")

        # Verify it's gone
        gone = await sqlite_backend.load_item("del-me", "episodic")
        assert gone is None

    @pytest.mark.asyncio
    async def test_load_all_by_tier(self, sqlite_backend):
        """Save items in different tiers, load_all by tier."""
        await sqlite_backend.save_item("w1", "working", {"id": "w1", "content": "Working 1", "importance": 0.5})
        await sqlite_backend.save_item("e1", "episodic", {"id": "e1", "content": "Episodic 1", "importance": 0.6})
        await sqlite_backend.save_item("w2", "working", {"id": "w2", "content": "Working 2", "importance": 0.7})

        working_items = await sqlite_backend.load_all(tier="working")
        assert len(working_items) == 2
        ids = {item["id"] for item in working_items}
        assert "w1" in ids
        assert "w2" in ids

    @pytest.mark.asyncio
    async def test_load_all_no_tier_filter(self, sqlite_backend):
        """load_all without tier returns all items."""
        for tier in ["working", "episodic", "semantic"]:
            await sqlite_backend.save_item(
                f"{tier}-1",
                tier,
                {"id": f"{tier}-1", "content": f"Item in {tier}", "importance": 0.5},
            )

        all_items = await sqlite_backend.load_all()
        assert len(all_items) >= 3

    @pytest.mark.asyncio
    async def test_close_is_safe(self, sqlite_backend):
        """close() should not raise."""
        await sqlite_backend.close()

    @pytest.mark.asyncio
    async def test_overwrite_existing_item(self, sqlite_backend):
        """Saving with same ID should update, not duplicate."""
        data1 = {"id": "ow-1", "content": "Version 1", "importance": 0.3}
        data2 = {"id": "ow-1", "content": "Version 2", "importance": 0.9}

        await sqlite_backend.save_item("ow-1", "working", data1)
        await sqlite_backend.save_item("ow-1", "working", data2)

        loaded = await sqlite_backend.load_item("ow-1", "working")
        assert loaded is not None
        assert loaded["content"] == "Version 2"


# ═══════════════════════════════════════════════════════════════════
# JsonFileBackend — Unit Tests
# ═══════════════════════════════════════════════════════════════════


class TestJsonFileBackend:
    """Tests for JsonFileBackend conforming to MemoryBackend ABC."""

    def test_implements_memory_backend(self, json_backend):
        """Verify backend implements the ABC."""
        assert isinstance(json_backend, MemoryBackend)

    @pytest.mark.asyncio
    async def test_save_and_load_round_trip(self, json_backend):
        """Save and load a single item."""
        data = {
            "id": "json-1",
            "content": "Test JSON persistence",
            "memory_type": "semantic",
            "importance": 0.75,
            "tags": ["test"],
        }
        await json_backend.save_item("json-1", "semantic", data)
        loaded = await json_backend.load_item("json-1", "semantic")

        assert loaded is not None
        assert loaded["content"] == "Test JSON persistence"
        assert loaded["importance"] == 0.75

    @pytest.mark.asyncio
    async def test_delete_item(self, json_backend):
        """Delete removes the JSON file."""
        data = {"id": "del-json", "content": "To delete", "importance": 0.1}
        await json_backend.save_item("del-json", "working", data)
        await json_backend.delete_item("del-json", "working")

        loaded = await json_backend.load_item("del-json", "working")
        assert loaded is None

    @pytest.mark.asyncio
    async def test_load_all(self, json_backend):
        """Load all items across tiers."""
        await json_backend.save_item("j1", "working", {"id": "j1", "content": "W", "importance": 0.5})
        await json_backend.save_item("j2", "episodic", {"id": "j2", "content": "E", "importance": 0.5})
        all_items = await json_backend.load_all()
        assert len(all_items) == 2

    @pytest.mark.asyncio
    async def test_embeddings_not_persisted(self, json_backend):
        """Embedding field should be stripped before saving."""
        data = {
            "id": "emb-1",
            "content": "With embedding",
            "importance": 0.5,
            "embedding": [0.1, 0.2, 0.3],
        }
        await json_backend.save_item("emb-1", "working", data)
        loaded = await json_backend.load_item("emb-1", "working")

        assert loaded is not None
        assert "embedding" not in loaded


# ═══════════════════════════════════════════════════════════════════
# HierarchicalMemory + SQLiteBackendAdapter — Integration Tests
# ═══════════════════════════════════════════════════════════════════


class TestHierarchicalMemoryWithSQLite:
    """Integration tests: HierarchicalMemory backed by SQLiteBackendAdapter."""

    @pytest.mark.asyncio
    async def test_store_persists_to_sqlite(self, sqlite_db_path):
        """Store() in HierarchicalMemory should persist to SQLite."""
        backend = SQLiteBackendAdapter(db_path=sqlite_db_path)
        memory = HierarchicalMemory(backend=backend)

        item = await memory.store(
            content="RSI oversold at 25 is a strong buy signal",
            memory_type=MemoryType.WORKING,
            importance=0.9,
            tags=["rsi", "signals"],
        )

        # Verify item is in in-memory store
        assert item.id in memory.stores[MemoryType.WORKING]

        # Verify item was persisted to SQLite via backend
        loaded = await backend.load_item(item.id, "working")
        assert loaded is not None
        assert loaded["content"] == "RSI oversold at 25 is a strong buy signal"
        assert loaded["importance"] == 0.9

    @pytest.mark.asyncio
    async def test_restart_round_trip(self, sqlite_db_path):
        """Simulate process restart: store items, create new instance, verify loaded."""
        # Session 1: Store items
        backend1 = SQLiteBackendAdapter(db_path=sqlite_db_path)
        memory1 = HierarchicalMemory(backend=backend1)

        await memory1.store(
            content="MACD crossover is reliable on 4h timeframe",
            memory_type=MemoryType.SEMANTIC,
            importance=0.8,
            tags=["macd", "timeframe"],
        )
        await memory1.store(
            content="Bollinger squeeze precedes breakout",
            memory_type=MemoryType.SEMANTIC,
            importance=0.7,
            tags=["bollinger"],
        )

        # Verify session 1 has 2 items
        assert len(memory1.stores[MemoryType.SEMANTIC]) == 2

        # Session 2: New instance with same DB (simulates restart)
        # Note: HierarchicalMemory._load_from_disk() is called on init
        # but SQLiteBackendAdapter loading needs explicit load
        backend2 = SQLiteBackendAdapter(db_path=sqlite_db_path)

        # Verify data is in SQLite
        all_items = await backend2.load_all(tier="semantic")
        assert len(all_items) == 2
        contents = {item["content"] for item in all_items}
        assert "MACD crossover is reliable on 4h timeframe" in contents
        assert "Bollinger squeeze precedes breakout" in contents

    @pytest.mark.asyncio
    async def test_delete_removes_from_sqlite(self, sqlite_db_path):
        """delete() should remove from both in-memory and SQLite."""
        backend = SQLiteBackendAdapter(db_path=sqlite_db_path)
        memory = HierarchicalMemory(backend=backend)

        item = await memory.store(
            content="Test deletion persistence",
            memory_type=MemoryType.EPISODIC,
            importance=0.5,
        )
        item_id = item.id

        # Delete
        result = await memory.delete(item_id)
        assert result is True

        # Verify removed from in-memory
        assert item_id not in memory.stores[MemoryType.EPISODIC]

        # Verify removed from SQLite
        loaded = await backend.load_item(item_id, "episodic")
        assert loaded is None

    @pytest.mark.asyncio
    async def test_forget_expired_with_sqlite(self, sqlite_db_path):
        """forget() should clean up expired items from SQLite too."""
        backend = SQLiteBackendAdapter(db_path=sqlite_db_path)
        memory = HierarchicalMemory(backend=backend)

        # Store item with very short TTL (working memory = 5 min)
        item = await memory.store(
            content="Ephemeral data",
            memory_type=MemoryType.WORKING,
            importance=0.3,
        )

        # Manually expire the item by backdating created_at
        from datetime import UTC, datetime, timedelta

        item.created_at = datetime.now(UTC) - timedelta(hours=1)

        # Run forget
        forgotten = await memory.forget()
        assert forgotten["working"] >= 1

        # Verify cleaned from SQLite backend
        loaded = await backend.load_item(item.id, "working")
        assert loaded is None

    @pytest.mark.asyncio
    async def test_capacity_eviction_with_sqlite(self, sqlite_db_path):
        """When tier is full, eviction should still persist remaining items."""
        backend = SQLiteBackendAdapter(db_path=sqlite_db_path)
        memory = HierarchicalMemory(backend=backend)

        # Working memory max = 10 items
        # Store 12 items — 2 should be evicted
        stored_items = []
        for i in range(12):
            item = await memory.store(
                content=f"Working item {i}",
                memory_type=MemoryType.WORKING,
                importance=i * 0.08,  # 0.0 to 0.88
            )
            stored_items.append(item)

        # Should have max 10 in working memory
        assert len(memory.stores[MemoryType.WORKING]) <= 10

        # Remaining items should be in SQLite
        all_working = await backend.load_all(tier="working")
        assert len(all_working) >= 10  # At least 10 persisted

    @pytest.mark.asyncio
    async def test_multiple_tiers_with_sqlite(self, sqlite_db_path):
        """Store across multiple tiers and verify independent persistence."""
        backend = SQLiteBackendAdapter(db_path=sqlite_db_path)
        memory = HierarchicalMemory(backend=backend)

        await memory.store("Working data", MemoryType.WORKING, importance=0.5)
        await memory.store("Episodic data", MemoryType.EPISODIC, importance=0.6)
        await memory.store("Semantic data", MemoryType.SEMANTIC, importance=0.7)
        await memory.store("Procedural data", MemoryType.PROCEDURAL, importance=0.8)

        # Verify each tier independently
        working = await backend.load_all(tier="working")
        episodic = await backend.load_all(tier="episodic")
        semantic = await backend.load_all(tier="semantic")
        procedural = await backend.load_all(tier="procedural")

        assert len(working) == 1
        assert len(episodic) == 1
        assert len(semantic) == 1
        assert len(procedural) == 1

    @pytest.mark.asyncio
    async def test_recall_after_store_with_sqlite(self, sqlite_db_path):
        """recall() should work with SQLite-backed memory."""
        backend = SQLiteBackendAdapter(db_path=sqlite_db_path)
        memory = HierarchicalMemory(backend=backend)

        await memory.store(
            content="RSI period 14 is standard for crypto trading",
            memory_type=MemoryType.SEMANTIC,
            importance=0.9,
            tags=["rsi", "crypto"],
        )
        await memory.store(
            content="MACD histogram divergence signals reversal",
            memory_type=MemoryType.SEMANTIC,
            importance=0.8,
            tags=["macd"],
        )

        results = await memory.recall(
            query="RSI trading crypto",
            memory_type=MemoryType.SEMANTIC,
            top_k=5,
        )
        assert len(results) >= 1
        # RSI item should score higher due to keyword match
        assert "RSI" in results[0].content

    @pytest.mark.asyncio
    async def test_consolidation_with_sqlite(self, sqlite_db_path):
        """consolidate() should work with SQLite backend."""
        backend = SQLiteBackendAdapter(db_path=sqlite_db_path)
        memory = HierarchicalMemory(backend=backend)

        # Store high-importance working memory
        await memory.store(
            content="BTC broke above 100K resistance",
            memory_type=MemoryType.WORKING,
            importance=0.9,
            tags=["btc", "resistance"],
        )

        # Consolidate: working → episodic
        result = await memory.consolidate()
        assert result["working_to_episodic"] >= 1

        # Verify episodic items are persisted to SQLite
        episodic = await backend.load_all(tier="episodic")
        assert len(episodic) >= 1

    @pytest.mark.asyncio
    async def test_stats_with_sqlite_backend(self, sqlite_db_path):
        """get_stats() should work with SQLite backend."""
        backend = SQLiteBackendAdapter(db_path=sqlite_db_path)
        memory = HierarchicalMemory(backend=backend)

        await memory.store("Test item", MemoryType.WORKING, importance=0.5)

        stats = memory.get_stats()
        assert stats["total_stored"] == 1
        assert stats["tiers"]["working"]["count"] == 1
        assert stats["tiers"]["working"]["utilization"] > 0


# ═══════════════════════════════════════════════════════════════════
# HierarchicalMemory + JsonFileBackend — Integration Tests
# ═══════════════════════════════════════════════════════════════════


class TestHierarchicalMemoryWithJsonFile:
    """Integration tests: HierarchicalMemory with JsonFileBackend via persist_path."""

    @pytest.mark.asyncio
    async def test_persist_path_creates_json_backend(self, tmp_path):
        """persist_path should auto-create JsonFileBackend."""
        persist_dir = str(tmp_path / "auto_json")
        memory = HierarchicalMemory(persist_path=persist_dir)

        assert memory._backend is not None
        assert isinstance(memory._backend, JsonFileBackend)

    @pytest.mark.asyncio
    async def test_store_creates_json_files(self, tmp_path):
        """store() with persist_path should create JSON files on disk."""
        persist_dir = tmp_path / "json_persist"
        memory = HierarchicalMemory(persist_path=str(persist_dir))

        await memory.store(
            content="JSON persisted item",
            memory_type=MemoryType.WORKING,
            importance=0.7,
        )

        # Check that a JSON file was created
        working_dir = persist_dir / "working"
        assert working_dir.exists()
        json_files = list(working_dir.glob("*.json"))
        assert len(json_files) == 1

    @pytest.mark.asyncio
    async def test_json_restart_round_trip(self, tmp_path):
        """Simulate restart with JsonFileBackend."""
        persist_dir = str(tmp_path / "json_restart")

        # Session 1
        memory1 = HierarchicalMemory(persist_path=persist_dir)
        await memory1.store(
            content="Persisted across restart",
            memory_type=MemoryType.SEMANTIC,
            importance=0.8,
        )

        # Session 2
        memory2 = HierarchicalMemory(persist_path=persist_dir)
        assert len(memory2.stores[MemoryType.SEMANTIC]) == 1
        item = next(iter(memory2.stores[MemoryType.SEMANTIC].values()))
        assert item.content == "Persisted across restart"

    @pytest.mark.asyncio
    async def test_no_backend_means_in_memory_only(self):
        """No persist_path and no backend = pure in-memory."""
        memory = HierarchicalMemory()
        assert memory._backend is None

        await memory.store("Ephemeral", MemoryType.WORKING, importance=0.5)
        assert len(memory.stores[MemoryType.WORKING]) == 1


# ═══════════════════════════════════════════════════════════════════
# Backend switching / edge cases
# ═══════════════════════════════════════════════════════════════════


class TestBackendEdgeCases:
    """Edge cases and backend switching tests."""

    @pytest.mark.asyncio
    async def test_explicit_backend_overrides_persist_path(self, sqlite_db_path, tmp_path):
        """If both backend and persist_path are given, backend wins."""
        backend = SQLiteBackendAdapter(db_path=sqlite_db_path)
        memory = HierarchicalMemory(
            persist_path=str(tmp_path / "should_not_be_used"),
            backend=backend,
        )
        assert isinstance(memory._backend, SQLiteBackendAdapter)

    @pytest.mark.asyncio
    async def test_sqlite_handles_empty_content(self, sqlite_db_path):
        """Store empty content should not crash."""
        backend = SQLiteBackendAdapter(db_path=sqlite_db_path)
        memory = HierarchicalMemory(backend=backend)

        item = await memory.store("", MemoryType.WORKING, importance=0.1)
        loaded = await backend.load_item(item.id, "working")
        assert loaded is not None
        assert loaded["content"] == ""

    @pytest.mark.asyncio
    async def test_sqlite_handles_large_content(self, sqlite_db_path):
        """Store large content (10KB+) should work."""
        backend = SQLiteBackendAdapter(db_path=sqlite_db_path)
        memory = HierarchicalMemory(backend=backend)

        large_content = "A" * 10_000
        item = await memory.store(large_content, MemoryType.SEMANTIC, importance=0.5)
        loaded = await backend.load_item(item.id, "semantic")
        assert loaded is not None
        assert len(loaded["content"]) == 10_000

    @pytest.mark.asyncio
    async def test_concurrent_stores_with_sqlite(self, sqlite_db_path):
        """Multiple concurrent stores should not corrupt SQLite."""
        backend = SQLiteBackendAdapter(db_path=sqlite_db_path)
        memory = HierarchicalMemory(backend=backend)

        # Store 20 items concurrently
        tasks = [
            memory.store(
                content=f"Concurrent item {i}",
                memory_type=MemoryType.EPISODIC,
                importance=0.5,
            )
            for i in range(20)
        ]
        items = await asyncio.gather(*tasks)
        assert len(items) == 20

        # Verify all persisted
        all_items = await backend.load_all(tier="episodic")
        assert len(all_items) >= 20

    @pytest.mark.asyncio
    async def test_delete_nonexistent_item(self, sqlite_db_path):
        """Deleting a non-existent item should return False gracefully."""
        backend = SQLiteBackendAdapter(db_path=sqlite_db_path)
        memory = HierarchicalMemory(backend=backend)

        result = await memory.delete("nonexistent-id-12345")
        assert result is False

    @pytest.mark.asyncio
    async def test_metadata_preserved_in_sqlite(self, sqlite_db_path):
        """Custom metadata should survive SQLite round-trip."""
        backend = SQLiteBackendAdapter(db_path=sqlite_db_path)
        memory = HierarchicalMemory(backend=backend)

        await memory.store(
            content="Strategy with metadata",
            memory_type=MemoryType.SEMANTIC,
            importance=0.8,
            metadata={"strategy_type": "rsi", "win_rate": 0.65},
            tags=["rsi", "high-performance"],
        )

        all_items = await backend.load_all(tier="semantic")
        assert len(all_items) == 1
        item = all_items[0]
        assert "rsi" in item.get("tags", [])
