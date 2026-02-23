"""
Sentiment Analysis Module for Universal Math Engine v2.4.

This module provides sentiment-based trading signals:
1. NewsSentimentAnalyzer - News article sentiment analysis
2. SocialSentimentTracker - Social media sentiment (Twitter/Reddit)
3. FearGreedIndex - Fear & Greed index calculation
4. SentimentSignalGenerator - Trading signals from sentiment

Data Sources:
- News APIs (Crypto Panic, NewsAPI, etc.)
- Social Media (Twitter, Reddit via API)
- On-chain metrics (optional)

Author: Universal Math Engine Team
Version: 2.4.0
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

import numpy as np
from numpy.typing import NDArray

# =============================================================================
# ENUMS AND DATA CLASSES
# =============================================================================


class SentimentLevel(Enum):
    """Sentiment classification levels."""

    EXTREME_FEAR = "extreme_fear"
    FEAR = "fear"
    NEUTRAL = "neutral"
    GREED = "greed"
    EXTREME_GREED = "extreme_greed"


class SentimentSource(Enum):
    """Sources of sentiment data."""

    NEWS = "news"
    TWITTER = "twitter"
    REDDIT = "reddit"
    TELEGRAM = "telegram"
    FEAR_GREED_INDEX = "fear_greed"
    ON_CHAIN = "on_chain"


@dataclass
class SentimentData:
    """Individual sentiment data point."""

    source: SentimentSource
    timestamp: datetime
    score: float  # -1 (bearish) to +1 (bullish)
    confidence: float  # 0-1
    volume: int = 1  # Number of mentions/articles
    raw_text: str | None = None
    keywords: list[str] = field(default_factory=list)
    symbol: str | None = None


@dataclass
class AggregateSentiment:
    """Aggregated sentiment across sources."""

    timestamp: datetime
    overall_score: float  # -1 to +1
    overall_confidence: float
    level: SentimentLevel
    source_scores: dict[SentimentSource, float] = field(default_factory=dict)
    source_volumes: dict[SentimentSource, int] = field(default_factory=dict)
    trending_keywords: list[str] = field(default_factory=list)
    change_24h: float = 0.0


@dataclass
class SentimentConfig:
    """Configuration for sentiment analysis."""

    # Sources to use
    enabled_sources: list[SentimentSource] = field(
        default_factory=lambda: [SentimentSource.NEWS, SentimentSource.TWITTER]
    )

    # Weights for each source
    source_weights: dict[SentimentSource, float] = field(
        default_factory=lambda: {
            SentimentSource.NEWS: 0.3,
            SentimentSource.TWITTER: 0.25,
            SentimentSource.REDDIT: 0.2,
            SentimentSource.FEAR_GREED_INDEX: 0.15,
            SentimentSource.ON_CHAIN: 0.1,
        }
    )

    # Thresholds for sentiment levels
    extreme_fear_threshold: float = -0.6
    fear_threshold: float = -0.2
    greed_threshold: float = 0.2
    extreme_greed_threshold: float = 0.6

    # Time windows
    short_window_hours: int = 4
    medium_window_hours: int = 24
    long_window_hours: int = 168  # 1 week

    # Signal generation
    signal_threshold: float = 0.3  # Minimum sentiment for signal
    contrarian_mode: bool = False  # Trade against extreme sentiment

    # Keywords to track
    bullish_keywords: list[str] = field(
        default_factory=lambda: [
            "bullish",
            "moon",
            "pump",
            "buy",
            "long",
            "breakout",
            "rally",
            "accumulate",
            "hodl",
            "support",
            "bounce",
            "reversal up",
        ]
    )
    bearish_keywords: list[str] = field(
        default_factory=lambda: [
            "bearish",
            "dump",
            "crash",
            "sell",
            "short",
            "breakdown",
            "correction",
            "distribution",
            "resistance",
            "reversal down",
        ]
    )


@dataclass
class SentimentSignal:
    """Trading signal from sentiment analysis."""

    timestamp: datetime
    signal_type: str  # "long", "short", "neutral"
    strength: float  # 0-1
    sentiment_score: float
    sentiment_level: SentimentLevel
    reason: str
    sources_agree: int  # Number of sources agreeing


# =============================================================================
# LEXICON-BASED SENTIMENT ANALYZER
# =============================================================================


class LexiconSentimentAnalyzer:
    """
    Simple lexicon-based sentiment analyzer.

    Uses predefined word lists to calculate sentiment scores.
    """

    def __init__(self, config: SentimentConfig):
        self.config = config
        self._build_lexicon()

    def _build_lexicon(self):
        """Build sentiment lexicon."""
        # Crypto-specific sentiment words
        self.positive_words = {
                # General positive
                "good",
                "great",
                "excellent",
                "amazing",
                "positive",
                "bullish",
                "strong",
                "growth",
                "profit",
                "gain",
                "success",
                "win",
                "up",
                # Crypto specific
                "moon",
                "mooning",
                "pump",
                "pumping",
                "rally",
                "breakout",
                "accumulate",
                "hodl",
                "hold",
                "buy",
                "long",
                "support",
                "adoption",
                "institutional",
                "partnership",
                "upgrade",
                "milestone",
                "ath",
                "new high",
                "recovery",
                "bounce",
            }

        self.negative_words = {
                # General negative
                "bad",
                "terrible",
                "awful",
                "negative",
                "bearish",
                "weak",
                "loss",
                "fail",
                "down",
                "crash",
                "fear",
                "panic",
                "worry",
                # Crypto specific
                "dump",
                "dumping",
                "correction",
                "sell",
                "short",
                "resistance",
                "breakdown",
                "scam",
                "hack",
                "exploit",
                "rug",
                "fud",
                "bear",
                "capitulation",
                "liquidation",
                "rekt",
            }

        # Intensifiers and negations
        self.intensifiers = {"very", "extremely", "highly", "super", "mega"}
        self.negations = {"not", "no", "never", "neither", "nobody", "nothing"}

    def analyze(self, text: str) -> float:
        """
        Analyze sentiment of text.

        Returns:
            Score from -1 (bearish) to +1 (bullish)
        """
        if not text:
            return 0.0

        # Normalize text
        text = text.lower()
        words = re.findall(r"\b\w+\b", text)

        if not words:
            return 0.0

        positive_count = 0
        negative_count = 0
        negation_active = False

        for i, word in enumerate(words):
            # Check for negation
            if word in self.negations:
                negation_active = True
                continue

            # Check for intensifier
            intensifier = 1.0
            if i > 0 and words[i - 1] in self.intensifiers:
                intensifier = 1.5

            # Count sentiment
            if word in self.positive_words:
                if negation_active:
                    negative_count += intensifier
                else:
                    positive_count += intensifier
                negation_active = False
            elif word in self.negative_words:
                if negation_active:
                    positive_count += intensifier
                else:
                    negative_count += intensifier
                negation_active = False
            else:
                # Reset negation after non-sentiment word
                if i > 0:
                    negation_active = False

        total = positive_count + negative_count
        if total == 0:
            return 0.0

        # Calculate normalized score
        score = (positive_count - negative_count) / total

        return max(-1.0, min(1.0, score))

    def extract_keywords(self, text: str) -> list[str]:
        """Extract sentiment-relevant keywords from text."""
        if not text:
            return []

        text = text.lower()
        words = re.findall(r"\b\w+\b", text)

        keywords = []
        for word in words:
            if word in self.positive_words or word in self.negative_words:
                keywords.append(word)

        return list(set(keywords))


# =============================================================================
# NEWS SENTIMENT ANALYZER
# =============================================================================


class NewsSentimentAnalyzer:
    """
    Analyzes sentiment from crypto news articles.

    Can work with cached data or simulated data for backtesting.
    """

    def __init__(self, config: SentimentConfig):
        self.config = config
        self.lexicon = LexiconSentimentAnalyzer(config)
        self._cache: dict[str, SentimentData] = {}

    def analyze_article(
        self,
        title: str,
        content: str | None = None,
        timestamp: datetime | None = None,
        source_name: str = "unknown",
    ) -> SentimentData:
        """Analyze a single news article."""
        # Combine title and content
        full_text = title
        if content:
            full_text += " " + content

        # Calculate sentiment score
        score = self.lexicon.analyze(full_text)

        # Title has more weight
        title_score = self.lexicon.analyze(title)
        score = 0.6 * title_score + 0.4 * score

        # Calculate confidence based on text length and keywords
        keywords = self.lexicon.extract_keywords(full_text)
        confidence = min(1.0, len(keywords) / 5)

        return SentimentData(
            source=SentimentSource.NEWS,
            timestamp=timestamp or datetime.now(),
            score=score,
            confidence=confidence,
            volume=1,
            raw_text=title[:200],
            keywords=keywords,
        )

    def analyze_batch(
        self,
        articles: list[dict],
        timestamp: datetime | None = None,
    ) -> SentimentData:
        """Analyze a batch of articles and aggregate."""
        if not articles:
            return SentimentData(
                source=SentimentSource.NEWS,
                timestamp=timestamp or datetime.now(),
                score=0.0,
                confidence=0.0,
                volume=0,
            )

        scores = []
        all_keywords = []

        for article in articles:
            result = self.analyze_article(
                title=article.get("title", ""),
                content=article.get("content"),
                timestamp=timestamp,
            )
            scores.append(result.score * result.confidence)
            all_keywords.extend(result.keywords)

        # Weighted average
        avg_score = np.mean(scores) if scores else 0.0
        avg_confidence = (
            len([s for s in scores if abs(s) > 0.1]) / len(scores) if scores else 0.0
        )

        return SentimentData(
            source=SentimentSource.NEWS,
            timestamp=timestamp or datetime.now(),
            score=avg_score,
            confidence=avg_confidence,
            volume=len(articles),
            keywords=list(set(all_keywords))[:10],
        )


# =============================================================================
# SOCIAL SENTIMENT TRACKER
# =============================================================================


class SocialSentimentTracker:
    """
    Tracks sentiment from social media platforms.

    Supports Twitter, Reddit, and Telegram (simulated for backtesting).
    """

    def __init__(self, config: SentimentConfig):
        self.config = config
        self.lexicon = LexiconSentimentAnalyzer(config)

    def analyze_posts(
        self,
        posts: list[dict],
        platform: SentimentSource,
        timestamp: datetime | None = None,
    ) -> SentimentData:
        """Analyze social media posts."""
        if not posts:
            return SentimentData(
                source=platform,
                timestamp=timestamp or datetime.now(),
                score=0.0,
                confidence=0.0,
                volume=0,
            )

        scores = []
        all_keywords = []
        total_engagement = 0

        for post in posts:
            text = post.get("text", post.get("content", ""))
            score = self.lexicon.analyze(text)

            # Weight by engagement
            engagement = (
                post.get("likes", 0)
                + post.get("retweets", 0) * 2
                + post.get("comments", 0) * 1.5
            )
            engagement = max(1, engagement)

            scores.append(score * np.log1p(engagement))
            total_engagement += engagement
            all_keywords.extend(self.lexicon.extract_keywords(text))

        # Weighted average
        avg_score = np.sum(scores) / max(1, np.log1p(total_engagement))
        avg_score = max(-1.0, min(1.0, avg_score))

        return SentimentData(
            source=platform,
            timestamp=timestamp or datetime.now(),
            score=avg_score,
            confidence=min(1.0, len(posts) / 100),
            volume=len(posts),
            keywords=list(set(all_keywords))[:10],
        )

    def simulate_social_sentiment(
        self,
        price_returns: NDArray,
        volatility: NDArray,
        base_sentiment: float = 0.0,
    ) -> list[SentimentData]:
        """
        Simulate social sentiment based on price action.

        For backtesting when real social data is unavailable.
        """
        n = len(price_returns)
        sentiments = []

        np.random.seed(42)

        for i in range(n):
            # Base sentiment influenced by recent returns
            lookback = min(24, i + 1)
            recent_return = np.mean(price_returns[max(0, i - lookback + 1) : i + 1])

            # Sentiment tends to follow price with lag
            price_sentiment = np.tanh(recent_return * 50)  # Scale returns

            # Add noise
            noise = np.random.normal(0, 0.2)

            # Combine factors
            score = 0.7 * price_sentiment + 0.3 * base_sentiment + noise
            score = max(-1.0, min(1.0, score))

            # Higher volatility = lower confidence
            confidence = max(0.2, 1.0 - volatility[i] * 10)

            sentiments.append(
                SentimentData(
                    source=SentimentSource.TWITTER,
                    timestamp=datetime.now() - timedelta(hours=n - i),
                    score=score,
                    confidence=confidence,
                    volume=int(100 + abs(recent_return) * 1000),
                )
            )

        return sentiments


# =============================================================================
# FEAR & GREED INDEX
# =============================================================================


class FearGreedCalculator:
    """
    Calculates Fear & Greed Index similar to alternative.me.

    Components:
    - Volatility (25%)
    - Market Momentum/Volume (25%)
    - Social Media (15%)
    - Dominance (10%)
    - Trends (10%)
    - Sentiment Survey (15%) - simulated
    """

    def __init__(self, config: SentimentConfig):
        self.config = config

    def calculate(
        self,
        close: NDArray,
        volume: NDArray | None = None,
        btc_dominance: float | None = None,
        social_sentiment: float | None = None,
    ) -> tuple[float, SentimentLevel]:
        """
        Calculate Fear & Greed Index.

        Returns:
            Tuple of (index 0-100, SentimentLevel)
        """
        components = {}

        # 1. Volatility (25%) - lower volatility = more greed
        volatility_score = self._calculate_volatility_component(close)
        components["volatility"] = volatility_score

        # 2. Market Momentum/Volume (25%)
        momentum_score = self._calculate_momentum_component(close, volume)
        components["momentum"] = momentum_score

        # 3. Social Media (15%)
        if social_sentiment is not None:
            social_score = (social_sentiment + 1) / 2 * 100  # Convert -1,1 to 0-100
        else:
            # Simulate based on price trend
            recent_return = (close[-1] / close[-20] - 1) if len(close) > 20 else 0
            social_score = 50 + recent_return * 500
        social_score = max(0, min(100, social_score))
        components["social"] = social_score

        # 4. BTC Dominance (10%)
        if btc_dominance is not None:
            # Higher dominance = more fear (flight to safety)
            dominance_score = 100 - btc_dominance
        else:
            dominance_score = 50
        components["dominance"] = dominance_score

        # 5. Trends (10%) - search volume simulation
        trend_score = (
            50 + (close[-1] / np.mean(close[-30:]) - 1) * 100 if len(close) > 30 else 50
        )
        trend_score = max(0, min(100, trend_score))
        components["trends"] = trend_score

        # 6. Sentiment Survey (15%) - simulated based on other components
        survey_score = np.mean([volatility_score, momentum_score, social_score])
        components["survey"] = survey_score

        # Weighted average
        weights = {
            "volatility": 0.25,
            "momentum": 0.25,
            "social": 0.15,
            "dominance": 0.10,
            "trends": 0.10,
            "survey": 0.15,
        }

        index = sum(components[k] * weights[k] for k in weights)
        index = max(0, min(100, index))

        # Determine level
        level = self._index_to_level(index)

        return index, level

    def _calculate_volatility_component(self, close: NDArray) -> float:
        """Calculate volatility component (0-100)."""
        if len(close) < 30:
            return 50

        # 30-day volatility
        returns = np.diff(close) / close[:-1]
        current_vol = np.std(returns[-30:]) * np.sqrt(365)

        # 90-day average volatility for comparison
        avg_vol = (
            np.std(returns[-90:]) * np.sqrt(365) if len(returns) > 90 else current_vol
        )

        # Lower volatility = higher score (more greed)
        vol_ratio = current_vol / (avg_vol + 1e-10)
        score = 100 - min(100, vol_ratio * 50)

        return max(0, min(100, score))

    def _calculate_momentum_component(
        self,
        close: NDArray,
        volume: NDArray | None = None,
    ) -> float:
        """Calculate momentum/volume component."""
        if len(close) < 30:
            return 50

        # Price momentum
        momentum_7d = (close[-1] / close[-7] - 1) * 100 if len(close) > 7 else 0
        momentum_30d = (close[-1] / close[-30] - 1) * 100 if len(close) > 30 else 0

        price_score = 50 + (momentum_7d * 2 + momentum_30d) / 3

        # Volume momentum
        if volume is not None and len(volume) > 30:
            vol_ratio = np.mean(volume[-7:]) / np.mean(volume[-30:])
            vol_score = 50 + (vol_ratio - 1) * 50
        else:
            vol_score = 50

        score = 0.6 * price_score + 0.4 * vol_score
        return max(0, min(100, score))

    def _index_to_level(self, index: float) -> SentimentLevel:
        """Convert index to sentiment level."""
        if index < 20:
            return SentimentLevel.EXTREME_FEAR
        elif index < 40:
            return SentimentLevel.FEAR
        elif index < 60:
            return SentimentLevel.NEUTRAL
        elif index < 80:
            return SentimentLevel.GREED
        else:
            return SentimentLevel.EXTREME_GREED


# =============================================================================
# SENTIMENT SIGNAL GENERATOR
# =============================================================================


class SentimentSignalGenerator:
    """
    Generates trading signals from sentiment analysis.

    Can operate in:
    - Momentum mode: Trade with sentiment
    - Contrarian mode: Trade against extreme sentiment
    """

    def __init__(self, config: SentimentConfig):
        self.config = config
        self.news_analyzer = NewsSentimentAnalyzer(config)
        self.social_tracker = SocialSentimentTracker(config)
        self.fear_greed = FearGreedCalculator(config)

    def generate_signal(
        self,
        sentiment: AggregateSentiment,
        price_trend: float = 0.0,
    ) -> SentimentSignal:
        """Generate trading signal from sentiment."""
        score = sentiment.overall_score
        level = sentiment.level
        confidence = sentiment.overall_confidence

        # Count agreeing sources
        sources_agree = sum(
            1
            for s in sentiment.source_scores.values()
            if (s > 0 and score > 0) or (s < 0 and score < 0)
        )

        signal_type = "neutral"
        strength = 0.0
        reason = ""

        if self.config.contrarian_mode:
            # Contrarian: trade against extreme sentiment
            if level == SentimentLevel.EXTREME_FEAR:
                signal_type = "long"
                strength = min(1.0, abs(score) * confidence)
                reason = "Contrarian buy: Extreme fear"
            elif level == SentimentLevel.EXTREME_GREED:
                signal_type = "short"
                strength = min(1.0, abs(score) * confidence)
                reason = "Contrarian sell: Extreme greed"
        else:
            # Momentum: trade with sentiment
            if score > self.config.signal_threshold:
                signal_type = "long"
                strength = min(1.0, score * confidence)
                reason = f"Bullish sentiment: {level.value}"
            elif score < -self.config.signal_threshold:
                signal_type = "short"
                strength = min(1.0, abs(score) * confidence)
                reason = f"Bearish sentiment: {level.value}"

        # Reduce strength if sentiment conflicts with price trend
        if (signal_type == "long" and price_trend < -0.02) or (
            signal_type == "short" and price_trend > 0.02
        ):
            strength *= 0.5
            reason += " (conflicting with price trend)"

        return SentimentSignal(
            timestamp=sentiment.timestamp,
            signal_type=signal_type,
            strength=strength,
            sentiment_score=score,
            sentiment_level=level,
            reason=reason,
            sources_agree=sources_agree,
        )

    def aggregate_sentiment(
        self,
        sentiment_data: list[SentimentData],
        timestamp: datetime | None = None,
    ) -> AggregateSentiment:
        """Aggregate sentiment from multiple sources."""
        if not sentiment_data:
            return AggregateSentiment(
                timestamp=timestamp or datetime.now(),
                overall_score=0.0,
                overall_confidence=0.0,
                level=SentimentLevel.NEUTRAL,
            )

        source_scores: dict[SentimentSource, list[float]] = {}
        source_volumes: dict[SentimentSource, int] = {}
        all_keywords = []

        for data in sentiment_data:
            source = data.source
            if source not in source_scores:
                source_scores[source] = []
                source_volumes[source] = 0

            source_scores[source].append(data.score * data.confidence)
            source_volumes[source] += data.volume
            all_keywords.extend(data.keywords)

        # Calculate weighted average
        weighted_scores = []
        total_weight = 0

        for source, scores in source_scores.items():
            weight = self.config.source_weights.get(source, 0.1)
            avg_score = np.mean(scores) if scores else 0
            weighted_scores.append(avg_score * weight)
            total_weight += weight

        overall_score = sum(weighted_scores) / total_weight if total_weight > 0 else 0
        overall_score = max(-1.0, min(1.0, overall_score))

        # Calculate confidence
        overall_confidence = min(1.0, len(sentiment_data) / 10)

        # Determine level
        level = self._score_to_level(overall_score)

        # Get trending keywords
        keyword_counts: dict[str, int] = {}
        for kw in all_keywords:
            keyword_counts[kw] = keyword_counts.get(kw, 0) + 1
        trending = sorted(
            keyword_counts.keys(), key=lambda x: keyword_counts[x], reverse=True
        )[:5]

        return AggregateSentiment(
            timestamp=timestamp or datetime.now(),
            overall_score=overall_score,
            overall_confidence=overall_confidence,
            level=level,
            source_scores={s: np.mean(v) for s, v in source_scores.items()},
            source_volumes=source_volumes,
            trending_keywords=trending,
        )

    def _score_to_level(self, score: float) -> SentimentLevel:
        """Convert sentiment score to level."""
        if score <= self.config.extreme_fear_threshold:
            return SentimentLevel.EXTREME_FEAR
        elif score <= self.config.fear_threshold:
            return SentimentLevel.FEAR
        elif score >= self.config.extreme_greed_threshold:
            return SentimentLevel.EXTREME_GREED
        elif score >= self.config.greed_threshold:
            return SentimentLevel.GREED
        else:
            return SentimentLevel.NEUTRAL

    def simulate_sentiment_history(
        self,
        close: NDArray,
        volume: NDArray | None = None,
    ) -> list[AggregateSentiment]:
        """
        Simulate sentiment history for backtesting.

        Uses price action to generate realistic sentiment patterns.
        """
        n = len(close)
        returns = np.zeros(n)
        returns[1:] = (close[1:] - close[:-1]) / close[:-1]

        volatility = np.zeros(n)
        for i in range(20, n):
            volatility[i] = np.std(returns[i - 20 : i])

        # Simulate social sentiment
        social_data = self.social_tracker.simulate_social_sentiment(returns, volatility)

        sentiments = []
        for i in range(n):
            # Create simulated sentiment data
            data_points = [social_data[i]]

            # Add simulated fear/greed
            fg_index, _fg_level = self.fear_greed.calculate(
                close[: i + 1],
                volume[: i + 1] if volume is not None else None,
            )
            fg_score = (fg_index - 50) / 50  # Convert 0-100 to -1,1

            data_points.append(
                SentimentData(
                    source=SentimentSource.FEAR_GREED_INDEX,
                    timestamp=datetime.now() - timedelta(hours=n - i),
                    score=fg_score,
                    confidence=0.8,
                    volume=1,
                )
            )

            # Aggregate
            agg = self.aggregate_sentiment(data_points)
            sentiments.append(agg)

        return sentiments


# =============================================================================
# MAIN SENTIMENT ANALYZER
# =============================================================================


class SentimentAnalyzer:
    """
    Main interface for sentiment analysis.

    Combines all sentiment sources and generates trading signals.
    """

    def __init__(self, config: SentimentConfig | None = None):
        self.config = config or SentimentConfig()
        self.signal_generator = SentimentSignalGenerator(self.config)
        self.fear_greed = FearGreedCalculator(self.config)

    def analyze(
        self,
        close: NDArray,
        volume: NDArray | None = None,
        news_data: list[dict] | None = None,
        social_data: list[dict] | None = None,
    ) -> tuple[list[AggregateSentiment], list[SentimentSignal]]:
        """
        Analyze sentiment and generate signals.

        Args:
            close: Close prices
            volume: Volume data
            news_data: Optional news articles
            social_data: Optional social media posts

        Returns:
            Tuple of (sentiments, signals)
        """
        # Generate or use provided sentiment data
        if news_data is None and social_data is None:
            # Simulate for backtesting
            sentiments = self.signal_generator.simulate_sentiment_history(close, volume)
        else:
            # Use provided data
            sentiments = self._process_real_data(close, news_data, social_data)

        # Generate signals
        signals = []
        for i, sentiment in enumerate(sentiments):
            # Calculate price trend
            price_trend = (close[i] - close[i - 20]) / close[i - 20] if i >= 20 else 0.0

            signal = self.signal_generator.generate_signal(sentiment, price_trend)
            signals.append(signal)

        return sentiments, signals

    def _process_real_data(
        self,
        close: NDArray,
        news_data: list[dict] | None,
        social_data: list[dict] | None,
    ) -> list[AggregateSentiment]:
        """Process real sentiment data."""
        n = len(close)
        sentiments = []

        for i in range(n):
            data_points = []

            # Process news if available
            if news_data:
                news_analyzer = NewsSentimentAnalyzer(self.config)
                news_result = news_analyzer.analyze_batch(news_data)
                data_points.append(news_result)

            # Process social if available
            if social_data:
                social_tracker = SocialSentimentTracker(self.config)
                social_result = social_tracker.analyze_posts(
                    social_data, SentimentSource.TWITTER
                )
                data_points.append(social_result)

            # Add fear/greed
            fg_index, _ = self.fear_greed.calculate(close[: i + 1])
            data_points.append(
                SentimentData(
                    source=SentimentSource.FEAR_GREED_INDEX,
                    timestamp=datetime.now(),
                    score=(fg_index - 50) / 50,
                    confidence=0.8,
                    volume=1,
                )
            )

            agg = self.signal_generator.aggregate_sentiment(data_points)
            sentiments.append(agg)

        return sentiments

    def get_sentiment_filter(
        self,
        close: NDArray,
        allowed_levels: list[SentimentLevel],
        volume: NDArray | None = None,
    ) -> NDArray:
        """
        Get boolean filter for trading based on sentiment levels.

        Args:
            close: Close prices
            allowed_levels: List of sentiment levels to allow trading
            volume: Optional volume data

        Returns:
            Boolean array where True = trading allowed
        """
        sentiments, _ = self.analyze(close, volume)
        return np.array([s.level in allowed_levels for s in sentiments])

    def get_fear_greed_history(
        self,
        close: NDArray,
        volume: NDArray | None = None,
    ) -> tuple[NDArray, list[SentimentLevel]]:
        """
        Get Fear & Greed index history.

        Returns:
            Tuple of (index values 0-100, levels)
        """
        n = len(close)
        indices = np.zeros(n)
        levels = []

        for i in range(n):
            idx, level = self.fear_greed.calculate(
                close[: i + 1],
                volume[: i + 1] if volume is not None else None,
            )
            indices[i] = idx
            levels.append(level)

        return indices, levels
