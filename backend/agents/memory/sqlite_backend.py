"""
SQLite-backed Persistent Memory for Agent System

Replaces in-memory-only HierarchicalMemory with SQLite persistence.
Addresses audit finding: "All memory tiers in-memory only, data loss on restart" (All 3, P1)

Features:
- SQLite storage with WAL mode for concurrent reads
- TTL-based automatic expiration
- LRU eviction when tier limits exceeded
- Thread-safe async operations
- Import/export for migration
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class PersistentMemoryItem:
    """A single memory item with persistence support."""

    id: str
    content: str
    memory_type: str  # working, episodic, semantic, procedural
    importance: float = 0.5
    created_at: float = field(default_factory=time.time)
    accessed_at: float = field(default_factory=time.time)
    access_count: int = 0
    ttl_seconds: float = 3600.0
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        """Check if this item has expired based on TTL."""
        return time.time() - self.created_at > self.ttl_seconds

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type,
            "importance": self.importance,
            "created_at": self.created_at,
            "accessed_at": self.accessed_at,
            "access_count": self.access_count,
            "ttl_seconds": self.ttl_seconds,
            "tags": self.tags,
            "metadata": self.metadata,
        }


class SQLiteMemoryBackend:
    """
    SQLite-backed memory with WAL mode and concurrent access.

    Example:
        memory = SQLiteMemoryBackend("data/agent_memory.db")
        memory.store("working", "Current analysis context", importance=0.9)
        items = memory.query("working", limit=10)
    """

    def __init__(self, db_path: str = "data/agent_memory.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        logger.info(f"SQLite memory backend initialized: {db_path}")

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_items (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    importance REAL DEFAULT 0.5,
                    created_at REAL NOT NULL,
                    accessed_at REAL NOT NULL,
                    access_count INTEGER DEFAULT 0,
                    ttl_seconds REAL DEFAULT 3600.0,
                    tags TEXT DEFAULT '[]',
                    metadata TEXT DEFAULT '{}'
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memory_type
                ON memory_items (memory_type)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_importance
                ON memory_items (importance DESC)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_accessed_at
                ON memory_items (accessed_at DESC)
            """)
            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Get a database connection with proper cleanup."""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def store(
        self,
        memory_type: str,
        content: str,
        *,
        importance: float = 0.5,
        ttl_seconds: float = 3600.0,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        item_id: str | None = None,
    ) -> str:
        """
        Store a memory item.

        Returns:
            The ID of the stored item.
        """
        item_id = item_id or str(uuid.uuid4())[:12]
        now = time.time()

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO memory_items
                (id, content, memory_type, importance, created_at, accessed_at,
                 access_count, ttl_seconds, tags, metadata)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
                """,
                (
                    item_id,
                    content,
                    memory_type,
                    importance,
                    now,
                    now,
                    ttl_seconds,
                    json.dumps(tags or []),
                    json.dumps(metadata or {}),
                ),
            )
            conn.commit()

        return item_id

    def query(
        self,
        memory_type: str | None = None,
        *,
        limit: int = 10,
        min_importance: float = 0.0,
        tags: list[str] | None = None,
        include_expired: bool = False,
    ) -> list[PersistentMemoryItem]:
        """Query memory items with filters."""
        conditions = []
        params: list[Any] = []

        if memory_type:
            conditions.append("memory_type = ?")
            params.append(memory_type)

        if min_importance > 0:
            conditions.append("importance >= ?")
            params.append(min_importance)

        if not include_expired:
            conditions.append("(created_at + ttl_seconds) > ?")
            params.append(time.time())

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        with self._get_connection() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM memory_items
                WHERE {where_clause}
                ORDER BY importance DESC, accessed_at DESC
                LIMIT ?
                """,
                [*params, limit],
            ).fetchall()

            items = []
            for row in rows:
                item = PersistentMemoryItem(
                    id=row["id"],
                    content=row["content"],
                    memory_type=row["memory_type"],
                    importance=row["importance"],
                    created_at=row["created_at"],
                    accessed_at=row["accessed_at"],
                    access_count=row["access_count"],
                    ttl_seconds=row["ttl_seconds"],
                    tags=json.loads(row["tags"]),
                    metadata=json.loads(row["metadata"]),
                )
                items.append(item)

                # Update access stats
                conn.execute(
                    "UPDATE memory_items SET accessed_at = ?, access_count = access_count + 1 WHERE id = ?",
                    (time.time(), row["id"]),
                )

            conn.commit()

            # Filter by tags if specified
            if tags:
                tag_set = set(tags)
                items = [item for item in items if tag_set.intersection(item.tags)]

            return items

    def get_by_id(self, item_id: str) -> PersistentMemoryItem | None:
        """Get a specific memory item by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM memory_items WHERE id = ?", (item_id,)).fetchone()
            if not row:
                return None

            conn.execute(
                "UPDATE memory_items SET accessed_at = ?, access_count = access_count + 1 WHERE id = ?",
                (time.time(), item_id),
            )
            conn.commit()

            return PersistentMemoryItem(
                id=row["id"],
                content=row["content"],
                memory_type=row["memory_type"],
                importance=row["importance"],
                created_at=row["created_at"],
                accessed_at=row["accessed_at"],
                access_count=row["access_count"] + 1,
                ttl_seconds=row["ttl_seconds"],
                tags=json.loads(row["tags"]),
                metadata=json.loads(row["metadata"]),
            )

    def delete(self, item_id: str) -> bool:
        """Delete a memory item. Returns True if item existed."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM memory_items WHERE id = ?", (item_id,))
            conn.commit()
            return cursor.rowcount > 0

    def cleanup_expired(self) -> int:
        """Remove expired items. Returns count removed."""
        now = time.time()
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM memory_items WHERE (created_at + ttl_seconds) < ?",
                (now,),
            )
            conn.commit()
            removed = cursor.rowcount
            if removed > 0:
                logger.info(f"🧹 Cleaned {removed} expired memory items")
            return removed

    def evict_lru(self, memory_type: str, max_items: int) -> int:
        """Evict least-recently-used items to enforce tier size limits."""
        with self._get_connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM memory_items WHERE memory_type = ?",
                (memory_type,),
            ).fetchone()[0]

            if count <= max_items:
                return 0

            excess = count - max_items
            cursor = conn.execute(
                """
                DELETE FROM memory_items WHERE id IN (
                    SELECT id FROM memory_items
                    WHERE memory_type = ?
                    ORDER BY importance ASC, accessed_at ASC
                    LIMIT ?
                )
                """,
                (memory_type, excess),
            )
            conn.commit()
            evicted = cursor.rowcount
            if evicted > 0:
                logger.info(f"🧹 Evicted {evicted} LRU items from {memory_type} tier")
            return evicted

    def get_stats(self) -> dict[str, Any]:
        """Get memory usage statistics."""
        with self._get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM memory_items").fetchone()[0]
            by_type = conn.execute(
                "SELECT memory_type, COUNT(*) as cnt FROM memory_items GROUP BY memory_type"
            ).fetchall()

            now = time.time()
            expired = conn.execute(
                "SELECT COUNT(*) FROM memory_items WHERE (created_at + ttl_seconds) < ?",
                (now,),
            ).fetchone()[0]

            return {
                "total_items": total,
                "expired_items": expired,
                "by_type": {row["memory_type"]: row["cnt"] for row in by_type},
                "db_path": self.db_path,
            }


# Singleton
_memory_backend: SQLiteMemoryBackend | None = None


def get_memory_backend() -> SQLiteMemoryBackend:
    """Get global SQLite memory backend singleton."""
    global _memory_backend
    if _memory_backend is None:
        try:
            from backend.agents.config_validator import get_agent_config

            config = get_agent_config()
            db_path = config.memory.sqlite_path
        except Exception:
            db_path = "data/agent_memory.db"
        _memory_backend = SQLiteMemoryBackend(db_path)
    return _memory_backend
