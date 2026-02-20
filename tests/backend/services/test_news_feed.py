"""Tests for backend.services.news_feed — News Feed Service."""

import pytest

from backend.services.news_feed import (
    ArticleCache,
    FeedArticle,
    MockNewsSource,
    NewsFeedService,
    SentimentSummary,
)

# ============================================================================
# MockNewsSource
# ============================================================================


class TestMockNewsSource:
    """Tests for the mock news source adapter."""

    @pytest.mark.asyncio
    async def test_fetch_returns_articles(self):
        """Test mock source returns non-empty list."""
        source = MockNewsSource()
        articles = await source.fetch(symbol="BTC")
        assert len(articles) > 0
        assert all(a.article_id for a in articles)

    @pytest.mark.asyncio
    async def test_fetch_uses_symbol(self):
        """Test that symbol is used in article titles."""
        source = MockNewsSource()
        articles = await source.fetch(symbol="ETH")
        assert any("ETH" in a.title for a in articles)

    @pytest.mark.asyncio
    async def test_fetch_default_symbol(self):
        """Test default symbol is BTC."""
        source = MockNewsSource()
        articles = await source.fetch()
        assert any("BTC" in a.title for a in articles)


# ============================================================================
# ArticleCache
# ============================================================================


class TestArticleCache:
    """Tests for TTL-based article cache."""

    def _make_feed_article(self, article_id: str = "test_001", symbol: str = "BTC"):
        """Helper to create a FeedArticle for testing."""
        from backend.ml.news_nlp_analyzer import NewsArticle, NewsSource

        article = NewsArticle(
            article_id=article_id,
            title=f"{symbol} test article",
            content="Test content",
            source=NewsSource.CUSTOM,
            symbols=[symbol],
        )
        return FeedArticle(article=article)

    def test_put_and_get(self):
        """Test caching and retrieving an article."""
        cache = ArticleCache(ttl=60)
        fa = self._make_feed_article()
        cache.put(fa)
        retrieved = cache.get("test_001")
        assert retrieved is not None
        assert retrieved.article.article_id == "test_001"

    def test_get_nonexistent_returns_none(self):
        """Test getting non-existent article returns None."""
        cache = ArticleCache(ttl=60)
        assert cache.get("nonexistent") is None

    def test_get_all_filters_by_symbol(self):
        """Test get_all filters by symbol."""
        cache = ArticleCache(ttl=60)
        cache.put(self._make_feed_article("a1", "BTC"))
        cache.put(self._make_feed_article("a2", "ETH"))
        cache.put(self._make_feed_article("a3", "BTC"))

        btc_articles = cache.get_all(symbol="BTC")
        assert len(btc_articles) == 2

        eth_articles = cache.get_all(symbol="ETH")
        assert len(eth_articles) == 1

    def test_size(self):
        """Test cache size tracking."""
        cache = ArticleCache(ttl=60)
        assert cache.size() == 0
        cache.put(self._make_feed_article("a1"))
        assert cache.size() == 1

    def test_clear(self):
        """Test cache clearing."""
        cache = ArticleCache(ttl=60)
        cache.put(self._make_feed_article("a1"))
        cache.put(self._make_feed_article("a2"))
        cache.clear()
        assert cache.size() == 0

    def test_eviction_on_max_size(self):
        """Test oldest entries evicted when cache is full."""
        cache = ArticleCache(ttl=300, max_size=5)
        for i in range(6):
            cache.put(self._make_feed_article(f"art_{i}"))
        # After eviction, should be <= max_size
        assert cache.size() <= 5


# ============================================================================
# FeedArticle
# ============================================================================


class TestFeedArticle:
    """Tests for FeedArticle serialization."""

    def test_to_dict_without_sentiment(self):
        """Test serialization without sentiment result."""
        from backend.ml.news_nlp_analyzer import NewsArticle, NewsSource

        article = NewsArticle(
            article_id="s1",
            title="Test",
            content="Content",
            source=NewsSource.CUSTOM,
            symbols=["BTC"],
        )
        fa = FeedArticle(article=article)
        d = fa.to_dict()
        assert d["id"] == "s1"
        assert d["sentiment"] is None
        assert d["source"] == "custom"


