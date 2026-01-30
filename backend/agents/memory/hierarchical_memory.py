"""
Hierarchical Memory System for Autonomous AI Agents

Implements a multi-layered memory architecture inspired by human cognition:
- Working Memory: Immediate context, high priority, short TTL
- Episodic Memory: Session-specific experiences
- Semantic Memory: Generalized knowledge extracted from episodes
- Procedural Memory: Learned skills and action patterns

References:
- Anthropic "Building Effective Agents" (2025)
- "The Illustrated Guide to AI Agent Architecture" (2025)
- Cognitive architectures: LIDA, Sigma, ACT-R
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from loguru import logger

# Constants
MAX_WORKING_MEMORY_ITEMS = 10
MAX_EPISODIC_MEMORY_ITEMS = 1000
MAX_SEMANTIC_MEMORY_ITEMS = 10000
MAX_PROCEDURAL_MEMORY_ITEMS = 500


class MemoryType(Enum):
    """Types of memory in the hierarchical system"""

    WORKING = "working"  # Current context, very short-term
    EPISODIC = "episodic"  # Session-specific events and experiences
    SEMANTIC = "semantic"  # Generalized knowledge, facts, concepts
    PROCEDURAL = "procedural"  # Learned skills, patterns, procedures


@dataclass
class MemoryTier:
    """Configuration for a memory tier"""

    name: str
    memory_type: MemoryType
    max_items: int
    ttl: timedelta
    priority: int  # Higher = more important for retention
    consolidation_threshold: float = 0.5  # Min importance to consolidate up


@dataclass
class MemoryItem:
    """A single memory item"""

    id: str
    content: str
    memory_type: MemoryType
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    accessed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    access_count: int = 0
    importance: float = 0.5  # 0.0 to 1.0
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    source: Optional[str] = None
    related_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type.value,
            "created_at": self.created_at.isoformat(),
            "accessed_at": self.accessed_at.isoformat(),
            "access_count": self.access_count,
            "importance": self.importance,
            "metadata": self.metadata,
            "tags": self.tags,
            "source": self.source,
            "related_ids": self.related_ids,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryItem":
        """Create from dictionary"""
        return cls(
            id=data["id"],
            content=data["content"],
            memory_type=MemoryType(data["memory_type"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            accessed_at=datetime.fromisoformat(data["accessed_at"]),
            access_count=data.get("access_count", 0),
            importance=data.get("importance", 0.5),
            metadata=data.get("metadata", {}),
            tags=data.get("tags", []),
            source=data.get("source"),
            related_ids=data.get("related_ids", []),
        )

    def is_expired(self, ttl: timedelta) -> bool:
        """Check if memory has expired based on TTL"""
        now = datetime.now(timezone.utc)
        return (now - self.created_at) > ttl

    def update_access(self) -> None:
        """Update access time and count"""
        self.accessed_at = datetime.now(timezone.utc)
        self.access_count += 1
        # Slightly increase importance based on access
        self.importance = min(1.0, self.importance + 0.01)


class HierarchicalMemory:
    """
    Multi-layered memory system for autonomous AI agents

    Implements cognitive-inspired memory architecture with:
    - Automatic tier management and TTL expiration
    - Importance-based retention
    - Memory consolidation (short-term → long-term)
    - Semantic search via embeddings
    - Intelligent forgetting

    Example:
        memory = HierarchicalMemory(persist_path="./agent_memory")

        # Store in working memory
        await memory.store(
            content="User asked about RSI calculation",
            memory_type=MemoryType.WORKING,
            importance=0.8,
            tags=["trading", "indicators"]
        )

        # Recall relevant memories
        results = await memory.recall(
            query="How to calculate RSI?",
            memory_type=MemoryType.SEMANTIC,
            top_k=5
        )

        # Consolidate memories (like sleep)
        await memory.consolidate()
    """

    def __init__(
        self,
        persist_path: Optional[str] = None,
        embedding_fn: Optional[Callable[[str], List[float]]] = None,
    ):
        """
        Initialize hierarchical memory

        Args:
            persist_path: Path for persistent storage (None = in-memory only)
            embedding_fn: Function to generate embeddings for semantic search
        """
        self.persist_path = Path(persist_path) if persist_path else None
        self.embedding_fn = embedding_fn

        # Define memory tiers
        self.tiers: Dict[MemoryType, MemoryTier] = {
            MemoryType.WORKING: MemoryTier(
                name="Working Memory",
                memory_type=MemoryType.WORKING,
                max_items=MAX_WORKING_MEMORY_ITEMS,
                ttl=timedelta(minutes=5),
                priority=1,
                consolidation_threshold=0.7,
            ),
            MemoryType.EPISODIC: MemoryTier(
                name="Episodic Memory",
                memory_type=MemoryType.EPISODIC,
                max_items=MAX_EPISODIC_MEMORY_ITEMS,
                ttl=timedelta(days=7),
                priority=2,
                consolidation_threshold=0.6,
            ),
            MemoryType.SEMANTIC: MemoryTier(
                name="Semantic Memory",
                memory_type=MemoryType.SEMANTIC,
                max_items=MAX_SEMANTIC_MEMORY_ITEMS,
                ttl=timedelta(days=365),
                priority=3,
                consolidation_threshold=0.5,
            ),
            MemoryType.PROCEDURAL: MemoryTier(
                name="Procedural Memory",
                memory_type=MemoryType.PROCEDURAL,
                max_items=MAX_PROCEDURAL_MEMORY_ITEMS,
                ttl=timedelta(days=365 * 10),  # Very long-term
                priority=4,
                consolidation_threshold=0.8,
            ),
        }

        # Memory stores
        self.stores: Dict[MemoryType, Dict[str, MemoryItem]] = {tier: {} for tier in MemoryType}

        # Statistics
        self.stats = {
            "total_stored": 0,
            "total_recalled": 0,
            "consolidations": 0,
            "forgettings": 0,
        }

        # Load persisted memories if available
        if self.persist_path:
            self._load_from_disk()

        logger.info(
            f"🧠 HierarchicalMemory initialized "
            f"(persist={self.persist_path is not None}, "
            f"embedding={self.embedding_fn is not None})"
        )

    async def store(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.WORKING,
        importance: float = 0.5,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        source: Optional[str] = None,
    ) -> MemoryItem:
        """
        Store content in specified memory tier

        Args:
            content: Text content to store
            memory_type: Which tier to store in
            importance: Importance score (0.0 to 1.0)
            tags: Optional tags for categorization
            metadata: Optional metadata dict
            source: Optional source identifier

        Returns:
            Created MemoryItem
        """
        # Generate ID based on content hash
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
        item_id = f"{memory_type.value}_{content_hash}_{int(time.time())}"

        # Generate embedding if function provided
        embedding = None
        if self.embedding_fn:
            try:
                embedding = await asyncio.to_thread(self.embedding_fn, content)
            except Exception as e:
                logger.warning(f"Failed to generate embedding: {e}")

        # Create memory item
        item = MemoryItem(
            id=item_id,
            content=content,
            memory_type=memory_type,
            importance=max(0.0, min(1.0, importance)),
            embedding=embedding,
            tags=tags or [],
            metadata=metadata or {},
            source=source,
        )

        # Add to store
        tier = self.tiers[memory_type]
        store = self.stores[memory_type]

        # Check capacity and evict if necessary
        if len(store) >= tier.max_items:
            await self._evict_lowest_importance(memory_type)

        store[item.id] = item
        self.stats["total_stored"] += 1

        # Persist if enabled
        if self.persist_path:
            await self._persist_item(item)

        logger.debug(f"📝 Stored memory [{memory_type.value}]: {content[:50]}... (importance={importance:.2f})")

        return item

    async def recall(
        self,
        query: str,
        memory_type: Optional[MemoryType] = None,
        top_k: int = 5,
        min_importance: float = 0.0,
        tags: Optional[List[str]] = None,
        use_semantic: bool = True,
    ) -> List[MemoryItem]:
        """
        Recall memories matching query

        Args:
            query: Search query
            memory_type: Specific tier to search (None = all)
            top_k: Maximum number of results
            min_importance: Minimum importance threshold
            tags: Filter by tags
            use_semantic: Use embedding similarity if available

        Returns:
            List of matching MemoryItems
        """
        results: List[tuple[float, MemoryItem]] = []

        # Determine which tiers to search
        tiers_to_search = [memory_type] if memory_type else list(MemoryType)

        # Get query embedding if semantic search enabled
        query_embedding = None
        if use_semantic and self.embedding_fn:
            try:
                query_embedding = await asyncio.to_thread(self.embedding_fn, query)
            except Exception as e:
                logger.warning(f"Failed to get query embedding: {e}")

        for tier_type in tiers_to_search:
            store = self.stores[tier_type]
            tier = self.tiers[tier_type]

            for item in store.values():
                # Skip expired items
                if item.is_expired(tier.ttl):
                    continue

                # Filter by importance
                if item.importance < min_importance:
                    continue

                # Filter by tags
                if tags and not any(t in item.tags for t in tags):
                    continue

                # Calculate relevance score
                score = self._calculate_relevance(item, query, query_embedding)

                results.append((score, item))

        # Sort by score and take top_k
        results.sort(key=lambda x: x[0], reverse=True)
        top_results = [item for _, item in results[:top_k]]

        # Update access stats for recalled items
        for item in top_results:
            item.update_access()

        self.stats["total_recalled"] += len(top_results)

        logger.debug(f"🔍 Recalled {len(top_results)} memories for query: {query[:30]}...")

        return top_results

    async def get(self, item_id: str) -> Optional[MemoryItem]:
        """Get specific memory by ID"""
        for store in self.stores.values():
            if item_id in store:
                item = store[item_id]
                item.update_access()
                return item
        return None

    async def delete(self, item_id: str) -> bool:
        """Delete specific memory by ID"""
        for memory_type, store in self.stores.items():
            if item_id in store:
                del store[item_id]
                if self.persist_path:
                    await self._delete_persisted(item_id, memory_type)
                return True
        return False

    async def consolidate(self) -> Dict[str, int]:
        """
        Consolidate memories between tiers (like sleep consolidation)

        This process:
        1. Moves high-importance working memories to episodic
        2. Extracts patterns from episodic → semantic
        3. Identifies repeated actions → procedural

        Returns:
            Dict with consolidation statistics
        """
        consolidated = {
            "working_to_episodic": 0,
            "episodic_to_semantic": 0,
            "to_procedural": 0,
        }

        # Working → Episodic: Important short-term memories
        working_store = self.stores[MemoryType.WORKING]
        working_tier = self.tiers[MemoryType.WORKING]

        items_to_consolidate = []
        for item_id, item in list(working_store.items()):
            # Check if item should be consolidated based on importance
            if item.importance >= working_tier.consolidation_threshold:
                items_to_consolidate.append(item)

        for item in items_to_consolidate:
            # Create episodic memory from working
            new_item = await self.store(
                content=item.content,
                memory_type=MemoryType.EPISODIC,
                importance=item.importance,
                tags=item.tags + ["consolidated_from_working"],
                metadata={**item.metadata, "original_id": item.id},
                source=item.source,
            )
            new_item.related_ids.append(item.id)

            # Remove from working memory
            del working_store[item.id]
            consolidated["working_to_episodic"] += 1

        # Episodic → Semantic: Extract patterns and generalizations
        episodic_store = self.stores[MemoryType.EPISODIC]
        episodic_tier = self.tiers[MemoryType.EPISODIC]

        # Group episodic memories by tags for pattern extraction
        tag_groups: Dict[str, List[MemoryItem]] = {}
        for item in episodic_store.values():
            for tag in item.tags:
                if tag not in tag_groups:
                    tag_groups[tag] = []
                tag_groups[tag].append(item)

        # Extract semantic knowledge from groups with multiple items
        for tag, items in tag_groups.items():
            if len(items) >= 3:  # Need multiple instances to extract pattern
                avg_importance = sum(i.importance for i in items) / len(items)
                if avg_importance >= episodic_tier.consolidation_threshold:
                    # Create semantic summary
                    summary = await self._create_semantic_summary(items, tag)
                    if summary:
                        await self.store(
                            content=summary,
                            memory_type=MemoryType.SEMANTIC,
                            importance=avg_importance,
                            tags=[tag, "extracted_pattern"],
                            metadata={
                                "source_count": len(items),
                                "source_ids": [i.id for i in items],
                            },
                        )
                        consolidated["episodic_to_semantic"] += 1

        self.stats["consolidations"] += 1

        logger.info(f"🧬 Consolidated memories: {consolidated}")
        return consolidated

    async def forget(self) -> Dict[str, int]:
        """
        Intelligent forgetting - remove low-relevance and expired items

        Implements:
        1. TTL-based expiration
        2. Importance decay
        3. Capacity-based eviction

        Returns:
            Dict with forgetting statistics
        """
        forgotten = {tier.value: 0 for tier in MemoryType}

        now = datetime.now(timezone.utc)

        for memory_type, store in self.stores.items():
            tier = self.tiers[memory_type]

            items_to_forget = []

            for item_id, item in store.items():
                # Check TTL expiration
                if item.is_expired(tier.ttl):
                    items_to_forget.append(item_id)
                    continue

                # Apply importance decay based on time since access
                time_since_access = (now - item.accessed_at).total_seconds()
                decay_rate = 0.001  # 0.1% per hour
                decay = (time_since_access / 3600) * decay_rate
                item.importance = max(0.0, item.importance - decay)

                # Forget very low importance items
                if item.importance < 0.1 and item.access_count < 2:
                    items_to_forget.append(item_id)

            for item_id in items_to_forget:
                del store[item_id]
                if self.persist_path:
                    await self._delete_persisted(item_id, memory_type)
                forgotten[memory_type.value] += 1

        total_forgotten = sum(forgotten.values())
        if total_forgotten > 0:
            self.stats["forgettings"] += total_forgotten
            logger.info(f"🗑️ Forgot {total_forgotten} memories: {forgotten}")

        return forgotten

    async def _evict_lowest_importance(self, memory_type: MemoryType) -> None:
        """Evict lowest importance item from tier"""
        store = self.stores[memory_type]

        if not store:
            return

        lowest_item = min(store.values(), key=lambda x: (x.importance, -x.access_count))

        del store[lowest_item.id]
        logger.debug(f"⏏️ Evicted low-importance memory: {lowest_item.id}")

    def _calculate_relevance(
        self,
        item: MemoryItem,
        query: str,
        query_embedding: Optional[List[float]],
    ) -> float:
        """Calculate relevance score for an item"""
        score = 0.0

        # Text-based matching (simple keyword overlap)
        query_words = set(query.lower().split())
        content_words = set(item.content.lower().split())
        overlap = len(query_words & content_words) / max(len(query_words), 1)
        score += overlap * 0.3

        # Embedding similarity if available
        if query_embedding and item.embedding:
            similarity = self._cosine_similarity(query_embedding, item.embedding)
            score += similarity * 0.5

        # Importance boost
        score += item.importance * 0.1

        # Recency boost (more recent = higher score)
        now = datetime.now(timezone.utc)
        age_hours = (now - item.accessed_at).total_seconds() / 3600
        recency_score = 1.0 / (1.0 + age_hours / 24)  # Decay over days
        score += recency_score * 0.1

        return score

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        import math

        if len(a) != len(b):
            return 0.0

        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    async def _create_semantic_summary(
        self,
        items: List[MemoryItem],
        topic: str,
    ) -> Optional[str]:
        """Create semantic summary from multiple episodic memories"""
        # Simple summary - could be enhanced with AI
        contents = [item.content for item in items]

        # For now, just combine unique sentences
        unique_sentences = []
        for content in contents:
            sentences = content.split(". ")
            for sentence in sentences:
                if sentence and sentence not in unique_sentences:
                    unique_sentences.append(sentence)

        if len(unique_sentences) > 5:
            # Take most important based on frequency
            unique_sentences = unique_sentences[:5]

        return f"[{topic}] " + ". ".join(unique_sentences)

    def _load_from_disk(self) -> None:
        """Load persisted memories from disk"""
        if not self.persist_path:
            return

        for memory_type in MemoryType:
            tier_path = self.persist_path / memory_type.value
            if not tier_path.exists():
                tier_path.mkdir(parents=True, exist_ok=True)
                continue

            for file_path in tier_path.glob("*.json"):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        item = MemoryItem.from_dict(data)
                        self.stores[memory_type][item.id] = item
                except Exception as e:
                    logger.warning(f"Failed to load memory {file_path}: {e}")

        total = sum(len(store) for store in self.stores.values())
        logger.info(f"📂 Loaded {total} persisted memories")

    async def _persist_item(self, item: MemoryItem) -> None:
        """Persist single memory item to disk"""
        if not self.persist_path:
            return

        tier_path = self.persist_path / item.memory_type.value
        tier_path.mkdir(parents=True, exist_ok=True)

        file_path = tier_path / f"{item.id}.json"

        try:
            data = item.to_dict()
            # Don't persist embeddings to save space
            data.pop("embedding", None)

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to persist memory {item.id}: {e}")

    async def _delete_persisted(self, item_id: str, memory_type: MemoryType) -> None:
        """Delete persisted memory file"""
        if not self.persist_path:
            return

        file_path = self.persist_path / memory_type.value / f"{item_id}.json"

        try:
            if file_path.exists():
                file_path.unlink()
        except Exception as e:
            logger.warning(f"Failed to delete persisted memory {item_id}: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get memory system statistics"""
        tier_stats = {}
        for memory_type, store in self.stores.items():
            tier = self.tiers[memory_type]
            tier_stats[memory_type.value] = {
                "count": len(store),
                "max_items": tier.max_items,
                "utilization": len(store) / tier.max_items if tier.max_items > 0 else 0,
            }

        return {
            **self.stats,
            "tiers": tier_stats,
        }


