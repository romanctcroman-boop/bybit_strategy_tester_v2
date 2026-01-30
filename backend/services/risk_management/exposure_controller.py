"""
Exposure Control Module.

Controls and limits trading exposure:
- Maximum position size per symbol
- Maximum total exposure (portfolio)
- Leverage limits
- Correlation-based limits
- Sector/asset class diversification
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ExposureViolationType(str, Enum):
    """Types of exposure limit violations."""

    MAX_POSITION_SIZE = "max_position_size"
    MAX_TOTAL_EXPOSURE = "max_total_exposure"
    MAX_LEVERAGE = "max_leverage"
    MAX_POSITIONS = "max_positions"
    MAX_CORRELATION = "max_correlation"
    MAX_SECTOR_EXPOSURE = "max_sector_exposure"
    MAX_SINGLE_ASSET = "max_single_asset"
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    DRAWDOWN_LIMIT = "drawdown_limit"


@dataclass
class ExposureLimits:
    """Exposure limit configuration."""

    # Position limits
    max_position_size_pct: float = 20.0  # Max 20% of equity per position
    max_position_size_usd: float = 100000.0  # Max $100k per position
    max_positions: int = 10  # Max 10 open positions

    # Portfolio limits
    max_total_exposure_pct: float = 200.0  # Max 200% total (allows 2x leverage)
    max_long_exposure_pct: float = 150.0  # Max 150% long
    max_short_exposure_pct: float = 100.0  # Max 100% short
    max_net_exposure_pct: float = 100.0  # Max net directional exposure

    # Leverage limits
    max_leverage: float = 10.0  # Max 10x leverage per position
    max_portfolio_leverage: float = 3.0  # Max 3x portfolio leverage

    # Correlation limits
    max_correlated_positions: int = 3  # Max positions with >0.7 correlation
    correlation_threshold: float = 0.7  # Correlation threshold

    # Diversification
    max_single_asset_pct: float = 30.0  # Max 30% in single asset
    max_sector_exposure_pct: float = 50.0  # Max 50% per sector

    # Loss limits
    max_daily_loss_pct: float = 5.0  # Stop trading at 5% daily loss
    max_drawdown_pct: float = 15.0  # Stop trading at 15% drawdown

    # Cooling off
    cooling_period_after_violation: int = 300  # 5 minutes cooldown


@dataclass
class Position:
    """Position representation for exposure calculations."""

    symbol: str
    side: str  # "long" or "short"
    size: float  # Base currency amount
    entry_price: float
    current_price: float
    leverage: float = 1.0
    sector: str = "crypto"
    unrealized_pnl: float = 0.0

    @property
    def notional_value(self) -> float:
        """Position notional value."""
        return self.size * self.current_price

    @property
    def exposure(self) -> float:
        """Directional exposure (positive for long, negative for short)."""
        value = self.notional_value
        return value if self.side == "long" else -value


@dataclass
class ExposureCheckResult:
    """Result of exposure check."""

    allowed: bool
    violations: list[ExposureViolationType]
    messages: list[str]
    current_exposure: dict[str, float]
    limits: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "violations": [v.value for v in self.violations],
            "messages": self.messages,
            "current_exposure": self.current_exposure,
            "limits": self.limits,
        }


class ExposureController:
    """
    Controls and validates trading exposure.

    Features:
    - Position size limits
    - Portfolio exposure limits
    - Leverage management
    - Correlation checking
    - Loss limit enforcement

    Usage:
        controller = ExposureController(
            equity=100000,
            limits=ExposureLimits(max_position_size_pct=15.0)
        )

        # Check if trade is allowed
        result = controller.check_new_position(
            symbol="BTCUSDT",
            side="long",
            size=1.5,
            entry_price=50000,
            leverage=5.0
        )

        if result.allowed:
            # Execute trade
            ...
        else:
            print(f"Trade rejected: {result.messages}")
    """

    def __init__(
        self,
        equity: float,
        limits: ExposureLimits | None = None,
    ):
        self.equity = equity
        self.limits = limits or ExposureLimits()

        # Current positions
        self.positions: dict[str, Position] = {}

        # Correlation matrix (symbol -> {symbol -> correlation})
        self.correlations: dict[str, dict[str, float]] = {}

        # Sector mappings
        self.sector_map: dict[str, str] = {}

        # Daily tracking
        self.daily_pnl: float = 0.0
        self.daily_start_equity: float = equity
        self.peak_equity: float = equity

        # State
        self.cooling_until: datetime | None = None
        self.violations_today: list[ExposureViolationType] = []

        # Callbacks
        self.on_limit_breach: Callable[[ExposureViolationType, str], None] | None = None

        logger.info(
            f"ExposureController initialized: equity=${equity:.2f}, max_position={self.limits.max_position_size_pct}%"
        )

    @property
    def current_drawdown_pct(self) -> float:
        """Calculate current drawdown as percentage."""
        if self.peak_equity <= 0:
            return 0.0
        return ((self.peak_equity - self.equity) / self.peak_equity) * 100

    @property
    def used_margin(self) -> float:
        """Calculate total used margin."""
        return sum(p.notional_value / p.leverage for p in self.positions.values())

    @property
    def total_pnl(self) -> float:
        """Calculate total unrealized P&L across all positions."""
        return sum(p.unrealized_pnl for p in self.positions.values())

    def can_add_position(
        self,
        symbol: str,
        side: str,
        size: float,
        entry_price: float,
        leverage: float = 1.0,
    ) -> dict[str, Any]:
        """
        Check if a new position can be added.

        Args:
            symbol: Trading symbol
            side: 'long' or 'short'
            size: Position size in base currency
            entry_price: Entry price
            leverage: Position leverage

        Returns:
            Dict with 'allowed' (bool) and 'reason' (str if not allowed)
        """
        result = self.check_new_position(
            symbol=symbol,
            side=side,
            size=size,
            entry_price=entry_price,
            leverage=leverage,
        )

        if result.allowed:
            return {"allowed": True}
        else:
            reason = "; ".join(result.messages) if result.messages else "Exposure limit exceeded"
            return {"allowed": False, "reason": reason}

    def update_equity(self, equity: float):
        """Update current equity."""
        self.equity = equity

        # Update peak for drawdown calculation
        if equity > self.peak_equity:
            self.peak_equity = equity

        # Update daily P&L
        self.daily_pnl = equity - self.daily_start_equity

        # Check if we hit loss limits
        self._check_loss_limits()

    def reset_daily(self):
        """Reset daily tracking (call at start of each trading day)."""
        self.daily_start_equity = self.equity
        self.daily_pnl = 0.0
        self.violations_today = []
        logger.info("Daily exposure tracking reset")

    def update_position(self, position: Position):
        """Update or add a position."""
        self.positions[position.symbol] = position

    def remove_position(self, symbol: str):
        """Remove a closed position."""
        if symbol in self.positions:
            del self.positions[symbol]

    def set_correlation(self, symbol1: str, symbol2: str, correlation: float):
        """Set correlation between two symbols."""
        if symbol1 not in self.correlations:
            self.correlations[symbol1] = {}
        if symbol2 not in self.correlations:
            self.correlations[symbol2] = {}

        self.correlations[symbol1][symbol2] = correlation
        self.correlations[symbol2][symbol1] = correlation

    def set_sector(self, symbol: str, sector: str):
        """Set sector for a symbol."""
        self.sector_map[symbol] = sector

    def check_new_position(
        self,
        symbol: str,
        side: str,
        size: float,
        entry_price: float,
        leverage: float = 1.0,
    ) -> ExposureCheckResult:
        """
        Check if a new position is allowed.

        Args:
            symbol: Trading symbol
            side: "long" or "short"
            size: Position size in base currency
            entry_price: Entry price
            leverage: Position leverage

        Returns:
            ExposureCheckResult with allowed status and any violations
        """
        violations = []
        messages = []

        # Check cooling period
        if self.cooling_until and datetime.now(UTC) < self.cooling_until:
            violations.append(ExposureViolationType.DAILY_LOSS_LIMIT)
            messages.append(f"Trading paused until {self.cooling_until.isoformat()}")
            return self._build_result(False, violations, messages)

        # Calculate new position value
        position_value = size * entry_price
        position_pct = (position_value / self.equity) * 100 if self.equity > 0 else 0

        # 1. Check max position size (%)
        if position_pct > self.limits.max_position_size_pct:
            violations.append(ExposureViolationType.MAX_POSITION_SIZE)
            messages.append(f"Position size {position_pct:.1f}% exceeds limit {self.limits.max_position_size_pct}%")

        # 2. Check max position size (USD)
        if position_value > self.limits.max_position_size_usd:
            violations.append(ExposureViolationType.MAX_POSITION_SIZE)
            messages.append(
                f"Position value ${position_value:.0f} exceeds limit ${self.limits.max_position_size_usd:.0f}"
            )

        # 3. Check max positions count
        if len(self.positions) >= self.limits.max_positions and symbol not in self.positions:  # Adding new position
            violations.append(ExposureViolationType.MAX_POSITIONS)
            messages.append(f"Max positions ({self.limits.max_positions}) reached")

        # 4. Check leverage
        if leverage > self.limits.max_leverage:
            violations.append(ExposureViolationType.MAX_LEVERAGE)
            messages.append(f"Leverage {leverage}x exceeds limit {self.limits.max_leverage}x")

        # 5. Check total exposure
        exposure_check = self._check_total_exposure(symbol, side, position_value)
        violations.extend(exposure_check["violations"])
        messages.extend(exposure_check["messages"])

        # 6. Check portfolio leverage
        portfolio_leverage = self._calculate_portfolio_leverage(symbol, side, position_value)
        if portfolio_leverage > self.limits.max_portfolio_leverage:
            violations.append(ExposureViolationType.MAX_LEVERAGE)
            messages.append(
                f"Portfolio leverage {portfolio_leverage:.1f}x exceeds limit {self.limits.max_portfolio_leverage}x"
            )

        # 7. Check correlation limits
        if self.correlations:
            corr_violations = self._check_correlation(symbol)
            violations.extend(corr_violations["violations"])
            messages.extend(corr_violations["messages"])

        # 8. Check sector exposure
        if self.sector_map.get(symbol):
            sector_check = self._check_sector_exposure(symbol, position_value)
            violations.extend(sector_check["violations"])
            messages.extend(sector_check["messages"])

        # 9. Check daily loss limit
        if self._is_daily_loss_exceeded():
            violations.append(ExposureViolationType.DAILY_LOSS_LIMIT)
            messages.append(f"Daily loss limit {self.limits.max_daily_loss_pct}% exceeded")

        # 10. Check drawdown limit
        if self._is_drawdown_exceeded():
            violations.append(ExposureViolationType.DRAWDOWN_LIMIT)
            messages.append(f"Drawdown limit {self.limits.max_drawdown_pct}% exceeded")

        allowed = len(violations) == 0

        if not allowed:
            # Record violations
            for v in violations:
                if v not in self.violations_today:
                    self.violations_today.append(v)
                if self.on_limit_breach:
                    self.on_limit_breach(v, "; ".join(messages))

            logger.warning(f"Position rejected for {symbol}: {'; '.join(messages)}")

        return self._build_result(allowed, violations, messages)

    def check_position_increase(
        self,
        symbol: str,
        additional_size: float,
        current_price: float,
    ) -> ExposureCheckResult:
        """Check if increasing an existing position is allowed."""
        position = self.positions.get(symbol)
        if not position:
            return self.check_new_position(symbol, "long", additional_size, current_price, 1.0)

        # Calculate new total size
        new_size = position.size + additional_size

        return self.check_new_position(
            symbol=symbol,
            side=position.side,
            size=new_size,
            entry_price=current_price,
            leverage=position.leverage,
        )

    def _check_total_exposure(
        self,
        symbol: str,
        side: str,
        position_value: float,
    ) -> dict[str, list]:
        """Check total portfolio exposure limits."""
        violations = []
        messages = []

        # Calculate current exposure
        long_exposure = sum(p.notional_value for p in self.positions.values() if p.side == "long")
        short_exposure = sum(p.notional_value for p in self.positions.values() if p.side == "short")

        # Add new position
        if side == "long":
            long_exposure += position_value
        else:
            short_exposure += position_value

        total_exposure = long_exposure + short_exposure
        net_exposure = abs(long_exposure - short_exposure)

        # Check limits
        total_pct = (total_exposure / self.equity) * 100 if self.equity > 0 else 0
        long_pct = (long_exposure / self.equity) * 100 if self.equity > 0 else 0
        short_pct = (short_exposure / self.equity) * 100 if self.equity > 0 else 0
        net_pct = (net_exposure / self.equity) * 100 if self.equity > 0 else 0

        if total_pct > self.limits.max_total_exposure_pct:
            violations.append(ExposureViolationType.MAX_TOTAL_EXPOSURE)
            messages.append(f"Total exposure {total_pct:.1f}% exceeds limit {self.limits.max_total_exposure_pct}%")

        if long_pct > self.limits.max_long_exposure_pct:
            violations.append(ExposureViolationType.MAX_TOTAL_EXPOSURE)
            messages.append(f"Long exposure {long_pct:.1f}% exceeds limit {self.limits.max_long_exposure_pct}%")

        if short_pct > self.limits.max_short_exposure_pct:
            violations.append(ExposureViolationType.MAX_TOTAL_EXPOSURE)
            messages.append(f"Short exposure {short_pct:.1f}% exceeds limit {self.limits.max_short_exposure_pct}%")

        if net_pct > self.limits.max_net_exposure_pct:
            violations.append(ExposureViolationType.MAX_TOTAL_EXPOSURE)
            messages.append(f"Net exposure {net_pct:.1f}% exceeds limit {self.limits.max_net_exposure_pct}%")

        return {"violations": violations, "messages": messages}

    def _calculate_portfolio_leverage(
        self,
        symbol: str,
        side: str,
        position_value: float,
    ) -> float:
        """Calculate total portfolio leverage after adding position."""
        total_exposure = sum(p.notional_value for p in self.positions.values())
        total_exposure += position_value

        if self.equity > 0:
            return total_exposure / self.equity
        return 0.0

    def _check_correlation(self, new_symbol: str) -> dict[str, list]:
        """Check correlation limits for new position."""
        violations = []
        messages = []

        correlated_count = 0
        correlated_symbols = []

        symbol_correlations = self.correlations.get(new_symbol, {})

        for existing_symbol in self.positions:
            correlation = symbol_correlations.get(existing_symbol, 0)
            if abs(correlation) >= self.limits.correlation_threshold:
                correlated_count += 1
                correlated_symbols.append(f"{existing_symbol}({correlation:.2f})")

        if correlated_count >= self.limits.max_correlated_positions:
            violations.append(ExposureViolationType.MAX_CORRELATION)
            messages.append(f"Too many correlated positions: {', '.join(correlated_symbols)}")

        return {"violations": violations, "messages": messages}

    def _check_sector_exposure(
        self,
        symbol: str,
        position_value: float,
    ) -> dict[str, list]:
        """Check sector exposure limits."""
        violations = []
        messages = []

        sector = self.sector_map.get(symbol, "other")

        # Calculate current sector exposure
        sector_exposure = sum(
            p.notional_value for p in self.positions.values() if self.sector_map.get(p.symbol) == sector
        )
        sector_exposure += position_value

        sector_pct = (sector_exposure / self.equity) * 100 if self.equity > 0 else 0

        if sector_pct > self.limits.max_sector_exposure_pct:
            violations.append(ExposureViolationType.MAX_SECTOR_EXPOSURE)
            messages.append(
                f"Sector '{sector}' exposure {sector_pct:.1f}% exceeds limit {self.limits.max_sector_exposure_pct}%"
            )

        return {"violations": violations, "messages": messages}

    def _is_daily_loss_exceeded(self) -> bool:
        """Check if daily loss limit is exceeded."""
        if self.daily_start_equity <= 0:
            return False

        loss_pct = (self.daily_pnl / self.daily_start_equity) * 100
        return loss_pct < -self.limits.max_daily_loss_pct

    def _is_drawdown_exceeded(self) -> bool:
        """Check if drawdown limit is exceeded."""
        if self.peak_equity <= 0:
            return False

        drawdown_pct = ((self.peak_equity - self.equity) / self.peak_equity) * 100
        return drawdown_pct > self.limits.max_drawdown_pct

    def _check_loss_limits(self):
        """Check loss limits and set cooling period if needed."""
        if self._is_daily_loss_exceeded() or self._is_drawdown_exceeded():
            self.cooling_until = datetime.now(UTC) + timedelta(seconds=self.limits.cooling_period_after_violation)

            logger.warning(f"Loss limit breached! Trading paused until {self.cooling_until.isoformat()}")

    def get_max_position_size(
        self,
        symbol: str,
        current_price: float,
    ) -> float:
        """
        Calculate maximum allowed position size based on exposure limits.

        Args:
            symbol: Trading symbol
            current_price: Current price for calculation

        Returns:
            Maximum position size in base currency
        """
        if self.equity <= 0 or current_price <= 0:
            return 0.0

        # Calculate max from position size limit
        max_position_value = self.equity * (self.limits.max_position_size_pct / 100)
        max_from_position = max_position_value / current_price

        # Calculate available exposure capacity
        current_exposure = sum(p.notional_value for p in self.positions.values())
        max_total_value = self.equity * (self.limits.max_total_exposure_pct / 100)
        available_exposure = max(0, max_total_value - current_exposure)
        max_from_exposure = available_exposure / current_price

        # Return the smaller of the two limits
        return min(max_from_position, max_from_exposure)

    def _build_result(
        self,
        allowed: bool,
        violations: list[ExposureViolationType],
        messages: list[str],
    ) -> ExposureCheckResult:
        """Build exposure check result."""
        # Calculate current exposure metrics
        long_exp = sum(p.notional_value for p in self.positions.values() if p.side == "long")
        short_exp = sum(p.notional_value for p in self.positions.values() if p.side == "short")

        current = {
            "total_exposure_pct": ((long_exp + short_exp) / self.equity * 100 if self.equity > 0 else 0),
            "long_exposure_pct": long_exp / self.equity * 100 if self.equity > 0 else 0,
            "short_exposure_pct": short_exp / self.equity * 100 if self.equity > 0 else 0,
            "net_exposure_pct": (abs(long_exp - short_exp) / self.equity * 100 if self.equity > 0 else 0),
            "positions_count": len(self.positions),
            "daily_pnl_pct": (self.daily_pnl / self.daily_start_equity * 100 if self.daily_start_equity > 0 else 0),
            "drawdown_pct": ((self.peak_equity - self.equity) / self.peak_equity * 100 if self.peak_equity > 0 else 0),
        }

        limits = {
            "max_total_exposure_pct": self.limits.max_total_exposure_pct,
            "max_long_exposure_pct": self.limits.max_long_exposure_pct,
            "max_short_exposure_pct": self.limits.max_short_exposure_pct,
            "max_positions": self.limits.max_positions,
            "max_daily_loss_pct": self.limits.max_daily_loss_pct,
            "max_drawdown_pct": self.limits.max_drawdown_pct,
        }

        return ExposureCheckResult(
            allowed=allowed,
            violations=violations,
            messages=messages,
            current_exposure=current,
            limits=limits,
        )

    def get_current_exposure(self) -> dict[str, Any]:
        """Get current exposure metrics."""
        long_exp = sum(p.notional_value for p in self.positions.values() if p.side == "long")
        short_exp = sum(p.notional_value for p in self.positions.values() if p.side == "short")
        total_exp = long_exp + short_exp

        # Sector breakdown
        sector_exposure: dict[str, float] = {}
        for p in self.positions.values():
            sector = self.sector_map.get(p.symbol, "other")
            sector_exposure[sector] = sector_exposure.get(sector, 0) + p.notional_value

        return {
            "equity": self.equity,
            "total_exposure": total_exp,
            "total_exposure_pct": total_exp / self.equity * 100 if self.equity > 0 else 0,
            "long_exposure": long_exp,
            "long_exposure_pct": long_exp / self.equity * 100 if self.equity > 0 else 0,
            "short_exposure": short_exp,
            "short_exposure_pct": short_exp / self.equity * 100 if self.equity > 0 else 0,
            "net_exposure": long_exp - short_exp,
            "net_exposure_pct": (long_exp - short_exp) / self.equity * 100 if self.equity > 0 else 0,
            "portfolio_leverage": total_exp / self.equity if self.equity > 0 else 0,
            "positions_count": len(self.positions),
            "daily_pnl": self.daily_pnl,
            "daily_pnl_pct": self.daily_pnl / self.daily_start_equity * 100 if self.daily_start_equity > 0 else 0,
            "drawdown_pct": (self.peak_equity - self.equity) / self.peak_equity * 100 if self.peak_equity > 0 else 0,
            "sector_exposure": sector_exposure,
            "is_in_cooling": self.cooling_until and datetime.now(UTC) < self.cooling_until,
            "violations_today": [v.value for v in self.violations_today],
        }

    def calculate_max_position_size(
        self,
        symbol: str,
        side: str,
        current_price: float,
        leverage: float = 1.0,
    ) -> float:
        """
        Calculate maximum allowed position size for a symbol.

        Returns:
            Maximum position size in base currency
        """
        # Start with position size limit
        max_by_pct = self.equity * (self.limits.max_position_size_pct / 100)
        max_by_usd = self.limits.max_position_size_usd
        max_position_value = min(max_by_pct, max_by_usd)

        # Adjust for remaining exposure capacity
        current_exposure = sum(p.notional_value for p in self.positions.values())
        max_total = self.equity * (self.limits.max_total_exposure_pct / 100)
        remaining_exposure = max(0, max_total - current_exposure)

        # Take the minimum
        max_value = min(max_position_value, remaining_exposure)

        # Convert to base currency
        if current_price > 0:
            return max_value / current_price
        return 0.0
