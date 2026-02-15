"""
Auto Tagger -- automatic tag generation from content and metadata.

Generates tags via:
    1. Pattern matching (symbols, indicators, timeframes)
    2. Keyword extraction (simple TF weighting)
    3. Metadata mapping (source -> tag, agent -> tag)

All generated tags are normalized through TagNormalizer before return.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from loguru import logger

from backend.agents.memory.tag_normalizer import get_tag_normalizer

# ------------------------------------------------------------------
# Stop words (stripped before keyword extraction)
# ------------------------------------------------------------------

_STOP_WORDS: set[str] = {
    "a",
    "an",
    "the",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "shall",
    "should",
    "may",
    "might",
    "must",
    "can",
    "could",
    "i",
    "me",
    "my",
    "we",
    "our",
    "you",
    "your",
    "he",
    "she",
    "it",
    "they",
    "them",
    "their",
    "this",
    "that",
    "these",
    "those",
    "and",
    "but",
    "or",
    "nor",
    "not",
    "no",
    "so",
    "if",
    "then",
    "for",
    "to",
    "from",
    "of",
    "in",
    "on",
    "at",
    "by",
    "with",
    "about",
    "into",
    "through",
    "during",
    "before",
    "after",
    "above",
    "below",
    "between",
    "same",
    "other",
    "each",
    "every",
    "all",
    "both",
    "few",
    "more",
    "most",
    "some",
    "any",
    "such",
    "only",
    "very",
    "just",
    "also",
    "than",
    "too",
    "here",
    "there",
    "when",
    "where",
    "how",
    "what",
    "which",
    "who",
    "whom",
    "why",
    "up",
    "out",
    "as",
    "its",
}


class AutoTagger:
    """Automatically generate tags from content and metadata.

    Strategies (applied in order, results merged):

    1. **Pattern matching** -- regex for known trading entities
       (crypto symbols, technical indicators, timeframes).
    2. **Keyword extraction** -- simple term-frequency weighting
       with stop-word removal.
    3. **Metadata mapping** -- ``source`` and ``agent_namespace``
       are mapped to prefixed tags (``source:backtest``,
       ``agent:deepseek``).

    All tags are normalized via :class:`TagNormalizer` and deduplicated.
    """

    # ------------------------------------------------------------------
    # Compiled patterns for domain entities
    # ------------------------------------------------------------------
    PATTERNS: dict[str, re.Pattern[str]] = {
        # Crypto trading pairs: BTCUSDT, ETHUSDT, SOLUSDT etc.
        "symbol": re.compile(r"\b([A-Z]{2,10}USDT)\b"),
        # Technical indicators (case-insensitive)
        "indicator": re.compile(
            r"\b(RSI|MACD|EMA|SMA|ATR|ADX|CCI|OBV|MFI|VWAP"
            r"|Bollinger|Stochastic|Ichimoku|Fibonacci|Williams"
            r"|Parabolic\s*SAR|Keltner|Donchian)\b",
            re.IGNORECASE,
        ),
        # Timeframes
        "timeframe": re.compile(r"\b(1m|3m|5m|15m|30m|1h|2h|4h|6h|8h|12h|1d|3d|1w|1M)\b"),
        # Price action concepts
        "price_action": re.compile(
            r"\b(support|resistance|breakout|breakdown|consolidation"
            r"|reversal|pullback|retracement|divergence|crossover"
            r"|overbought|oversold|golden\s*cross|death\s*cross)\b",
            re.IGNORECASE,
        ),
    }

    # Token-splitting regex: word boundaries + strip punctuation.
    _TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")

    def __init__(self, max_keyword_tags: int = 5) -> None:
        self._max_keyword_tags = max_keyword_tags
        self._normalizer = get_tag_normalizer()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_tags(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
        source: str | None = None,
        agent_namespace: str | None = None,
        existing_tags: list[str] | None = None,
    ) -> list[str]:
        """Generate and normalize tags from all available signals.

        Args:
            content: The text content to analyze.
            metadata: Optional metadata dict.
            source: Origin identifier (e.g. ``"backtest_engine"``).
            agent_namespace: Agent name for ``agent:`` prefixed tag.
            existing_tags: Tags already provided by the caller.

        Returns:
            Deduplicated, normalized list of tags.
        """
        raw_tags: list[str] = list(existing_tags or [])

        # 1. Pattern matching
        raw_tags.extend(self._extract_patterns(content))

        # 2. Keyword extraction
        raw_tags.extend(self._extract_keywords(content))

        # 3. Metadata mapping
        raw_tags.extend(self._map_metadata(metadata, source, agent_namespace))

        # Normalize + deduplicate
        normalized = self._normalizer.normalize_list(raw_tags)

        logger.debug(f"AutoTagger: {len(raw_tags)} raw -> {len(normalized)} normalized tags")
        return normalized

    def extract_keywords(self, content: str, top_k: int | None = None) -> list[str]:
        """Extract top keywords using simple TF weighting (public API)."""
        return self._extract_keywords(content, top_k or self._max_keyword_tags)

    # ------------------------------------------------------------------
    # Internal extraction methods
    # ------------------------------------------------------------------

    def _extract_patterns(self, content: str) -> list[str]:
        """Extract tags via regex pattern matching."""
        tags: list[str] = []
        for _category, pattern in self.PATTERNS.items():
            matches = pattern.findall(content)
            for match in matches:
                cleaned = match.strip().lower()
                if cleaned:
                    tags.append(cleaned)
        return tags

    def _extract_keywords(self, content: str, top_k: int | None = None) -> list[str]:
        """Extract top keywords by term frequency (stop words removed)."""
        top_k = top_k or self._max_keyword_tags
        tokens = self._TOKEN_RE.findall(content.lower())
        # Filter: remove stop words and very short tokens
        tokens = [t for t in tokens if t not in _STOP_WORDS and len(t) >= 3]

        if not tokens:
            return []

        freq = Counter(tokens)
        # Take top_k most common
        return [word for word, _count in freq.most_common(top_k)]

    @staticmethod
    def _map_metadata(
        metadata: dict[str, Any] | None,
        source: str | None,
        agent_namespace: str | None,
    ) -> list[str]:
        """Generate tags from metadata, source, and agent namespace."""
        tags: list[str] = []

        if source:
            tags.append(f"source:{source.lower()}")

        if agent_namespace and agent_namespace != "shared":
            tags.append(f"agent:{agent_namespace.lower()}")

        if metadata:
            # Map known metadata keys to tags
            if "symbol" in metadata:
                tags.append(str(metadata["symbol"]).lower())
            if "timeframe" in metadata:
                tags.append(str(metadata["timeframe"]).lower())
            if "strategy_name" in metadata:
                tags.append(str(metadata["strategy_name"]).lower())

        return tags


# ------------------------------------------------------------------
# Module-level singleton
# ------------------------------------------------------------------

_auto_tagger: AutoTagger | None = None


def get_auto_tagger() -> AutoTagger:
    """Return the module-level AutoTagger singleton."""
    global _auto_tagger
    if _auto_tagger is None:
        _auto_tagger = AutoTagger()
    return _auto_tagger
