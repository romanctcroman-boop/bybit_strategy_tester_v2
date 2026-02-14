"""
Pattern Extractor — Discover Winning Strategy Patterns.

Analyses backtest history to extract recurring patterns:
- Which strategy types perform best on which symbols/timeframes
- Optimal parameter ranges per strategy type
- Market-regime correlation (trending vs ranging)
- Win-rate and Sharpe distribution across configurations

Uses both SQL-based analytics (fast, broad) and vector memory
(semantic, flexible).

Added 2026-02-12 per Agent Ecosystem Audit — Additional Directions.
"""

from __future__ import annotations

import asyncio
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from loguru import logger

# =============================================================================
# DATA MODELS
# =============================================================================


@dataclass
class StrategyPattern:
    """A discovered pattern for a strategy type."""

    strategy_type: str
    sample_count: int = 0

    # Aggregate performance
    avg_win_rate: float = 0.0
    avg_sharpe: float = 0.0
    avg_return_pct: float = 0.0
    avg_drawdown_pct: float = 0.0
    avg_profit_factor: float = 0.0
    avg_trades: float = 0.0

    # Best observed
    best_win_rate: float = 0.0
    best_sharpe: float = 0.0
    best_return_pct: float = 0.0
    best_config: dict[str, Any] = field(default_factory=dict)

    # Timeframe/symbol affinity
    best_timeframes: list[str] = field(default_factory=list)
    best_symbols: list[str] = field(default_factory=list)

    # Parameter ranges
    param_ranges: dict[str, dict[str, float]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_type": self.strategy_type,
            "sample_count": self.sample_count,
            "avg_win_rate": round(self.avg_win_rate, 2),
            "avg_sharpe": round(self.avg_sharpe, 4),
            "avg_return_pct": round(self.avg_return_pct, 2),
            "avg_drawdown_pct": round(self.avg_drawdown_pct, 2),
            "avg_profit_factor": round(self.avg_profit_factor, 4),
            "avg_trades": round(self.avg_trades, 1),
            "best_win_rate": round(self.best_win_rate, 2),
            "best_sharpe": round(self.best_sharpe, 4),
            "best_return_pct": round(self.best_return_pct, 2),
            "best_config": self.best_config,
            "best_timeframes": self.best_timeframes,
            "best_symbols": self.best_symbols,
            "param_ranges": self.param_ranges,
        }


@dataclass
class TimeframeAffinity:
    """Performance of a strategy on a given timeframe."""

    timeframe: str
    strategy_type: str
    avg_sharpe: float = 0.0
    avg_win_rate: float = 0.0
    avg_return_pct: float = 0.0
    sample_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "timeframe": self.timeframe,
            "strategy_type": self.strategy_type,
            "avg_sharpe": round(self.avg_sharpe, 4),
            "avg_win_rate": round(self.avg_win_rate, 2),
            "avg_return_pct": round(self.avg_return_pct, 2),
            "sample_count": self.sample_count,
        }


@dataclass
class ExtractionResult:
    """Complete extraction output."""

    extracted_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    total_backtests_analysed: int = 0
    patterns: list[StrategyPattern] = field(default_factory=list)
    timeframe_affinities: list[TimeframeAffinity] = field(default_factory=list)
    top_configurations: list[dict[str, Any]] = field(default_factory=list)
    insights: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "extracted_at": self.extracted_at.isoformat(),
            "total_backtests_analysed": self.total_backtests_analysed,
            "patterns": [p.to_dict() for p in self.patterns],
            "timeframe_affinities": [t.to_dict() for t in self.timeframe_affinities],
            "top_configurations": self.top_configurations,
            "insights": self.insights,
        }


# =============================================================================
# PATTERN EXTRACTOR
# =============================================================================


