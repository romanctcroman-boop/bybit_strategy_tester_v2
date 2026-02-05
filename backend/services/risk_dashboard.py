"""
Risk Management Dashboard Service

Provides real-time risk monitoring for trading strategies including:
- Portfolio risk metrics (VaR, drawdown, exposure)
- Position monitoring and limits
- Risk alerts and thresholds
- Historical risk analysis
"""

import logging
import math
import statistics
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    """Risk severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """Types of risk alerts."""

    DRAWDOWN = "drawdown"
    EXPOSURE = "exposure"
    VOLATILITY = "volatility"
    POSITION_SIZE = "position_size"
    LOSS_LIMIT = "loss_limit"
    CORRELATION = "correlation"
    LIQUIDITY = "liquidity"


@dataclass
class RiskAlert:
    """Risk alert notification."""

    id: str
    alert_type: AlertType
    level: RiskLevel
    message: str
    value: float
    threshold: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    strategy_id: str | None = None
    acknowledged: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "alert_type": self.alert_type.value,
            "level": self.level.value,
            "message": self.message,
            "value": self.value,
            "threshold": self.threshold,
            "timestamp": self.timestamp.isoformat(),
            "strategy_id": self.strategy_id,
            "acknowledged": self.acknowledged,
        }


@dataclass
class PositionRisk:
    """Risk metrics for a single position."""

    symbol: str
    side: str  # "long" or "short"
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    exposure: float
    exposure_pct: float
    risk_score: float  # 0-100
    stop_loss: float | None = None
    take_profit: float | None = None
    liquidation_price: float | None = None
    leverage: float = 1.0


@dataclass
class PortfolioRisk:
    """Portfolio-level risk metrics."""

    total_equity: float
    total_exposure: float
    exposure_pct: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    realized_pnl_today: float
    max_drawdown: float
    current_drawdown: float
    var_95: float  # Value at Risk 95%
    var_99: float  # Value at Risk 99%
    sharpe_ratio: float
    sortino_ratio: float
    win_rate: float
    profit_factor: float
    risk_score: float  # 0-100
    positions_count: int
    open_orders_count: int


@dataclass
class RiskThresholds:
    """Configurable risk thresholds."""

    max_drawdown_pct: float = 10.0
    max_exposure_pct: float = 100.0
    max_position_size_pct: float = 20.0
    max_daily_loss_pct: float = 5.0
    max_correlation: float = 0.8
    min_liquidity_ratio: float = 0.1
    var_confidence: float = 0.95
    volatility_lookback_days: int = 30


class RiskCalculator:
    """Calculates various risk metrics."""

    @staticmethod
    def calculate_var(returns: list[float], confidence: float = 0.95) -> float:
        """Calculate Value at Risk using historical method."""
        if not returns or len(returns) < 2:
            return 0.0
        sorted_returns = sorted(returns)
        index = int((1 - confidence) * len(sorted_returns))
        return abs(sorted_returns[max(0, index)])

    @staticmethod
    def calculate_max_drawdown(equity_curve: list[float]) -> float:
        """Calculate maximum drawdown from equity curve."""
        if not equity_curve or len(equity_curve) < 2:
            return 0.0

        peak = equity_curve[0]
        max_dd = 0.0

        for value in equity_curve:
            if value > peak:
                peak = value
            dd = (peak - value) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)

        return max_dd * 100  # Return as percentage

    @staticmethod
    def calculate_current_drawdown(equity_curve: list[float]) -> float:
        """Calculate current drawdown from peak."""
        if not equity_curve or len(equity_curve) < 2:
            return 0.0

        peak = max(equity_curve)
        current = equity_curve[-1]

        return ((peak - current) / peak * 100) if peak > 0 else 0.0

    @staticmethod
    def calculate_sharpe_ratio(
        returns: list[float], risk_free_rate: float = 0.0
    ) -> float:
        """Calculate Sharpe ratio."""
        if not returns or len(returns) < 2:
            return 0.0

        avg_return = statistics.mean(returns)
        std_dev = statistics.stdev(returns)

        if std_dev == 0:
            return 0.0

        return (avg_return - risk_free_rate) / std_dev * math.sqrt(252)

    @staticmethod
    def calculate_sortino_ratio(
        returns: list[float], risk_free_rate: float = 0.0
    ) -> float:
        """Calculate Sortino ratio (downside deviation only)."""
        if not returns or len(returns) < 2:
            return 0.0

        avg_return = statistics.mean(returns)

        # TradingView Sortino formula: DD = sqrt(sum(min(0, Xi))^2 / N)
        downside_sq = [min(0, r) ** 2 for r in returns]
        downside_dev = math.sqrt(sum(downside_sq) / len(returns))

        if downside_dev == 0:
            return float("inf") if avg_return > 0 else 0.0

        return (avg_return - risk_free_rate) / downside_dev * math.sqrt(252)

    @staticmethod
    def calculate_win_rate(trades: list[dict[str, float]]) -> float:
        """Calculate win rate from trades."""
        if not trades:
            return 0.0

        winning = sum(1 for t in trades if t.get("pnl", 0) > 0)
        return (winning / len(trades)) * 100

    @staticmethod
    def calculate_profit_factor(trades: list[dict[str, float]]) -> float:
        """Calculate profit factor (gross profit / gross loss)."""
        if not trades:
            return 0.0

        gross_profit = sum(t.get("pnl", 0) for t in trades if t.get("pnl", 0) > 0)
        gross_loss = abs(sum(t.get("pnl", 0) for t in trades if t.get("pnl", 0) < 0))

        if gross_loss == 0:
            return float("inf") if gross_profit > 0 else 0.0

        return gross_profit / gross_loss

    @staticmethod
    def calculate_risk_score(
        drawdown: float,
        exposure_pct: float,
        var_pct: float,
        thresholds: RiskThresholds,
    ) -> float:
        """Calculate composite risk score (0-100, higher = more risk)."""
        dd_score = min(100, (drawdown / thresholds.max_drawdown_pct) * 50)
        exp_score = min(100, (exposure_pct / thresholds.max_exposure_pct) * 30)
        var_score = min(100, var_pct * 20)

        return min(100, dd_score + exp_score + var_score)


class RiskDashboardService:
    """
    Central service for risk monitoring and alerting.
    """

    def __init__(self, thresholds: RiskThresholds | None = None):
        self.thresholds = thresholds or RiskThresholds()
        self.calculator = RiskCalculator()

        # Data storage
        self.positions: dict[str, PositionRisk] = {}
        self.alerts: list[RiskAlert] = []
        self.equity_history: list[float] = []
        self.returns_history: list[float] = []
        self.trades_history: list[dict[str, Any]] = []

        # State
        self.last_update: datetime | None = None
        self.alert_counter = 0

        # Metrics
        self.total_alerts_generated = 0
        self.critical_alerts_count = 0

    def _generate_alert_id(self) -> str:
        """Generate unique alert ID."""
        self.alert_counter += 1
        return f"alert_{int(time.time())}_{self.alert_counter}"

    def update_position(self, position: PositionRisk):
        """Update or add a position."""
        self.positions[position.symbol] = position
        self.last_update = datetime.now(UTC)
        self._check_position_alerts(position)

    def remove_position(self, symbol: str):
        """Remove a closed position."""
        if symbol in self.positions:
            del self.positions[symbol]

    def update_equity(self, equity: float):
        """Update equity value and track history."""
        self.equity_history.append(equity)

        # Keep last 1000 data points
        if len(self.equity_history) > 1000:
            self.equity_history = self.equity_history[-1000:]

        # Calculate return if we have previous equity
        if len(self.equity_history) >= 2:
            prev = self.equity_history[-2]
            if prev > 0:
                ret = (equity - prev) / prev
                self.returns_history.append(ret)

                if len(self.returns_history) > 1000:
                    self.returns_history = self.returns_history[-1000:]

        self.last_update = datetime.now(UTC)

    def record_trade(self, trade: dict[str, Any]):
        """Record a completed trade."""
        self.trades_history.append(
            {
                **trade,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

        # Keep last 500 trades
        if len(self.trades_history) > 500:
            self.trades_history = self.trades_history[-500:]

    def get_portfolio_risk(self) -> PortfolioRisk:
        """Calculate current portfolio risk metrics."""
        # Calculate totals
        total_equity = self.equity_history[-1] if self.equity_history else 0.0
        total_exposure = sum(p.exposure for p in self.positions.values())
        exposure_pct = (
            (total_exposure / total_equity * 100) if total_equity > 0 else 0.0
        )

        unrealized_pnl = sum(p.unrealized_pnl for p in self.positions.values())
        unrealized_pnl_pct = (
            (unrealized_pnl / total_equity * 100) if total_equity > 0 else 0.0
        )

        # Calculate drawdown
        max_dd = self.calculator.calculate_max_drawdown(self.equity_history)
        current_dd = self.calculator.calculate_current_drawdown(self.equity_history)

        # Calculate VaR
        var_95 = self.calculator.calculate_var(self.returns_history, 0.95) * 100
        var_99 = self.calculator.calculate_var(self.returns_history, 0.99) * 100

        # Calculate ratios
        sharpe = self.calculator.calculate_sharpe_ratio(self.returns_history)
        sortino = self.calculator.calculate_sortino_ratio(self.returns_history)

        # Trade statistics
        win_rate = self.calculator.calculate_win_rate(self.trades_history)
        profit_factor = self.calculator.calculate_profit_factor(self.trades_history)

        # Today's realized P&L
        today = datetime.now(UTC).date()
        today_trades = [
            t
            for t in self.trades_history
            if datetime.fromisoformat(t["timestamp"]).date() == today
        ]
        realized_today = sum(t.get("pnl", 0) for t in today_trades)

        # Risk score
        risk_score = self.calculator.calculate_risk_score(
            current_dd, exposure_pct, var_95, self.thresholds
        )

        return PortfolioRisk(
            total_equity=total_equity,
            total_exposure=total_exposure,
            exposure_pct=round(exposure_pct, 2),
            unrealized_pnl=round(unrealized_pnl, 2),
            unrealized_pnl_pct=round(unrealized_pnl_pct, 2),
            realized_pnl_today=round(realized_today, 2),
            max_drawdown=round(max_dd, 2),
            current_drawdown=round(current_dd, 2),
            var_95=round(var_95, 2),
            var_99=round(var_99, 2),
            sharpe_ratio=round(sharpe, 2),
            sortino_ratio=round(sortino, 2),
            win_rate=round(win_rate, 2),
            profit_factor=round(profit_factor, 2),
            risk_score=round(risk_score, 2),
            positions_count=len(self.positions),
            open_orders_count=0,  # Would be updated from order book
        )

    def _check_position_alerts(self, position: PositionRisk):
        """Check and generate alerts for a position."""
        total_equity = self.equity_history[-1] if self.equity_history else 1.0

        # Position size alert
        position_pct = (
            (position.exposure / total_equity * 100) if total_equity > 0 else 0
        )
        if position_pct > self.thresholds.max_position_size_pct:
            self._create_alert(
                AlertType.POSITION_SIZE,
                RiskLevel.HIGH
                if position_pct > self.thresholds.max_position_size_pct * 1.5
                else RiskLevel.MEDIUM,
                f"Position size for {position.symbol} exceeds threshold",
                position_pct,
                self.thresholds.max_position_size_pct,
                strategy_id=position.symbol,
            )

    def check_portfolio_alerts(self):
        """Check and generate portfolio-level alerts."""
        portfolio = self.get_portfolio_risk()

        # Drawdown alert
        if portfolio.current_drawdown > self.thresholds.max_drawdown_pct:
            level = (
                RiskLevel.CRITICAL
                if portfolio.current_drawdown > self.thresholds.max_drawdown_pct * 1.5
                else RiskLevel.HIGH
            )
            self._create_alert(
                AlertType.DRAWDOWN,
                level,
                f"Portfolio drawdown exceeds threshold: {portfolio.current_drawdown:.1f}%",
                portfolio.current_drawdown,
                self.thresholds.max_drawdown_pct,
            )

        # Exposure alert
        if portfolio.exposure_pct > self.thresholds.max_exposure_pct:
            self._create_alert(
                AlertType.EXPOSURE,
                RiskLevel.HIGH,
                f"Portfolio exposure exceeds threshold: {portfolio.exposure_pct:.1f}%",
                portfolio.exposure_pct,
                self.thresholds.max_exposure_pct,
            )

        # Daily loss alert
        daily_loss_pct = (
            abs(portfolio.realized_pnl_today / portfolio.total_equity * 100)
            if portfolio.total_equity > 0 and portfolio.realized_pnl_today < 0
            else 0
        )
        if daily_loss_pct > self.thresholds.max_daily_loss_pct:
            self._create_alert(
                AlertType.LOSS_LIMIT,
                RiskLevel.CRITICAL,
                f"Daily loss limit exceeded: {daily_loss_pct:.1f}%",
                daily_loss_pct,
                self.thresholds.max_daily_loss_pct,
            )

    def _create_alert(
        self,
        alert_type: AlertType,
        level: RiskLevel,
        message: str,
        value: float,
        threshold: float,
        strategy_id: str | None = None,
    ):
        """Create and store a new alert."""
        alert = RiskAlert(
            id=self._generate_alert_id(),
            alert_type=alert_type,
            level=level,
            message=message,
            value=value,
            threshold=threshold,
            strategy_id=strategy_id,
        )

        self.alerts.append(alert)
        self.total_alerts_generated += 1

        if level == RiskLevel.CRITICAL:
            self.critical_alerts_count += 1

        # Keep last 100 alerts
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]

        logger.warning(f"Risk Alert [{level.value.upper()}]: {message}")

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                return True
        return False

    def get_alerts(
        self,
        unacknowledged_only: bool = False,
        level: RiskLevel | None = None,
        limit: int = 50,
    ) -> list[RiskAlert]:
        """Get alerts with optional filtering."""
        alerts = self.alerts

        if unacknowledged_only:
            alerts = [a for a in alerts if not a.acknowledged]

        if level:
            alerts = [a for a in alerts if a.level == level]

        return alerts[-limit:]

    def get_risk_summary(self) -> dict[str, Any]:
        """Get comprehensive risk summary."""
        portfolio = self.get_portfolio_risk()

        # Determine overall risk level
        if portfolio.risk_score > 80:
            overall_level = RiskLevel.CRITICAL
        elif portfolio.risk_score > 60:
            overall_level = RiskLevel.HIGH
        elif portfolio.risk_score > 30:
            overall_level = RiskLevel.MEDIUM
        else:
            overall_level = RiskLevel.LOW

        unack_alerts = [a for a in self.alerts if not a.acknowledged]

        return {
            "overall_risk_level": overall_level.value,
            "risk_score": portfolio.risk_score,
            "portfolio": {
                "equity": portfolio.total_equity,
                "exposure_pct": portfolio.exposure_pct,
                "drawdown": portfolio.current_drawdown,
                "max_drawdown": portfolio.max_drawdown,
                "var_95": portfolio.var_95,
                "sharpe_ratio": portfolio.sharpe_ratio,
                "win_rate": portfolio.win_rate,
            },
            "positions_count": portfolio.positions_count,
            "active_alerts": len(unack_alerts),
            "critical_alerts": len(
                [a for a in unack_alerts if a.level == RiskLevel.CRITICAL]
            ),
            "thresholds": {
                "max_drawdown": self.thresholds.max_drawdown_pct,
                "max_exposure": self.thresholds.max_exposure_pct,
                "max_daily_loss": self.thresholds.max_daily_loss_pct,
            },
            "last_update": self.last_update.isoformat() if self.last_update else None,
        }

    def get_metrics(self) -> dict[str, Any]:
        """Get service metrics."""
        return {
            "positions_tracked": len(self.positions),
            "equity_data_points": len(self.equity_history),
            "returns_data_points": len(self.returns_history),
            "trades_recorded": len(self.trades_history),
            "total_alerts": self.total_alerts_generated,
            "critical_alerts": self.critical_alerts_count,
            "active_alerts": len([a for a in self.alerts if not a.acknowledged]),
        }


# Global instance
_risk_dashboard: RiskDashboardService | None = None


def get_risk_dashboard() -> RiskDashboardService:
    """Get or create the global risk dashboard service."""
    global _risk_dashboard
    if _risk_dashboard is None:
        _risk_dashboard = RiskDashboardService()
    return _risk_dashboard
