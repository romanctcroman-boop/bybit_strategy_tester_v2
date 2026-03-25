"""
Chat Conversation model

Persists AI Studio chat history to the main database so conversations survive
restarts and can be filtered efficiently.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, Index, String, Text

from backend.database import Base


class ChatConversation(Base):
    """Server-side chat conversation history."""

    __tablename__ = "chat_conversations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    prompt = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    reasoning = Column(Text, nullable=True)
    tab = Column(String(50), nullable=False, index=True)
    agent = Column(String(50), nullable=False, index=True)
    title = Column(String(200), nullable=True)
    starred = Column(Boolean, nullable=False, default=False, index=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        Index("ix_chat_conversations_tab_created_at", "tab", "created_at"),
        Index("ix_chat_conversations_agent_created_at", "agent", "created_at"),
    )

    def to_dict(self) -> dict:
        """Return a dict representation used by API responses."""

        return {
            "id": self.id,
            "prompt": self.prompt,
            "response": self.response,
            "reasoning": self.reasoning,
            "tab": self.tab,
            "agent": self.agent,
            "title": self.title,
            "starred": self.starred,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