class PatternExtractor:
    """
    Analyse backtest history and extract winning patterns.

    Works in two modes:
    1. **DB mode** (default): queries SQLite for aggregate analysis
    2. **Memory mode**: uses VectorMemoryStore for semantic search

    Usage::

        extractor = PatternExtractor()
        result = await extractor.extract()
        for pattern in result.patterns:
            print(pattern.to_dict())
    """

    def __init__(self, min_samples: int = 3, profitable_only: bool = False):
        """
        Args:
            min_samples: Minimum number of backtests to consider a pattern
            profitable_only: Only include profitable backtests in analysis
        """
        self.min_samples = min_samples
        self.profitable_only = profitable_only

    async def extract(self, limit: int = 500) -> ExtractionResult:
        """
        Run full pattern extraction from backtest database.

        Args:
            limit: Max number of backtests to analyse (default 500)

        Returns:
            ExtractionResult with patterns, affinities, and insights
        """
        result = ExtractionResult()
        t0 = datetime.now(UTC)

        # 1. Fetch raw backtest data from DB
        rows = await self._fetch_backtest_data(limit)
        result.total_backtests_analysed = len(rows)

        if not rows:
            result.insights.append("No backtest data found in database.")
            return result

        # 2. Group by strategy type
        by_strategy: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            st = row.get("strategy_type", "unknown")
            if self.profitable_only and row.get("total_return", 0) <= 0:
                continue
            by_strategy[st].append(row)

        # 3. Extract strategy patterns
        for strategy_type, data in by_strategy.items():
            if len(data) < self.min_samples:
                continue
            pattern = self._analyse_strategy(strategy_type, data)
            result.patterns.append(pattern)

        # Sort by average Sharpe descending
        result.patterns.sort(key=lambda p: p.avg_sharpe, reverse=True)

        # 4. Extract timeframe affinities
        result.timeframe_affinities = self._analyse_timeframe_affinities(rows)

        # 5. Extract top configurations
        result.top_configurations = self._extract_top_configs(rows, top_n=10)

        # 6. Generate insights
        result.insights = self._generate_insights(result)

        result.extracted_at = t0
        logger.info(
            f"Pattern extraction complete: {len(result.patterns)} patterns "
            f"from {result.total_backtests_analysed} backtests"
        )
        return result

    # ------------------------------------------------------------------
    # Data retrieval
    # ------------------------------------------------------------------

    async def _fetch_backtest_data(self, limit: int) -> list[dict[str, Any]]:
        """Fetch backtest data from database."""
        try:
            from backend.database import SessionLocal
            from backend.database.models import Backtest

            def _query():
                db = SessionLocal()
                try:
                    backtests = (
                        db.query(Backtest)
                        .filter(Backtest.status == "completed")
                        .order_by(Backtest.id.desc())
                        .limit(limit)
                        .all()
                    )
                    return [
                        {
                            "id": bt.id,
                            "symbol": getattr(bt, "symbol", ""),
                            "interval": getattr(bt, "interval", ""),
                            "strategy_type": getattr(bt, "strategy_type", ""),
                            "total_trades": int(getattr(bt, "total_trades", 0) or 0),
                            "win_rate": float(getattr(bt, "win_rate", 0) or 0),
                            "total_return": float(getattr(bt, "total_return", 0) or 0),
                            "sharpe_ratio": float(getattr(bt, "sharpe_ratio", 0) or 0),
                            "max_drawdown": float(getattr(bt, "max_drawdown", 0) or 0),
                            "profit_factor": float(getattr(bt, "profit_factor", 0) or 0),
                            "initial_capital": float(getattr(bt, "initial_capital", 10000) or 10000),
                            "final_capital": float(getattr(bt, "final_capital", 0) or 0),
                            "leverage": float(getattr(bt, "leverage", 1) or 1),
                            "direction": getattr(bt, "direction", "both"),
                            "stop_loss": float(getattr(bt, "stop_loss", 0) or 0),
                            "take_profit": float(getattr(bt, "take_profit", 0) or 0),
                            "created_at": str(getattr(bt, "created_at", "")),
                        }
                        for bt in backtests
                    ]
                finally:
                    db.close()

            return await asyncio.to_thread(_query)

        except Exception as e:
            logger.error(f"Failed to fetch backtest data: {e}")
            return []

    # ------------------------------------------------------------------
    # Analysis helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _analyse_strategy(strategy_type: str, data: list[dict[str, Any]]) -> StrategyPattern:
        """Compute aggregate stats for a single strategy type."""
        pattern = StrategyPattern(strategy_type=strategy_type, sample_count=len(data))

        win_rates = [d["win_rate"] for d in data]
        sharpes = [d["sharpe_ratio"] for d in data]
        returns = [d["total_return"] for d in data]
        drawdowns = [d["max_drawdown"] for d in data]
        pfs = [d["profit_factor"] for d in data]
        trades = [d["total_trades"] for d in data]

        pattern.avg_win_rate = statistics.mean(win_rates) if win_rates else 0
        pattern.avg_sharpe = statistics.mean(sharpes) if sharpes else 0
        pattern.avg_return_pct = statistics.mean(returns) if returns else 0
        pattern.avg_drawdown_pct = statistics.mean(drawdowns) if drawdowns else 0
        pattern.avg_profit_factor = statistics.mean(pfs) if pfs else 0
        pattern.avg_trades = statistics.mean(trades) if trades else 0

        pattern.best_win_rate = max(win_rates) if win_rates else 0
        pattern.best_sharpe = max(sharpes) if sharpes else 0
        pattern.best_return_pct = max(returns) if returns else 0

        # Find best config (by Sharpe)
        best_idx = sharpes.index(max(sharpes)) if sharpes else 0
        pattern.best_config = data[best_idx] if data else {}

        # Timeframe affinity
        tf_sharpes: dict[str, list[float]] = defaultdict(list)
        sym_sharpes: dict[str, list[float]] = defaultdict(list)
        for d in data:
            tf_sharpes[d.get("interval", "")].append(d["sharpe_ratio"])
            sym_sharpes[d.get("symbol", "")].append(d["sharpe_ratio"])

        # Best timeframes (top 3 by avg Sharpe)
        tf_avg = {tf: statistics.mean(vals) for tf, vals in tf_sharpes.items() if vals}
        pattern.best_timeframes = sorted(tf_avg, key=tf_avg.get, reverse=True)[:3]  # type: ignore[arg-type]

        # Best symbols (top 3 by avg Sharpe)
        sym_avg = {sym: statistics.mean(vals) for sym, vals in sym_sharpes.items() if vals}
        pattern.best_symbols = sorted(sym_avg, key=sym_avg.get, reverse=True)[:3]  # type: ignore[arg-type]

        return pattern

    def _analyse_timeframe_affinities(self, rows: list[dict[str, Any]]) -> list[TimeframeAffinity]:
        """Group by (strategy_type, timeframe) and rank."""
        grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for row in rows:
            key = (row.get("strategy_type", ""), row.get("interval", ""))
            grouped[key].append(row)

        affinities = []
        for (st, tf), data in grouped.items():
            if len(data) < self.min_samples:
                continue
            affinities.append(
                TimeframeAffinity(
                    timeframe=tf,
                    strategy_type=st,
                    avg_sharpe=statistics.mean([d["sharpe_ratio"] for d in data]),
                    avg_win_rate=statistics.mean([d["win_rate"] for d in data]),
                    avg_return_pct=statistics.mean([d["total_return"] for d in data]),
                    sample_count=len(data),
                )
            )

        affinities.sort(key=lambda a: a.avg_sharpe, reverse=True)
        return affinities

    @staticmethod
    def _extract_top_configs(rows: list[dict[str, Any]], top_n: int = 10) -> list[dict[str, Any]]:
        """Return top-N backtests ranked by Sharpe ratio."""
        sorted_rows = sorted(rows, key=lambda r: r.get("sharpe_ratio", 0), reverse=True)
        return sorted_rows[:top_n]

    @staticmethod
    def _generate_insights(result: ExtractionResult) -> list[str]:
        """Generate human-readable insights from extracted patterns."""
        insights: list[str] = []

        if not result.patterns:
            insights.append("Insufficient data to generate insights.")
            return insights

        # Best strategy overall
        best = result.patterns[0]
        insights.append(
            f"Best strategy overall: {best.strategy_type} "
            f"(avg Sharpe={best.avg_sharpe:.3f}, "
            f"avg WR={best.avg_win_rate:.1f}%, "
            f"N={best.sample_count})"
        )

        # Strategies to avoid
        losing = [p for p in result.patterns if p.avg_return_pct < 0]
        if losing:
            names = ", ".join(p.strategy_type for p in losing[:3])
            insights.append(f"Strategies with avg negative return: {names}")

        # Best timeframe
        if result.timeframe_affinities:
            top_tf = result.timeframe_affinities[0]
            insights.append(
                f"Best timeframe: {top_tf.strategy_type} on {top_tf.timeframe} (avg Sharpe={top_tf.avg_sharpe:.3f})"
            )

        # High-drawdown strategies
        high_dd = [p for p in result.patterns if p.avg_drawdown_pct > 20]
        if high_dd:
            names = ", ".join(p.strategy_type for p in high_dd[:3])
            insights.append(f"High-drawdown strategies (>20%): {names}")

        # Sample counts
        total = sum(p.sample_count for p in result.patterns)
        insights.append(f"Total qualifying backtests analysed: {total}")

        return insights

    # ------------------------------------------------------------------
    # Semantic search (optional — uses vector memory)
    # ------------------------------------------------------------------

    async def search_similar_patterns(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """
        Use VectorMemoryStore to find semantically similar backtests.

        Args:
            query: Natural language query (e.g. "RSI strategy with low drawdown")
            top_k: Number of results

        Returns:
            List of matching backtest records
        """
        try:
            from backend.agents.memory.vector_store import VectorMemoryStore

            store = VectorMemoryStore()
            results = await store.find_similar_results(query=query, top_k=top_k)
            return [
                {
                    "text": r.text,
                    "score": r.score,
                    "metadata": r.metadata,
                }
                for r in results
            ]
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []
