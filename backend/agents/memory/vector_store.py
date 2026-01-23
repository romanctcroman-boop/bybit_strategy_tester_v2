"""
Vector Memory Store for Semantic Search

Provides embedding-based semantic search capabilities for the hierarchical memory system.
Uses ChromaDB for local vector storage with optional API-based embedding generation.

Supports:
- Local sentence-transformers embeddings (offline)
- DeepSeek API embeddings (online)
- Hybrid approach (local with API fallback)
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from loguru import logger

# Constants
DEFAULT_COLLECTION_NAME = "agent_memory"
DEFAULT_EMBEDDING_DIMENSION = 384  # all-MiniLM-L6-v2
MAX_BATCH_SIZE = 100


@dataclass
class SearchResult:
    """Result from vector search"""

    id: str
    content: str
    distance: float
    score: float  # Similarity score (1 - normalized distance)
    metadata: Dict[str, Any]


class VectorMemoryStore:
    """
    Vector store for embedding-based semantic retrieval

    Uses ChromaDB for local persistent vector storage.
    Supports multiple embedding strategies:
    1. Local: sentence-transformers (no API needed)
    2. Remote: DeepSeek/OpenAI API
    3. Hybrid: Local with remote fallback

    Example:
        store = VectorMemoryStore(persist_path="./data/vectors")
        await store.initialize()

        # Add documents
        await store.add(
            texts=["RSI is a momentum indicator", "MACD shows trend direction"],
            ids=["doc_1", "doc_2"],
            metadatas=[{"type": "indicator"}, {"type": "indicator"}]
        )

        # Search
        results = await store.query(
            query_text="momentum analysis",
            n_results=5
        )
    """

    def __init__(
        self,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        persist_path: Optional[str] = None,
        embedding_fn: Optional[Callable[[str], List[float]]] = None,
        use_local_embeddings: bool = True,
    ):
        """
        Initialize vector store

        Args:
            collection_name: Name of ChromaDB collection
            persist_path: Path for persistent storage (None = in-memory)
            embedding_fn: Custom embedding function
            use_local_embeddings: Use local sentence-transformers if available
        """
        self.collection_name = collection_name
        self.persist_path = Path(persist_path) if persist_path else None
        self.custom_embedding_fn = embedding_fn
        self.use_local_embeddings = use_local_embeddings

        self._client = None
        self._collection = None
        self._local_model = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize ChromaDB and embedding model"""
        if self._initialized:
            return

        # Initialize ChromaDB
        await self._init_chromadb()

        # Initialize embedding model
        if self.use_local_embeddings:
            await self._init_local_embeddings()

        self._initialized = True
        logger.info(
            f"🔢 VectorMemoryStore initialized "
            f"(collection={self.collection_name}, "
            f"local_embeddings={self._local_model is not None})"
        )

    async def _init_chromadb(self) -> None:
        """Initialize ChromaDB client and collection"""
        try:
            import chromadb
            from chromadb.config import Settings

            if self.persist_path:
                self.persist_path.mkdir(parents=True, exist_ok=True)
                self._client = chromadb.PersistentClient(
                    path=str(self.persist_path),
                    settings=Settings(anonymized_telemetry=False),
                )
            else:
                self._client = chromadb.Client(
                    settings=Settings(anonymized_telemetry=False),
                )

            # Get or create collection
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )

            logger.debug(f"ChromaDB collection initialized: {self.collection_name}")

        except ImportError:
            logger.warning(
                "ChromaDB not installed. Run: pip install chromadb\n"
                "Vector search will be unavailable."
            )
            self._client = None
            self._collection = None

    async def _init_local_embeddings(self) -> None:
        """Initialize local sentence-transformers model"""
        try:
            from sentence_transformers import SentenceTransformer

            # Use a small, fast model (384 dimensions)
            model_name = "all-MiniLM-L6-v2"

            # Load model in thread pool to avoid blocking
            def load_model():
                return SentenceTransformer(model_name)

            self._local_model = await asyncio.to_thread(load_model)
            logger.debug(f"Loaded local embedding model: {model_name}")

        except ImportError:
            logger.warning(
                "sentence-transformers not installed. "
                "Run: pip install sentence-transformers\n"
                "Will use API embeddings if available."
            )
            self._local_model = None

    async def get_embedding(self, text: str) -> Optional[List[float]]:
        """
        Get embedding for text

        Priority:
        1. Custom embedding function
        2. Local sentence-transformers
        3. None (fall back to ChromaDB default)
        """
        if not text:
            return None

        # Try custom function first
        if self.custom_embedding_fn:
            try:
                embedding = self.custom_embedding_fn(text)
                if embedding:
                    return embedding
            except Exception as e:
                logger.warning(f"Custom embedding failed: {e}")

        # Try local model
        if self._local_model:
            try:

                def encode():
                    return self._local_model.encode(text).tolist()

                return await asyncio.to_thread(encode)
            except Exception as e:
                logger.warning(f"Local embedding failed: {e}")

        return None

    async def add(
        self,
        texts: List[str],
        ids: Optional[List[str]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None,
        embeddings: Optional[List[List[float]]] = None,
    ) -> List[str]:
        """
        Add documents to vector store

        Args:
            texts: Document texts
            ids: Optional custom IDs (auto-generated if not provided)
            metadatas: Optional metadata for each document
            embeddings: Optional pre-computed embeddings

        Returns:
            List of document IDs
        """
        if not self._collection:
            logger.warning("Vector store not initialized, skipping add")
            return []

        if not texts:
            return []

        # Generate IDs if not provided
        if ids is None:
            ids = [f"doc_{hashlib.sha256(t.encode()).hexdigest()[:12]}" for t in texts]

        # Ensure metadatas list matches texts
        if metadatas is None:
            metadatas = [{}] * len(texts)

        # Generate embeddings if not provided
        if embeddings is None:
            embeddings = []
            for text in texts:
                embedding = await self.get_embedding(text)
                if embedding:
                    embeddings.append(embedding)

            # If no embeddings generated, let ChromaDB use its default
            if not embeddings:
                embeddings = None

        # Add to ChromaDB (in batches)
        added_ids = []
        for i in range(0, len(texts), MAX_BATCH_SIZE):
            batch_end = min(i + MAX_BATCH_SIZE, len(texts))
            batch_ids = ids[i:batch_end]
            batch_texts = texts[i:batch_end]
            batch_metadatas = metadatas[i:batch_end]
            batch_embeddings = embeddings[i:batch_end] if embeddings else None

            try:
                # Use upsert to handle duplicates
                if batch_embeddings:
                    self._collection.upsert(
                        ids=batch_ids,
                        documents=batch_texts,
                        metadatas=batch_metadatas,
                        embeddings=batch_embeddings,
                    )
                else:
                    self._collection.upsert(
                        ids=batch_ids,
                        documents=batch_texts,
                        metadatas=batch_metadatas,
                    )

                added_ids.extend(batch_ids)

            except Exception as e:
                logger.error(f"Failed to add batch to vector store: {e}")

        logger.debug(f"Added {len(added_ids)} documents to vector store")
        return added_ids

    async def query(
        self,
        query_text: Optional[str] = None,
        query_embedding: Optional[List[float]] = None,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
        include: Optional[List[str]] = None,
    ) -> List[SearchResult]:
        """
        Query similar documents

        Args:
            query_text: Text query (will be embedded)
            query_embedding: Pre-computed query embedding
            n_results: Maximum number of results
            where: Optional metadata filter
            include: Optional fields to include (documents, metadatas, distances)

        Returns:
            List of SearchResult objects
        """
        if not self._collection:
            logger.warning("Vector store not initialized")
            return []

        if not query_text and not query_embedding:
            logger.warning("No query provided")
            return []

        # Get embedding if not provided
        if query_embedding is None and query_text:
            query_embedding = await self.get_embedding(query_text)

        include = include or ["documents", "metadatas", "distances"]

        try:
            if query_embedding:
                results = self._collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results,
                    where=where,
                    include=include,
                )
            else:
                # Fall back to ChromaDB's default embedding
                results = self._collection.query(
                    query_texts=[query_text],
                    n_results=n_results,
                    where=where,
                    include=include,
                )

        except Exception as e:
            logger.error(f"Vector query failed: {e}")
            return []

        # Convert to SearchResult objects
        search_results = []

        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for i, doc_id in enumerate(ids):
            distance = distances[i] if i < len(distances) else 0.0

            # Convert distance to similarity score (cosine distance to similarity)
            score = 1.0 - min(distance, 1.0)

            search_results.append(
                SearchResult(
                    id=doc_id,
                    content=documents[i] if i < len(documents) else "",
                    distance=distance,
                    score=score,
                    metadata=metadatas[i] if i < len(metadatas) else {},
                )
            )

        return search_results

    async def delete(
        self,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Delete documents from vector store

        Args:
            ids: Specific IDs to delete
            where: Metadata filter for deletion

        Returns:
            Number of deleted documents
        """
        if not self._collection:
            return 0

        try:
            if ids:
                self._collection.delete(ids=ids)
                return len(ids)
            elif where:
                # Get matching IDs first
                results = self._collection.get(where=where, include=[])
                matching_ids = results.get("ids", [])
                if matching_ids:
                    self._collection.delete(ids=matching_ids)
                    return len(matching_ids)

        except Exception as e:
            logger.error(f"Delete failed: {e}")

        return 0

    async def count(self) -> int:
        """Get total document count"""
        if not self._collection:
            return 0

        try:
            return self._collection.count()
        except Exception:
            return 0

    async def clear(self) -> None:
        """Clear all documents from collection"""
        if not self._client:
            return

        try:
            self._client.delete_collection(self.collection_name)
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(f"Cleared vector store collection: {self.collection_name}")
        except Exception as e:
            logger.error(f"Failed to clear collection: {e}")


class DeepSeekEmbeddingProvider:
    """
    DeepSeek API-based embedding provider

    Uses DeepSeek's embedding endpoint for high-quality embeddings.
    Requires DEEPSEEK_API_KEY to be configured.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "deepseek-chat",  # DeepSeek doesn't have separate embedding model yet
    ):
        self.api_key = api_key
        self.model = model
        self._client = None

    async def initialize(self) -> None:
        """Initialize API client"""
        if not self.api_key:
            from backend.security.key_manager import KeyManager

            km = KeyManager()
            try:
                self.api_key = km.get_decrypted_key("DEEPSEEK_API_KEY")
            except Exception:
                logger.warning("DeepSeek API key not available for embeddings")

    async def get_embedding(self, text: str) -> Optional[List[float]]:
        """Get embedding from DeepSeek API"""
        if not self.api_key:
            return None

        # Note: DeepSeek doesn't have a dedicated embedding endpoint yet
        # This is a placeholder for when they add one
        # For now, use local embeddings or sentence-transformers

        logger.debug("DeepSeek embedding API not yet available, using fallback")
        return None


__all__ = [
    "VectorMemoryStore",
    "SearchResult",
    "DeepSeekEmbeddingProvider",
]
