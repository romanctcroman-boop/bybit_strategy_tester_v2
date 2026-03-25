"""
Tag Normalizer — Canonical tag resolution with synonym support.

Solves the EPISODIC->SEMANTIC consolidation blockage (TZ Problem #3):
agents use different forms ("RSI", "rsi_indicator", "relative-strength-index")
which prevents the ≥3 same-tag threshold from being met.

Usage:
    normalizer = TagNormalizer()
    normalizer.normalize("RSI_indicator")      # → "rsi"
    normalizer.normalize_list(["RSI", "Trade"]) # → ["rsi", "trading"]
"""

from __future__ import annotations

import re

from loguru import logger


class TagNormalizer:
    """Normalize tags to canonical form with synonym resolution.

    Examples::

        "RSI"                       → "rsi"
        "RSI_indicator"             → "rsi"
        "relative-strength-index"   → "rsi"
        "Trading"                   → "trading"
        "trade"                     → "trading"

    Thread-safe: the synonym map is read-only after init (or extended
    via ``add_synonym`` which is append-only).
    """

    # ------------------------------------------------------------------
    # Pre-defined synonym groups for the trading domain.
    # Key = canonical tag, Values = known aliases (lowercased).
    # ------------------------------------------------------------------
    SYNONYM_GROUPS: dict[str, list[str]] = {
        # Indicators
        "rsi": [
            "rsi_indicator",
            "relative-strength-index",
            "relative_strength_index",
            "rsi_signal",
        ],
        "macd": [
            "macd_indicator",
            "moving-average-convergence-divergence",
            "macd_signal",
            "macd_histogram",
        ],
        "bollinger": [
            "bollinger_bands",
            "bb",
            "bbands",
            "bollinger-bands",
        ],
        "ema": [
            "exponential_moving_average",
            "exponential-moving-average",
        ],
        "sma": [
            "simple_moving_average",
            "simple-moving-average",
        ],
        "atr": [
            "average_true_range",
            "average-true-range",
            "atr_indicator",
        ],
        "stochastic": [
            "stoch",
            "stochastic_oscillator",
            "stochastic-oscillator",
            "stoch_rsi",
            "stochrsi",
        ],
        "adx": [
            "average_directional_index",
            "average-directional-index",
            "adx_indicator",
        ],
        "ichimoku": [
            "ichimoku_cloud",
            "ichimoku-cloud",
        ],
        "vwap": [
            "volume_weighted_average_price",
            "volume-weighted-average-price",
        ],
        # Trading concepts
        "trading": [
            "trade",
            "trades",
            "trader",
            "trading_strategy",
        ],
        "backtest": [
            "backtesting",
            "back-test",
            "back_test",
            "backtester",
        ],
        "strategy": [
            "strategies",
            "strat",
            "strats",
            "trading_strategy",
        ],
        "optimization": [
            "optimize",
            "optimizer",
            "optimizing",
            "optimisation",
        ],
        "risk": [
            "risk_management",
            "risk-management",
            "risk_mgmt",
        ],
        "position": [
            "position_size",
            "position_sizing",
            "position-sizing",
            "pos_size",
        ],
        # Market concepts
        "support": [
            "support_level",
            "support-level",
            "support_zone",
        ],
        "resistance": [
            "resistance_level",
            "resistance-level",
            "resistance_zone",
        ],
        "trend": [
            "trend_analysis",
            "trend-analysis",
            "trending",
            "trend_following",
        ],
        "volatility": [
            "vol",
            "implied_volatility",
            "historical_volatility",
        ],
        "momentum": [
            "momentum_indicator",
            "momentum-indicator",
        ],
        # Actions
        "buy": [
            "long",
            "go_long",
            "buy_signal",
        ],
        "sell": [
            "short",
            "go_short",
            "sell_signal",
        ],
        # Timeframes
        "scalping": [
            "scalp",
            "scalper",
        ],
        "swing": [
            "swing_trading",
            "swing-trading",
        ],
        "intraday": [
            "day_trading",
            "daytrading",
            "day-trading",
        ],
    }

    # ------------------------------------------------------------------
    # Regex to split compound tags into tokens.
    # Matches: underscores, hyphens, spaces, camelCase boundaries.
    # ------------------------------------------------------------------
    _SPLIT_RE = re.compile(r"[-_\s]+|(?<=[a-z])(?=[A-Z])")

    def __init__(
        self,
        extra_synonyms: dict[str, list[str]] | None = None,
    ) -> None:
        # Build reverse lookup: alias → canonical.
        self._alias_to_canonical: dict[str, str] = {}
        for canonical, aliases in self.SYNONYM_GROUPS.items():
            canonical_lc = canonical.lower()
            self._alias_to_canonical[canonical_lc] = canonical_lc
            for alias in aliases:
                self._alias_to_canonical[alias.lower()] = canonical_lc

        # Merge extra synonyms supplied at construction.
        if extra_synonyms:
            for canonical, aliases in extra_synonyms.items():
                self.add_synonym_group(canonical, aliases)

        logger.debug(
            f"TagNormalizer initialized: {len(self.SYNONYM_GROUPS)} canonical groups, "
            f"{len(self._alias_to_canonical)} total aliases"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def normalize(self, tag: str) -> str:
        """Normalize a single tag to its canonical form.

        Steps:
            1. Strip whitespace, lowercase
            2. Look up in alias map
            3. If not found, return cleaned lowercase form
        """
        cleaned = self._clean(tag)
        if not cleaned:
            return ""
        return self._alias_to_canonical.get(cleaned, cleaned)

    def normalize_list(self, tags: list[str]) -> list[str]:
        """Normalize and deduplicate a list of tags.

        Preserves insertion order of first occurrence.
        """
        seen: set[str] = set()
        result: list[str] = []
        for tag in tags:
            canonical = self.normalize(tag)
            if canonical and canonical not in seen:
                seen.add(canonical)
                result.append(canonical)
        return result

    def get_canonical(self, tag: str) -> str:
        """Get canonical form, or cleaned original if unknown."""
        return self.normalize(tag)

    def add_synonym(self, canonical: str, synonym: str) -> None:
        """Register a new synonym at runtime."""
        canonical_lc = canonical.lower().strip()
        synonym_lc = synonym.lower().strip()
        if not canonical_lc or not synonym_lc:
            return
        self._alias_to_canonical[synonym_lc] = canonical_lc
        # Ensure canonical maps to itself.
        self._alias_to_canonical[canonical_lc] = canonical_lc

    def add_synonym_group(self, canonical: str, aliases: list[str]) -> None:
        """Register a whole synonym group at runtime."""
        for alias in aliases:
            self.add_synonym(canonical, alias)

    def is_known(self, tag: str) -> bool:
        """Check whether a tag resolves to a known canonical form."""
        cleaned = self._clean(tag)
        return cleaned in self._alias_to_canonical

    def get_all_canonicals(self) -> list[str]:
        """Return sorted list of all canonical tag names."""
        return sorted(set(self._alias_to_canonical.values()))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clean(tag: str) -> str:
        """Lowercase, strip, collapse separators."""
        return re.sub(r"[-_\s]+", "_", tag.strip().lower())


# ------------------------------------------------------------------
# Module-level singleton
# ------------------------------------------------------------------

_normalizer: TagNormalizer | None = None


def get_tag_normalizer() -> TagNormalizer:
    """Return the module-level TagNormalizer singleton."""
    global _normalizer
    if _normalizer is None:
        _normalizer = TagNormalizer()
    return _normalizer
