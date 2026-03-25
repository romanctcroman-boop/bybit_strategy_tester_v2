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

from backend.agents.memory.auto_tagger import AutoTagger, get_auto_tagger
from backend.agents.memory.bm25_ranker import BM25Ranker
from backend.agents.memory.hierarchical_memory import (
    HierarchicalMemory,
    MemoryConsolidator,
    MemoryItem,
    MemoryTier,
    UnifiedMemoryItem,
)
from backend.agents.memory.tag_normalizer import TagNormalizer, get_tag_normalizer
from backend.agents.memory.vector_store import VectorMemoryStore

# Backward compatibility: PersistentMemoryItem was removed in P1.2.
# Any code importing it from the old sqlite_backend module should use MemoryItem
# instead, but we provide a deprecation alias here.
PersistentMemoryItem = MemoryItem

__all__ = [
    "AutoTagger",
    "BM25Ranker",
    "HierarchicalMemory",
    "MemoryConsolidator",
    "MemoryItem",
    "MemoryTier",
    "PersistentMemoryItem",
    "TagNormalizer",
    "UnifiedMemoryItem",
    "VectorMemoryStore",
    "get_auto_tagger",
    "get_tag_normalizer",
]
