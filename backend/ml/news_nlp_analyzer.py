"""
News NLP Analyzer for Crypto Trading.

Provides sentiment analysis for crypto news using:
- FinBERT-like models for financial sentiment
- Named Entity Recognition for crypto assets
- Topic classification for market events
- Real-time news aggregation and scoring
"""

import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Configuration
# ============================================================================


class Sentiment(Enum):
    """Sentiment classification."""

    VERY_BEARISH = -2
    BEARISH = -1
    NEUTRAL = 0
    BULLISH = 1
    VERY_BULLISH = 2


class NewsCategory(Enum):
    """News category classification."""

    PRICE_MOVEMENT = "price_movement"
    REGULATION = "regulation"
    ADOPTION = "adoption"
    TECHNOLOGY = "technology"
    PARTNERSHIP = "partnership"
    HACK_SECURITY = "hack_security"
    EXCHANGE = "exchange"
    MACRO = "macro"
    DEFI = "defi"
    NFT = "nft"
    OTHER = "other"


class NewsSource(Enum):
    """News source types."""

    TWITTER = "twitter"
    REDDIT = "reddit"
    COINDESK = "coindesk"
    COINTELEGRAPH = "cointelegraph"
    BLOOMBERG = "bloomberg"
    REUTERS = "reuters"
    CUSTOM = "custom"


@dataclass
class NewsArticle:
    """News article data."""

    article_id: str
    title: str
    content: str
    source: NewsSource
    url: str = ""
    published_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    author: str = ""
    symbols: list[str] = field(default_factory=list)
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class SentimentResult:
    """Sentiment analysis result."""

    article_id: str
    sentiment: Sentiment
    confidence: float  # 0 to 1
    sentiment_score: float  # -1 to 1
    category: NewsCategory
    mentioned_symbols: list[str]
    key_phrases: list[str]
    impact_score: float  # 0 to 1 (potential market impact)
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "article_id": self.article_id,
            "sentiment": self.sentiment.name,
            "confidence": self.confidence,
            "sentiment_score": self.sentiment_score,
            "category": self.category.value,
            "mentioned_symbols": self.mentioned_symbols,
            "key_phrases": self.key_phrases,
            "impact_score": self.impact_score,
            "analyzed_at": self.analyzed_at.isoformat(),
        }


# ============================================================================
# Lexicon-Based Sentiment (No ML Dependencies)
# ============================================================================