# ============================================================================
# SentimentSummary
# ============================================================================


class TestSentimentSummary:
    """Tests for SentimentSummary."""

    def test_to_dict_serializable(self):
        """Test sentiment summary serialization."""
        import json

        summary = SentimentSummary(
            symbol="BTC",
            window_minutes=60,
            article_count=10,
            avg_score=0.35,
            sentiment_label="bullish",
            bullish_pct=60.0,
            bearish_pct=20.0,
            neutral_pct=20.0,
            top_categories=["price_movement", "adoption"],
            high_impact_count=3,
        )
        d = summary.to_dict()
        assert d["symbol"] == "BTC"
        json.dumps(d)  # Must be JSON-serializable


# ============================================================================
# NewsFeedService
# ============================================================================


class TestNewsFeedService:
    """Tests for the main news feed service."""

    @pytest.mark.asyncio
    async def test_fetch_and_analyze(self):
        """Test fetching and analyzing articles."""
        service = NewsFeedService(sources=[MockNewsSource()])
        articles = await service.fetch_and_analyze(symbol="BTC")
        assert len(articles) > 0
        # Each article should have sentiment analysis
        for fa in articles:
            assert fa.sentiment is not None

    @pytest.mark.asyncio
    async def test_get_feed_returns_dicts(self):
        """Test get_feed returns list of dicts."""
        service = NewsFeedService(sources=[MockNewsSource()])
        feed = await service.get_feed(symbol="BTC", limit=5)
        assert isinstance(feed, list)
        assert all(isinstance(item, dict) for item in feed)
        assert all("id" in item for item in feed)

    @pytest.mark.asyncio
    async def test_get_feed_respects_limit(self):
        """Test get_feed limits results."""
        service = NewsFeedService(sources=[MockNewsSource()])
        feed = await service.get_feed(symbol="BTC", limit=2)
        assert len(feed) <= 2

    @pytest.mark.asyncio
    async def test_get_sentiment_summary_empty(self):
        """Test sentiment summary with no cached data returns neutral."""
        service = NewsFeedService(sources=[MockNewsSource()], cache_ttl=300)
        summary = await service.get_sentiment_summary("XYZNONEXISTENT", window_minutes=1)
        # May get articles from mock or may be empty
        assert isinstance(summary, SentimentSummary)
        assert summary.symbol == "XYZNONEXISTENT"

    @pytest.mark.asyncio
    async def test_get_sentiment_summary_with_data(self):
        """Test sentiment summary aggregation."""
        service = NewsFeedService(sources=[MockNewsSource()])
        # Pre-populate cache
        await service.fetch_and_analyze(symbol="BTC")
        summary = await service.get_sentiment_summary("BTC", window_minutes=60)
        assert summary.article_count > 0
        assert summary.sentiment_label in (
            "very_bearish",
            "bearish",
            "neutral",
            "bullish",
            "very_bullish",
        )

    def test_add_source(self):
        """Test adding a new source."""
        service = NewsFeedService(sources=[MockNewsSource()])
        assert len(service.sources) == 1
        service.add_source(MockNewsSource())
        assert len(service.sources) == 2

    def test_clear_cache(self):
        """Test clearing the cache."""
        service = NewsFeedService()
        service.cache.put(
            FeedArticle(
                article=__import__("backend.ml.news_nlp_analyzer", fromlist=["NewsArticle"]).NewsArticle(
                    article_id="x",
                    title="x",
                    content="x",
                    source=__import__("backend.ml.news_nlp_analyzer", fromlist=["NewsSource"]).NewsSource.CUSTOM,
                )
            )
        )
        assert service.cache.size() == 1
        service.clear_cache()
        assert service.cache.size() == 0
