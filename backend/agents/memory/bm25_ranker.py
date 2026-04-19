"""
BM25 Ranker -- Best Matching 25 keyword ranking.

Replaces the naive word-overlap scorer in HierarchicalMemory.recall()
with proper TF-IDF-like ranking that handles:
    - Term frequency saturation (k1 parameter)
    - Document length normalization (b parameter)
    - IDF weighting

No external dependencies -- pure Python implementation (~120 LOC).
Thread-safe via a reentrant lock for concurrent store/recall.
"""

from __future__ import annotations

import math
import re
import threading
from collections import Counter

# Simple tokenizer: extract alphanumeric words, lowercased.
_TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")


def _tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase words."""
    return _TOKEN_RE.findall(text.lower())


class BM25Ranker:
    """BM25 keyword ranker with incremental indexing.

    Parameters:
        k1: Term-frequency saturation. Higher = slower saturation (default 1.2).
        b:  Document-length normalization. 0 = no normalization, 1 = full (default 0.75).

    Usage::

        ranker = BM25Ranker()
        ranker.add_document("doc1", "RSI crossed above 70 on BTCUSDT")
        ranker.add_document("doc2", "MACD histogram turning positive")
        ranker.add_document("doc3", "RSI divergence on ETHUSDT 4h chart")

        results = ranker.rank("RSI overbought", top_k=2)
        # → [("doc1", 0.85), ("doc3", 0.62)]
    """

    def __init__(self, k1: float = 1.2, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b

        # Corpus state
        self._docs: dict[str, list[str]] = {}  # doc_id → tokens
        self._doc_lens: dict[str, int] = {}  # doc_id → token count
        self._doc_freq: Counter[str] = Counter()  # term → number of docs containing it
        self._avg_dl: float = 0.0  # average document length
        self._n: int = 0  # total documents

        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def add_document(self, doc_id: str, content: str) -> None:
        """Add or replace a document in the index."""
        tokens = _tokenize(content)
        with self._lock:
            # If replacing, remove old doc first
            if doc_id in self._docs:
                self._remove_doc_unlocked(doc_id)

            self._docs[doc_id] = tokens
            self._doc_lens[doc_id] = len(tokens)

            # Update document frequencies
            unique_terms = set(tokens)
            for term in unique_terms:
                self._doc_freq[term] += 1

            self._n += 1
            self._avg_dl = sum(self._doc_lens.values()) / self._n if self._n else 0.0

    def remove_document(self, doc_id: str) -> None:
        """Remove a document from the index."""
        with self._lock:
            self._remove_doc_unlocked(doc_id)

    def _remove_doc_unlocked(self, doc_id: str) -> None:
        """Remove doc without acquiring lock (caller must hold lock)."""
        if doc_id not in self._docs:
            return
        tokens = self._docs[doc_id]
        unique_terms = set(tokens)
        for term in unique_terms:
            self._doc_freq[term] -= 1
            if self._doc_freq[term] <= 0:
                del self._doc_freq[term]
        del self._docs[doc_id]
        del self._doc_lens[doc_id]
        self._n -= 1
        self._avg_dl = sum(self._doc_lens.values()) / self._n if self._n else 0.0

    def clear(self) -> None:
        """Remove all documents from the index."""
        with self._lock:
            self._docs.clear()
            self._doc_lens.clear()
            self._doc_freq.clear()
            self._avg_dl = 0.0
            self._n = 0

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def score(self, query: str, doc_id: str) -> float:
        """Score a single document against a query."""
        query_tokens = _tokenize(query)
        with self._lock:
            return self._score_unlocked(query_tokens, doc_id)

    def _score_unlocked(self, query_tokens: list[str], doc_id: str) -> float:
        """BM25 score (caller must hold lock)."""
        if doc_id not in self._docs:
            return 0.0
        if self._n == 0:
            return 0.0

        doc_tokens = self._docs[doc_id]
        dl = self._doc_lens[doc_id]
        tf_counts = Counter(doc_tokens)

        total = 0.0
        for term in query_tokens:
            if term not in self._doc_freq:
                continue

            tf = tf_counts.get(term, 0)
            if tf == 0:
                continue

            df = self._doc_freq[term]
            # IDF component (Robertson-Sparck Jones)
            idf = math.log((self._n - df + 0.5) / (df + 0.5) + 1.0)

            # TF saturation + length normalization
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * dl / self._avg_dl)

            total += idf * (numerator / denominator)

        return total

    def rank(
        self,
        query: str,
        candidate_ids: list[str] | None = None,
        top_k: int = 20,
    ) -> list[tuple[str, float]]:
        """Rank documents by BM25 score.

        Args:
            query: Search query text.
            candidate_ids: Restrict to these doc IDs (None = all docs).
            top_k: Maximum results to return.

        Returns:
            List of (doc_id, score) tuples, sorted by score descending.
        """
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        with self._lock:
            ids = candidate_ids if candidate_ids is not None else list(self._docs)
            scored = [(doc_id, self._score_unlocked(query_tokens, doc_id)) for doc_id in ids if doc_id in self._docs]

        # Filter zero-score and sort
        scored = [(did, s) for did, s in scored if s > 0.0]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    @property
    def document_count(self) -> int:
        """Number of indexed documents."""
        return self._n

    @property
    def vocabulary_size(self) -> int:
        """Number of unique terms in the index."""
        return len(self._doc_freq)

    def __len__(self) -> int:
        return self._n

    def __contains__(self, doc_id: str) -> bool:
        return doc_id in self._docs