class CryptoSentimentLexicon:
    """
    Crypto-specific sentiment lexicon.

    Contains words and phrases with sentiment scores for crypto domain.
    """

    # Bullish words/phrases with scores (0 to 1)
    BULLISH_TERMS: dict[str, float] = {
        # Strong bullish
        "moon": 0.9,
        "mooning": 0.95,
        "bullish": 0.85,
        "breakout": 0.8,
        "all-time high": 0.9,
        "ath": 0.85,
        "pump": 0.7,
        "rally": 0.75,
        "surge": 0.8,
        "soar": 0.85,
        "skyrocket": 0.9,
        "adoption": 0.7,
        "partnership": 0.65,
        "institutional": 0.7,
        "buy signal": 0.8,
        "accumulate": 0.6,
        "hodl": 0.6,
        "diamond hands": 0.7,
        "green candle": 0.6,
        "support holding": 0.6,
        "whale accumulation": 0.75,
        "etf approved": 0.9,
        "halving": 0.65,
        "scarcity": 0.6,
        "deflationary": 0.55,
        "burn": 0.5,
        "staking rewards": 0.5,
        # Moderate bullish
        "growth": 0.5,
        "increase": 0.45,
        "gain": 0.5,
        "profit": 0.55,
        "positive": 0.4,
        "upgrade": 0.5,
        "innovation": 0.45,
        "expansion": 0.5,
        "recovery": 0.55,
        "bounce": 0.5,
    }

    # Bearish words/phrases with scores (0 to 1)
    BEARISH_TERMS: dict[str, float] = {
        # Strong bearish
        "crash": 0.9,
        "dump": 0.85,
        "bearish": 0.85,
        "collapse": 0.9,
        "plunge": 0.85,
        "tank": 0.8,
        "capitulation": 0.85,
        "bloodbath": 0.9,
        "rekt": 0.8,
        "liquidation": 0.75,
        "hack": 0.85,
        "exploit": 0.8,
        "rug pull": 0.95,
        "scam": 0.9,
        "fraud": 0.9,
        "ban": 0.8,
        "regulation": 0.6,
        "crackdown": 0.75,
        "lawsuit": 0.7,
        "sec": 0.5,
        "fud": 0.6,
        "paper hands": 0.55,
        "red candle": 0.6,
        "death cross": 0.75,
        "breakdown": 0.7,
        "whale dump": 0.8,
        "sell-off": 0.75,
        "panic sell": 0.8,
        # Moderate bearish
        "decline": 0.5,
        "decrease": 0.45,
        "loss": 0.55,
        "drop": 0.5,
        "fall": 0.5,
        "negative": 0.4,
        "warning": 0.5,
        "concern": 0.45,
        "risk": 0.4,
        "volatility": 0.35,
    }

    # Crypto symbols/tickers
    CRYPTO_SYMBOLS: set[str] = {
        "BTC",
        "ETH",
        "XRP",
        "BNB",
        "SOL",
        "ADA",
        "DOGE",
        "AVAX",
        "DOT",
        "MATIC",
        "LINK",
        "UNI",
        "ATOM",
        "LTC",
        "ETC",
        "XLM",
        "ALGO",
        "VET",
        "FIL",
        "THETA",
        "AAVE",
        "MKR",
        "COMP",
        "SNX",
        "CRV",
        "SUSHI",
        "YFI",
        "1INCH",
        "SAND",
        "MANA",
        "AXS",
        "GALA",
        "ENJ",
        "APE",
        "SHIB",
        "PEPE",
        "FLOKI",
        "ARB",
        "OP",
        "SUI",
        "APT",
        "SEI",
        "TIA",
        "INJ",
        "PYTH",
        "JUP",
        "WIF",
        "BONK",
        "USDT",
        "USDC",
        "DAI",
        "BUSD",
    }

    # Category keywords
    CATEGORY_KEYWORDS: dict[NewsCategory, list[str]] = {
        NewsCategory.PRICE_MOVEMENT: [
            "price",
            "rally",
            "crash",
            "surge",
            "drop",
            "ath",
            "all-time",
            "market cap",
        ],
        NewsCategory.REGULATION: [
            "sec",
            "regulation",
            "law",
            "legal",
            "ban",
            "approve",
            "license",
            "compliance",
        ],
        NewsCategory.ADOPTION: [
            "adopt",
            "accept",
            "payment",
            "merchant",
            "institutional",
            "mainstream",
        ],
        NewsCategory.TECHNOLOGY: [
            "upgrade",
            "fork",
            "protocol",
            "layer",
            "scalability",
            "consensus",
            "network",
        ],
        NewsCategory.PARTNERSHIP: [
            "partner",
            "collaboration",
            "integration",
            "alliance",
            "deal",
        ],
        NewsCategory.HACK_SECURITY: [
            "hack",
            "exploit",
            "vulnerability",
            "attack",
            "breach",
            "theft",
            "stolen",
        ],
        NewsCategory.EXCHANGE: [
            "exchange",
            "trading",
            "listing",
            "delist",
            "withdrawal",
            "deposit",
        ],
        NewsCategory.MACRO: [
            "fed",
            "inflation",
            "interest rate",
            "economy",
            "recession",
            "dollar",
        ],
        NewsCategory.DEFI: [
            "defi",
            "yield",
            "liquidity",
            "lending",
            "borrowing",
            "tvl",
            "amm",
        ],
        NewsCategory.NFT: ["nft", "collectible", "opensea", "blur", "artwork", "mint"],
    }


# ============================================================================
# News NLP Analyzer
# ============================================================================


