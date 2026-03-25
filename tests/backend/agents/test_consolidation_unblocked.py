"""
P3 Integration Test -- Consolidation unblocked by tag normalization.

TZ: test_consolidation_unblocked -- 3 items from different agents with
different tag forms should consolidate to SEMANTIC via canonical tags.
"""

from __future__ import annotations

import pytest

from backend.agents.memory.hierarchical_memory import HierarchicalMemory, MemoryType


@pytest.fixture()
def memory() -> HierarchicalMemory:
    """In-memory HierarchicalMemory for consolidation tests."""
    return HierarchicalMemory()


class TestConsolidationUnblocked:
    """Verify that tag normalization unblocks EPISODIC -> SEMANTIC consolidation."""

    @pytest.mark.asyncio
    async def test_different_tag_forms_consolidate(self, memory: HierarchicalMemory):
        """3 items with different RSI tag forms -> normalized -> consolidation fires."""
        # Store 3 episodic items from "different agents" with different tag forms
        await memory.store(
            content="RSI above 70 indicates overbought conditions on BTCUSDT",
            memory_type=MemoryType.EPISODIC,
            importance=0.8,
            tags=["RSI", "trading"],
            agent_namespace="deepseek",
        )
        await memory.store(
            content="RSI_indicator crossed below 30 on ETHUSDT, oversold signal",
            memory_type=MemoryType.EPISODIC,
            importance=0.7,
            tags=["RSI_indicator", "trade"],
            agent_namespace="qwen",
        )
        await memory.store(
            content="Relative strength index divergence detected on SOLUSDT",
            memory_type=MemoryType.EPISODIC,
            importance=0.75,
            tags=["relative-strength-index", "Trading"],
            agent_namespace="perplexity",
        )

        # Before consolidation: EPISODIC has items, SEMANTIC is empty
        episodic_count = len(memory.stores[MemoryType.EPISODIC])
        semantic_count_before = len(memory.stores[MemoryType.SEMANTIC])
        assert episodic_count >= 3
        assert semantic_count_before == 0

        # Trigger consolidation
        result = await memory.consolidate()

        # After consolidation: should have promoted at least something
        # All 3 items have "rsi" canonical tag, avg importance >= 0.6 threshold
        semantic_count_after = len(memory.stores[MemoryType.SEMANTIC])

        assert result["episodic_to_semantic"] >= 1, (
            f"Consolidation should have promoted at least 1 group to SEMANTIC, got {result}"
        )
        assert semantic_count_after > semantic_count_before

    @pytest.mark.asyncio
    async def test_tags_normalized_on_store(self, memory: HierarchicalMemory):
        """Verify that store() normalizes tags automatically via AutoTagger."""
        item = await memory.store(
            content="RSI crossed above 70",
            memory_type=MemoryType.EPISODIC,
            importance=0.6,
            tags=["RSI_indicator", "Trading"],
        )
        # Tags should be normalized
        assert "rsi" in item.tags
        assert "trading" in item.tags
        # Un-normalized forms should be gone
        assert "RSI_indicator" not in item.tags
        assert "Trading" not in item.tags

    @pytest.mark.asyncio
    async def test_working_to_episodic_still_works(self, memory: HierarchicalMemory):
        """Working -> Episodic promotion should still work with P3 changes."""
        await memory.store(
            content="Important short-term finding about market",
            memory_type=MemoryType.WORKING,
            importance=0.9,  # Above 0.7 threshold
            tags=["critical"],
        )

        result = await memory.consolidate()
        assert result["working_to_episodic"] >= 1

    @pytest.mark.asyncio
    async def test_below_threshold_no_consolidation(self, memory: HierarchicalMemory):
        """Items below importance threshold should NOT consolidate."""
        for i in range(3):
            await memory.store(
                content=f"Low importance item {i}",
                memory_type=MemoryType.EPISODIC,
                importance=0.2,  # Below 0.6 threshold
                tags=["lowprio"],
            )

        result = await memory.consolidate()
        assert result["episodic_to_semantic"] == 0
