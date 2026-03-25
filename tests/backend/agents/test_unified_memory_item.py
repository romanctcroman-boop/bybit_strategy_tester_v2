# tests/backend/agents/test_unified_memory_item.py
"""
Tests for the unified MemoryItem and SQLite backend integration.

Validates P1 acceptance criteria:
- Unified dataclass for the entire system
- agent_namespace in all CRUD operations
- SQLite schema stores all fields without loss
- to_dict() -> from_dict() roundtrip is lossless
- Backward compatibility with old code
- Namespace isolation between agents
"""

import contextlib
import os
import tempfile
from datetime import UTC, datetime, timedelta

import pytest

from backend.agents.memory.hierarchical_memory import (
    HierarchicalMemory,
    MemoryItem,
    MemoryType,
    UnifiedMemoryItem,
)
from backend.agents.memory.sqlite_backend import SQLiteMemoryBackend

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def memory_item() -> MemoryItem:
    """Standard MemoryItem for testing."""
    return MemoryItem(
        id="test-001",
        content="BTCUSDT RSI crossed above 70",
        memory_type=MemoryType.EPISODIC,  # type: ignore[arg-type]
        agent_namespace="deepseek",
        importance=0.85,
        ttl_seconds=3600.0,
        tags=["btc", "rsi", "overbought"],
        metadata={"symbol": "BTCUSDT", "timeframe": "15"},
        source="backtest_analysis",
        related_ids=["test-000", "test-002"],
    )


@pytest.fixture
def sqlite_backend():
    """Temporary SQLite backend for testing."""
    tmp = tempfile.mktemp(suffix=".db")
    backend = SQLiteMemoryBackend(db_path=tmp)
    yield backend
    with contextlib.suppress(OSError):
        os.unlink(tmp)


# ---------------------------------------------------------------------------
# P1 Tests: Serialization roundtrip
# ---------------------------------------------------------------------------


class TestSerializationRoundtrip:
    """to_dict() -> from_dict() must be lossless."""

    def test_roundtrip_preserves_all_fields(self, memory_item: MemoryItem):
        d = memory_item.to_dict()
        restored = MemoryItem.from_dict(d)

        assert restored.id == memory_item.id
        assert restored.content == memory_item.content
        assert restored.memory_type == memory_item.memory_type
        assert restored.agent_namespace == memory_item.agent_namespace
        assert restored.importance == memory_item.importance
        assert restored.ttl_seconds == memory_item.ttl_seconds
        assert restored.tags == memory_item.tags
        assert restored.metadata == memory_item.metadata
        assert restored.source == memory_item.source
        assert restored.related_ids == memory_item.related_ids

    def test_roundtrip_preserves_timestamps(self, memory_item: MemoryItem):
        d = memory_item.to_dict()
        restored = MemoryItem.from_dict(d)

        # Timestamps should be equal (both are datetime objects)
        assert restored.created_at == memory_item.created_at
        assert restored.accessed_at == memory_item.accessed_at

    def test_roundtrip_with_defaults(self):
        """Minimal item with all defaults should roundtrip cleanly."""
        item = MemoryItem(id="min-1", content="minimal", memory_type="working")
        d = item.to_dict()
        restored = MemoryItem.from_dict(d)

        assert restored.id == "min-1"
        assert restored.content == "minimal"
        assert restored.agent_namespace == "shared"
        assert restored.importance == 0.5
        assert restored.ttl_seconds is None
        assert restored.tags == []
        assert restored.metadata == {}
        assert restored.source is None
        assert restored.related_ids == []

    def test_roundtrip_with_none_ttl(self):
        item = MemoryItem(
            id="ttl-none",
            content="no ttl",
            memory_type="semantic",
            ttl_seconds=None,
        )
        d = item.to_dict()
        restored = MemoryItem.from_dict(d)
        assert restored.ttl_seconds is None

    def test_roundtrip_with_legacy_float_timestamp(self):
        """from_dict should handle legacy float timestamps (time.time())."""
        legacy_dict = {
            "id": "legacy-1",
            "content": "legacy item",
            "memory_type": "working",
            "created_at": 1739600000.0,  # float timestamp
            "accessed_at": 1739600100.0,
        }
        item = MemoryItem.from_dict(legacy_dict)
        assert isinstance(item.created_at, datetime)
        assert item.created_at.tzinfo is not None

    def test_roundtrip_with_hierarchical_prefix(self):
        """from_dict should strip 'hierarchical.' prefix from memory_type."""
        d = {
            "id": "prefix-1",
            "content": "prefixed type",
            "memory_type": "hierarchical.episodic",
        }
        item = MemoryItem.from_dict(d)
        assert item.memory_type == MemoryType.EPISODIC


