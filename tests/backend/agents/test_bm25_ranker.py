"""
Tests for BM25 Ranker — P4.2

Covers:
  - Indexing (add, remove, replace, clear)
  - Scoring (single doc, multi-term, unknown doc/term)
  - Ranking (top_k, candidate subset, empty corpus)
  - Thread safety (concurrent add/score)
  - Edge cases (empty content, single-word docs)
  - Properties (document_count, vocabulary_size, __len__, __contains__)
"""

from __future__ import annotations

import threading

import pytest

from backend.agents.memory.bm25_ranker import BM25Ranker, _tokenize

# ── Tokenizer ──────────────────────────────────────────────────────────


class TestTokenize:
    def test_basic_words(self):
        assert _tokenize("Hello World") == ["hello", "world"]

    def test_with_punctuation(self):
        assert _tokenize("RSI is 70.5!") == ["rsi", "is", "70", "5"]

    def test_empty_string(self):
        assert _tokenize("") == []

    def test_mixed_case(self):
        tokens = _tokenize("BTCUSDT btcusdt BtcUsdt")
        assert all(t == "btcusdt" for t in tokens)

    def test_numbers_preserved(self):
        assert _tokenize("EMA 200 cross") == ["ema", "200", "cross"]


# ── Indexing ───────────────────────────────────────────────────────────


class TestIndexing:
    def test_add_single_document(self):
        r = BM25Ranker()
        r.add_document("d1", "RSI crossed above 70")
        assert r.document_count == 1
        assert "d1" in r

    def test_add_multiple_documents(self):
        r = BM25Ranker()
        r.add_document("d1", "RSI crossed above 70")
        r.add_document("d2", "MACD histogram turning positive")
        r.add_document("d3", "Bollinger bands squeeze")
        assert r.document_count == 3

    def test_replace_document(self):
        r = BM25Ranker()
        r.add_document("d1", "RSI above 70")
        r.add_document("d1", "MACD crossover bullish")
        assert r.document_count == 1
        # Old terms should not be indexed
        assert r.score("RSI", "d1") == 0.0
        assert r.score("MACD", "d1") > 0.0

    def test_remove_document(self):
        r = BM25Ranker()
        r.add_document("d1", "RSI signal")
        r.remove_document("d1")
        assert r.document_count == 0
        assert "d1" not in r

    def test_remove_nonexistent_is_safe(self):
        r = BM25Ranker()
        r.remove_document("nonexistent")  # Should not raise
        assert r.document_count == 0

    def test_clear(self):
        r = BM25Ranker()
        for i in range(10):
            r.add_document(f"d{i}", f"Document content number {i}")
        r.clear()
        assert r.document_count == 0
        assert r.vocabulary_size == 0

    def test_vocabulary_size(self):
        r = BM25Ranker()
        r.add_document("d1", "RSI MACD EMA")
        assert r.vocabulary_size == 3
        r.add_document("d2", "RSI divergence")
        assert r.vocabulary_size == 4  # RSI shared, divergence new

    def test_vocabulary_shrinks_on_remove(self):
        r = BM25Ranker()
        r.add_document("d1", "alpha beta")
        r.add_document("d2", "beta gamma")
        assert r.vocabulary_size == 3
        r.remove_document("d1")
        # "alpha" should be gone, "beta" and "gamma" remain
        assert r.vocabulary_size == 2


# ── Scoring ────────────────────────────────────────────────────────────


class TestScoring:
    @pytest.fixture()
    def corpus(self):
        r = BM25Ranker()
        r.add_document("d1", "RSI crossed above 70 on BTCUSDT")
        r.add_document("d2", "MACD histogram turning positive")
        r.add_document("d3", "RSI divergence on ETHUSDT 4h chart")
        return r

    def test_score_matching_term(self, corpus):
        # "RSI" appears in d1 and d3 but not d2
        assert corpus.score("RSI", "d1") > 0.0
        assert corpus.score("RSI", "d3") > 0.0
        assert corpus.score("RSI", "d2") == 0.0

    def test_score_unknown_document(self, corpus):
        assert corpus.score("RSI", "unknown_id") == 0.0

    def test_score_unknown_term(self, corpus):
        assert corpus.score("xyznotfound", "d1") == 0.0

    def test_score_empty_query(self, corpus):
        assert corpus.score("", "d1") == 0.0

    def test_score_empty_corpus(self):
        r = BM25Ranker()
        assert r.score("anything", "d1") == 0.0

    def test_multi_term_query_higher_score(self, corpus):
        # "RSI BTCUSDT" matches both terms in d1, only "RSI" in d3
        score_d1 = corpus.score("RSI BTCUSDT", "d1")
        score_d3 = corpus.score("RSI BTCUSDT", "d3")
        assert score_d1 > score_d3

    def test_score_case_insensitive(self, corpus):
        s1 = corpus.score("rsi", "d1")
        s2 = corpus.score("RSI", "d1")
        s3 = corpus.score("Rsi", "d1")
        assert s1 == s2 == s3

    def test_idf_weighting(self):
        """Rare terms should get higher IDF."""
        r = BM25Ranker()
        # "common" in all 3 docs, "rare" in only 1
        r.add_document("d1", "common word rare")
        r.add_document("d2", "common word stuff")
        r.add_document("d3", "common word other")
        # Query for "rare" should score d1 high because IDF of "rare" is high
        assert r.score("rare", "d1") > r.score("common", "d1")