class MemoryConsolidator:
    """
    Background memory consolidation process

    Runs periodically to:
    1. Consolidate important memories
    2. Forget expired/irrelevant memories
    3. Maintain memory health
    """

    def __init__(
        self,
        memory: HierarchicalMemory,
        consolidation_interval: timedelta = timedelta(hours=1),
        forgetting_interval: timedelta = timedelta(minutes=15),
    ):
        self.memory = memory
        self.consolidation_interval = consolidation_interval
        self.forgetting_interval = forgetting_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start background consolidation"""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("🔄 Memory consolidator started")

    async def stop(self) -> None:
        """Stop background consolidation"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("⏹️ Memory consolidator stopped")

    async def _run_loop(self) -> None:
        """Main consolidation loop"""
        last_consolidation = datetime.now(timezone.utc)
        last_forgetting = datetime.now(timezone.utc)

        while self._running:
            now = datetime.now(timezone.utc)

            # Check if it's time to consolidate
            if (now - last_consolidation) >= self.consolidation_interval:
                try:
                    await self.memory.consolidate()
                    last_consolidation = now
                except Exception as e:
                    logger.error(f"Consolidation error: {e}")

            # Check if it's time to forget
            if (now - last_forgetting) >= self.forgetting_interval:
                try:
                    await self.memory.forget()
                    last_forgetting = now
                except Exception as e:
                    logger.error(f"Forgetting error: {e}")

            # Sleep briefly
            await asyncio.sleep(60)  # Check every minute


__all__ = [
    "HierarchicalMemory",
    "MemoryItem",
    "MemoryType",
    "MemoryTier",
    "MemoryConsolidator",
]