# ---------------------------------------------------------------------------
# P1 Tests: Namespace isolation
# ---------------------------------------------------------------------------


class TestNamespaceIsolation:
    """Items from different agents should not interfere."""

    def test_store_with_different_namespaces(self, sqlite_backend: SQLiteMemoryBackend):
        sqlite_backend.store(
            "working",
            "DeepSeek analysis",
            agent_namespace="deepseek",
            importance=0.9,
        )
        sqlite_backend.store(
            "working",
            "Qwen analysis",
            agent_namespace="qwen",
            importance=0.8,
        )
        sqlite_backend.store(
            "working",
            "Shared insight",
            agent_namespace="shared",
            importance=0.7,
        )

        # Query with namespace filter
        deepseek_items = sqlite_backend.query("working", agent_namespace="deepseek")
        qwen_items = sqlite_backend.query("working", agent_namespace="qwen")

        # Each agent sees its own + shared items
        deepseek_contents = {i["content"] for i in deepseek_items}
        qwen_contents = {i["content"] for i in qwen_items}

        assert "DeepSeek analysis" in deepseek_contents
        assert "Shared insight" in deepseek_contents
        assert "Qwen analysis" not in deepseek_contents

        assert "Qwen analysis" in qwen_contents
        assert "Shared insight" in qwen_contents
        assert "DeepSeek analysis" not in qwen_contents

    def test_default_namespace_is_shared(self, sqlite_backend: SQLiteMemoryBackend):
        sqlite_backend.store("working", "Default namespace item")
        items = sqlite_backend.query("working")
        assert items[0]["agent_namespace"] == "shared"

    def test_namespace_in_stats(self, sqlite_backend: SQLiteMemoryBackend):
        sqlite_backend.store("working", "A", agent_namespace="agent_a")
        sqlite_backend.store("working", "B", agent_namespace="agent_b")
        sqlite_backend.store("working", "C", agent_namespace="shared")

        stats = sqlite_backend.get_stats()
        assert "by_namespace" in stats
        assert stats["by_namespace"]["agent_a"] == 1
        assert stats["by_namespace"]["agent_b"] == 1
        assert stats["by_namespace"]["shared"] == 1


# ---------------------------------------------------------------------------
# P1 Tests: SQLite stores all fields without loss
# ---------------------------------------------------------------------------


class TestSQLiteFieldPersistence:
    """SQLite schema must store ALL MemoryItem fields."""

    def test_all_fields_persist(self, sqlite_backend: SQLiteMemoryBackend):
        item_id = sqlite_backend.store(
            "episodic",
            "Full field test",
            importance=0.95,
            ttl_seconds=7200.0,
            tags=["test", "full"],
            metadata={"key": "value", "nested": {"a": 1}},
            item_id="full-001",
            agent_namespace="tester",
            source="unit_test",
            related_ids=["rel-1", "rel-2"],
            embedding=[0.1, 0.2, 0.3, 0.4, 0.5],
        )

        result = sqlite_backend.get_by_id(item_id)
        assert result is not None
        assert result["id"] == "full-001"
        assert result["content"] == "Full field test"
        assert result["memory_type"] == "episodic"
        assert result["agent_namespace"] == "tester"
        assert result["importance"] == 0.95
        assert result["ttl_seconds"] == 7200.0
        assert result["tags"] == ["test", "full"]
        assert result["metadata"]["key"] == "value"
        assert result["metadata"]["nested"]["a"] == 1
        assert result["source"] == "unit_test"
        assert result["related_ids"] == ["rel-1", "rel-2"]
        assert result["embedding"] == [0.1, 0.2, 0.3, 0.4, 0.5]

    def test_null_optional_fields(self, sqlite_backend: SQLiteMemoryBackend):
        item_id = sqlite_backend.store("working", "Minimal store")
        result = sqlite_backend.get_by_id(item_id)
        assert result is not None
        assert result["ttl_seconds"] is None
        assert result["source"] is None
        assert result["embedding"] is None
        assert result["related_ids"] == []

    def test_query_returns_dicts(self, sqlite_backend: SQLiteMemoryBackend):
        sqlite_backend.store("working", "Dict check")
        items = sqlite_backend.query("working")
        assert len(items) == 1
        assert isinstance(items[0], dict)
        assert "id" in items[0]
        assert "content" in items[0]
        assert "agent_namespace" in items[0]


