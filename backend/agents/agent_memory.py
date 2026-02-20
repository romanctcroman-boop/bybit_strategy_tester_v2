"""
Agent Memory Manager

Manages conversation history and memory for agents.
Provides storage and retrieval of agent interactions.

Supports two backends (configured via AGENT_MEMORY_BACKEND env var):
- "file"   : Legacy JSON file-per-conversation (default)
- "sqlite" : SQLite WAL mode for durability and concurrent access
"""

import json
import logging
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _get_backend_setting() -> str:
    """Read AGENT_MEMORY_BACKEND from config (avoids circular import at module level)."""
    try:
        from backend.agents.base_config import AGENT_MEMORY_BACKEND

        return AGENT_MEMORY_BACKEND
    except Exception:
        return "file"


class AgentMemoryManager:
    """
    Manages memory storage for agents.

    Stores conversation history and context for agent-to-agent communication.
    Uses per-conversation locks to prevent data corruption from concurrent writes.

    Backend selection (P5.1a):
    - ``AGENT_MEMORY_BACKEND=file``   → JSON files in ``agent_memory/`` (legacy)
    - ``AGENT_MEMORY_BACKEND=sqlite`` → SQLite WAL at ``data/agent_conversations.db``
    """

    def __init__(self, project_root: Path | str, *, backend: str | None = None):
        """
        Initialize the memory manager.

        Args:
            project_root: Root path of the project
            backend: Override backend type ("file" or "sqlite").
                     If None, reads from AGENT_MEMORY_BACKEND env var.
        """
        self.project_root = Path(project_root)
        self.memory_dir = self.project_root / "agent_memory"
        self.memory_dir.mkdir(exist_ok=True)
        self.conversations: dict[str, list[dict[str, Any]]] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()  # Protects _locks dict itself

        # Select backend
        self._backend = backend or _get_backend_setting()
        if self._backend == "sqlite":
            self._db_path = str(self.project_root / "data" / "agent_conversations.db")
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
            self._init_sqlite()
            logger.info("AgentMemoryManager initialized (SQLite WAL): %s", self._db_path)
        else:
            self._db_path = None
            logger.info("AgentMemoryManager initialized (JSON files): %s", self.memory_dir)

    # ------------------------------------------------------------------
    # SQLite setup
    # ------------------------------------------------------------------

    def _init_sqlite(self) -> None:
        """Create the conversations table with WAL journal mode."""
        with self._get_sqlite() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_conv_id
                ON conversations (conversation_id)
            """)
            conn.commit()

    @contextmanager
    def _get_sqlite(self):
        """Yield a SQLite connection with proper cleanup."""
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def _get_lock(self, conversation_id: str) -> threading.Lock:
        """Get or create a lock for the given conversation_id (thread-safe)."""
        with self._locks_guard:
            if conversation_id not in self._locks:
                self._locks[conversation_id] = threading.Lock()
            return self._locks[conversation_id]

    def store_message(self, conversation_id: str, message: dict[str, Any]) -> None:
        """
        Store a message in the conversation history.

        Thread-safe: uses per-conversation locking to prevent data corruption.

        Args:
            conversation_id: Unique identifier for the conversation
            message: Message dictionary containing message data
        """
        lock = self._get_lock(conversation_id)
        with lock:
            if conversation_id not in self.conversations:
                self.conversations[conversation_id] = []

            self.conversations[conversation_id].append(message)

            if self._backend == "sqlite":
                self._persist_conversation_sqlite(conversation_id, message)
            else:
                self._persist_conversation_json(conversation_id)

    def get_conversation(self, conversation_id: str) -> list[dict[str, Any]]:
        """
        Retrieve all messages in a conversation.

        Args:
            conversation_id: Unique identifier for the conversation

        Returns:
            List of message dictionaries
        """
        if conversation_id in self.conversations:
            return self.conversations[conversation_id]

        # Try to load from disk
        if self._backend == "sqlite":
            return self._load_conversation_sqlite(conversation_id)
        return self._load_conversation_json(conversation_id)

    def clear_conversation(self, conversation_id: str) -> None:
        """
        Clear all messages in a conversation.

        Thread-safe: uses per-conversation locking.

        Args:
            conversation_id: Unique identifier for the conversation
        """
        lock = self._get_lock(conversation_id)
        with lock:
            if conversation_id in self.conversations:
                del self.conversations[conversation_id]

            if self._backend == "sqlite":
                self._clear_conversation_sqlite(conversation_id)
            else:
                conv_file = self.memory_dir / f"{conversation_id}.json"
                if conv_file.exists():
                    conv_file.unlink()

    # ------------------------------------------------------------------
    # JSON backend (legacy)
    # ------------------------------------------------------------------

    def _persist_conversation_json(self, conversation_id: str) -> None:
        """Save entire conversation to a JSON file."""
        try:
            conv_file = self.memory_dir / f"{conversation_id}.json"
            conv_file.write_text(json.dumps(self.conversations[conversation_id], indent=2))
        except Exception as e:
            logger.warning("Failed to persist conversation %s (JSON): %s", conversation_id, e)

    def _load_conversation_json(self, conversation_id: str) -> list[dict[str, Any]]:
        """Load conversation from a JSON file."""
        try:
            conv_file = self.memory_dir / f"{conversation_id}.json"
            if conv_file.exists():
                data = json.loads(conv_file.read_text())
                self.conversations[conversation_id] = data
                return data
        except Exception as e:
            logger.warning("Failed to load conversation %s (JSON): %s", conversation_id, e)
        return []

    # ------------------------------------------------------------------
    # SQLite backend (P5.1a)
    # ------------------------------------------------------------------

    def _persist_conversation_sqlite(self, conversation_id: str, message: dict[str, Any]) -> None:
        """Append a single message to the SQLite conversations table."""
        try:
            with self._get_sqlite() as conn:
                conn.execute(
                    "INSERT INTO conversations (conversation_id, message) VALUES (?, ?)",
                    (conversation_id, json.dumps(message, default=str)),
                )
                conn.commit()
        except Exception as e:
            logger.warning("Failed to persist message for %s (SQLite): %s", conversation_id, e)

    def _load_conversation_sqlite(self, conversation_id: str) -> list[dict[str, Any]]:
        """Load all messages for a conversation from SQLite."""
        try:
            with self._get_sqlite() as conn:
                rows = conn.execute(
                    "SELECT message FROM conversations WHERE conversation_id = ? ORDER BY id",
                    (conversation_id,),
                ).fetchall()
                data = [json.loads(row["message"]) for row in rows]
                self.conversations[conversation_id] = data
                return data
        except Exception as e:
            logger.warning("Failed to load conversation %s (SQLite): %s", conversation_id, e)
        return []

    def _clear_conversation_sqlite(self, conversation_id: str) -> None:
        """Delete all messages for a conversation from SQLite."""
        try:
            with self._get_sqlite() as conn:
                conn.execute(
                    "DELETE FROM conversations WHERE conversation_id = ?",
                    (conversation_id,),
                )
                conn.commit()
        except Exception as e:
            logger.warning("Failed to clear conversation %s (SQLite): %s", conversation_id, e)


class AgentMemory:
    """
    Simple wrapper for agent memory with session support.
    Provides a simpler interface for tests.
    """

    def __init__(self, session_id: str):
        """Initialize agent memory for a session"""
        from pathlib import Path

        project_root = Path(__file__).parent.parent.parent
        self.manager = AgentMemoryManager(project_root)
        self.session_id = session_id
        self._context: list[dict[str, Any]] = []

    def add_context(self, role: str, content: str) -> None:
        """Add context message to memory"""
        message = {
            "role": role,
            "content": content,
            "timestamp": time.time(),
        }
        self._context.append(message)
        self.manager.store_message(self.session_id, message)

    def get_context(self) -> list[dict[str, Any]]:
        """Get all context messages"""
        # Load from disk if not in memory
        if not self._context:
            self._context = self.manager.get_conversation(self.session_id)
        return self._context

    def clear_context(self) -> None:
        """Clear context for current session"""
        self._context = []
        self.manager.clear_conversation(self.session_id)


__all__ = ["AgentMemory", "AgentMemoryManager"]