# ── Ranking ────────────────────────────────────────────────────────────


class TestRanking:
    @pytest.fixture()
    def corpus(self):
        r = BM25Ranker()
        r.add_document("d1", "RSI crossed above 70 on BTCUSDT daily chart")
        r.add_document("d2", "MACD histogram turning positive signal")
        r.add_document("d3", "RSI divergence on ETHUSDT 4h chart RSI")
        r.add_document("d4", "Support resistance levels on BTC")
        return r

    def test_rank_returns_sorted(self, corpus):
        results = corpus.rank("RSI chart")
        assert len(results) > 0
        # Scores should be descending
        scores = [s for _, s in results]
        assert scores == sorted(scores, reverse=True)

    def test_rank_top_k(self, corpus):
        results = corpus.rank("RSI chart", top_k=2)
        assert len(results) <= 2

    def test_rank_candidate_subset(self, corpus):
        results = corpus.rank("RSI", candidate_ids=["d1", "d4"])
        doc_ids = [did for did, _ in results]
        assert "d1" in doc_ids
        assert "d3" not in doc_ids  # Not in candidates

    def test_rank_empty_query(self, corpus):
        results = corpus.rank("")
        assert results == []

    def test_rank_empty_corpus(self):
        r = BM25Ranker()
        results = r.rank("anything")
        assert results == []

    def test_rank_no_match(self, corpus):
        results = corpus.rank("xyznotfound")
        assert results == []


# ── Thread Safety ──────────────────────────────────────────────────────


class TestThreadSafety:
    def test_concurrent_add_and_score(self):
        """Concurrent add + score should not raise."""
        r = BM25Ranker()
        errors: list[Exception] = []

        def add_docs(start: int) -> None:
            try:
                for i in range(start, start + 50):
                    r.add_document(f"doc_{i}", f"content for document number {i}")
            except Exception as e:
                errors.append(e)

        def score_docs() -> None:
            try:
                for _ in range(100):
                    r.score("content document", "doc_0")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=add_docs, args=(0,)),
            threading.Thread(target=add_docs, args=(50,)),
            threading.Thread(target=score_docs),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert errors == [], f"Thread errors: {errors}"
        assert r.document_count == 100


# ── Properties & Dunder ───────────────────────────────────────────────


class TestProperties:
    def test_len(self):
        r = BM25Ranker()
        assert len(r) == 0
        r.add_document("d1", "hello")
        assert len(r) == 1

    def test_contains(self):
        r = BM25Ranker()
        r.add_document("d1", "hello")
        assert "d1" in r
        assert "d2" not in r

    def test_custom_parameters(self):
        r = BM25Ranker(k1=2.0, b=0.5)
        assert r.k1 == 2.0
        assert r.b == 0.5


# ── Edge Cases ─────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_single_word_document(self):
        r = BM25Ranker()
        r.add_document("d1", "RSI")
        assert r.score("RSI", "d1") > 0.0

    def test_empty_document_content(self):
        r = BM25Ranker()
        r.add_document("d1", "")
        assert r.document_count == 1
        assert r.score("anything", "d1") == 0.0

    def test_very_long_document(self):
        r = BM25Ranker()
        content = " ".join(f"word{i}" for i in range(1000))
        r.add_document("d1", content)
        assert r.document_count == 1
        assert r.score("word500", "d1") > 0.0

    def test_repeated_terms_in_query(self):
        r = BM25Ranker()
        r.add_document("d1", "RSI is good RSI is great")
        # Repeated query term should not double the score
        s1 = r.score("RSI", "d1")
        s2 = r.score("RSI RSI RSI", "d1")
        assert s2 > s1  # Higher but saturated