# ---------------------------------------------------------------------------
# P1 Tests: Backward compatibility
# ---------------------------------------------------------------------------


class TestBackwardCompat:
    """Old code using MemoryItem and PersistentMemoryItem should still work."""

    def test_unified_memory_item_is_memory_item(self):
        assert UnifiedMemoryItem is MemoryItem

    def test_persistent_memory_item_alias(self):
        from backend.agents.memory import PersistentMemoryItem

        # PersistentMemoryItem should be an alias for MemoryItem
        assert PersistentMemoryItem is MemoryItem

    def test_old_memory_item_api(self):
        """Old API: MemoryItem(id, content, memory_type) still works."""
        item = MemoryItem(
            id="old-1",
            content="Old API",
            memory_type="working",
        )
        assert item.id == "old-1"
        assert item.to_dict()["content"] == "Old API"

    @pytest.mark.asyncio
    async def test_hierarchical_memory_store_recall(self):
        """HierarchicalMemory.store() and .recall() still work."""
        mem = HierarchicalMemory()
        await mem.store("Test recall", memory_type=MemoryType.WORKING, importance=0.8)
        results = await mem.recall("Test", top_k=5)
        assert len(results) >= 1
        assert any("Test recall" in r.content for r in results)

    @pytest.mark.asyncio
    async def test_hierarchical_memory_with_namespace(self):
        """New agent_namespace parameter works with HierarchicalMemory."""
        mem = HierarchicalMemory()
        await mem.store(
            "Agent-specific data",
            memory_type=MemoryType.EPISODIC,
            importance=0.9,
            agent_namespace="test_agent",
        )
        # Recall without namespace returns all
        all_results = await mem.recall("Agent-specific", top_k=10)
        assert len(all_results) >= 1

    def test_memory_type_enum_coercion(self):
        """String memory_type should be coerced to MemoryTier enum."""
        item = MemoryItem(id="coerce-1", content="test", memory_type="semantic")
        assert item.memory_type == MemoryType.SEMANTIC
        assert item.memory_type.value == "semantic"

    def test_importance_clamping(self):
        """Importance should be clamped to [0, 1]."""
        item_high = MemoryItem(id="h", content="h", memory_type="working", importance=5.0)
        item_low = MemoryItem(id="l", content="l", memory_type="working", importance=-1.0)
        assert item_high.importance == 1.0
        assert item_low.importance == 0.0


# ---------------------------------------------------------------------------
# P1 Tests: TTL behavior
# ---------------------------------------------------------------------------


class TestTTLBehavior:
    def test_per_item_ttl_overrides_tier_ttl(self):
        """Per-item ttl_seconds should override tier-level TTL."""
        item = MemoryItem(
            id="ttl-1",
            content="Short-lived",
            memory_type="semantic",
            ttl_seconds=1.0,
            created_at=datetime.now(UTC) - timedelta(seconds=2),
        )
        # Semantic tier normally has 365-day TTL, but item TTL is 1s
        tier_ttl = timedelta(days=365)
        assert item.is_expired(tier_ttl) is True

    def test_none_ttl_uses_tier_ttl(self):
        """Item with ttl_seconds=None should use the tier TTL."""
        item = MemoryItem(
            id="ttl-2",
            content="Long-lived",
            memory_type="working",
            ttl_seconds=None,
            created_at=datetime.now(UTC) - timedelta(minutes=1),
        )
        # 5-minute tier TTL: item is 1 minute old, so not expired
        assert item.is_expired(timedelta(minutes=5)) is False
        # 30-second tier TTL: item is 1 minute old, so expired
        assert item.is_expired(timedelta(seconds=30)) is True
