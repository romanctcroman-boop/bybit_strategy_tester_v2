"""
News Feed Service — Real-Time Crypto News Aggregation.

Aggregates news from multiple sources, runs sentiment analysis via
``backend.ml.news_nlp_analyzer``, and provides a unified feed with
caching, filtering, and impact scoring.

Architecture::

    Sources (CoinDesk, CryptoPanic, RSS)
         ↓
    NewsFeedService.fetch_all()
         ↓
    NewsNLPAnalyzer.analyze()     → SentimentResult
         ↓
    Cache (TTL-based, in-memory)
         ↓
    API / WebSocket consumers

Usage::

    from backend.services.news_feed import NewsFeedService

    feed = NewsFeedService()
    articles = await feed.get_feed(symbol="BTC", limit=20)
    sentiment = await feed.get_sentiment_summary("BTC")
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from backend.ml.news_nlp_analyzer import (
    NewsArticle,
    NewsNLPAnalyzer,
    NewsSource,
    SentimentResult,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_CACHE_TTL_SECONDS = int(os.getenv("NEWS_CACHE_TTL", "300"))  # 5 minutes
_MAX_CACHED_ARTICLES = 500
_FETCH_TIMEOUT = 10  # seconds


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class FeedArticle:
    """Enriched article with sentiment analysis."""

    article: NewsArticle
    sentiment: SentimentResult | None = None
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API responses."""
        return {
            "id": self.article.article_id,
            "title": self.article.title,
            "source": self.article.source.value,
            "url": self.article.url,
            "published_at": self.article.published_at.isoformat(),
            "symbols": self.article.symbols,
            "sentiment": self.sentiment.to_dict() if self.sentiment else None,
            "fetched_at": self.fetched_at.isoformat(),
        }


