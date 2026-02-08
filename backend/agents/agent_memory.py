"""
Agent Memory Manager

Manages conversation history and memory for agents.
Provides storage and retrieval of agent interactions.
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class AgentMemoryManager:
    """
    Manages memory storage for agents.

    Stores conversation history and context for agent-to-agent communication.
    """

    def __init__(self, project_root: Path | str):
        """
        Initialize the memory manager.

        Args:
            project_root: Root path of the project
        """
        self.project_root = Path(project_root)
        self.memory_dir = self.project_root / "agent_memory"
        self.memory_dir.mkdir(exist_ok=True)
        self.conversations: dict[str, list[dict[str, Any]]] = {}
        logger.info(f"AgentMemoryManager initialized at {self.memory_dir}")

    def store_message(self, conversation_id: str, message: dict[str, Any]) -> None:
        """
        Store a message in the conversation history.

        Args:
            conversation_id: Unique identifier for the conversation
            message: Message dictionary containing message data
        """
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = []

        self.conversations[conversation_id].append(message)
        self._persist_conversation(conversation_id)

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
        return self._load_conversation(conversation_id)

    def clear_conversation(self, conversation_id: str) -> None:
        """
        Clear all messages in a conversation.

        Args:
            conversation_id: Unique identifier for the conversation
        """
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]

        conv_file = self.memory_dir / f"{conversation_id}.json"
        if conv_file.exists():
            conv_file.unlink()

    def _persist_conversation(self, conversation_id: str) -> None:
        """
        Save conversation to disk.

        Args:
            conversation_id: Unique identifier for the conversation
        """
        try:
            conv_file = self.memory_dir / f"{conversation_id}.json"
            conv_file.write_text(
                json.dumps(self.conversations[conversation_id], indent=2)
            )
        except Exception as e:
            logger.warning(f"Failed to persist conversation {conversation_id}: {e}")

    def _load_conversation(self, conversation_id: str) -> list[dict[str, Any]]:
        """
        Load conversation from disk.

        Args:
            conversation_id: Unique identifier for the conversation

        Returns:
            List of message dictionaries
        """
        try:
            conv_file = self.memory_dir / f"{conversation_id}.json"
            if conv_file.exists():
                data = json.loads(conv_file.read_text())
                self.conversations[conversation_id] = data
                return data
        except Exception as e:
            logger.warning(f"Failed to load conversation {conversation_id}: {e}")

        return []


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
        self._context = []

    def add_context(self, role: str, content: str) -> None:
        """Add context message to memory"""
        message = {
            "role": role,
            "content": content,
            "timestamp": __import__("time").time(),
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
