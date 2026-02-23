"""
Trade Validator Module

Validates trades before execution against risk limits and rules.
Pre-trade checks for position sizing, exposure, and strategy constraints.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ValidationResult(Enum):
    """Trade validation result."""

    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"
    PENDING_REVIEW = "pending_review"


class RejectionReason(Enum):
    """Reasons for trade rejection."""

    INSUFFICIENT_BALANCE = "insufficient_balance"
    POSITION_SIZE_EXCEEDED = "position_size_exceeded"
    EXPOSURE_LIMIT_EXCEEDED = "exposure_limit_exceeded"
    LEVERAGE_LIMIT_EXCEEDED = "leverage_limit_exceeded"
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    DRAWDOWN_LIMIT = "drawdown_limit"
    CORRELATION_LIMIT = "correlation_limit"
    SYMBOL_BLOCKED = "symbol_blocked"
    TRADING_PAUSED = "trading_paused"
    INVALID_ORDER_PARAMS = "invalid_order_params"
    MIN_ORDER_SIZE = "min_order_size"
    MAX_ORDER_SIZE = "max_order_size"
    PRICE_OUT_OF_RANGE = "price_out_of_range"
    MARGIN_REQUIREMENT = "margin_requirement"
    RISK_REWARD_RATIO = "risk_reward_ratio"
    STRATEGY_LIMIT = "strategy_limit"
    COOLDOWN_ACTIVE = "cooldown_active"
    MAX_TRADES_REACHED = "max_trades_reached"


@dataclass
class ValidationConfig:
    """Configuration for trade validation."""

    # Balance checks
    min_balance_usd: float = 100.0
    min_free_balance_pct: float = 10.0  # Keep 10% free

    # Order size limits
    min_order_size_usd: float = 10.0
    max_order_size_usd: float = 100000.0
    max_order_size_pct: float = 20.0  # Max 20% of equity per order

    # Leverage limits
    max_leverage: float = 10.0
    default_leverage: float = 1.0

    # Price checks
    max_price_deviation_pct: float = 5.0  # Max 5% from current price

    # Risk/Reward
    min_risk_reward_ratio: float = 1.0  # Min 1:1 RR

    # Frequency limits
    max_trades_per_day: int = 100
    max_trades_per_hour: int = 20
    min_trade_interval_seconds: int = 5

    # Position limits
    max_open_positions: int = 20
    max_positions_per_symbol: int = 1

    # Symbol restrictions
    blocked_symbols: list[str] = None
    allowed_symbols: list[str] = None  # If set, only these symbols allowed

    def __post_init__(self):
        if self.blocked_symbols is None:
            self.blocked_symbols = []


@dataclass
class TradeRequest:
    """Trade request to be validated."""

    symbol: str
    side: str  # "buy" or "sell"
    order_type: str  # "market", "limit", "stop_market", "stop_limit"
    quantity: float
    price: float | None = None  # Required for limit orders
    stop_loss: float | None = None
    take_profit: float | None = None
    leverage: float = 1.0
    strategy_id: str | None = None
    reduce_only: bool = False
    time_in_force: str = "GTC"
    client_order_id: str | None = None
    metadata: dict[str, Any] | None = None

    @property
    def is_limit(self) -> bool:
        return "limit" in self.order_type.lower()

    @property
    def notional_value(self) -> float:
        """Calculate notional value (needs current price for market orders)."""
        if self.price:
            return self.quantity * self.price
        return 0.0


@dataclass
class ValidationReport:
    """Result of trade validation."""

    request: TradeRequest
    result: ValidationResult
    approved: bool
    rejection_reasons: list[RejectionReason]
    warnings: list[str]
    modifications: dict[str, Any]  # Suggested modifications
    details: dict[str, Any]
    validated_at: datetime
    validation_time_ms: float

    @classmethod
    def approve(
        cls,
        request: TradeRequest,
        warnings: list[str] | None = None,
        details: dict[str, Any] | None = None,
        validation_time_ms: float = 0,
    ) -> "ValidationReport":
        """Create approved validation report."""
        return cls(
            request=request,
            result=ValidationResult.APPROVED,
            approved=True,
            rejection_reasons=[],
            warnings=warnings or [],
            modifications={},
            details=details or {},
            validated_at=datetime.now(),
            validation_time_ms=validation_time_ms,
        )

    @classmethod
    def reject(
        cls,
        request: TradeRequest,
        reasons: list[RejectionReason],
        details: dict[str, Any] | None = None,
        validation_time_ms: float = 0,
    ) -> "ValidationReport":
        """Create rejected validation report."""
        return cls(
            request=request,
            result=ValidationResult.REJECTED,
            approved=False,
            rejection_reasons=reasons,
            warnings=[],
            modifications={},
            details=details or {},
            validated_at=datetime.now(),
            validation_time_ms=validation_time_ms,
        )

    @classmethod
    def modify(
        cls,
        request: TradeRequest,
        modifications: dict[str, Any],
        warnings: list[str] | None = None,
        details: dict[str, Any] | None = None,
        validation_time_ms: float = 0,
    ) -> "ValidationReport":
        """Create modified validation report with suggested changes."""
        return cls(
            request=request,
            result=ValidationResult.MODIFIED,
            approved=True,
            rejection_reasons=[],
            warnings=warnings or [],
            modifications=modifications,
            details=details or {},
            validated_at=datetime.now(),
            validation_time_ms=validation_time_ms,
        )


@dataclass
class AccountState:
    """Current account state for validation."""

    total_equity: float
    available_balance: float
    used_margin: float
    total_pnl: float
    daily_pnl: float
    open_positions_count: int
    positions_by_symbol: dict[str, int]  # symbol -> position count
    trades_today: int
    trades_this_hour: int
    last_trade_time: datetime | None
    is_trading_paused: bool = False
    current_drawdown_pct: float = 0.0


class TradeValidator:
    """
    Validates trade requests against risk limits and account state.

    Features:
    - Balance and margin validation
    - Position size limits
    - Leverage checks
    - Symbol restrictions
    - Trading frequency limits
    - Risk/reward validation
    """

    def __init__(self, config: ValidationConfig | None = None):
        """Initialize TradeValidator."""
        self.config = config or ValidationConfig()
        self._custom_validators: list[
            Callable[[TradeRequest, AccountState], RejectionReason | None]
        ] = []
        self._price_cache: dict[str, float] = {}
        self._last_price_update: dict[str, datetime] = {}

        # Callbacks
        self.on_rejection: Callable[[TradeRequest, list[RejectionReason]], None] | None = None
        self.on_approval: Callable[[TradeRequest, ValidationReport], None] | None = (
            None
        )

        logger.info("TradeValidator initialized")

    def update_price(self, symbol: str, price: float):
        """Update cached price for a symbol."""
        self._price_cache[symbol] = price
        self._last_price_update[symbol] = datetime.now()

    def update_prices(self, prices: dict[str, float]):
        """Batch update prices."""
        now = datetime.now()
        for symbol, price in prices.items():
            self._price_cache[symbol] = price
            self._last_price_update[symbol] = now

    def get_price(self, symbol: str) -> float | None:
        """Get cached price for a symbol."""
        return self._price_cache.get(symbol)

    def add_custom_validator(
        self,
        validator: Callable[[TradeRequest, AccountState], RejectionReason | None],
    ):
        """Add a custom validation function."""
        self._custom_validators.append(validator)
        logger.info(f"Added custom validator: {validator.__name__}")

    def validate(
        self, request: TradeRequest, account_state: AccountState
    ) -> ValidationReport:
        """
        Validate a trade request against all rules.

        Args:
            request: The trade request to validate
            account_state: Current account state

        Returns:
            ValidationReport with approval status and details
        """
        import time

        start_time = time.time()

        rejection_reasons: list[RejectionReason] = []
        warnings: list[str] = []
        details: dict[str, Any] = {}

        # Check trading status
        if account_state.is_trading_paused:
            rejection_reasons.append(RejectionReason.TRADING_PAUSED)

        # Validate order parameters
        param_errors = self._validate_order_params(request)
        rejection_reasons.extend(param_errors)

        # Check symbol restrictions
        symbol_error = self._validate_symbol(request.symbol)
        if symbol_error:
            rejection_reasons.append(symbol_error)

        # Get current price for calculations
        current_price = self.get_price(request.symbol) or request.price
        if not current_price:
            warnings.append("No price available for notional calculation")
            current_price = request.price or 1.0

        notional_value = request.quantity * current_price
        details["notional_value"] = notional_value
        details["current_price"] = current_price

        # Balance checks
        balance_errors = self._validate_balance(
            notional_value, request.leverage, account_state
        )
        rejection_reasons.extend(balance_errors)

        # Order size checks
        size_errors = self._validate_order_size(
            notional_value, account_state.total_equity
        )
        rejection_reasons.extend(size_errors)

        # Leverage check
        if request.leverage > self.config.max_leverage:
            rejection_reasons.append(RejectionReason.LEVERAGE_LIMIT_EXCEEDED)
            details["max_leverage"] = self.config.max_leverage
            details["requested_leverage"] = request.leverage

        # Price deviation check for limit orders
        if request.is_limit and request.price and current_price:
            deviation = abs(request.price - current_price) / current_price * 100
            if deviation > self.config.max_price_deviation_pct:
                rejection_reasons.append(RejectionReason.PRICE_OUT_OF_RANGE)
                details["price_deviation_pct"] = deviation

        # Position limits
        position_errors = self._validate_position_limits(request, account_state)
        rejection_reasons.extend(position_errors)

        # Trading frequency limits
        frequency_errors = self._validate_frequency(account_state)
        rejection_reasons.extend(frequency_errors)

        # Risk/Reward check
        rr_error = self._validate_risk_reward(request, current_price)
        if rr_error:
            rejection_reasons.append(rr_error)

        # Run custom validators
        for validator in self._custom_validators:
            try:
                error = validator(request, account_state)
                if error:
                    rejection_reasons.append(error)
            except Exception as e:
                logger.error(f"Custom validator error: {e}")
                warnings.append(f"Custom validation failed: {e!s}")

        validation_time_ms = (time.time() - start_time) * 1000

        # Create report
        if rejection_reasons:
            report = ValidationReport.reject(
                request=request,
                reasons=rejection_reasons,
                details=details,
                validation_time_ms=validation_time_ms,
            )

            if self.on_rejection:
                self.on_rejection(request, rejection_reasons)

            logger.warning(
                f"Trade rejected: {request.symbol} {request.side} "
                f"qty={request.quantity}, reasons={[r.value for r in rejection_reasons]}"
            )
        else:
            report = ValidationReport.approve(
                request=request,
                warnings=warnings,
                details=details,
                validation_time_ms=validation_time_ms,
            )

            if self.on_approval:
                self.on_approval(request, report)

            logger.info(
                f"Trade approved: {request.symbol} {request.side} "
                f"qty={request.quantity}, notional=${notional_value:.2f}"
            )

        return report

    def _validate_order_params(self, request: TradeRequest) -> list[RejectionReason]:
        """Validate basic order parameters."""
        errors = []

        if request.quantity <= 0:
            errors.append(RejectionReason.INVALID_ORDER_PARAMS)

        if request.side.lower() not in ["buy", "sell"]:
            errors.append(RejectionReason.INVALID_ORDER_PARAMS)

        if request.is_limit and not request.price:
            errors.append(RejectionReason.INVALID_ORDER_PARAMS)

        if request.price is not None and request.price <= 0:
            errors.append(RejectionReason.INVALID_ORDER_PARAMS)

        if request.leverage <= 0:
            errors.append(RejectionReason.INVALID_ORDER_PARAMS)

        return errors

    def _validate_symbol(self, symbol: str) -> RejectionReason | None:
        """Validate symbol is allowed."""
        if symbol in self.config.blocked_symbols:
            return RejectionReason.SYMBOL_BLOCKED

        if self.config.allowed_symbols and symbol not in self.config.allowed_symbols:
            return RejectionReason.SYMBOL_BLOCKED

        return None

    def _validate_balance(
        self, notional_value: float, leverage: float, account_state: AccountState
    ) -> list[RejectionReason]:
        """Validate account balance is sufficient."""
        errors = []

        # Minimum balance check
        if account_state.total_equity < self.config.min_balance_usd:
            errors.append(RejectionReason.INSUFFICIENT_BALANCE)

        # Required margin calculation
        required_margin = notional_value / leverage

        # Available balance check
        if required_margin > account_state.available_balance:
            errors.append(RejectionReason.MARGIN_REQUIREMENT)

        # Keep minimum free balance
        min_free = account_state.total_equity * (self.config.min_free_balance_pct / 100)
        if account_state.available_balance - required_margin < min_free:
            errors.append(RejectionReason.INSUFFICIENT_BALANCE)

        return errors

    def _validate_order_size(
        self, notional_value: float, equity: float
    ) -> list[RejectionReason]:
        """Validate order size limits."""
        errors = []

        if notional_value < self.config.min_order_size_usd:
            errors.append(RejectionReason.MIN_ORDER_SIZE)

        if notional_value > self.config.max_order_size_usd:
            errors.append(RejectionReason.MAX_ORDER_SIZE)

        # Percentage of equity check
        size_pct = (notional_value / equity) * 100 if equity > 0 else 100
        if size_pct > self.config.max_order_size_pct:
            errors.append(RejectionReason.POSITION_SIZE_EXCEEDED)

        return errors

    def _validate_position_limits(
        self, request: TradeRequest, account_state: AccountState
    ) -> list[RejectionReason]:
        """Validate position count limits."""
        errors = []

        # Max open positions
        if not request.reduce_only:
            if account_state.open_positions_count >= self.config.max_open_positions:
                errors.append(RejectionReason.EXPOSURE_LIMIT_EXCEEDED)

            # Max positions per symbol
            symbol_positions = account_state.positions_by_symbol.get(request.symbol, 0)
            if symbol_positions >= self.config.max_positions_per_symbol:
                errors.append(RejectionReason.POSITION_SIZE_EXCEEDED)

        return errors

    def _validate_frequency(self, account_state: AccountState) -> list[RejectionReason]:
        """Validate trading frequency limits."""
        errors = []

        # Daily limit
        if account_state.trades_today >= self.config.max_trades_per_day:
            errors.append(RejectionReason.MAX_TRADES_REACHED)

        # Hourly limit
        if account_state.trades_this_hour >= self.config.max_trades_per_hour:
            errors.append(RejectionReason.MAX_TRADES_REACHED)

        # Minimum interval between trades
        if account_state.last_trade_time:
            elapsed = (datetime.now() - account_state.last_trade_time).total_seconds()
            if elapsed < self.config.min_trade_interval_seconds:
                errors.append(RejectionReason.COOLDOWN_ACTIVE)

        return errors

    def _validate_risk_reward(
        self, request: TradeRequest, current_price: float
    ) -> RejectionReason | None:
        """Validate risk/reward ratio if stop loss and take profit are set."""
        if not request.stop_loss or not request.take_profit:
            return None

        entry_price = request.price or current_price
        if not entry_price:
            return None

        if request.side.lower() == "buy":
            risk = entry_price - request.stop_loss
            reward = request.take_profit - entry_price
        else:
            risk = request.stop_loss - entry_price
            reward = entry_price - request.take_profit

        if risk <= 0 or reward <= 0:
            return RejectionReason.INVALID_ORDER_PARAMS

        rr_ratio = reward / risk
        if rr_ratio < self.config.min_risk_reward_ratio:
            return RejectionReason.RISK_REWARD_RATIO

        return None

    def quick_check(
        self, symbol: str, side: str, quantity: float, account_state: AccountState
    ) -> bool:
        """Quick validation without full report."""
        request = TradeRequest(
            symbol=symbol, side=side, order_type="market", quantity=quantity
        )
        report = self.validate(request, account_state)
        return report.approved

    def calculate_max_quantity(
        self, symbol: str, side: str, account_state: AccountState, leverage: float = 1.0
    ) -> float | None:
        """
        Calculate maximum allowed quantity for a symbol.

        Returns:
            Maximum quantity or None if trading not allowed
        """
        current_price = self.get_price(symbol)
        if not current_price:
            return None

        # Check if symbol is allowed
        if self._validate_symbol(symbol):
            return None

        # Calculate based on available balance and limits
        available = account_state.available_balance
        min_free = account_state.total_equity * (self.config.min_free_balance_pct / 100)
        usable_balance = max(0, available - min_free)

        # Max from balance
        max_notional_balance = usable_balance * leverage

        # Max from percentage limit
        max_notional_pct = account_state.total_equity * (
            self.config.max_order_size_pct / 100
        )

        # Max from absolute limit
        max_notional_abs = self.config.max_order_size_usd

        # Take minimum
        max_notional = min(max_notional_balance, max_notional_pct, max_notional_abs)

        # Convert to quantity
        max_quantity = max_notional / current_price

        return max(0, max_quantity)

    def get_stats(self) -> dict[str, Any]:
        """Get validator statistics."""
        return {
            "config": {
                "min_balance_usd": self.config.min_balance_usd,
                "max_leverage": self.config.max_leverage,
                "max_order_size_pct": self.config.max_order_size_pct,
                "max_trades_per_day": self.config.max_trades_per_day,
                "max_open_positions": self.config.max_open_positions,
            },
            "custom_validators_count": len(self._custom_validators),
            "cached_prices_count": len(self._price_cache),
        }


class TradeValidatorBuilder:
    """Builder for creating configured TradeValidator instances."""

    def __init__(self):
        self._config = ValidationConfig()

    def with_balance_limits(
        self, min_balance: float = 100.0, min_free_pct: float = 10.0
    ) -> "TradeValidatorBuilder":
        """Set balance limits."""
        self._config.min_balance_usd = min_balance
        self._config.min_free_balance_pct = min_free_pct
        return self

    def with_order_limits(
        self, min_size: float = 10.0, max_size: float = 100000.0, max_pct: float = 20.0
    ) -> "TradeValidatorBuilder":
        """Set order size limits."""
        self._config.min_order_size_usd = min_size
        self._config.max_order_size_usd = max_size
        self._config.max_order_size_pct = max_pct
        return self

    def with_leverage_limit(
        self, max_leverage: float = 10.0
    ) -> "TradeValidatorBuilder":
        """Set maximum leverage."""
        self._config.max_leverage = max_leverage
        return self

    def with_frequency_limits(
        self,
        max_per_day: int = 100,
        max_per_hour: int = 20,
        min_interval_seconds: int = 5,
    ) -> "TradeValidatorBuilder":
        """Set trading frequency limits."""
        self._config.max_trades_per_day = max_per_day
        self._config.max_trades_per_hour = max_per_hour
        self._config.min_trade_interval_seconds = min_interval_seconds
        return self

    def with_position_limits(
        self, max_positions: int = 20, max_per_symbol: int = 1
    ) -> "TradeValidatorBuilder":
        """Set position limits."""
        self._config.max_open_positions = max_positions
        self._config.max_positions_per_symbol = max_per_symbol
        return self

    def with_blocked_symbols(self, symbols: list[str]) -> "TradeValidatorBuilder":
        """Set blocked symbols."""
        self._config.blocked_symbols = symbols
        return self

    def with_allowed_symbols(self, symbols: list[str]) -> "TradeValidatorBuilder":
        """Set allowed symbols (whitelist)."""
        self._config.allowed_symbols = symbols
        return self

    def with_risk_reward(self, min_ratio: float = 1.0) -> "TradeValidatorBuilder":
        """Set minimum risk/reward ratio."""
        self._config.min_risk_reward_ratio = min_ratio
        return self

    def build(self) -> TradeValidator:
        """Build the configured TradeValidator."""
        return TradeValidator(self._config)


# Factory function for common configurations
def create_conservative_validator() -> TradeValidator:
    """Create a conservative trade validator with strict limits."""
    return (
        TradeValidatorBuilder()
        .with_balance_limits(min_balance=500.0, min_free_pct=20.0)
        .with_order_limits(min_size=50.0, max_size=10000.0, max_pct=5.0)
        .with_leverage_limit(3.0)
        .with_frequency_limits(max_per_day=20, max_per_hour=5, min_interval_seconds=30)
        .with_position_limits(max_positions=5, max_per_symbol=1)
        .with_risk_reward(min_ratio=1.5)
        .build()
    )


def create_moderate_validator() -> TradeValidator:
    """Create a moderate trade validator with balanced limits."""
    return (
        TradeValidatorBuilder()
        .with_balance_limits(min_balance=200.0, min_free_pct=15.0)
        .with_order_limits(min_size=20.0, max_size=50000.0, max_pct=10.0)
        .with_leverage_limit(5.0)
        .with_frequency_limits(max_per_day=50, max_per_hour=10, min_interval_seconds=10)
        .with_position_limits(max_positions=10, max_per_symbol=1)
        .with_risk_reward(min_ratio=1.0)
        .build()
    )


def create_aggressive_validator() -> TradeValidator:
    """Create an aggressive trade validator with relaxed limits."""
    return (
        TradeValidatorBuilder()
        .with_balance_limits(min_balance=100.0, min_free_pct=10.0)
        .with_order_limits(min_size=10.0, max_size=100000.0, max_pct=25.0)
        .with_leverage_limit(10.0)
        .with_frequency_limits(max_per_day=100, max_per_hour=20, min_interval_seconds=5)
        .with_position_limits(max_positions=20, max_per_symbol=3)
        .with_risk_reward(min_ratio=0.5)
        .build()
    )
