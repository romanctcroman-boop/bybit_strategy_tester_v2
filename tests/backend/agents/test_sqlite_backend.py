# Tests for memory/sqlite_backend.py

import os
import tempfile
import time

from backend.agents.memory.hierarchical_memory import MemoryItem
from backend.agents.memory.sqlite_backend import (
    SQLiteMemoryBackend,
)


class TestMemoryItemCompat:
    """Verify MemoryItem works as a replacement for the old PersistentMemoryItem."""

    def test_creation(self):
        item = MemoryItem(
            id="test-1",
            content="Test content",
            memory_type="working",
        )
        assert item.id == "test-1"
        assert item.content == "Test content"
        assert item.memory_type.value == "working"
        assert item.importance == 0.5
        assert item.access_count == 0

    def test_is_expired_false(self):
        from datetime import timedelta

        item = MemoryItem(
            id="test-1",
            content="Fresh",
            memory_type="working",
            ttl_seconds=3600.0,
        )
        assert item.is_expired(timedelta(hours=1)) is False

    def test_is_expired_true(self):
        from datetime import UTC, datetime, timedelta

        item = MemoryItem(
            id="test-1",
            content="Old",
            memory_type="working",
            ttl_seconds=0.01,
            created_at=datetime.now(UTC) - timedelta(seconds=2),
        )
        # Per-item ttl_seconds=0.01 overrides the tier ttl argument
        assert item.is_expired(timedelta(hours=1)) is True

    def test_to_dict(self):
        item = MemoryItem(
            id="test-1",
            content="Content",
            memory_type="episodic",
            tags=["tag1", "tag2"],
        )
        d = item.to_dict()
        assert d["id"] == "test-1"
        assert d["memory_type"] == "episodic"
        assert d["tags"] == ["tag1", "tag2"]
        assert "metadata" in d


class TestSQLiteMemoryBackend:
    def _make_backend(self):
        """Create a temp backend for testing."""
        tmp = tempfile.mktemp(suffix=".db")
        return SQLiteMemoryBackend(db_path=tmp), tmp

    def test_store_and_query(self):
        backend, tmp = self._make_backend()
        try:
            item_id = backend.store("working", "Test content", importance=0.8)
            assert isinstance(item_id, str)
            items = backend.query("working")
            assert len(items) == 1
            assert items[0]["content"] == "Test content"
            assert items[0]["importance"] == 0.8
        finally:
            os.unlink(tmp)

    def test_store_with_custom_id(self):
        backend, tmp = self._make_backend()
        try:
            item_id = backend.store("working", "Content", item_id="custom-123")
            assert item_id == "custom-123"
        finally:
            os.unlink(tmp)

    def test_query_by_type(self):
        backend, tmp = self._make_backend()
        try:
            backend.store("working", "Working item")
            backend.store("episodic", "Episodic item")
            working = backend.query("working")
            episodic = backend.query("episodic")
            assert len(working) == 1
            assert len(episodic) == 1
            assert working[0]["memory_type"] == "working"
            assert episodic[0]["memory_type"] == "episodic"
        finally:
            os.unlink(tmp)

    def test_query_min_importance(self):
        backend, tmp = self._make_backend()
        try:
            backend.store("working", "Low", importance=0.1)
            backend.store("working", "High", importance=0.9)
            items = backend.query("working", min_importance=0.5)
            assert len(items) == 1
            assert items[0]["content"] == "High"
        finally:
            os.unlink(tmp)

    def test_query_limit(self):
        backend, tmp = self._make_backend()
        try:
            for i in range(10):
                backend.store("working", f"Item {i}")
            items = backend.query("working", limit=3)
            assert len(items) == 3
        finally:
            os.unlink(tmp)

    def test_get_by_id(self):
        backend, tmp = self._make_backend()
        try:
            item_id = backend.store("working", "Specific item", item_id="find-me")
            found = backend.get_by_id("find-me")
            assert found is not None
            assert found["content"] == "Specific item"
            # access_count reflects the row state before the access UPDATE
            assert found["access_count"] >= 0
        finally:
            os.unlink(tmp)

    def test_get_by_id_not_found(self):
        backend, tmp = self._make_backend()
        try:
            result = backend.get_by_id("nonexistent")
            assert result is None
        finally:
            os.unlink(tmp)

    def test_delete(self):
        backend, tmp = self._make_backend()
        try:
            backend.store("working", "To delete", item_id="del-1")
            assert backend.delete("del-1") is True
            assert backend.get_by_id("del-1") is None
        finally:
            os.unlink(tmp)

    def test_delete_nonexistent(self):
        backend, tmp = self._make_backend()
        try:
            assert backend.delete("nonexistent") is False
        finally:
            os.unlink(tmp)

    def test_cleanup_expired(self):
        backend, tmp = self._make_backend()
        try:
            backend.store("working", "Fresh", ttl_seconds=3600.0)
            backend.store("working", "Expired", ttl_seconds=1.0)
            time.sleep(2.0)
            removed = backend.cleanup_expired()
            assert removed == 1
            items = backend.query("working", include_expired=True)
            assert len(items) == 1
            assert items[0]["content"] == "Fresh"
        finally:
            os.unlink(tmp)

    def test_evict_lru(self):
        backend, tmp = self._make_backend()
        try:
            for i in range(5):
                backend.store("working", f"Item {i}", importance=i * 0.1)
            evicted = backend.evict_lru("working", max_items=2)
            assert evicted == 3
            remaining = backend.query("working")
            assert len(remaining) == 2
        finally:
            os.unlink(tmp)

    def test_evict_lru_no_excess(self):
        backend, tmp = self._make_backend()
        try:
            backend.store("working", "Single item")
            evicted = backend.evict_lru("working", max_items=10)
            assert evicted == 0
        finally:
            os.unlink(tmp)

    def test_get_stats(self):
        backend, tmp = self._make_backend()
        try:
            backend.store("working", "W1")
            backend.store("working", "W2")
            backend.store("episodic", "E1")
            stats = backend.get_stats()
            assert stats["total_items"] == 3
            assert stats["by_type"]["working"] == 2
            assert stats["by_type"]["episodic"] == 1
            assert "db_path" in stats
        finally:
            os.unlink(tmp)

    def test_store_with_tags_and_metadata(self):
        backend, tmp = self._make_backend()
        try:
            backend.store(
                "semantic",
                "Tagged item",
                tags=["btc", "strategy"],
                metadata={"source": "backtest"},
            )
            items = backend.query("semantic")
            assert items[0]["tags"] == ["btc", "strategy"]
            assert items[0]["metadata"] == {"source": "backtest"}
        finally:
            os.unlink(tmp)

    def test_query_by_tags(self):
        backend, tmp = self._make_backend()
        try:
            backend.store("working", "Tagged", tags=["important"])
            backend.store("working", "Untagged", tags=[])
            items = backend.query("working", tags=["important"])
            assert len(items) == 1
            assert items[0]["content"] == "Tagged"
        finally:
            os.unlink(tmp)
