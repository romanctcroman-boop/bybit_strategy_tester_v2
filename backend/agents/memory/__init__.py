"""
Multi-Layered Memory System for AI Agents

This module provides hierarchical memory management for autonomous AI agents:
- Working Memory: Short-term context (5 min TTL)
- Episodic Memory: Session-based memories (7 day TTL)
- Semantic Memory: Long-term knowledge (365 day TTL)
- Procedural Memory: Learned skills and patterns (permanent)
- Vector Memory: Embedding-based semantic search

Based on cognitive science research and 2025 AI agent best practices.
"""

from backend.agents.memory.hierarchical_memory import (
    HierarchicalMemory,
    MemoryItem,
    MemoryTier,
    MemoryConsolidator,
)
from backend.agents.memory.vector_store import VectorMemoryStore

__all__ = [
    "HierarchicalMemory",
    "MemoryItem",
    "MemoryTier",
    "MemoryConsolidator",
    "VectorMemoryStore",
]