@dataclass
class SentimentSummary:
    """Aggregated sentiment for a symbol over a time window."""

    symbol: str
    window_minutes: int
    article_count: int
    avg_score: float  # -1.0 to 1.0
    sentiment_label: str  # very_bearish .. very_bullish
    bullish_pct: float
    bearish_pct: float
    neutral_pct: float
    top_categories: list[str]
    high_impact_count: int  # articles with impact_score > 0.7
    computed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API responses."""
        return {
            "symbol": self.symbol,
            "window_minutes": self.window_minutes,
            "article_count": self.article_count,
            "avg_score": round(self.avg_score, 4),
            "sentiment_label": self.sentiment_label,
            "bullish_pct": round(self.bullish_pct, 2),
            "bearish_pct": round(self.bearish_pct, 2),
            "neutral_pct": round(self.neutral_pct, 2),
            "top_categories": self.top_categories,
            "high_impact_count": self.high_impact_count,
            "computed_at": self.computed_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# Feed sources (pluggable adapters)
# ---------------------------------------------------------------------------


class BaseNewsSource:
    """Abstract news source adapter."""

    name: str = "base"

    async def fetch(self, symbol: str | None = None) -> list[NewsArticle]:
        """Fetch articles, optionally filtered by symbol."""
        raise NotImplementedError


class MockNewsSource(BaseNewsSource):
    """
    Mock news source for testing and development.

    Generates realistic-looking sample articles.
    """

    name = "mock"

    _TEMPLATES = [
        ("{symbol} breaks above key resistance level — analysts bullish", 0.7),
        ("Whale alert: Large {symbol} transfer to exchange detected", -0.3),
        ("{symbol} network upgrade scheduled for next week", 0.5),
        ("SEC delays decision on {symbol} ETF application", -0.4),
        ("Major exchange lists new {symbol} trading pair", 0.6),
        ("{symbol} trading volume surges 300% in 24 hours", 0.5),
        ("Analyst predicts {symbol} correction before next rally", -0.2),
        ("{symbol} partnership with Fortune 500 company announced", 0.8),
    ]

    async def fetch(self, symbol: str | None = None) -> list[NewsArticle]:
        """Generate mock articles."""
        import random

        sym = symbol or "BTC"
        articles = []
        for template, _ in random.sample(self._TEMPLATES, min(3, len(self._TEMPLATES))):
            title = template.format(symbol=sym)
            article_id = hashlib.sha256(f"{title}:{time.time()}".encode()).hexdigest()[:16]
            articles.append(
                NewsArticle(
                    article_id=article_id,
                    title=title,
                    content=f"Detailed analysis of {sym} market conditions...",
                    source=NewsSource.CUSTOM,
                    url=f"https://example.com/news/{article_id}",
                    symbols=[sym],
                )
            )
        return articles


class RSSNewsSource(BaseNewsSource):
    """
    RSS feed news source.

    Fetches from configurable RSS/Atom feed URLs.
    Requires ``httpx`` (already a project dependency).
    """

    name = "rss"

    def __init__(self, feed_urls: list[str] | None = None) -> None:
        self.feed_urls = feed_urls or []

    async def fetch(self, symbol: str | None = None) -> list[NewsArticle]:
        """Fetch from RSS feeds (stub — requires feed parsing library)."""
        # Real implementation would use feedparser or xml.etree
        # For now, return empty to avoid external dependencies
        logger.debug("RSS source: %d feeds configured", len(self.feed_urls))
        return []


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


class ArticleCache:
    """TTL-based in-memory cache for news articles."""

    def __init__(self, ttl: int = _CACHE_TTL_SECONDS, max_size: int = _MAX_CACHED_ARTICLES) -> None:
        self.ttl = ttl
        self.max_size = max_size
        self._cache: dict[str, tuple[float, FeedArticle]] = {}

    def get(self, article_id: str) -> FeedArticle | None:
        """Get a cached article if not expired."""
        entry = self._cache.get(article_id)
        if entry is None:
            return None
        ts, article = entry
        if time.time() - ts > self.ttl:
            del self._cache[article_id]
            return None
        return article

    def put(self, article: FeedArticle) -> None:
        """Cache an article."""
        self._evict_if_full()
        self._cache[article.article.article_id] = (time.time(), article)

    def get_all(
        self,
        symbol: str | None = None,
        since: datetime | None = None,
    ) -> list[FeedArticle]:
        """Get all cached articles, optionally filtered."""
        now = time.time()
        results = []
        expired_keys = []

        for key, (ts, article) in self._cache.items():
            if now - ts > self.ttl:
                expired_keys.append(key)
                continue
            if symbol and symbol.upper() not in [s.upper() for s in article.article.symbols]:
                continue
            if since and article.article.published_at < since:
                continue
            results.append(article)

        for key in expired_keys:
            del self._cache[key]

        # Sort by publication date, newest first
        results.sort(key=lambda a: a.article.published_at, reverse=True)
        return results

    def _evict_if_full(self) -> None:
        """Remove oldest entries if cache exceeds max size."""
        if len(self._cache) >= self.max_size:
            # Remove oldest 20%
            sorted_keys = sorted(self._cache, key=lambda k: self._cache[k][0])
            for key in sorted_keys[: len(sorted_keys) // 5]:
                del self._cache[key]

    def clear(self) -> None:
        """Clear all cached articles."""
        self._cache.clear()

    def size(self) -> int:
        """Return current cache size."""
        return len(self._cache)


# ---------------------------------------------------------------------------
# Main service
# ---------------------------------------------------------------------------


class NewsFeedService:
    """
    High-level news aggregation and sentiment service.

    Coordinates multiple news sources, runs NLP analysis, caches results,
    and provides a unified API for consumers.
    """

    def __init__(
        self,
        sources: list[BaseNewsSource] | None = None,
        analyzer: NewsNLPAnalyzer | None = None,
        cache_ttl: int = _CACHE_TTL_SECONDS,
    ) -> None:
        self.sources = sources or [MockNewsSource()]
        self.analyzer = analyzer or NewsNLPAnalyzer()
        self.cache = ArticleCache(ttl=cache_ttl)
        self._fetch_lock = asyncio.Lock()

    async def fetch_and_analyze(
        self,
        symbol: str | None = None,
    ) -> list[FeedArticle]:
        """
        Fetch articles from all sources and run sentiment analysis.

        Args:
            symbol: Optional symbol to filter by (e.g., "BTC").

        Returns:
            List of enriched FeedArticle objects.
        """
        async with self._fetch_lock:
            all_articles: list[NewsArticle] = []

            # Fetch from all sources concurrently
            tasks = [source.fetch(symbol) for source in self.sources]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(results):
                if isinstance(result, BaseException):
                    logger.warning(
                        "Source %s failed: %s",
                        self.sources[i].name,
                        result,
                    )
                    continue
                all_articles.extend(result)  # type: ignore[arg-type]

            logger.info(
                "Fetched %d articles from %d sources",
                len(all_articles),
                len(self.sources),
            )

            # Analyze each article
            feed_articles: list[FeedArticle] = []
            for article in all_articles:
                # Check cache first
                cached = self.cache.get(article.article_id)
                if cached:
                    feed_articles.append(cached)
                    continue

                # Run sentiment analysis
                sentiment = self.analyzer.analyze(article)
                feed_article = FeedArticle(article=article, sentiment=sentiment)
                self.cache.put(feed_article)
                feed_articles.append(feed_article)

            return feed_articles

    async def get_feed(
        self,
        symbol: str | None = None,
        limit: int = 20,
        include_sentiment: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Get the news feed as a list of dicts (API-ready).

        Args:
            symbol: Filter by symbol.
            limit: Maximum articles to return.
            include_sentiment: Whether to include sentiment analysis.

        Returns:
            List of article dicts.
        """
        # Try cache first
        cached = self.cache.get_all(symbol=symbol)
        if not cached:
            cached = await self.fetch_and_analyze(symbol)

        articles = cached[:limit]
        return [a.to_dict() for a in articles]

    async def get_sentiment_summary(
        self,
        symbol: str,
        window_minutes: int = 60,
    ) -> SentimentSummary:
        """
        Compute aggregated sentiment for a symbol.

        Args:
            symbol: Crypto symbol (e.g., "BTC").
            window_minutes: Look-back window in minutes.

        Returns:
            SentimentSummary with aggregate scores.
        """
        since = datetime.now(UTC) - timedelta(minutes=window_minutes)
        articles = self.cache.get_all(symbol=symbol, since=since)

        if not articles:
            # Fetch fresh data if cache empty
            await self.fetch_and_analyze(symbol)
            articles = self.cache.get_all(symbol=symbol, since=since)

        if not articles:
            return SentimentSummary(
                symbol=symbol,
                window_minutes=window_minutes,
                article_count=0,
                avg_score=0.0,
                sentiment_label="neutral",
                bullish_pct=0.0,
                bearish_pct=0.0,
                neutral_pct=100.0,
                top_categories=[],
                high_impact_count=0,
            )

        # Aggregate
        scores = []
        categories: dict[str, int] = defaultdict(int)
        bullish = bearish = neutral = 0
        high_impact = 0

        for fa in articles:
            if fa.sentiment:
                score = fa.sentiment.sentiment_score
                scores.append(score)

                if score > 0.1:
                    bullish += 1
                elif score < -0.1:
                    bearish += 1
                else:
                    neutral += 1

                categories[fa.sentiment.category.value] += 1

                if fa.sentiment.impact_score > 0.7:
                    high_impact += 1

        total = len(articles)
        avg_score = sum(scores) / len(scores) if scores else 0.0

        # Determine label
        if avg_score > 0.5:
            label = "very_bullish"
        elif avg_score > 0.1:
            label = "bullish"
        elif avg_score < -0.5:
            label = "very_bearish"
        elif avg_score < -0.1:
            label = "bearish"
        else:
            label = "neutral"

        # Top categories by frequency
        top_cats = sorted(categories, key=lambda c: categories[c], reverse=True)[:3]

        return SentimentSummary(
            symbol=symbol,
            window_minutes=window_minutes,
            article_count=total,
            avg_score=avg_score,
            sentiment_label=label,
            bullish_pct=(bullish / total * 100) if total else 0.0,
            bearish_pct=(bearish / total * 100) if total else 0.0,
            neutral_pct=(neutral / total * 100) if total else 0.0,
            top_categories=top_cats,
            high_impact_count=high_impact,
        )

    def add_source(self, source: BaseNewsSource) -> None:
        """Register an additional news source."""
        self.sources.append(source)
        logger.info("Added news source: %s", source.name)

    def clear_cache(self) -> None:
        """Clear the article cache."""
        self.cache.clear()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_service: NewsFeedService | None = None


def get_news_feed_service() -> NewsFeedService:
    """Get or create the global NewsFeedService instance."""
    global _service
    if _service is None:
        _service = NewsFeedService()
    return _service
