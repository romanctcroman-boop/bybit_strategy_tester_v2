"""
Memory MCP Tools

Agent-facing tools for storing, recalling, and managing memories.
Auto-registered with the global MCP tool registry on import.

Implements TZ P2 -- agents can self-serve memory via MCP interface.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from backend.agents.mcp.tool_registry import get_tool_registry
from backend.agents.memory.hierarchical_memory import (
    HierarchicalMemory,
    MemoryType,
)

registry = get_tool_registry()

# ---------------------------------------------------------------------------
# Singleton HierarchicalMemory (P2.3)
# ---------------------------------------------------------------------------

_global_memory: HierarchicalMemory | None = None


def get_global_memory() -> HierarchicalMemory:
    """Get the global HierarchicalMemory singleton.

    Initialised on first call with SQLiteBackendAdapter for persistence.
    """
    global _global_memory
    if _global_memory is None:
        try:
            from backend.agents.memory.backend_interface import SQLiteBackendAdapter

            backend = SQLiteBackendAdapter(db_path="data/agent_memory.db")
            _global_memory = HierarchicalMemory(backend=backend)
            logger.info("Global HierarchicalMemory initialised with SQLite backend")
        except Exception as e:
            logger.warning(f"SQLite backend init failed, using in-memory: {e}")
            _global_memory = HierarchicalMemory()
    return _global_memory


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------

_VALID_TIERS = {"working", "episodic", "semantic", "procedural"}


def _parse_memory_type(tier: str) -> MemoryType:
    """Convert string tier name to MemoryType enum."""
    tier = tier.lower().strip()
    try:
        return MemoryType(tier)
    except ValueError:
        raise ValueError(f"Invalid memory_type '{tier}'. Must be one of: {sorted(_VALID_TIERS)}") from None


@registry.register(
    name="memory_store",
    description=(
        "Store content in agent memory with specified tier and importance. "
        "Use for preserving insights, analysis results, and learned patterns."
    ),
    category="memory",
)
async def memory_store(
    content: str,
    memory_type: str = "episodic",
    importance: float = 0.5,
    tags: list[str] | None = None,
    namespace: str = "shared",
    source: str | None = None,
) -> dict[str, Any]:
    """
    Store content in agent memory.

    Args:
        content: Text content to store.
        memory_type: Tier -- working/episodic/semantic/procedural.
        importance: Relevance score 0.0-1.0.
        tags: Categorisation tags for later filtering.
        namespace: Agent namespace for isolation (default "shared").
        source: Origin identifier (e.g. "backtest_analysis").

    Returns:
        Dict with stored item ID and metadata.
    """
    mem = get_global_memory()
    mt = _parse_memory_type(memory_type)

    item = await mem.store(
        content=content,
        memory_type=mt,
        importance=importance,
        tags=tags,
        source=source,
        agent_namespace=namespace,
    )

    logger.debug(f"MCP memory_store: id={item.id}, tier={memory_type}, importance={importance}, namespace={namespace}")

    return {
        "status": "stored",
        "item_id": item.id,
        "memory_type": memory_type,
        "importance": importance,
        "namespace": namespace,
        "tags": tags or [],
    }


@registry.register(
    name="memory_recall",
    description=(
        "Recall memories matching a query with optional filters. "
        "Use to retrieve past analysis, learned patterns, or context."
    ),
    category="memory",
)
async def memory_recall(
    query: str,
    memory_type: str | None = None,
    top_k: int = 5,
    min_importance: float = 0.0,
    tags: list[str] | None = None,
    namespace: str | None = None,
    use_semantic: bool = True,
) -> dict[str, Any]:
    """
    Recall memories matching query with optional filters.

    Args:
        query: Search query text.
        memory_type: Specific tier to search (None = all tiers).
        top_k: Maximum number of results.
        min_importance: Minimum importance threshold.
        tags: Filter by these tags.
        namespace: Filter by agent namespace (None = all).
        use_semantic: Use embedding similarity if available.

    Returns:
        Dict with list of matching memory items.
    """
    mem = get_global_memory()
    mt = _parse_memory_type(memory_type) if memory_type else None

    results = await mem.recall(
        query=query,
        memory_type=mt,
        top_k=top_k,
        min_importance=min_importance,
        tags=tags,
        use_semantic=use_semantic,
        agent_namespace=namespace,
    )

    items = []
    for item in results:
        items.append(
            {
                "id": item.id,
                "content": item.content,
                "memory_type": item.memory_type.value,
                "importance": item.importance,
                "tags": item.tags,
                "namespace": item.agent_namespace,
                "created_at": str(item.created_at),
                "access_count": item.access_count,
            }
        )

    logger.debug(f"MCP memory_recall: query='{query[:50]}', found={len(items)}")

    return {
        "query": query,
        "results": items,
        "total_found": len(items),
    }


@registry.register(
    name="memory_get_stats",
    description="Get memory system statistics: item counts, tier utilization, namespace breakdown.",
    category="memory",
)
async def memory_get_stats(
    namespace: str | None = None,
) -> dict[str, Any]:
    """
    Get memory system statistics.

    Args:
        namespace: Filter stats by namespace (None = all).

    Returns:
        Dict with counts, utilization, and tier health.
    """
    mem = get_global_memory()
    stats = mem.get_stats()

    # Add SQLite backend stats if available
    try:
        from backend.agents.memory.sqlite_backend import get_memory_backend

        db_stats = get_memory_backend().get_stats()
        stats["sqlite"] = db_stats
    except Exception:
        pass

    logger.debug(f"MCP memory_get_stats: {stats.get('total_items', '?')} items")
    return stats


@registry.register(
    name="memory_consolidate",
    description=(
        "Trigger manual memory consolidation: promote important memories from working -> episodic -> semantic tier."
    ),
    category="memory",
)
async def memory_consolidate() -> dict[str, Any]:
    """
    Trigger manual memory consolidation.

    Promotes important short-term memories to longer-term tiers
    based on importance and access frequency.

    Returns:
        Dict with consolidation results (per-tier promotion counts).
    """
    mem = get_global_memory()

    try:
        result = await mem.consolidate()
        total = sum(result.values())
        logger.info(f"MCP memory_consolidate: {result}")
        return {
            "status": "completed",
            "items_consolidated": total,
            "details": result,
        }
    except Exception as e:
        logger.error(f"MCP memory_consolidate failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "items_consolidated": 0,
        }


@registry.register(
    name="memory_forget",
    description=("Intelligent forgetting: remove low-value memories older than a threshold to prevent memory bloat."),
    category="memory",
)
async def memory_forget(
    min_age_hours: float = 24.0,
    max_importance: float = 0.1,
) -> dict[str, Any]:
    """
    Trigger intelligent forgetting of low-value memories.

    Delegates to HierarchicalMemory.forget() which applies:
    1. TTL-based expiration
    2. Importance decay over time
    3. Eviction of very-low-importance items

    Also cleans expired rows from the SQLite backend.

    Args:
        min_age_hours: Informational — the engine uses per-tier TTLs.
        max_importance: Informational — engine threshold is 0.1.

    Returns:
        Dict with per-tier and total forgotten counts.
    """
    mem = get_global_memory()
    total = 0

    try:
        # 1. Clean expired items in SQLite backend
        sqlite_expired = 0
        try:
            from backend.agents.memory.sqlite_backend import get_memory_backend

            sqlite_expired = get_memory_backend().cleanup_expired()
        except Exception:
            pass

        # 2. Run in-memory forgetting (TTL + decay + low-importance)
        result = await mem.forget()
        tier_counts = dict(result)
        total = sum(tier_counts.values()) + sqlite_expired

        logger.info(f"MCP memory_forget: removed {total} items (tiers={tier_counts}, sqlite_expired={sqlite_expired})")
    except Exception as e:
        logger.error(f"MCP memory_forget failed: {e}")
        return {"status": "error", "error": str(e), "items_forgotten": 0}

    return {
        "status": "completed",
        "items_forgotten": total,
        "details": {
            **tier_counts,
            "sqlite_expired": sqlite_expired,
        },
        "criteria": {
            "min_age_hours": min_age_hours,
            "max_importance": max_importance,
        },
    }
