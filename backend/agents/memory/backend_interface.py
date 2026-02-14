"""
Memory Backend Interface (ABC)

Defines a common interface for memory persistence backends.
Implementations:
- JsonFileBackend: Legacy file-per-item storage (default for backward compat)
- SQLiteMemoryBackend: SQLite-based persistent storage with WAL, TTL, LRU

This abstracts the persistence layer so HierarchicalMemory can use either
backend without changing its in-memory data structures or logic.

Addresses audit finding: "HierarchicalMemory is in-memory only, no integration
path with sqlite_backend.py" (Qwen, HIGH severity)
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from loguru import logger


class MemoryBackend(ABC):
    """Abstract base for memory persistence backends."""

    @abstractmethod
    async def save_item(self, item_id: str, tier: str, data: dict[str, Any]) -> None:
        """Persist a single memory item."""

    @abstractmethod
    async def load_item(self, item_id: str, tier: str) -> dict[str, Any] | None:
        """Load a single memory item by ID and tier."""

    @abstractmethod
    async def delete_item(self, item_id: str, tier: str) -> None:
        """Delete a persisted memory item."""

    @abstractmethod
    async def load_all(self, tier: str | None = None) -> list[dict[str, Any]]:
        """Load all items, optionally filtered by tier."""

    @abstractmethod
    async def close(self) -> None:
        """Release backend resources."""


class JsonFileBackend(MemoryBackend):
    """
    Legacy JSON file-per-item backend.

    Stores each MemoryItem as a separate .json file under
    <persist_path>/<tier>/<item_id>.json.
    """

    def __init__(self, persist_path: str | Path):
        self.persist_path = Path(persist_path)
        self.persist_path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"JsonFileBackend initialized: {self.persist_path}")

    async def save_item(self, item_id: str, tier: str, data: dict[str, Any]) -> None:
        """Save item to JSON file."""
        tier_path = self.persist_path / tier
        tier_path.mkdir(parents=True, exist_ok=True)
        file_path = tier_path / f"{item_id}.json"
        try:
            # Don't persist embeddings to save space
            save_data = {k: v for k, v in data.items() if k != "embedding"}
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(save_data, f, indent=2, default=str)
        except Exception as e:
            logger.warning(f"Failed to save memory {item_id}: {e}")

    async def load_item(self, item_id: str, tier: str) -> dict[str, Any] | None:
        """Load item from JSON file."""
        file_path = self.persist_path / tier / f"{item_id}.json"
        if not file_path.exists():
            return None
        try:
            with open(file_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load memory {item_id}: {e}")
            return None

    async def delete_item(self, item_id: str, tier: str) -> None:
        """Delete JSON file for item."""
        file_path = self.persist_path / tier / f"{item_id}.json"
        try:
            if file_path.exists():
                file_path.unlink()
        except Exception as e:
            logger.warning(f"Failed to delete memory {item_id}: {e}")

    async def load_all(self, tier: str | None = None) -> list[dict[str, Any]]:
        """Load all items from JSON files."""
        items = []
        tiers = [tier] if tier else [d.name for d in self.persist_path.iterdir() if d.is_dir()]
        for t in tiers:
            tier_path = self.persist_path / t
            if not tier_path.exists():
                continue
            for fp in tier_path.glob("*.json"):
                try:
                    with open(fp, encoding="utf-8") as f:
                        data = json.load(f)
                        data.setdefault("memory_type", t)
                        items.append(data)
                except Exception as e:
                    logger.warning(f"Failed to load {fp}: {e}")
        return items

    async def close(self) -> None:
        """No resources to release for file backend."""
        pass


class SQLiteBackendAdapter(MemoryBackend):
    """
    Adapter that wraps SQLiteMemoryBackend to conform to MemoryBackend ABC.

    Bridges the gap between HierarchicalMemory's persistence needs and
    the existing SQLiteMemoryBackend (which has its own schema).
    SQLiteMemoryBackend is sync — we wrap calls via ``asyncio.to_thread``
    to avoid blocking the event loop.
    """

    def __init__(self, db_path: str = "agent_memory.db"):
        # Lazy import to avoid circular dependencies
        from backend.agents.memory.sqlite_backend import SQLiteMemoryBackend

        self._backend = SQLiteMemoryBackend(db_path=db_path)
        logger.debug(f"SQLiteBackendAdapter initialized: {db_path}")

    async def save_item(self, item_id: str, tier: str, data: dict[str, Any]) -> None:
        """Save item to SQLite via SQLiteMemoryBackend (non-blocking)."""
        import asyncio

        content = data.get("content", "")
        importance = data.get("importance", 0.5)
        tags = data.get("tags", [])
        metadata = {
            k: v
            for k, v in data.items()
            if k not in ("id", "content", "memory_type", "importance", "tags", "embedding")
        }
        await asyncio.to_thread(
            self._backend.store,
            memory_type=f"hierarchical.{tier}",
            content=content,
            importance=importance,
            tags=tags,
            metadata=metadata,
            item_id=item_id,
        )

    async def load_item(self, item_id: str, tier: str) -> dict[str, Any] | None:
        """Load item from SQLite (non-blocking)."""
        import asyncio

        result = await asyncio.to_thread(self._backend.get_by_id, item_id)
        if result is None:
            return None
        return {
            "id": result.id,
            "content": result.content,
            "memory_type": tier,
            "importance": result.importance,
            "tags": result.tags,
            **result.metadata,
        }

    async def delete_item(self, item_id: str, tier: str) -> None:
        """Delete item from SQLite (non-blocking)."""
        import asyncio

        await asyncio.to_thread(self._backend.delete, item_id)

    async def load_all(self, tier: str | None = None) -> list[dict[str, Any]]:
        """Load all items from SQLite (non-blocking)."""
        import asyncio

        memory_type = f"hierarchical.{tier}" if tier else None
        results = await asyncio.to_thread(
            self._backend.query,
            memory_type=memory_type,
            limit=10000,
            include_expired=True,
        )
        items = []
        for r in results:
            items.append(
                {
                    "id": r.id,
                    "content": r.content,
                    "memory_type": tier or r.memory_type.replace("hierarchical.", ""),
                    "importance": r.importance,
                    "tags": r.tags,
                    **r.metadata,
                }
            )
        return items

    async def close(self) -> None:
        """SQLiteMemoryBackend doesn't require explicit close."""


__all__ = [
    "JsonFileBackend",
    "MemoryBackend",
    "SQLiteBackendAdapter",
]
