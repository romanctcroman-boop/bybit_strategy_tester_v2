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
import contextlib
import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

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
    """
    Unified memory item — single dataclass for the entire memory subsystem.

    Replaces the former dual-dataclass anti-pattern (MemoryItem + PersistentMemoryItem)
    identified in Phase 13 architecture audit (3/3 agents, HIGH severity).

    Fields:
        id:               Unique identifier (content hash + timestamp)
        content:          Text content of the memory
        memory_type:      Tier enum (WORKING / EPISODIC / SEMANTIC / PROCEDURAL)
        agent_namespace:  Per-agent isolation key ("shared" for cross-agent data)
        created_at:       UTC datetime of creation
        accessed_at:      UTC datetime of last access
        access_count:     Number of times recalled
        importance:       Relevance score 0.0-1.0
        ttl_seconds:      Optional per-item TTL override (None = use tier default)
        embedding:        Optional vector (384-dim MiniLM) for semantic search
        metadata:         Arbitrary key-value metadata
        tags:             Categorization tags (normalized by TagNormalizer)
        source:           Origin identifier (agent name, "deliberation", etc.)
        related_ids:      Links to related memory items
    """

    id: str
    content: str
    memory_type: MemoryType
    agent_namespace: str = "shared"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    accessed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    access_count: int = 0
    importance: float = 0.5  # 0.0 to 1.0
    ttl_seconds: float | None = None  # None = use tier default
    embedding: list[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    source: str | None = None
    related_ids: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate fields after initialization."""
        self.importance = max(0.0, min(1.0, self.importance))
        if isinstance(self.memory_type, str):
            self.memory_type = MemoryType(self.memory_type)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization (lossless roundtrip)."""
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type.value,
            "agent_namespace": self.agent_namespace,
            "created_at": self.created_at.isoformat(),
            "accessed_at": self.accessed_at.isoformat(),
            "access_count": self.access_count,
            "importance": self.importance,
            "ttl_seconds": self.ttl_seconds,
            "metadata": self.metadata,
            "tags": self.tags,
            "source": self.source,
            "related_ids": self.related_ids,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryItem:
        """Create from dictionary (lossless roundtrip with to_dict)."""
        created_at = data.get("created_at")
        accessed_at = data.get("accessed_at")

        # Handle both datetime ISO strings and float timestamps (legacy)
        if isinstance(created_at, (int, float)):
            created_at = datetime.fromtimestamp(created_at, tz=UTC)
        elif isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        else:
            created_at = datetime.now(UTC)

        if isinstance(accessed_at, (int, float)):
            accessed_at = datetime.fromtimestamp(accessed_at, tz=UTC)
        elif isinstance(accessed_at, str):
            accessed_at = datetime.fromisoformat(accessed_at)
        else:
            accessed_at = datetime.now(UTC)

        # Handle memory_type as string or enum
        memory_type_raw = data.get("memory_type", "working")
        if isinstance(memory_type_raw, str):
            # Strip legacy "hierarchical." prefix if present
            memory_type_raw = memory_type_raw.replace("hierarchical.", "")
            memory_type = MemoryType(memory_type_raw)
        else:
            memory_type = memory_type_raw

        return cls(
            id=data["id"],
            content=data["content"],
            memory_type=memory_type,
            agent_namespace=data.get("agent_namespace", "shared"),
            created_at=created_at,
            accessed_at=accessed_at,
            access_count=data.get("access_count", 0),
            importance=data.get("importance", 0.5),
            ttl_seconds=data.get("ttl_seconds"),
            metadata=data.get("metadata", {}),
            tags=data.get("tags", []),
            source=data.get("source"),
            related_ids=data.get("related_ids", []),
        )

    def is_expired(self, ttl: timedelta) -> bool:
        """Check if memory has expired based on TTL."""
        # Per-item TTL override takes priority
        if self.ttl_seconds is not None:
            return (datetime.now(UTC) - self.created_at).total_seconds() > self.ttl_seconds
        return (datetime.now(UTC) - self.created_at) > ttl

    def update_access(self) -> None:
        """Update access time and count."""
        self.accessed_at = datetime.now(UTC)
        self.access_count += 1
        # Slightly increase importance based on access
        self.importance = min(1.0, self.importance + 0.01)


# Backward compatibility alias (TZ P1.4 — memory evolution plan)
UnifiedMemoryItem = MemoryItem


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
        persist_path: str | None = None,
        embedding_fn: Callable[[str], list[float]] | None = None,
        backend: Any | None = None,
    ):
        """
        Initialize hierarchical memory

        Args:
            persist_path: Path for persistent storage (None = in-memory only)
            embedding_fn: Function to generate embeddings for semantic search
            backend: Optional MemoryBackend instance (overrides persist_path).
                     Use SQLiteBackendAdapter for SQLite persistence or
                     JsonFileBackend for legacy file-per-item storage.
        """
        self.persist_path = Path(persist_path) if persist_path else None
        self.embedding_fn = embedding_fn

        # Backend for persistence (ABC-compliant)
        self._backend: Any | None = backend
        if self._backend is None and self.persist_path:
            # Default: use legacy JsonFileBackend for backward compatibility
            from backend.agents.memory.backend_interface import JsonFileBackend

            self._backend = JsonFileBackend(self.persist_path)

        # Define memory tiers
        self.tiers: dict[MemoryType, MemoryTier] = {
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
        self.stores: dict[MemoryType, dict[str, MemoryItem]] = {tier: {} for tier in MemoryType}

        # BM25 keyword ranker (P4: Hybrid Retrieval)
        from backend.agents.memory.bm25_ranker import BM25Ranker

        self._bm25 = BM25Ranker()

        # Statistics
        self.stats = {
            "total_stored": 0,
            "total_recalled": 0,
            "consolidations": 0,
            "forgettings": 0,
        }

        # Load persisted memories if available
        if self._backend:
            self._load_from_disk()

        logger.info(
            f"🧠 HierarchicalMemory initialized "
            f"(backend={type(self._backend).__name__ if self._backend else 'None'}, "
            f"embedding={self.embedding_fn is not None})"
        )

    async def store(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.WORKING,
        importance: float = 0.5,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        source: str | None = None,
        agent_namespace: str = "shared",
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
            agent_namespace: Per-agent isolation key ("shared" for cross-agent)

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
            agent_namespace=agent_namespace,
            importance=max(0.0, min(1.0, importance)),
            embedding=embedding,
            tags=tags or [],
            metadata=metadata or {},
            source=source,
        )

        # P3: Auto-tag and normalize tags
        try:
            from backend.agents.memory.auto_tagger import get_auto_tagger
            from backend.agents.memory.tag_normalizer import get_tag_normalizer

            tagger = get_auto_tagger()
            item.tags = tagger.generate_tags(
                content=content,
                metadata=metadata,
                source=source,
                agent_namespace=agent_namespace,
                existing_tags=item.tags,
            )
        except Exception as e:
            # Fallback: just normalize existing tags
            try:
                normalizer = get_tag_normalizer()
                item.tags = normalizer.normalize_list(item.tags)
            except Exception:
                pass
            logger.debug(f"AutoTagger unavailable, using basic normalization: {e}")

        # Add to store
        tier = self.tiers[memory_type]
        store = self.stores[memory_type]

        # Check capacity and evict if necessary
        if len(store) >= tier.max_items:
            await self._evict_lowest_importance(memory_type)

        store[item.id] = item
        self.stats["total_stored"] += 1

        # Index in BM25 for hybrid recall (P4)
        self._bm25.add_document(item.id, content)

        # Persist if enabled
        if self._backend:
            await self._persist_item(item)

        logger.debug(f"📝 Stored memory [{memory_type.value}]: {content[:50]}... (importance={importance:.2f})")

        return item

    async def recall(
        self,
        query: str,
        memory_type: MemoryType | None = None,
        top_k: int = 5,
        min_importance: float = 0.0,
        tags: list[str] | None = None,
        use_semantic: bool = True,
        agent_namespace: str | None = None,
    ) -> list[MemoryItem]:
        """
        Recall memories matching query

        Args:
            query: Search query
            memory_type: Specific tier to search (None = all)
            top_k: Maximum number of results
            min_importance: Minimum importance threshold
            tags: Filter by tags
            use_semantic: Use embedding similarity if available
            agent_namespace: Filter by namespace (None = all namespaces)

        Returns:
            List of matching MemoryItems
        """
        results: list[tuple[float, MemoryItem]] = []

        # Determine which tiers to search
        tiers_to_search = [memory_type] if memory_type else list(MemoryType)

        # Get query embedding if semantic search enabled
        query_embedding = None
        if use_semantic and self.embedding_fn:
            try:
                query_embedding = await asyncio.to_thread(self.embedding_fn, query)
            except Exception as e:
                logger.warning(f"Failed to get query embedding: {e}")

        # P4.3: Warn on degraded mode (no vector embeddings)
        if query_embedding is None and use_semantic:
            logger.debug(
                "⚠️ Recall running in degraded mode (no embeddings). "
                "BM25-only scoring active — semantic similarity disabled."
            )

        # P4.1: Structured filter stage — collect candidates
        candidates = self._structured_filter(
            tiers=tiers_to_search,
            min_importance=min_importance,
            tags=tags,
            agent_namespace=agent_namespace,
        )

        # Score each candidate
        for item in candidates:
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

    async def get(self, item_id: str) -> MemoryItem | None:
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
                if self._backend:
                    await self._delete_persisted(item_id, memory_type)
                return True
        return False

    async def consolidate(self) -> dict[str, int]:
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
        for _item_id, item in list(working_store.items()):
            # Check if item should be consolidated based on importance
            if item.importance >= working_tier.consolidation_threshold:
                items_to_consolidate.append(item)

        for item in items_to_consolidate:
            # Create episodic memory from working
            new_item = await self.store(
                content=item.content,
                memory_type=MemoryType.EPISODIC,
                importance=item.importance,
                tags=[*item.tags, "consolidated_from_working"],
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
        # P3: Use canonical (normalized) tags for grouping to unblock
        # consolidation when agents use different tag forms.
        try:
            from backend.agents.memory.tag_normalizer import get_tag_normalizer

            normalizer = get_tag_normalizer()
        except Exception:
            normalizer = None

        tag_groups: dict[str, list[MemoryItem]] = {}
        for item in episodic_store.values():
            tags = normalizer.normalize_list(item.tags) if normalizer else item.tags
            for tag in tags:
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

    async def forget(self) -> dict[str, int]:
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

        now = datetime.now(UTC)

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
                self._bm25.remove_document(item_id)
                if self._backend:
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
        self._bm25.remove_document(lowest_item.id)
        logger.debug(f"⏏️ Evicted low-importance memory: {lowest_item.id}")

    def _structured_filter(
        self,
        tiers: list[MemoryType],
        min_importance: float = 0.0,
        tags: list[str] | None = None,
        agent_namespace: str | None = None,
    ) -> list[MemoryItem]:
        """P4.1: Structured filter stage — pre-filter candidates before scoring.

        Applies deterministic, zero-cost filters before the expensive
        BM25 / cosine scoring pass:
          1. TTL expiration check
          2. Agent namespace isolation (pass-through for "shared")
          3. Minimum importance threshold
          4. Tag intersection

        Args:
            tiers: Which memory tiers to search.
            min_importance: Minimum importance value.
            tags: If set, item must contain at least one matching tag.
            agent_namespace: If set, restrict to this namespace + "shared".

        Returns:
            Flat list of candidate MemoryItems that survived all filters.
        """
        candidates: list[MemoryItem] = []

        for tier_type in tiers:
            store = self.stores[tier_type]
            tier = self.tiers[tier_type]

            for item in store.values():
                # 1. TTL expiration
                if item.is_expired(tier.ttl):
                    continue

                # 2. Namespace isolation
                if agent_namespace and item.agent_namespace != agent_namespace and item.agent_namespace != "shared":
                    continue

                # 3. Importance threshold
                if item.importance < min_importance:
                    continue

                # 4. Tag intersection
                if tags and not any(t in item.tags for t in tags):
                    continue

                candidates.append(item)

        return candidates

    def _calculate_relevance(
        self,
        item: MemoryItem,
        query: str,
        query_embedding: list[float] | None,
    ) -> float:
        """Calculate hybrid relevance score for an item.

        P4 Hybrid Retrieval — combines four signals with configurable weights:

        Normal mode (embeddings available):
            0.35 * BM25 + 0.40 * cosine + 0.15 * importance + 0.10 * recency

        Degraded mode (no embeddings):
            0.65 * BM25 + 0.00 * cosine + 0.20 * importance + 0.15 * recency
        """
        # --- Determine mode (normal vs degraded) ---
        has_vectors = query_embedding is not None and item.embedding is not None

        if has_vectors:
            w_bm25, w_cosine, w_importance, w_recency = 0.35, 0.40, 0.15, 0.10
        else:
            w_bm25, w_cosine, w_importance, w_recency = 0.65, 0.00, 0.20, 0.15

        # --- BM25 keyword score ---
        bm25_score = self._bm25.score(query, item.id)
        # Normalize BM25 into [0, 1] via sigmoid-like squash
        bm25_norm = bm25_score / (1.0 + bm25_score) if bm25_score > 0 else 0.0

        # --- Cosine similarity ---
        cosine_score = 0.0
        if has_vectors:
            cosine_score = self._cosine_similarity(query_embedding, item.embedding)  # type: ignore[arg-type]

        # --- Importance ---
        importance_score = item.importance  # already in [0, 1]

        # --- Recency ---
        now = datetime.now(UTC)
        age_hours = (now - item.accessed_at).total_seconds() / 3600
        recency_score = 1.0 / (1.0 + age_hours / 24)  # Decay over days

        return (
            w_bm25 * bm25_norm + w_cosine * cosine_score + w_importance * importance_score + w_recency * recency_score
        )

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        import math

        if len(a) != len(b):
            return 0.0

        dot_product = sum(x * y for x, y in zip(a, b, strict=True))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    async def _create_semantic_summary(
        self,
        items: list[MemoryItem],
        topic: str,
    ) -> str | None:
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
        """Load persisted memories from backend (sync bootstrap).

        Supports both JsonFileBackend (file-per-item) and SQLiteBackendAdapter.
        Delegates to backend.load_all() for a uniform persistence interface,
        so HierarchicalMemory boots with full state from any backend.

        For JsonFileBackend, file I/O is cheap and synchronous — we call
        load_all() directly via a new event loop even if one is running.
        For SQLiteBackendAdapter (asyncio.to_thread), we defer to async_load().
        """
        if not self._backend:
            return

        try:
            import asyncio

            # Check if an event loop is already running
            loop_running = False
            try:
                asyncio.get_running_loop()
                loop_running = True
            except RuntimeError:
                pass

            if loop_running:
                # For JsonFileBackend: file I/O is sync, safe to call in a nested loop
                from backend.agents.memory.backend_interface import JsonFileBackend

                if isinstance(self._backend, JsonFileBackend):
                    # JsonFileBackend.load_all() is sync (file I/O), wrap in new thread
                    import concurrent.futures

                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                        backend = self._backend
                        assert backend is not None  # guaranteed by isinstance check above
                        items = pool.submit(lambda: asyncio.run(backend.load_all(tier=None))).result(timeout=10)  # type: ignore[union-attr]
                    self._hydrate_items(items)
                else:
                    # For async backends, defer to async_load()
                    logger.debug("_load_from_disk: event loop running, deferring to async_load")
                    return
            else:
                # No running loop — safe to use asyncio.run()
                items = asyncio.run(self._backend.load_all(tier=None))
                self._hydrate_items(items)
        except Exception as e:
            logger.warning(f"Failed to load memories from backend: {e}")

        total = sum(len(store) for store in self.stores.values())
        logger.info(f"📂 Loaded {total} persisted memories from {type(self._backend).__name__}")

    def _hydrate_items(self, items: list[dict]) -> None:
        """Hydrate in-memory stores from backend-loaded dicts."""
        for data in items:
            try:
                item = MemoryItem.from_dict(data)
                if item.memory_type in self.stores:
                    self.stores[item.memory_type][item.id] = item
                    self._bm25.add_document(item.id, item.content)
            except Exception as e:
                logger.warning(f"Failed to hydrate memory item: {e}")

    async def async_load(self) -> int:
        """Async bootstrap: load all persisted memories into in-memory stores.

        Call this after construction if running inside an existing event loop
        (e.g., FastAPI lifespan). Returns the number of items loaded.
        """
        if not self._backend:
            return 0

        loaded = 0
        try:
            items = await self._backend.load_all(tier=None)
            for data in items:
                try:
                    item = MemoryItem.from_dict(data)
                    if item.memory_type in self.stores:
                        self.stores[item.memory_type][item.id] = item
                        self._bm25.add_document(item.id, item.content)
                        loaded += 1
                except Exception as e:
                    logger.warning(f"Failed to hydrate memory item: {e}")
        except Exception as e:
            logger.warning(f"async_load failed: {e}")

        logger.info(f"📂 async_load: hydrated {loaded} memories from {type(self._backend).__name__}")
        return loaded

    async def _persist_item(self, item: MemoryItem) -> None:
        """Persist single memory item via backend."""
        if not self._backend:
            return

        try:
            data = item.to_dict()
            # Don't persist embeddings to save space
            data.pop("embedding", None)
            await self._backend.save_item(item.id, item.memory_type.value, data)
        except Exception as e:
            logger.warning(f"Failed to persist memory {item.id}: {e}")

    async def _delete_persisted(self, item_id: str, memory_type: MemoryType) -> None:
        """Delete persisted memory item via backend."""
        if not self._backend:
            return

        try:
            await self._backend.delete_item(item_id, memory_type.value)
        except Exception as e:
            logger.warning(f"Failed to delete persisted memory {item_id}: {e}")

    def get_stats(self) -> dict[str, Any]:
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
            "bm25_documents": self._bm25.document_count,
            "bm25_vocabulary": self._bm25.vocabulary_size,
            "vector_degraded": self.embedding_fn is None,
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
        self._task: asyncio.Task | None = None

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
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        logger.info("⏹️ Memory consolidator stopped")

    async def _run_loop(self) -> None:
        """Main consolidation loop"""
        last_consolidation = datetime.now(UTC)
        last_forgetting = datetime.now(UTC)

        while self._running:
            now = datetime.now(UTC)

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
    "MemoryConsolidator",
    "MemoryItem",
    "MemoryTier",
    "MemoryType",
    "UnifiedMemoryItem",
]
