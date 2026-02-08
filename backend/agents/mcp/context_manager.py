"""
MCP Context Manager

Manages context propagation across AI agents:
- Scope management
- Context inheritance
- Metadata tracking
- Cross-agent context sharing
"""

from __future__ import annotations

import contextvars
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from loguru import logger


class ContextScope(Enum):
    """Context scope levels"""

    GLOBAL = "global"  # Accessible everywhere
    SESSION = "session"  # Within a session
    REQUEST = "request"  # Single request
    AGENT = "agent"  # Single agent
    TASK = "task"  # Single task


@dataclass
class ContextMetadata:
    """Context metadata"""

    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    created_by: str | None = None
    expires_at: datetime | None = None
    tags: list[str] = field(default_factory=list)

    def is_expired(self) -> bool:
        """Check if context has expired"""
        if self.expires_at is None:
            return False
        return datetime.now(UTC) > self.expires_at


@dataclass
class Context:
    """
    AI agent context

    Carries state and metadata across agent interactions.

    Example:
        ctx = Context(
            id="ctx_123",
            scope=ContextScope.REQUEST,
            data={"user_id": "user_1", "session_id": "sess_1"},
        )

        # Access data
        user_id = ctx.get("user_id")

        # Update data
        ctx.set("last_action", "query")
    """

    id: str = field(default_factory=lambda: f"ctx_{uuid.uuid4().hex[:12]}")
    scope: ContextScope = ContextScope.REQUEST
    parent_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    metadata: ContextMetadata = field(default_factory=ContextMetadata)

    def get(self, key: str, default: Any = None) -> Any:
        """Get value from context"""
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set value in context"""
        self.data[key] = value

    def delete(self, key: str) -> None:
        """Delete value from context"""
        self.data.pop(key, None)

    def has(self, key: str) -> bool:
        """Check if key exists"""
        return key in self.data

    def update(self, data: dict[str, Any]) -> None:
        """Update multiple values"""
        self.data.update(data)

    def merge_from(self, other: Context) -> None:
        """Merge data from another context"""
        for key, value in other.data.items():
            if key not in self.data:
                self.data[key] = value

    def create_child(
        self,
        scope: ContextScope | None = None,
        inherit_data: bool = True,
    ) -> Context:
        """Create child context"""
        child_data = dict(self.data) if inherit_data else {}

        return Context(
            scope=scope or self.scope,
            parent_id=self.id,
            data=child_data,
            metadata=ContextMetadata(
                created_by=self.id,
                tags=list(self.metadata.tags),
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "scope": self.scope.value,
            "parent_id": self.parent_id,
            "data": self.data,
            "metadata": {
                "created_at": self.metadata.created_at.isoformat(),
                "created_by": self.metadata.created_by,
                "expires_at": self.metadata.expires_at.isoformat()
                if self.metadata.expires_at
                else None,
                "tags": self.metadata.tags,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Context:
        """Create from dictionary"""
        metadata = data.get("metadata", {})

        return cls(
            id=data.get("id", f"ctx_{uuid.uuid4().hex[:12]}"),
            scope=ContextScope(data.get("scope", "request")),
            parent_id=data.get("parent_id"),
            data=data.get("data", {}),
            metadata=ContextMetadata(
                created_at=datetime.fromisoformat(metadata.get("created_at"))
                if metadata.get("created_at")
                else datetime.now(UTC),
                created_by=metadata.get("created_by"),
                expires_at=datetime.fromisoformat(metadata["expires_at"])
                if metadata.get("expires_at")
                else None,
                tags=metadata.get("tags", []),
            ),
        )


# Context variable for async context propagation
_current_context: contextvars.ContextVar[Context | None] = contextvars.ContextVar(
    "current_context", default=None
)


class ContextManager:
    """
    Centralized context management

    Features:
    - Context lifecycle management
    - Scope-based access control
    - Cross-agent context sharing
    - Context inheritance

    Example:
        manager = ContextManager()

        # Create and enter context
        ctx = manager.create_context(ContextScope.REQUEST)
        ctx.set("user_id", "user_123")

        with manager.use_context(ctx):
            # Context is active here
            current = manager.get_current()
            print(current.get("user_id"))  # "user_123"
    """

    def __init__(self):
        self._contexts: dict[str, Context] = {}
        self._global_context = Context(
            id="global",
            scope=ContextScope.GLOBAL,
        )
        self._contexts["global"] = self._global_context

        logger.info("🔄 ContextManager initialized")

    @property
    def global_context(self) -> Context:
        """Get global context"""
        return self._global_context

    def create_context(
        self,
        scope: ContextScope = ContextScope.REQUEST,
        parent: Context | None = None,
        data: dict[str, Any] | None = None,
        inherit_data: bool = True,
    ) -> Context:
        """Create new context"""
        if parent and inherit_data:
            ctx = parent.create_child(scope, inherit_data=True)
            if data:
                ctx.update(data)
        else:
            ctx = Context(
                scope=scope,
                parent_id=parent.id if parent else None,
                data=data or {},
            )

        self._contexts[ctx.id] = ctx
        logger.debug(f"Created context: {ctx.id} [{scope.value}]")

        return ctx

    def get_context(self, context_id: str) -> Context | None:
        """Get context by ID"""
        return self._contexts.get(context_id)

    def get_current(self) -> Context | None:
        """Get current active context"""
        return _current_context.get()

    def set_current(self, context: Context) -> None:
        """Set current context"""
        _current_context.set(context)

    def use_context(self, context: Context):
        """Context manager for using a context"""
        return _ContextScope(self, context)

    def delete_context(self, context_id: str) -> bool:
        """Delete context"""
        if context_id in self._contexts and context_id != "global":
            del self._contexts[context_id]
            logger.debug(f"Deleted context: {context_id}")
            return True
        return False

    def cleanup_expired(self) -> int:
        """Clean up expired contexts"""
        expired = [
            ctx_id
            for ctx_id, ctx in self._contexts.items()
            if ctx.metadata.is_expired() and ctx_id != "global"
        ]

        for ctx_id in expired:
            del self._contexts[ctx_id]

        if expired:
            logger.info(f"Cleaned up {len(expired)} expired contexts")

        return len(expired)

    def get_children(self, context_id: str) -> list[Context]:
        """Get child contexts"""
        return [ctx for ctx in self._contexts.values() if ctx.parent_id == context_id]

    def get_lineage(self, context_id: str) -> list[Context]:
        """Get context lineage (ancestors)"""
        lineage = []
        current = self._contexts.get(context_id)

        while current:
            lineage.append(current)
            if current.parent_id:
                current = self._contexts.get(current.parent_id)
            else:
                break

        return lineage

    def share_context(
        self,
        source_id: str,
        target_id: str,
        keys: list[str] | None = None,
    ) -> None:
        """Share context data between contexts"""
        source = self._contexts.get(source_id)
        target = self._contexts.get(target_id)

        if not source or not target:
            raise KeyError("Source or target context not found")

        if keys:
            for key in keys:
                if source.has(key):
                    target.set(key, source.get(key))
        else:
            target.merge_from(source)

        logger.debug(f"Shared context: {source_id} -> {target_id}")

    def get_stats(self) -> dict[str, Any]:
        """Get manager statistics"""
        by_scope = {}
        for ctx in self._contexts.values():
            scope_name = ctx.scope.value
            by_scope[scope_name] = by_scope.get(scope_name, 0) + 1

        return {
            "total_contexts": len(self._contexts),
            "by_scope": by_scope,
            "active_context": self.get_current().id if self.get_current() else None,
        }


class _ContextScope:
    """Context manager helper for entering/exiting context"""

    def __init__(self, manager: ContextManager, context: Context):
        self.manager = manager
        self.context = context
        self.token = None

    def __enter__(self) -> Context:
        self.token = _current_context.set(self.context)
        return self.context

    def __exit__(self, exc_type, exc_val, exc_tb):
        _current_context.reset(self.token)
        return False

    async def __aenter__(self) -> Context:
        self.token = _current_context.set(self.context)
        return self.context

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        _current_context.reset(self.token)
        return False


# Convenience functions
def get_current_context() -> Context | None:
    """Get current context"""
    return _current_context.get()


def set_context_value(key: str, value: Any) -> None:
    """Set value in current context"""
    ctx = _current_context.get()
    if ctx:
        ctx.set(key, value)


def get_context_value(key: str, default: Any = None) -> Any:
    """Get value from current context"""
    ctx = _current_context.get()
    if ctx:
        return ctx.get(key, default)
    return default


# Global instance
_global_context_manager: ContextManager | None = None


def get_context_manager() -> ContextManager:
    """Get global context manager"""
    global _global_context_manager
    if _global_context_manager is None:
        _global_context_manager = ContextManager()
    return _global_context_manager


__all__ = [
    "Context",
    "ContextManager",
    "ContextMetadata",
    "ContextScope",
    "get_context_manager",
    "get_context_value",
    "get_current_context",
    "set_context_value",
]
