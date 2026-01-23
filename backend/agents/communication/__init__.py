"""
Agent Communication Module

Provides inter-agent communication infrastructure.
"""

from .protocol import (
    MessageType,
    MessagePriority,
    AgentInfo,
    Message,
    MessageHandler,
    Subscription,
    MessageBroker,
    AgentCommunicator,
    get_message_broker,
)

__all__ = [
    "MessageType",
    "MessagePriority",
    "AgentInfo",
    "Message",
    "MessageHandler",
    "Subscription",
    "MessageBroker",
    "AgentCommunicator",
    "get_message_broker",
]