class NewsNLPAnalyzer:
    """
    NLP analyzer for crypto news sentiment.

    Uses lexicon-based analysis with optional transformer models.
    """

    def __init__(self, use_transformers: bool = False):
        """
        Initialize analyzer.

        Args:
            use_transformers: Whether to use transformer models (requires additional deps)
        """
        self.lexicon = CryptoSentimentLexicon()
        self.use_transformers = use_transformers
        self._transformer_model: Optional[Any] = None
        self._tokenizer: Optional[Any] = None

        if use_transformers:
            self._load_transformer_model()

        self._analysis_cache: dict[str, SentimentResult] = {}
        self._cache_max_size = 1000

        logger.info(f"NewsNLPAnalyzer initialized (transformers={use_transformers})")

    def _load_transformer_model(self) -> None:
        """Load transformer model for sentiment analysis."""
        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            # Use FinBERT for financial sentiment
            model_name = "ProsusAI/finbert"
            self._tokenizer = AutoTokenizer.from_pretrained(model_name)
            self._transformer_model = (
                AutoModelForSequenceClassification.from_pretrained(model_name)
            )
            logger.info(f"Loaded transformer model: {model_name}")
        except ImportError:
            logger.warning("transformers package not installed, using lexicon only")
            self.use_transformers = False
        except Exception as e:
            logger.error(f"Failed to load transformer model: {e}")
            self.use_transformers = False

    def analyze(self, article: NewsArticle) -> SentimentResult:
        """
        Analyze news article for sentiment.

        Args:
            article: News article to analyze

        Returns:
            Sentiment analysis result
        """
        # Check cache
        cache_key = self._get_cache_key(article)
        if cache_key in self._analysis_cache:
            return self._analysis_cache[cache_key]

        # Combine title and content for analysis
        text = f"{article.title}. {article.content}"
        text_lower = text.lower()

        # Extract mentioned symbols
        symbols = self._extract_symbols(text)

        # Classify category
        category = self._classify_category(text_lower)

        # Calculate sentiment
        if self.use_transformers and self._transformer_model:
            sentiment_score, confidence = self._analyze_with_transformer(text)
        else:
            sentiment_score, confidence = self._analyze_with_lexicon(text_lower)

        # Map score to sentiment enum
        sentiment = self._score_to_sentiment(sentiment_score)

        # Extract key phrases
        key_phrases = self._extract_key_phrases(text)

        # Calculate impact score
        impact_score = self._calculate_impact_score(
            sentiment_score, confidence, symbols, category
        )

        result = SentimentResult(
            article_id=article.article_id,
            sentiment=sentiment,
            confidence=confidence,
            sentiment_score=sentiment_score,
            category=category,
            mentioned_symbols=symbols,
            key_phrases=key_phrases,
            impact_score=impact_score,
        )

        # Cache result
        self._cache_result(cache_key, result)

        return result

    def _get_cache_key(self, article: NewsArticle) -> str:
        """Generate cache key for article."""
        content = f"{article.title}:{article.content[:500]}"
        return hashlib.md5(content.encode()).hexdigest()

    def _cache_result(self, key: str, result: SentimentResult) -> None:
        """Cache analysis result."""
        if len(self._analysis_cache) >= self._cache_max_size:
            # Remove oldest entries
            oldest_keys = list(self._analysis_cache.keys())[: self._cache_max_size // 2]
            for k in oldest_keys:
                del self._analysis_cache[k]

        self._analysis_cache[key] = result

    def _extract_symbols(self, text: str) -> list[str]:
        """Extract crypto symbols from text."""
        text_upper = text.upper()
        found_symbols = []

        for symbol in self.lexicon.CRYPTO_SYMBOLS:
            # Match symbol with word boundaries
            pattern = r"\b" + re.escape(symbol) + r"\b"
            if re.search(pattern, text_upper):
                found_symbols.append(symbol)

        # Also check for full names
        name_to_symbol = {
            "BITCOIN": "BTC",
            "ETHEREUM": "ETH",
            "SOLANA": "SOL",
            "CARDANO": "ADA",
            "RIPPLE": "XRP",
            "DOGECOIN": "DOGE",
            "POLKADOT": "DOT",
            "POLYGON": "MATIC",
            "CHAINLINK": "LINK",
            "UNISWAP": "UNI",
        }

        for name, symbol in name_to_symbol.items():
            if name in text_upper and symbol not in found_symbols:
                found_symbols.append(symbol)

        return found_symbols

    def _classify_category(self, text: str) -> NewsCategory:
        """Classify news category based on keywords."""
        category_scores: dict[NewsCategory, int] = {}

        for category, keywords in self.lexicon.CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                category_scores[category] = score

        if not category_scores:
            return NewsCategory.OTHER

        return max(category_scores.keys(), key=lambda x: category_scores[x])

    def _analyze_with_lexicon(self, text: str) -> tuple[float, float]:
        """
        Analyze sentiment using lexicon.

        Returns:
            (sentiment_score, confidence) where score is -1 to 1
        """
        bullish_score = 0.0
        bearish_score = 0.0
        matches = 0

        # Check bullish terms
        for term, score in self.lexicon.BULLISH_TERMS.items():
            if term in text:
                bullish_score += score
                matches += 1

        # Check bearish terms
        for term, score in self.lexicon.BEARISH_TERMS.items():
            if term in text:
                bearish_score += score
                matches += 1

        # Calculate net sentiment
        if matches == 0:
            return 0.0, 0.3  # Neutral with low confidence

        total_score = bullish_score + bearish_score
        if total_score == 0:
            return 0.0, 0.5

        sentiment_score = (bullish_score - bearish_score) / total_score

        # Confidence based on number of matches
        confidence = min(0.5 + (matches * 0.1), 0.95)

        return sentiment_score, confidence

    def _analyze_with_transformer(self, text: str) -> tuple[float, float]:
        """
        Analyze sentiment using transformer model.

        Returns:
            (sentiment_score, confidence)
        """
        if not self._transformer_model or not self._tokenizer:
            return self._analyze_with_lexicon(text.lower())

        try:
            import torch

            # Tokenize
            inputs = self._tokenizer(
                text[:512],  # Truncate to max length
                return_tensors="pt",
                truncation=True,
                max_length=512,
            )

            # Get predictions
            with torch.no_grad():
                outputs = self._transformer_model(**inputs)
                probs = torch.softmax(outputs.logits, dim=1)[0]

            # FinBERT outputs: [negative, neutral, positive]
            neg_prob = float(probs[0])
            pos_prob = float(probs[2])

            sentiment_score = pos_prob - neg_prob
            confidence = float(probs.max())

            return sentiment_score, confidence

        except Exception as e:
            logger.error(f"Transformer analysis failed: {e}")
            return self._analyze_with_lexicon(text.lower())

    def _score_to_sentiment(self, score: float) -> Sentiment:
        """Convert sentiment score to enum."""
        if score >= 0.6:
            return Sentiment.VERY_BULLISH
        elif score >= 0.2:
            return Sentiment.BULLISH
        elif score <= -0.6:
            return Sentiment.VERY_BEARISH
        elif score <= -0.2:
            return Sentiment.BEARISH
        else:
            return Sentiment.NEUTRAL

    def _extract_key_phrases(self, text: str, max_phrases: int = 5) -> list[str]:
        """Extract key phrases from text."""
        # Simple extraction: sentences containing sentiment keywords
        sentences = re.split(r"[.!?]", text)
        key_phrases = []

        all_keywords = set(self.lexicon.BULLISH_TERMS.keys()) | set(
            self.lexicon.BEARISH_TERMS.keys()
        )

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 10 or len(sentence) > 200:
                continue

            sentence_lower = sentence.lower()
            if any(kw in sentence_lower for kw in all_keywords):
                key_phrases.append(sentence)

            if len(key_phrases) >= max_phrases:
                break

        return key_phrases

    def _calculate_impact_score(
        self,
        sentiment_score: float,
        confidence: float,
        symbols: list[str],
        category: NewsCategory,
    ) -> float:
        """Calculate potential market impact score."""
        # Base impact from sentiment strength
        impact = abs(sentiment_score) * 0.4

        # Boost for high confidence
        impact += confidence * 0.2

        # Boost for specific symbols mentioned
        impact += min(len(symbols) * 0.1, 0.2)

        # Category-specific impact modifiers
        category_weights = {
            NewsCategory.REGULATION: 1.3,
            NewsCategory.HACK_SECURITY: 1.4,
            NewsCategory.PRICE_MOVEMENT: 1.1,
            NewsCategory.ADOPTION: 1.2,
            NewsCategory.PARTNERSHIP: 1.0,
            NewsCategory.TECHNOLOGY: 0.9,
            NewsCategory.EXCHANGE: 1.1,
            NewsCategory.MACRO: 1.2,
            NewsCategory.DEFI: 0.9,
            NewsCategory.NFT: 0.8,
            NewsCategory.OTHER: 0.7,
        }

        impact *= category_weights.get(category, 1.0)

        return min(impact, 1.0)


# ============================================================================
# Aggregated Sentiment Score
# ============================================================================


class SentimentAggregator:
    """Aggregate sentiment from multiple news sources."""

    def __init__(self, decay_hours: float = 24.0):
        """
        Initialize aggregator.

        Args:
            decay_hours: Half-life for time decay of sentiment
        """
        self.decay_hours = decay_hours
        self._results: dict[str, list[SentimentResult]] = {}  # symbol -> results

    def add_result(self, result: SentimentResult) -> None:
        """Add sentiment result to aggregator."""
        for symbol in result.mentioned_symbols:
            if symbol not in self._results:
                self._results[symbol] = []
            self._results[symbol].append(result)

    def get_aggregated_sentiment(self, symbol: str) -> dict[str, Any]:
        """
        Get aggregated sentiment for symbol.

        Returns weighted average considering recency and impact.
        """
        results = self._results.get(symbol, [])
        if not results:
            return {
                "symbol": symbol,
                "sentiment": Sentiment.NEUTRAL.name,
                "score": 0.0,
                "confidence": 0.0,
                "num_sources": 0,
                "dominant_category": None,
            }

        now = datetime.now(timezone.utc)
        weighted_scores: list[float] = []
        weighted_confidences: list[float] = []
        category_counts: dict[NewsCategory, int] = {}

        for r in results:
            # Calculate time decay weight
            hours_old = (now - r.analyzed_at).total_seconds() / 3600
            time_weight = 0.5 ** (hours_old / self.decay_hours)

            # Combined weight
            weight = time_weight * r.impact_score * r.confidence

            weighted_scores.append(r.sentiment_score * weight)
            weighted_confidences.append(r.confidence * weight)

            category_counts[r.category] = category_counts.get(r.category, 0) + 1

        total_weight = sum(abs(s) for s in weighted_scores) or 1.0
        avg_score = sum(weighted_scores) / total_weight
        avg_confidence = sum(weighted_confidences) / len(weighted_confidences)

        # Map to sentiment
        if avg_score >= 0.6:
            sentiment = Sentiment.VERY_BULLISH
        elif avg_score >= 0.2:
            sentiment = Sentiment.BULLISH
        elif avg_score <= -0.6:
            sentiment = Sentiment.VERY_BEARISH
        elif avg_score <= -0.2:
            sentiment = Sentiment.BEARISH
        else:
            sentiment = Sentiment.NEUTRAL

        dominant_category = (
            max(category_counts.keys(), key=lambda x: category_counts[x])
            if category_counts
            else None
        )

        return {
            "symbol": symbol,
            "sentiment": sentiment.name,
            "score": avg_score,
            "confidence": avg_confidence,
            "num_sources": len(results),
            "dominant_category": dominant_category.value if dominant_category else None,
        }

    def get_trending_symbols(self, top_n: int = 10) -> list[dict[str, Any]]:
        """Get symbols with most news activity."""
        symbol_activity = []

        for symbol, results in self._results.items():
            recent_results = [
                r
                for r in results
                if (datetime.now(timezone.utc) - r.analyzed_at).total_seconds() < 86400
            ]

            if recent_results:
                avg_impact = sum(r.impact_score for r in recent_results) / len(
                    recent_results
                )
                symbol_activity.append(
                    {
                        "symbol": symbol,
                        "news_count": len(recent_results),
                        "avg_impact": avg_impact,
                        "sentiment": self.get_aggregated_sentiment(symbol),
                    }
                )

        # Sort by news count * impact
        symbol_activity.sort(
            key=lambda x: x["news_count"] * x["avg_impact"], reverse=True
        )

        return symbol_activity[:top_n]


# ============================================================================
# Global Instance
# ============================================================================

_analyzer: Optional[NewsNLPAnalyzer] = None
_aggregator: Optional[SentimentAggregator] = None


def get_news_analyzer(use_transformers: bool = False) -> NewsNLPAnalyzer:
    """Get or create global news analyzer."""
    global _analyzer
    if _analyzer is None:
        _analyzer = NewsNLPAnalyzer(use_transformers=use_transformers)
    return _analyzer


def get_sentiment_aggregator() -> SentimentAggregator:
    """Get or create global sentiment aggregator."""
    global _aggregator
    if _aggregator is None:
        _aggregator = SentimentAggregator()
    return _aggregator
