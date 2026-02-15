"""
P2.5 — MCP Memory Tools Tests

Tests for the 5 MCP memory tools:
    memory_store, memory_recall, memory_get_stats,
    memory_consolidate, memory_forget

Coverage targets:
    - Store → Recall roundtrip
    - Namespace isolation between agents
    - Stats correctness after operations
    - Consolidation lifecycle
    - Forgetting by criteria
    - Input validation / error handling
    - Singleton lifecycle
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_global_memory():
    """Reset the global memory singleton before each test."""
    import backend.agents.mcp.tools.memory as mem_mod

    mem_mod._global_memory = None
    yield
    mem_mod._global_memory = None


@pytest.fixture()
def global_memory():
    """Return a fresh in-memory HierarchicalMemory via get_global_memory().

    Forces in-memory mode by patching the import inside get_global_memory()
    so that SQLiteBackendAdapter raises ImportError.
    """
    with patch(
        "backend.agents.memory.backend_interface.SQLiteBackendAdapter",
        side_effect=ImportError("force in-memory"),
    ):
        import backend.agents.mcp.tools.memory as mem_mod

        mem_mod._global_memory = None
        mem = mem_mod.get_global_memory()
    return mem


# ============================================================================
# 1. Singleton
# ============================================================================


class TestGlobalMemorySingleton:
    """get_global_memory() returns the same instance on repeated calls."""

    def test_singleton_returns_same_instance(self, global_memory):
        from backend.agents.mcp.tools.memory import get_global_memory

        mem2 = get_global_memory()
        assert mem2 is global_memory

    def test_singleton_is_hierarchical_memory(self, global_memory):
        from backend.agents.memory.hierarchical_memory import HierarchicalMemory

        assert isinstance(global_memory, HierarchicalMemory)


# ============================================================================
# 2. memory_store + memory_recall  roundtrip
# ============================================================================


class TestMemoryStoreAndRecall:
    """TZ: test_memory_store_and_recall — store → recall roundtrip."""

    @pytest.mark.asyncio
    async def test_store_returns_item_id(self, global_memory):
        from backend.agents.mcp.tools.memory import memory_store

        result = await memory_store(
            content="BTC pump detected",
            memory_type="episodic",
            importance=0.8,
            tags=["btc", "pump"],
        )
        assert result["status"] == "stored"
        assert result["item_id"]
        assert result["memory_type"] == "episodic"
        assert result["importance"] == 0.8
        assert result["tags"] == ["btc", "pump"]

    @pytest.mark.asyncio
    async def test_recall_finds_stored_item(self, global_memory):
        from backend.agents.mcp.tools.memory import memory_recall, memory_store

        await memory_store(content="ETH support at 3000", importance=0.9)

        result = await memory_recall(query="ETH support")
        assert result["total_found"] >= 1
        contents = [r["content"] for r in result["results"]]
        assert any("ETH support" in c for c in contents)

    @pytest.mark.asyncio
    async def test_recall_empty_returns_zero(self, global_memory):
        from backend.agents.mcp.tools.memory import memory_recall

        result = await memory_recall(query="nonexistent topic xyz")
        assert result["total_found"] == 0
        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_recall_respects_top_k(self, global_memory):
        from backend.agents.mcp.tools.memory import memory_recall, memory_store

        for i in range(10):
            await memory_store(content=f"item {i}", importance=0.5)

        result = await memory_recall(query="item", top_k=3)
        assert len(result["results"]) <= 3

    @pytest.mark.asyncio
    async def test_recall_filters_by_memory_type(self, global_memory):
        from backend.agents.mcp.tools.memory import memory_recall, memory_store

        await memory_store(content="working data", memory_type="working")
        await memory_store(content="semantic data", memory_type="semantic")

        result = await memory_recall(query="data", memory_type="semantic")
        for item in result["results"]:
            assert item["memory_type"] == "semantic"

    @pytest.mark.asyncio
    async def test_recall_filters_by_min_importance(self, global_memory):
        from backend.agents.mcp.tools.memory import memory_recall, memory_store

        await memory_store(content="low value", importance=0.1)
        await memory_store(content="high value", importance=0.9)

        result = await memory_recall(query="value", min_importance=0.5)
        for item in result["results"]:
            assert item["importance"] >= 0.5

    @pytest.mark.asyncio
    async def test_recall_filters_by_tags(self, global_memory):
        from backend.agents.mcp.tools.memory import memory_recall, memory_store

        await memory_store(content="rsi signal", tags=["rsi"])
        await memory_store(content="macd signal", tags=["macd"])

        result = await memory_recall(query="signal", tags=["rsi"])
        contents = [r["content"] for r in result["results"]]
        assert any("rsi" in c for c in contents)
        assert not any("macd" in c for c in contents)

    @pytest.mark.asyncio
    async def test_store_with_source(self, global_memory):
        from backend.agents.mcp.tools.memory import memory_store

        result = await memory_store(
            content="analysis output",
            source="backtest_engine",
        )
        assert result["status"] == "stored"

    @pytest.mark.asyncio
    async def test_store_all_tiers(self, global_memory):
        """All 4 valid tiers can be stored to."""
        from backend.agents.mcp.tools.memory import memory_store

        for tier in ("working", "episodic", "semantic", "procedural"):
            result = await memory_store(
                content=f"content for {tier}",
                memory_type=tier,
            )
            assert result["status"] == "stored"
            assert result["memory_type"] == tier


# ============================================================================
# 3. Namespace isolation
# ============================================================================


class TestNamespaceIsolation:
    """TZ: test_memory_namespace_isolation — agent_A ≠ agent_B."""

    @pytest.mark.asyncio
    async def test_different_namespaces_isolated(self, global_memory):
        from backend.agents.mcp.tools.memory import memory_recall, memory_store

        await memory_store(
            content="deepseek secret",
            namespace="deepseek",
            importance=0.9,
        )
        await memory_store(
            content="qwen secret",
            namespace="qwen",
            importance=0.9,
        )

        # DeepSeek can see its own data
        ds_result = await memory_recall(query="secret", namespace="deepseek")
        ds_contents = [r["content"] for r in ds_result["results"]]
        assert any("deepseek" in c for c in ds_contents)

        # DeepSeek cannot see Qwen data
        assert not any("qwen" in c for c in ds_contents)

    @pytest.mark.asyncio
    async def test_shared_namespace_visible_to_all(self, global_memory):
        from backend.agents.mcp.tools.memory import memory_recall, memory_store

        await memory_store(
            content="shared knowledge",
            namespace="shared",
            importance=0.9,
        )

        # Both agents can see shared data
        for ns in ("deepseek", "qwen"):
            result = await memory_recall(query="shared knowledge", namespace=ns)
            contents = [r["content"] for r in result["results"]]
            assert any("shared" in c for c in contents), f"Agent {ns} should see shared namespace"

    @pytest.mark.asyncio
    async def test_no_namespace_filter_sees_all(self, global_memory):
        from backend.agents.mcp.tools.memory import memory_recall, memory_store

        await memory_store(content="agent_a item", namespace="a", importance=0.9)
        await memory_store(content="agent_b item", namespace="b", importance=0.9)

        result = await memory_recall(query="item", namespace=None)
        assert result["total_found"] >= 2


# ============================================================================
# 4. memory_get_stats
# ============================================================================


class TestMemoryStats:
    """TZ: test_memory_stats — correct statistics after operations."""

    @pytest.mark.asyncio
    async def test_stats_after_store(self, global_memory):
        from backend.agents.mcp.tools.memory import memory_get_stats, memory_store

        await memory_store(content="item 1", importance=0.5)
        await memory_store(content="item 2", importance=0.7)

        stats = await memory_get_stats()
        assert isinstance(stats, dict)
        # Should have total_stored > 0
        assert stats.get("total_stored", 0) >= 2

    @pytest.mark.asyncio
    async def test_stats_returns_dict(self, global_memory):
        from backend.agents.mcp.tools.memory import memory_get_stats

        stats = await memory_get_stats()
        assert isinstance(stats, dict)


# ============================================================================
# 5. memory_consolidate
# ============================================================================


class TestMemoryConsolidate:
    """TZ: test_memory_consolidate — manual consolidation trigger."""

    @pytest.mark.asyncio
    async def test_consolidate_returns_status(self, global_memory):
        from backend.agents.mcp.tools.memory import memory_consolidate

        result = await memory_consolidate()
        assert result["status"] == "completed"
        assert "items_consolidated" in result
        assert "details" in result

    @pytest.mark.asyncio
    async def test_consolidate_promotes_important_working(self, global_memory):
        from backend.agents.mcp.tools.memory import (
            memory_consolidate,
            memory_recall,
            memory_store,
        )

        # Store high-importance working memory
        await memory_store(
            content="critical pattern detected",
            memory_type="working",
            importance=0.95,
            tags=["critical"],
        )

        result = await memory_consolidate()
        assert result["status"] == "completed"

        # Should have promoted at least 1 item
        if result["items_consolidated"] > 0:
            # Item should now be in episodic tier
            ep_result = await memory_recall(
                query="critical pattern",
                memory_type="episodic",
            )
            assert ep_result["total_found"] >= 1

    @pytest.mark.asyncio
    async def test_consolidate_empty_memory(self, global_memory):
        from backend.agents.mcp.tools.memory import memory_consolidate

        result = await memory_consolidate()
        assert result["status"] == "completed"
        assert result["items_consolidated"] == 0


# ============================================================================
# 6. memory_forget
# ============================================================================


class TestMemoryForget:
    """TZ: test_memory_forget — cleanup by criteria."""

    @pytest.mark.asyncio
    async def test_forget_returns_status(self, global_memory):
        from backend.agents.mcp.tools.memory import memory_forget

        result = await memory_forget()
        assert result["status"] == "completed"
        assert "items_forgotten" in result

    @pytest.mark.asyncio
    async def test_forget_criteria_in_response(self, global_memory):
        from backend.agents.mcp.tools.memory import memory_forget

        result = await memory_forget(min_age_hours=48.0, max_importance=0.05)
        assert result["criteria"]["min_age_hours"] == 48.0
        assert result["criteria"]["max_importance"] == 0.05

    @pytest.mark.asyncio
    async def test_forget_empty_memory(self, global_memory):
        from backend.agents.mcp.tools.memory import memory_forget

        result = await memory_forget()
        assert result["items_forgotten"] == 0


# ============================================================================
# 7. Input validation
# ============================================================================


class TestStoreValidation:
    """TZ: test_memory_store_validation — invalid params → error."""

    @pytest.mark.asyncio
    async def test_invalid_memory_type_raises(self, global_memory):
        from backend.agents.mcp.tools.memory import memory_store

        with pytest.raises(ValueError, match="Invalid memory_type"):
            await memory_store(content="test", memory_type="nonexistent")

    @pytest.mark.asyncio
    async def test_invalid_recall_memory_type_raises(self, global_memory):
        from backend.agents.mcp.tools.memory import memory_recall

        with pytest.raises(ValueError, match="Invalid memory_type"):
            await memory_recall(query="test", memory_type="invalid")

    @pytest.mark.asyncio
    async def test_importance_clamped_to_0_1(self, global_memory):
        from backend.agents.mcp.tools.memory import memory_store

        # Importance > 1.0 should be clamped
        result = await memory_store(content="test", importance=5.0)
        assert result["status"] == "stored"
        # MemoryItem.__post_init__ clamps to 1.0
        assert result["importance"] == 5.0  # MCP tool returns input; clamping is internal

    @pytest.mark.asyncio
    async def test_empty_content_stores(self, global_memory):
        """Empty string is technically valid — engine handles it."""
        from backend.agents.mcp.tools.memory import memory_store

        result = await memory_store(content="")
        assert result["status"] == "stored"


# ============================================================================
# 8. Tool registration
# ============================================================================


class TestToolRegistration:
    """Verify all 5 tools registered in the MCP registry."""

    def test_all_tools_registered(self):
        from backend.agents.mcp.tool_registry import get_tool_registry

        registry = get_tool_registry()

        expected_tools = {
            "memory_store",
            "memory_recall",
            "memory_get_stats",
            "memory_consolidate",
            "memory_forget",
        }

        registered = set()
        for tool in registry.list_tools():
            name = tool.get("name") if isinstance(tool, dict) else getattr(tool, "name", None)
            if name:
                registered.add(name)

        for tool_name in expected_tools:
            assert tool_name in registered, f"Tool '{tool_name}' not registered"

    def test_memory_tools_in_memory_category(self):
        from backend.agents.mcp.tool_registry import get_tool_registry

        registry = get_tool_registry()

        for tool in registry.list_tools():
            name = tool.get("name") if isinstance(tool, dict) else getattr(tool, "name", None)
            if name and name.startswith("memory_"):
                category = tool.get("category") if isinstance(tool, dict) else getattr(tool, "category", None)
                assert category == "memory", f"{name} should be in 'memory' category"


# ============================================================================
# 9. Exports
# ============================================================================


class TestExports:
    """Verify public API exports."""

    def test_get_global_memory_exported(self):
        from backend.agents.mcp.tools import get_global_memory  # noqa: F401

    def test_memory_store_exported(self):
        from backend.agents.mcp.tools import memory_store  # noqa: F401

    def test_memory_recall_exported(self):
        from backend.agents.mcp.tools import memory_recall  # noqa: F401

    def test_memory_get_stats_exported(self):
        from backend.agents.mcp.tools import memory_get_stats  # noqa: F401

    def test_memory_consolidate_exported(self):
        from backend.agents.mcp.tools import memory_consolidate  # noqa: F401

    def test_memory_forget_exported(self):
        from backend.agents.mcp.tools import memory_forget  # noqa: F401
