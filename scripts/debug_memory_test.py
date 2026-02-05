"""Debug test for HierarchicalMemory store_and_recall"""
import asyncio
import sys

sys.path.insert(0, '.')

from backend.agents.memory.hierarchical_memory import HierarchicalMemory, MemoryType


async def test():
    print("Creating memory...")
    m = HierarchicalMemory(persist_path=None)
    print(f"Stats before: {m.get_stats()}")

    print("\nStoring RSI memory...")
    await m.store(
        'RSI is a momentum indicator',
        memory_type=MemoryType.SEMANTIC,
        importance=0.8,
        tags=['trading', 'RSI']
    )

    print("Storing MACD memory...")
    await m.store(
        'User asked about MACD',
        memory_type=MemoryType.EPISODIC,
        importance=0.6
    )

    print("Storing BTC memory...")
    await m.store(
        'Current task: analyze BTC',
        memory_type=MemoryType.WORKING,
        importance=0.9
    )

    print("\nRecalling RSI...")
    results = await m.recall('RSI indicator', top_k=3)
    print(f"Recalled {len(results)} items")

    for r in results:
        print(f"  - {r.content[:50]}")

    stats = m.get_stats()
    print(f"\nStats after: {stats}")
    print(f"total_items: {stats.get('total_items', 'N/A')}")

    # Check assertion
    assert len(results) >= 1, "Should recall at least 1 memory"
    assert any("RSI" in r.content for r in results), "Should find RSI memory"

    total = sum(len(store) for store in m.stores.values())
    print(f"Total items in stores: {total}")
    assert total >= 3, f"Should have 3 items, got {total}"

    print("\n✅ All assertions passed!")

if __name__ == "__main__":
    asyncio.run(test())
