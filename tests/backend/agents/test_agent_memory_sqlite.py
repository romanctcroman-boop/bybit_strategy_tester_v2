"""
Tests for AgentMemoryManager with SQLite WAL backend (P5.1a).

Verifies:
- SQLite backend stores and retrieves messages correctly
- JSON backend still works as fallback
- Thread safety with concurrent writes
- Conversation clearing works on both backends
- Backend selection via constructor kwarg
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from backend.agents.agent_memory import AgentMemory, AgentMemoryManager


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Create a temporary project root for testing."""
    (tmp_path / "agent_memory").mkdir()
    (tmp_path / "data").mkdir()
    return tmp_path


class TestSQLiteBackend:
    """Tests for AgentMemoryManager with SQLite WAL backend."""

    def test_store_and_retrieve_sqlite(self, tmp_project: Path):
        """Messages stored via SQLite can be retrieved."""
        mgr = AgentMemoryManager(tmp_project, backend="sqlite")
        msg = {"role": "user", "content": "Hello", "timestamp": time.time()}

        mgr.store_message("conv-1", msg)
        result = mgr.get_conversation("conv-1")

        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Hello"

    def test_multiple_messages_sqlite(self, tmp_project: Path):
        """Multiple messages are ordered correctly."""
        mgr = AgentMemoryManager(tmp_project, backend="sqlite")

        for i in range(5):
            mgr.store_message("conv-2", {"index": i, "content": f"msg-{i}"})

        result = mgr.get_conversation("conv-2")
        assert len(result) == 5
        assert [m["index"] for m in result] == [0, 1, 2, 3, 4]

    def test_clear_conversation_sqlite(self, tmp_project: Path):
        """Cleared conversations return empty list from SQLite."""
        mgr = AgentMemoryManager(tmp_project, backend="sqlite")
        mgr.store_message("conv-3", {"content": "to be deleted"})
        assert len(mgr.get_conversation("conv-3")) == 1

        mgr.clear_conversation("conv-3")
        # Clear in-memory cache too
        assert mgr.get_conversation("conv-3") == []

        # Verify on fresh manager (reads from SQLite only)
        mgr2 = AgentMemoryManager(tmp_project, backend="sqlite")
        assert mgr2.get_conversation("conv-3") == []

    def test_persistence_across_instances(self, tmp_project: Path):
        """Data persists when a new manager instance is created."""
        mgr1 = AgentMemoryManager(tmp_project, backend="sqlite")
        mgr1.store_message("persist-test", {"content": "I persist!"})

        mgr2 = AgentMemoryManager(tmp_project, backend="sqlite")
        result = mgr2.get_conversation("persist-test")
        assert len(result) == 1
        assert result[0]["content"] == "I persist!"

    def test_wal_mode_enabled(self, tmp_project: Path):
        """SQLite WAL journal mode is enabled."""
        import sqlite3

        mgr = AgentMemoryManager(tmp_project, backend="sqlite")
        assert mgr._db_path is not None

        conn = sqlite3.connect(mgr._db_path)
        journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()
        assert journal == "wal"

    def test_concurrent_writes_sqlite(self, tmp_project: Path):
        """Multiple threads can write concurrently without corruption."""
        mgr = AgentMemoryManager(tmp_project, backend="sqlite")
        errors: list[str] = []

        def writer(thread_id: int):
            try:
                for i in range(20):
                    mgr.store_message(
                        "concurrent-test",
                        {"thread": thread_id, "index": i},
                    )
            except Exception as e:
                errors.append(f"Thread {thread_id}: {e}")

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert errors == [], f"Concurrent write errors: {errors}"
        result = mgr.get_conversation("concurrent-test")
        assert len(result) == 100  # 5 threads x 20 messages

    def test_isolation_between_conversations(self, tmp_project: Path):
        """Messages from different conversations don't mix."""
        mgr = AgentMemoryManager(tmp_project, backend="sqlite")
        mgr.store_message("conv-a", {"who": "a"})
        mgr.store_message("conv-b", {"who": "b"})

        assert len(mgr.get_conversation("conv-a")) == 1
        assert len(mgr.get_conversation("conv-b")) == 1
        assert mgr.get_conversation("conv-a")[0]["who"] == "a"
        assert mgr.get_conversation("conv-b")[0]["who"] == "b"


class TestJSONBackend:
    """Tests for legacy JSON file backend (ensures backward compat)."""

    def test_store_and_retrieve_json(self, tmp_project: Path):
        """Messages stored via JSON can be retrieved."""
        mgr = AgentMemoryManager(tmp_project, backend="file")
        msg = {"role": "assistant", "content": "Hi", "timestamp": time.time()}

        mgr.store_message("json-conv-1", msg)
        result = mgr.get_conversation("json-conv-1")

        assert len(result) == 1
        assert result[0]["content"] == "Hi"

    def test_json_file_created(self, tmp_project: Path):
        """A .json file is created in the memory directory."""
        mgr = AgentMemoryManager(tmp_project, backend="file")
        mgr.store_message("json-file-test", {"content": "test"})

        json_file = tmp_project / "agent_memory" / "json-file-test.json"
        assert json_file.exists()

    def test_clear_conversation_json(self, tmp_project: Path):
        """Clearing removes the JSON file."""
        mgr = AgentMemoryManager(tmp_project, backend="file")
        mgr.store_message("json-clear", {"content": "delete me"})

        json_file = tmp_project / "agent_memory" / "json-clear.json"
        assert json_file.exists()

        mgr.clear_conversation("json-clear")
        assert not json_file.exists()
        assert mgr.get_conversation("json-clear") == []


class TestAgentMemoryWrapper:
    """Tests for the AgentMemory convenience wrapper."""

    def test_add_and_get_context(self, tmp_project: Path):
        """AgentMemory add_context / get_context round-trip."""
        # Create manager directly, assign to a wrapper
        mgr = AgentMemoryManager(tmp_project, backend="file")
        memory = AgentMemory.__new__(AgentMemory)
        memory.manager = mgr
        memory.session_id = "test-session"
        memory._context = []

        memory.add_context("user", "What is BTC price?")
        memory.add_context("assistant", "$50,000")

        ctx = memory.get_context()
        assert len(ctx) == 2
        assert ctx[0]["role"] == "user"
        assert ctx[1]["role"] == "assistant"

    def test_clear_context(self, tmp_project: Path):
        """AgentMemory.clear_context() empties the session."""
        mgr = AgentMemoryManager(tmp_project, backend="file")
        memory = AgentMemory.__new__(AgentMemory)
        memory.manager = mgr
        memory.session_id = "clear-session"
        memory._context = []

        memory.add_context("user", "Temp message")
        assert len(memory.get_context()) == 1

        memory.clear_context()
        assert memory.get_context() == []
