"""
SQLite-backed Persistent Memory for Agent System.

Unified persistence layer using the single MemoryItem dataclass.
Addresses audit finding: "Dual MemoryItem anti-pattern" (Phase 13, 3/3 agents, HIGH).

Features:
- SQLite storage with WAL mode for concurrent reads
- Unified schema matching MemoryItem fields (no data loss)
- agent_namespace for per-agent memory isolation
- TTL-based automatic expiration
- LRU eviction when tier limits exceeded
- Thread-safe sync operations (wrapped via asyncio.to_thread by adapter)
- Auto-migration from v1 (float timestamps) to v2 (ISO-8601)
"""

from __future__ import annotations

import contextlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from loguru import logger

# SQLite-compatible UTC timestamp format (space separator, no TZ suffix).
# IMPORTANT: SQLite datetime() returns "YYYY-MM-DD HH:MM:SS" (with space,
# not 'T'), so we MUST use the same format for correct string comparison.
_SQLITE_TS_FMT = "%Y-%m-%d %H:%M:%S"


def _utcnow_str() -> str:
    """Return current UTC time as SQLite-compatible string."""
    return datetime.now(UTC).strftime(_SQLITE_TS_FMT)


class SQLiteMemoryBackend:
    """
    SQLite-backed memory with WAL mode and concurrent access.

    Uses the unified MemoryItem schema -- all fields stored without loss.
    Returns ``dict[str, Any]`` (MemoryItem-compatible) instead of a separate dataclass.

    Example::

        memory = SQLiteMemoryBackend("data/agent_memory.db")
        memory.store("working", "Current analysis context", importance=0.9)
        items = memory.query("working", limit=10)
    """

    # Current schema version for migrations
    SCHEMA_VERSION = 2

    def __init__(self, db_path: str = "data/agent_memory.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        logger.info(f"SQLite memory backend initialized: {db_path}")

    def _init_db(self) -> None:
        """Initialize database schema (v2: unified MemoryItem fields)."""
        with self._get_connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")

            # Unified schema -- matches MemoryItem dataclass exactly
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_items (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    agent_namespace TEXT NOT NULL DEFAULT 'shared',
                    importance REAL DEFAULT 0.5,
                    created_at TEXT NOT NULL,
                    accessed_at TEXT NOT NULL,
                    access_count INTEGER DEFAULT 0,
                    ttl_seconds REAL,
                    tags TEXT DEFAULT '[]',
                    metadata TEXT DEFAULT '{}',
                    source TEXT,
                    related_ids TEXT DEFAULT '[]',
                    embedding BLOB
                )
            """)

            # Indexes for common access patterns
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memory_type
                ON memory_items (memory_type)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_namespace_type
                ON memory_items (agent_namespace, memory_type)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_importance
                ON memory_items (importance DESC)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_accessed_at
                ON memory_items (accessed_at DESC)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_namespace_importance
                ON memory_items (agent_namespace, importance DESC)
            """)
            conn.commit()

            # Run migration if upgrading from v1 schema
            self._migrate_schema(conn)

    @contextmanager
    def _get_connection(self):
        """Get a database connection with proper cleanup."""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Schema migration (v1 float timestamps -> v2 ISO-8601)
    # ------------------------------------------------------------------

    def _migrate_schema(self, conn: sqlite3.Connection) -> None:
        """Migrate old schema (v1) to new schema (v2) if needed."""
        cursor = conn.execute("PRAGMA table_info(memory_items)")
        columns = {row[1] for row in cursor.fetchall()}

        migrations_applied = False

        # v1 -> v2 migrations: add missing columns
        new_columns = {
            "agent_namespace": "TEXT NOT NULL DEFAULT 'shared'",
            "source": "TEXT",
            "related_ids": "TEXT DEFAULT '[]'",
            "embedding": "BLOB",
        }

        for col_name, col_def in new_columns.items():
            if col_name not in columns:
                try:
                    conn.execute(f"ALTER TABLE memory_items ADD COLUMN {col_name} {col_def}")
                    migrations_applied = True
                    logger.info(f"Migration: added column '{col_name}' to memory_items")
                except sqlite3.OperationalError:
                    pass  # Column may already exist

        # Migrate timestamp format: float -> ISO-8601 string
        if "created_at" in columns:
            sample = conn.execute("SELECT created_at FROM memory_items LIMIT 1").fetchone()
            if sample and sample[0]:
                try:
                    float(sample[0])
                    # Value is a float -- old schema, convert all rows
                    logger.info("Migration: converting timestamps from float to ISO-8601")
                    rows = conn.execute("SELECT id, created_at, accessed_at FROM memory_items").fetchall()
                    for row in rows:
                        try:
                            created = datetime.fromtimestamp(float(row[1]), tz=UTC).strftime(_SQLITE_TS_FMT)
                            accessed = datetime.fromtimestamp(float(row[2]), tz=UTC).strftime(_SQLITE_TS_FMT)
                            conn.execute(
                                "UPDATE memory_items SET created_at=?, accessed_at=? WHERE id=?",
                                (created, accessed, row[0]),
                            )
                        except (ValueError, TypeError, OSError):
                            pass
                    migrations_applied = True
                except (ValueError, TypeError):
                    pass  # Already ISO-8601

        if migrations_applied:
            conn.commit()
            logger.info("Schema migration completed")

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------

    def store(
        self,
        memory_type: str,
        content: str,
        *,
        importance: float = 0.5,
        ttl_seconds: float | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        item_id: str | None = None,
        agent_namespace: str = "shared",
        source: str | None = None,
        related_ids: list[str] | None = None,
        embedding: list[float] | None = None,
    ) -> str:
        """
        Store a memory item.

        Args:
            memory_type: Memory tier (working/episodic/semantic/procedural).
            content: Text content to store.
            importance: Importance score 0.0-1.0.
            ttl_seconds: Optional per-item TTL override (None = no per-item TTL).
            tags: Categorization tags.
            metadata: Arbitrary key-value metadata.
            item_id: Optional explicit ID (auto-generated if None).
            agent_namespace: Per-agent isolation key (default "shared").
            source: Origin identifier.
            related_ids: Links to related memory items.
            embedding: Optional vector embedding (list of floats).

        Returns:
            The ID of the stored item.
        """
        item_id = item_id or str(uuid.uuid4())[:12]
        now = _utcnow_str()

        # Serialize embedding as JSON blob if provided
        embedding_blob = json.dumps(embedding).encode() if embedding else None

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO memory_items
                (id, content, memory_type, agent_namespace, importance,
                 created_at, accessed_at, access_count, ttl_seconds,
                 tags, metadata, source, related_ids, embedding)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item_id,
                    content,
                    memory_type,
                    agent_namespace,
                    importance,
                    now,
                    now,
                    ttl_seconds,
                    json.dumps(tags or []),
                    json.dumps(metadata or {}),
                    source,
                    json.dumps(related_ids or []),
                    embedding_blob,
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
        agent_namespace: str | None = None,
    ) -> list[dict[str, Any]]:
        """Query memory items with filters.

        Returns list of dicts (MemoryItem-compatible).
        """
        conditions: list[str] = []
        params: list[Any] = []

        if memory_type:
            conditions.append("memory_type = ?")
            params.append(memory_type)

        if agent_namespace:
            conditions.append("(agent_namespace = ? OR agent_namespace = 'shared')")
            params.append(agent_namespace)

        if min_importance > 0:
            conditions.append("importance >= ?")
            params.append(min_importance)

        if not include_expired:
            # Items with NULL ttl_seconds never expire via this filter
            now = _utcnow_str()
            conditions.append(
                "(ttl_seconds IS NULL OR datetime(created_at, '+' || CAST(ttl_seconds AS TEXT) || ' seconds') > ?)"
            )
            params.append(now)

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
                item = self._row_to_dict(row)
                items.append(item)

                # Update access stats
                conn.execute(
                    "UPDATE memory_items SET accessed_at = ?, access_count = access_count + 1 WHERE id = ?",
                    (_utcnow_str(), row["id"]),
                )

            conn.commit()

            # Filter by tags if specified (post-filter for JSON array matching)
            if tags:
                tag_set = set(tags)
                items = [item for item in items if tag_set.intersection(item.get("tags", []))]

            return items

    def get_by_id(self, item_id: str) -> dict[str, Any] | None:
        """Get a specific memory item by ID.

        Returns dict (MemoryItem-compatible) or None.
        """
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM memory_items WHERE id = ?", (item_id,)).fetchone()
            if not row:
                return None

            conn.execute(
                "UPDATE memory_items SET accessed_at = ?, access_count = access_count + 1 WHERE id = ?",
                (_utcnow_str(), item_id),
            )
            conn.commit()

            return self._row_to_dict(row)

    # ------------------------------------------------------------------
    # Row conversion helper
    # ------------------------------------------------------------------

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        """Convert a SQLite row to a MemoryItem-compatible dict."""
        row_keys = row.keys()

        # Deserialize embedding from blob
        embedding = None
        if "embedding" in row_keys and row["embedding"]:
            with contextlib.suppress(json.JSONDecodeError, TypeError):
                embedding = json.loads(row["embedding"])

        return {
            "id": row["id"],
            "content": row["content"],
            "memory_type": row["memory_type"],
            "agent_namespace": (row["agent_namespace"] if "agent_namespace" in row_keys else "shared"),
            "importance": row["importance"],
            "created_at": row["created_at"],
            "accessed_at": row["accessed_at"],
            "access_count": row["access_count"],
            "ttl_seconds": row["ttl_seconds"] if "ttl_seconds" in row_keys else None,
            "tags": json.loads(row["tags"]) if row["tags"] else [],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
            "source": row["source"] if "source" in row_keys else None,
            "related_ids": (json.loads(row["related_ids"]) if "related_ids" in row_keys and row["related_ids"] else []),
            "embedding": embedding,
        }

    def delete(self, item_id: str) -> bool:
        """Delete a memory item. Returns True if item existed."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM memory_items WHERE id = ?", (item_id,))
            conn.commit()
            deleted: bool = (cursor.rowcount or 0) > 0
            return deleted  # type: ignore[return-value]

    def cleanup_expired(self) -> int:
        """Remove expired items. Returns count removed."""
        now = _utcnow_str()
        with self._get_connection() as conn:
            cursor = conn.execute(
                """DELETE FROM memory_items
                WHERE ttl_seconds IS NOT NULL
                AND datetime(created_at, '+' || CAST(ttl_seconds AS TEXT) || ' seconds') < ?""",
                (now,),
            )
            conn.commit()
            removed: int = cursor.rowcount or 0
            if removed > 0:
                logger.info(f"Cleaned {removed} expired memory items")
            return removed  # type: ignore[return-value]

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
            evicted: int = cursor.rowcount or 0
            if evicted > 0:
                logger.info(f"Evicted {evicted} LRU items from {memory_type} tier")
            return evicted  # type: ignore[return-value]

    def get_stats(self) -> dict[str, Any]:
        """Get memory usage statistics."""
        with self._get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM memory_items").fetchone()[0]
            by_type = conn.execute(
                "SELECT memory_type, COUNT(*) as cnt FROM memory_items GROUP BY memory_type"
            ).fetchall()
            by_namespace = conn.execute(
                "SELECT agent_namespace, COUNT(*) as cnt FROM memory_items GROUP BY agent_namespace"
            ).fetchall()

            return {
                "total_items": total,
                "by_type": {row["memory_type"]: row["cnt"] for row in by_type},
                "by_namespace": {row["agent_namespace"]: row["cnt"] for row in by_namespace},
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
