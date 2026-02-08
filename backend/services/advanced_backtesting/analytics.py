"""
Backtest Analytics Module

Provides detailed analysis of backtest results:
- Trade analysis and statistics
- Performance attribution
- Regime-based analysis
- Drawdown analysis
- Risk-adjusted metrics

Usage:
    from backend.services.advanced_backtesting.analytics import (
        BacktestAnalytics,
        TradeAnalysis,
        PerformanceAttribution,
    )

    analytics = BacktestAnalytics(backtest_results)
    report = analytics.generate_full_report()
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class TradeAnalysis:
    """Detailed trade analysis."""

    # Basic stats
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    breakeven_trades: int = 0

    # Win/Loss metrics
    win_rate: float = 0.0
    loss_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0

    # Streaks
    max_win_streak: int = 0
    max_loss_streak: int = 0
    current_streak: int = 0
    current_streak_type: str = "none"

    # Duration
    avg_trade_duration: float = 0.0  # seconds
    avg_winning_duration: float = 0.0
    avg_losing_duration: float = 0.0

    # Risk/Reward
    avg_risk_reward: float = 0.0
    expectancy: float = 0.0
    profit_factor: float = 0.0

    # Time analysis
    best_hour: int = 0
    worst_hour: int = 0
    best_day: str = "Monday"
    worst_day: str = "Monday"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "basic": {
                "total_trades": self.total_trades,
                "winning_trades": self.winning_trades,
                "losing_trades": self.losing_trades,
                "breakeven_trades": self.breakeven_trades,
            },
            "rates": {
                "win_rate_pct": round(self.win_rate * 100, 2),
                "loss_rate_pct": round(self.loss_rate * 100, 2),
            },
            "pnl": {
                "avg_win": round(self.avg_win, 2),
                "avg_loss": round(self.avg_loss, 2),
                "largest_win": round(self.largest_win, 2),
                "largest_loss": round(self.largest_loss, 2),
            },
            "streaks": {
                "max_win_streak": self.max_win_streak,
                "max_loss_streak": self.max_loss_streak,
                "current_streak": self.current_streak,
                "current_streak_type": self.current_streak_type,
            },
            "duration": {
                "avg_trade_seconds": round(self.avg_trade_duration, 0),
                "avg_winning_seconds": round(self.avg_winning_duration, 0),
                "avg_losing_seconds": round(self.avg_losing_duration, 0),
            },
            "risk_reward": {
                "avg_risk_reward": round(self.avg_risk_reward, 2),
                "expectancy": round(self.expectancy, 2),
                "profit_factor": round(self.profit_factor, 2),
            },
            "timing": {
                "best_hour": self.best_hour,
                "worst_hour": self.worst_hour,
                "best_day": self.best_day,
                "worst_day": self.worst_day,
            },
        }


@dataclass
class PerformanceAttribution:
    """Performance attribution analysis."""

    # Return attribution
    total_return: float = 0.0
    gross_return: float = 0.0
    commission_drag: float = 0.0
    slippage_drag: float = 0.0
    funding_drag: float = 0.0

    # By side
    long_return: float = 0.0
    short_return: float = 0.0
    long_trades: int = 0
    short_trades: int = 0

    # By time
    morning_return: float = 0.0  # 00:00 - 08:00
    day_return: float = 0.0  # 08:00 - 16:00
    evening_return: float = 0.0  # 16:00 - 24:00

    # By volatility regime
    low_vol_return: float = 0.0
    normal_vol_return: float = 0.0
    high_vol_return: float = 0.0

    # By market condition
    trending_return: float = 0.0
    ranging_return: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "returns": {
                "total_return_pct": round(self.total_return * 100, 2),
                "gross_return_pct": round(self.gross_return * 100, 2),
                "commission_drag_pct": round(self.commission_drag * 100, 2),
                "slippage_drag_pct": round(self.slippage_drag * 100, 2),
            },
            "by_direction": {
                "long_return_pct": round(self.long_return * 100, 2),
                "short_return_pct": round(self.short_return * 100, 2),
                "long_trades": self.long_trades,
                "short_trades": self.short_trades,
            },
            "by_time": {
                "morning_return_pct": round(self.morning_return * 100, 2),
                "day_return_pct": round(self.day_return * 100, 2),
                "evening_return_pct": round(self.evening_return * 100, 2),
            },
            "by_volatility": {
                "low_vol_return_pct": round(self.low_vol_return * 100, 2),
                "normal_vol_return_pct": round(self.normal_vol_return * 100, 2),
                "high_vol_return_pct": round(self.high_vol_return * 100, 2),
            },
        }


@dataclass
class RegimeAnalysis:
    """Market regime analysis."""

    # Regime detection
    regimes: list[dict] = field(default_factory=list)
    current_regime: str = "unknown"

    # Performance by regime
    regime_performance: dict[str, dict] = field(default_factory=dict)

    # Transitions
    regime_transitions: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "current_regime": self.current_regime,
            "regimes": self.regimes,
            "performance_by_regime": self.regime_performance,
            "transitions": self.regime_transitions[:20],  # Last 20 transitions
        }


@dataclass
class DrawdownAnalysis:
    """Detailed drawdown analysis."""

    # Current
    current_drawdown: float = 0.0
    current_drawdown_duration: int = 0  # bars

    # Maximum
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0
    max_drawdown_start: datetime | None = None
    max_drawdown_end: datetime | None = None
    recovery_time: int = 0  # bars to recover

    # Statistics
    avg_drawdown: float = 0.0
    drawdown_frequency: float = 0.0  # How often in drawdown

    # All drawdowns > 5%
    significant_drawdowns: list[dict] = field(default_factory=list)

    # Underwater analysis
    time_underwater_pct: float = 0.0
    avg_underwater_time: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "current": {
                "drawdown_pct": round(self.current_drawdown * 100, 2),
                "duration_bars": self.current_drawdown_duration,
            },
            "maximum": {
                "drawdown_pct": round(self.max_drawdown * 100, 2),
                "duration_bars": self.max_drawdown_duration,
                "start": self.max_drawdown_start.isoformat()
                if self.max_drawdown_start
                else None,
                "end": self.max_drawdown_end.isoformat()
                if self.max_drawdown_end
                else None,
                "recovery_bars": self.recovery_time,
            },
            "statistics": {
                "avg_drawdown_pct": round(self.avg_drawdown * 100, 2),
                "time_underwater_pct": round(self.time_underwater_pct * 100, 2),
                "avg_underwater_bars": round(self.avg_underwater_time, 0),
            },
            "significant_drawdowns": self.significant_drawdowns[:10],
        }


class BacktestAnalytics:
    """
    Comprehensive backtest analytics.

    Analyzes backtest results to provide:
    - Trade statistics
    - Performance attribution
    - Regime analysis
    - Drawdown analysis
    - Risk metrics
    """

    def __init__(self, results: dict[str, Any]):
        """
        Initialize analytics.

        Args:
            results: Backtest results dictionary
        """
        self.results = results
        self.trades = results.get("all_trades", [])
        self.equity_curve = results.get("equity_curve", [])
        self.drawdown_curve = results.get("drawdown_curve", [])
        self.initial_capital = results.get("config", {}).get("initial_capital", 10000)

    def analyze_trades(self) -> TradeAnalysis:
        """Analyze trade statistics."""
        analysis = TradeAnalysis()

        if not self.trades:
            return analysis

        # Basic counts
        analysis.total_trades = len(self.trades)
        winning = [t for t in self.trades if t.get("pnl", 0) > 0]
        losing = [t for t in self.trades if t.get("pnl", 0) < 0]
        breakeven = [t for t in self.trades if t.get("pnl", 0) == 0]

        analysis.winning_trades = len(winning)
        analysis.losing_trades = len(losing)
        analysis.breakeven_trades = len(breakeven)

        # Rates
        analysis.win_rate = len(winning) / len(self.trades)
        analysis.loss_rate = len(losing) / len(self.trades)

        # PnL stats
        if winning:
            analysis.avg_win = np.mean([t["pnl"] for t in winning])
            analysis.largest_win = max(t["pnl"] for t in winning)

        if losing:
            analysis.avg_loss = np.mean([t["pnl"] for t in losing])
            analysis.largest_loss = min(t["pnl"] for t in losing)

        # Streaks
        analysis.max_win_streak, analysis.max_loss_streak = self._calculate_streaks()

        # Duration
        durations = [t.get("duration_seconds", 0) for t in self.trades]
        if durations:
            analysis.avg_trade_duration = np.mean(durations)

        winning_durations = [t.get("duration_seconds", 0) for t in winning]
        if winning_durations:
            analysis.avg_winning_duration = np.mean(winning_durations)

        losing_durations = [t.get("duration_seconds", 0) for t in losing]
        if losing_durations:
            analysis.avg_losing_duration = np.mean(losing_durations)

        # Risk/Reward
        if analysis.avg_loss != 0:
            analysis.avg_risk_reward = abs(analysis.avg_win / analysis.avg_loss)

        analysis.expectancy = (
            analysis.win_rate * analysis.avg_win
            - analysis.loss_rate * abs(analysis.avg_loss)
        )

        gross_profit = sum(t["pnl"] for t in winning) if winning else 0
        gross_loss = abs(sum(t["pnl"] for t in losing)) if losing else 0
        analysis.profit_factor = (
            gross_profit / gross_loss if gross_loss > 0 else float("inf")
        )

        # Time analysis
        self._analyze_timing(analysis)

        return analysis

    def _calculate_streaks(self) -> tuple[int, int]:
        """Calculate win/loss streaks."""
        max_win = 0
        max_loss = 0
        current_win = 0
        current_loss = 0

        for trade in self.trades:
            pnl = trade.get("pnl", 0)
            if pnl > 0:
                current_win += 1
                current_loss = 0
                max_win = max(max_win, current_win)
            elif pnl < 0:
                current_loss += 1
                current_win = 0
                max_loss = max(max_loss, current_loss)
            else:
                current_win = 0
                current_loss = 0

        return max_win, max_loss

    def _analyze_timing(self, analysis: TradeAnalysis):
        """Analyze trade timing patterns."""
        hour_pnl: dict[int, list[float]] = {h: [] for h in range(24)}
        day_pnl: dict[str, list[float]] = {
            d: []
            for d in [
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ]
        }

        days = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]

        for trade in self.trades:
            entry_time_str = trade.get("entry_time")
            if not entry_time_str:
                continue

            try:
                if isinstance(entry_time_str, str):
                    entry_time = datetime.fromisoformat(
                        entry_time_str.replace("Z", "+00:00")
                    )
                else:
                    entry_time = entry_time_str

                hour = entry_time.hour
                day = days[entry_time.weekday()]
                pnl = trade.get("pnl", 0)

                hour_pnl[hour].append(pnl)
                day_pnl[day].append(pnl)
            except (ValueError, AttributeError):
                continue

        # Find best/worst hours
        hour_totals = {h: sum(pnls) for h, pnls in hour_pnl.items() if pnls}
        if hour_totals:
            analysis.best_hour = max(hour_totals, key=hour_totals.get)
            analysis.worst_hour = min(hour_totals, key=hour_totals.get)

        # Find best/worst days
        day_totals = {d: sum(pnls) for d, pnls in day_pnl.items() if pnls}
        if day_totals:
            analysis.best_day = max(day_totals, key=day_totals.get)
            analysis.worst_day = min(day_totals, key=day_totals.get)

    def analyze_performance_attribution(self) -> PerformanceAttribution:
        """Analyze performance attribution."""
        attr = PerformanceAttribution()

        if not self.trades:
            return attr

        # Calculate returns
        total_pnl = sum(t.get("pnl", 0) for t in self.trades)
        total_commission = sum(t.get("commission", 0) for t in self.trades)
        total_slippage = sum(t.get("slippage", 0) for t in self.trades)

        attr.total_return = total_pnl / self.initial_capital
        attr.gross_return = (
            total_pnl + total_commission + total_slippage
        ) / self.initial_capital
        attr.commission_drag = total_commission / self.initial_capital
        attr.slippage_drag = total_slippage / self.initial_capital

        # By side
        long_trades = [t for t in self.trades if t.get("side") == "long"]
        short_trades = [t for t in self.trades if t.get("side") == "short"]

        attr.long_trades = len(long_trades)
        attr.short_trades = len(short_trades)
        attr.long_return = (
            sum(t.get("pnl", 0) for t in long_trades) / self.initial_capital
        )
        attr.short_return = (
            sum(t.get("pnl", 0) for t in short_trades) / self.initial_capital
        )

        # By time
        morning_trades = []
        day_trades = []
        evening_trades = []

        for trade in self.trades:
            entry_time_str = trade.get("entry_time")
            if not entry_time_str:
                continue

            try:
                if isinstance(entry_time_str, str):
                    entry_time = datetime.fromisoformat(
                        entry_time_str.replace("Z", "+00:00")
                    )
                else:
                    entry_time = entry_time_str

                hour = entry_time.hour
                if hour < 8:
                    morning_trades.append(trade)
                elif hour < 16:
                    day_trades.append(trade)
                else:
                    evening_trades.append(trade)
            except (ValueError, AttributeError):
                continue

        attr.morning_return = (
            sum(t.get("pnl", 0) for t in morning_trades) / self.initial_capital
        )
        attr.day_return = (
            sum(t.get("pnl", 0) for t in day_trades) / self.initial_capital
        )
        attr.evening_return = (
            sum(t.get("pnl", 0) for t in evening_trades) / self.initial_capital
        )

        return attr

    def analyze_drawdowns(self) -> DrawdownAnalysis:
        """Analyze drawdowns in detail."""
        analysis = DrawdownAnalysis()

        if not self.equity_curve:
            return analysis

        equity = np.array(self.equity_curve)

        # Calculate running max and drawdowns
        running_max = np.maximum.accumulate(equity)
        drawdowns = (running_max - equity) / running_max

        # Current drawdown
        analysis.current_drawdown = drawdowns[-1] if len(drawdowns) > 0 else 0

        # Maximum drawdown
        analysis.max_drawdown = np.max(drawdowns)
        max_dd_idx = np.argmax(drawdowns)

        # Find duration
        if analysis.max_drawdown > 0:
            # Find start of max drawdown
            peak_idx = np.argmax(equity[: max_dd_idx + 1])
            analysis.max_drawdown_duration = max_dd_idx - peak_idx

            # Find recovery
            if max_dd_idx < len(equity) - 1:
                recovery_mask = equity[max_dd_idx:] >= equity[peak_idx]
                if np.any(recovery_mask):
                    analysis.recovery_time = np.argmax(recovery_mask)

        # Average drawdown (when in drawdown)
        in_drawdown = drawdowns > 0.01  # > 1%
        if np.any(in_drawdown):
            analysis.avg_drawdown = np.mean(drawdowns[in_drawdown])
            analysis.time_underwater_pct = np.mean(in_drawdown)

        # Significant drawdowns (> 5%)
        significant_threshold = 0.05
        in_significant = False
        dd_start = 0

        for i, dd in enumerate(drawdowns):
            if dd > significant_threshold and not in_significant:
                in_significant = True
                dd_start = i
            elif dd < 0.01 and in_significant:
                in_significant = False
                max_dd = np.max(drawdowns[dd_start:i])
                analysis.significant_drawdowns.append(
                    {
                        "start_idx": dd_start,
                        "end_idx": i,
                        "max_drawdown_pct": round(max_dd * 100, 2),
                        "duration_bars": i - dd_start,
                    }
                )

        return analysis

    def analyze_regimes(
        self, price_data: list[float] | None = None
    ) -> RegimeAnalysis:
        """Analyze performance by market regime."""
        analysis = RegimeAnalysis()

        if not price_data or len(price_data) < 20:
            return analysis

        prices = np.array(price_data)

        # Simple regime detection using volatility and trend
        returns = np.diff(prices) / prices[:-1]

        # Rolling volatility (20-period)
        window = 20
        rolling_vol = np.array(
            [
                np.std(returns[max(0, i - window) : i])
                if i >= window
                else np.std(returns[: i + 1])
                for i in range(len(returns))
            ]
        )

        # Regime classification
        vol_median = np.median(rolling_vol)

        regimes = []
        for i in range(len(returns)):
            if rolling_vol[i] > vol_median * 1.5:
                regime = "high_volatility"
            elif rolling_vol[i] < vol_median * 0.5:
                regime = "low_volatility"
            else:
                regime = "normal"

            regimes.append(
                {
                    "index": i,
                    "regime": regime,
                    "volatility": float(rolling_vol[i]),
                }
            )

        analysis.regimes = regimes[-100:]  # Last 100
        analysis.current_regime = regimes[-1]["regime"] if regimes else "unknown"

        # Performance by regime
        # This would require matching trades to regimes
        analysis.regime_performance = {
            "high_volatility": {"trades": 0, "pnl": 0, "win_rate": 0},
            "normal": {"trades": 0, "pnl": 0, "win_rate": 0},
            "low_volatility": {"trades": 0, "pnl": 0, "win_rate": 0},
        }

        return analysis

    def generate_full_report(self) -> dict[str, Any]:
        """Generate comprehensive analytics report."""
        trade_analysis = self.analyze_trades()
        attribution = self.analyze_performance_attribution()
        drawdown_analysis = self.analyze_drawdowns()

        return {
            "summary": {
                "total_trades": trade_analysis.total_trades,
                "win_rate_pct": round(trade_analysis.win_rate * 100, 2),
                "profit_factor": round(trade_analysis.profit_factor, 2),
                "expectancy": round(trade_analysis.expectancy, 2),
                "max_drawdown_pct": round(drawdown_analysis.max_drawdown * 100, 2),
                "total_return_pct": round(attribution.total_return * 100, 2),
            },
            "trade_analysis": trade_analysis.to_dict(),
            "performance_attribution": attribution.to_dict(),
            "drawdown_analysis": drawdown_analysis.to_dict(),
            "generated_at": datetime.now(UTC).isoformat(),
        }


def analyze_backtest(results: dict[str, Any]) -> dict[str, Any]:
    """
    Convenience function to analyze backtest results.

    Args:
        results: Backtest results dictionary

    Returns:
        Full analytics report
    """
    analytics = BacktestAnalytics(results)
    return analytics.generate_full_report()
