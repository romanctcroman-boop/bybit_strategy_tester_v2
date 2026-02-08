"""
Universal Position Manager - Управление позициями для ВСЕХ режимов.

Поддерживаемые режимы:
- Fixed: Фиксированный % от капитала
- Risk-based: Размер по риску на сделку
- Kelly: Критерий Келли
- Volatility: Обратно пропорционально волатильности
- DCA (Dollar Cost Averaging): Усреднение позиции
- Scale-in: Частичный вход
- Pyramiding: Несколько позиций

Автор: AI Agent
Версия: 1.0.0
"""

from dataclasses import dataclass, field

import numpy as np

try:
    from numba import njit

    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False

    def njit(*args, **kwargs):
        def decorator(func):
            return func

        if len(args) == 1 and callable(args[0]):
            return args[0]
        return decorator


# =============================================================================
# POSITION SIZING CALCULATIONS (NUMBA)
# =============================================================================


@njit(cache=True)
def calculate_fixed_position_size(
    capital: float, position_size_pct: float, leverage: int, price: float
) -> float:
    """
    Calculate fixed position size as % of capital.

    Args:
        capital: Available capital
        position_size_pct: Position size as fraction (0.1 = 10%)
        leverage: Leverage multiplier
        price: Entry price

    Returns:
        Position size in base currency
    """
    notional = capital * position_size_pct * leverage
    return notional / price


@njit(cache=True)
def calculate_risk_based_size(
    capital: float,
    risk_per_trade: float,
    stop_loss_pct: float,
    leverage: int,
    price: float,
) -> float:
    """
    Calculate position size based on risk per trade.

    Risk amount = capital × risk_per_trade
    Position = Risk amount / stop_loss_pct

    Args:
        capital: Available capital
        risk_per_trade: Risk as fraction (0.01 = 1%)
        stop_loss_pct: Stop loss as fraction (0.02 = 2%)
        leverage: Leverage multiplier
        price: Entry price

    Returns:
        Position size in base currency
    """
    if stop_loss_pct <= 0:
        return 0.0

    risk_amount = capital * risk_per_trade
    position_value = risk_amount / stop_loss_pct
    notional = position_value * leverage
    return notional / price


@njit(cache=True)
def calculate_kelly_size(
    capital: float,
    win_rate: float,
    avg_win_pct: float,
    avg_loss_pct: float,
    kelly_fraction: float,
    leverage: int,
    price: float,
    max_position_size: float,
) -> float:
    """
    Calculate position size using Kelly Criterion.

    Kelly % = W - (1-W)/R where:
    - W = win rate
    - R = avg_win / avg_loss (reward/risk ratio)

    Args:
        capital: Available capital
        win_rate: Historical win rate (0-1)
        avg_win_pct: Average win as fraction
        avg_loss_pct: Average loss as fraction (positive)
        kelly_fraction: Fraction of Kelly to use (0.5 = half-Kelly)
        leverage: Leverage multiplier
        price: Entry price
        max_position_size: Maximum position size as fraction

    Returns:
        Position size in base currency
    """
    if avg_loss_pct <= 0 or win_rate <= 0 or win_rate >= 1:
        return calculate_fixed_position_size(capital, 0.1, leverage, price)

    # Reward/risk ratio
    rr_ratio = avg_win_pct / avg_loss_pct

    # Kelly formula
    kelly_pct = win_rate - (1 - win_rate) / rr_ratio

    # Apply fraction and clamp
    if kelly_pct <= 0:
        return 0.0

    position_pct = kelly_pct * kelly_fraction
    if position_pct > max_position_size:
        position_pct = max_position_size

    return calculate_fixed_position_size(capital, position_pct, leverage, price)


@njit(cache=True)
def calculate_volatility_size(
    capital: float,
    current_atr: float,
    avg_atr: float,
    volatility_target: float,
    leverage: int,
    price: float,
    min_position_size: float,
    max_position_size: float,
) -> float:
    """
    Calculate position size inversely proportional to volatility.

    Higher volatility = smaller position

    Args:
        capital: Available capital
        current_atr: Current ATR value
        avg_atr: Average ATR (baseline)
        volatility_target: Target volatility as fraction
        leverage: Leverage multiplier
        price: Entry price
        min_position_size: Minimum position size as fraction
        max_position_size: Maximum position size as fraction

    Returns:
        Position size in base currency
    """
    if current_atr <= 0 or avg_atr <= 0:
        return calculate_fixed_position_size(capital, 0.1, leverage, price)

    # Volatility ratio
    vol_ratio = avg_atr / current_atr

    # Position size scales with inverse volatility
    position_pct = volatility_target * vol_ratio

    # Clamp to min/max
    if position_pct < min_position_size:
        position_pct = min_position_size
    if position_pct > max_position_size:
        position_pct = max_position_size

    return calculate_fixed_position_size(capital, position_pct, leverage, price)


@njit(cache=True)
def calculate_dca_levels(
    entry_price: float,
    direction: int,  # 0=long, 1=short
    num_safety_orders: int,
    price_deviation: float,
    step_scale: float,
    volume_scale: float,
    base_order_size: float,
    safety_order_size: float,
    capital: float,
    leverage: int,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Calculate DCA (Dollar Cost Averaging) entry levels.

    Args:
        entry_price: Initial entry price
        direction: 0=long, 1=short
        num_safety_orders: Number of safety orders
        price_deviation: First SO deviation (0.01 = 1%)
        step_scale: Step multiplier (1.5 = each SO 1.5x further)
        volume_scale: Volume multiplier (1.0 = no martingale)
        base_order_size: Base order as fraction of capital
        safety_order_size: First SO as fraction of capital
        capital: Available capital
        leverage: Leverage multiplier

    Returns:
        (prices, sizes): Arrays of entry prices and sizes
    """
    total_orders = num_safety_orders + 1  # Base + SOs
    prices = np.zeros(total_orders, dtype=np.float64)
    sizes = np.zeros(total_orders, dtype=np.float64)

    # Base order
    prices[0] = entry_price
    sizes[0] = (capital * base_order_size * leverage) / entry_price

    # Safety orders
    cumulative_deviation = price_deviation
    current_so_size = safety_order_size

    for i in range(1, total_orders):
        if direction == 0:  # Long - buy lower
            prices[i] = entry_price * (1 - cumulative_deviation)
        else:  # Short - sell higher
            prices[i] = entry_price * (1 + cumulative_deviation)

        sizes[i] = (capital * current_so_size * leverage) / prices[i]

        # Scale for next SO
        cumulative_deviation += price_deviation * (step_scale**i)
        current_so_size *= volume_scale

    return prices, sizes


@njit(cache=True)
def calculate_scale_in_levels(
    entry_price: float,
    direction: int,  # 0=long, 1=short
    scale_in_levels: np.ndarray,  # e.g., [0, 0.01, 0.02] for 0%, +1%, +2%
    scale_in_portions: np.ndarray,  # e.g., [0.33, 0.33, 0.34]
    total_position_size: float,
    price: float,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Calculate scale-in (partial entry) levels.

    Args:
        entry_price: Base entry price
        direction: 0=long, 1=short
        scale_in_levels: Price levels as fraction from entry
        scale_in_portions: Portions at each level (sum = 1.0)
        total_position_size: Total desired position size
        price: Current price (for notional calculation)

    Returns:
        (prices, sizes): Arrays of entry prices and sizes
    """
    n = len(scale_in_levels)
    prices = np.zeros(n, dtype=np.float64)
    sizes = np.zeros(n, dtype=np.float64)

    for i in range(n):
        level = scale_in_levels[i]
        portion = scale_in_portions[i]

        if direction == 0:  # Long - enter on pullback
            if level >= 0:
                prices[i] = entry_price * (1 + level)  # Higher
            else:
                prices[i] = entry_price * (1 + level)  # Lower
        else:  # Short - enter on rally
            if level >= 0:
                prices[i] = entry_price * (1 + level)
            else:
                prices[i] = entry_price * (1 + level)

        sizes[i] = total_position_size * portion

    return prices, sizes


# =============================================================================
# POSITION STATE MANAGEMENT
# =============================================================================


@dataclass
class PositionEntry:
    """Single entry in a position (for pyramiding/DCA)."""

    entry_bar: int
    entry_price: float
    size: float
    direction: str  # "long" or "short"
    entry_type: str = "signal"  # "signal", "dca", "scale_in"
    is_filled: bool = False


@dataclass
class Position:
    """
    Active position with multiple possible entries (pyramiding/DCA).
    """

    direction: str  # "long" or "short"
    entries: list[PositionEntry] = field(default_factory=list)
    avg_entry_price: float = 0.0
    total_size: float = 0.0
    unrealized_pnl: float = 0.0
    max_favorable: float = 0.0  # MFE tracking
    max_adverse: float = 0.0  # MAE tracking

    # DCA state
    pending_dca_levels: list[tuple[float, float]] = field(
        default_factory=list
    )  # (price, size)
    dca_orders_filled: int = 0

    # Breakeven state
    breakeven_activated: bool = False
    breakeven_price: float = 0.0

    # Trailing stop state
    trailing_activated: bool = False
    trailing_stop_price: float = 0.0

    # TP tracking for multi-level
    tp_levels_hit: list[int] = field(default_factory=list)

    def add_entry(self, entry: PositionEntry):
        """Add an entry to the position."""
        self.entries.append(entry)
        self._recalculate_average()

    def _recalculate_average(self):
        """Recalculate average entry price and total size."""
        if not self.entries:
            self.avg_entry_price = 0.0
            self.total_size = 0.0
            return

        total_value = 0.0
        total_size = 0.0
        for entry in self.entries:
            if entry.is_filled:
                total_value += entry.entry_price * entry.size
                total_size += entry.size

        self.total_size = total_size
        if total_size > 0:
            self.avg_entry_price = total_value / total_size
        else:
            self.avg_entry_price = 0.0

    def update_pnl(self, current_price: float):
        """Update unrealized PnL and MFE/MAE."""
        if self.total_size <= 0:
            return

        if self.direction == "long":
            pnl_pct = (current_price - self.avg_entry_price) / self.avg_entry_price
        else:
            pnl_pct = (self.avg_entry_price - current_price) / self.avg_entry_price

        self.unrealized_pnl = pnl_pct * self.total_size * self.avg_entry_price

        # Update MFE/MAE
        if pnl_pct > self.max_favorable:
            self.max_favorable = pnl_pct
        if pnl_pct < self.max_adverse:
            self.max_adverse = pnl_pct


@dataclass
class PositionConfig:
    """Configuration for position management."""

    # Basic sizing
    position_sizing_mode: str = "fixed"  # "fixed", "risk", "kelly", "volatility"
    position_size: float = 0.10  # 10% default
    leverage: int = 10

    # Risk-based sizing
    risk_per_trade: float = 0.01
    stop_loss: float = 0.02

    # Kelly sizing
    kelly_fraction: float = 0.5
    historical_win_rate: float = 0.5
    historical_avg_win: float = 0.02
    historical_avg_loss: float = 0.01

    # Volatility sizing
    volatility_target: float = 0.02
    atr_period: int = 14

    # Size limits
    min_position_size: float = 0.01
    max_position_size: float = 1.0

    # DCA
    dca_enabled: bool = False
    dca_safety_orders: int = 0
    dca_price_deviation: float = 0.01
    dca_step_scale: float = 1.4
    dca_volume_scale: float = 1.0
    dca_base_order_size: float = 0.1
    dca_safety_order_size: float = 0.1

    # Scale-in
    scale_in_enabled: bool = False
    scale_in_levels: tuple[float, ...] = (0.0,)
    scale_in_portions: tuple[float, ...] = (1.0,)

    # Pyramiding
    pyramiding: int = 1  # Max simultaneous positions

    # Fixed amount mode
    use_fixed_amount: bool = False
    fixed_amount: float = 0.0


class UniversalPositionManager:
    """
    Universal position manager for all sizing and entry modes.

    Modes:
    - Fixed: Fixed % of capital
    - Risk: Based on risk per trade
    - Kelly: Kelly Criterion
    - Volatility: Inverse volatility

    Features:
    - DCA (Dollar Cost Averaging)
    - Scale-in (partial entry)
    - Pyramiding (multiple positions)
    """

    def __init__(self, config: PositionConfig):
        self.config = config
        self.active_positions: list[Position] = []
        self._atr_values: np.ndarray | None = None

    def calculate_position_size(
        self, capital: float, price: float, direction: str, atr_value: float = 0.0
    ) -> float:
        """
        Calculate position size based on configured mode.

        Args:
            capital: Available capital
            price: Entry price
            direction: "long" or "short"
            atr_value: Current ATR (for volatility mode)

        Returns:
            Position size in base currency
        """
        cfg = self.config

        if cfg.use_fixed_amount and cfg.fixed_amount > 0:
            # TradingView-style fixed amount
            return (cfg.fixed_amount * cfg.leverage) / price

        if cfg.position_sizing_mode == "fixed":
            return calculate_fixed_position_size(
                capital, cfg.position_size, cfg.leverage, price
            )

        elif cfg.position_sizing_mode == "risk":
            return calculate_risk_based_size(
                capital, cfg.risk_per_trade, cfg.stop_loss, cfg.leverage, price
            )

        elif cfg.position_sizing_mode == "kelly":
            return calculate_kelly_size(
                capital,
                cfg.historical_win_rate,
                cfg.historical_avg_win,
                cfg.historical_avg_loss,
                cfg.kelly_fraction,
                cfg.leverage,
                price,
                cfg.max_position_size,
            )

        elif cfg.position_sizing_mode == "volatility":
            if atr_value <= 0:
                return calculate_fixed_position_size(
                    capital, cfg.position_size, cfg.leverage, price
                )
            # Use average ATR as baseline
            avg_atr = atr_value  # Should be from historical calculation
            return calculate_volatility_size(
                capital,
                atr_value,
                avg_atr,
                cfg.volatility_target,
                cfg.leverage,
                price,
                cfg.min_position_size,
                cfg.max_position_size,
            )

        else:
            # Default to fixed
            return calculate_fixed_position_size(
                capital, cfg.position_size, cfg.leverage, price
            )

    def can_open_position(self, direction: str) -> bool:
        """
        Check if new position can be opened (pyramiding limit).

        Args:
            direction: "long" or "short"

        Returns:
            True if position can be opened
        """
        same_direction = sum(
            1
            for p in self.active_positions
            if p.direction == direction and p.total_size > 0
        )
        return same_direction < self.config.pyramiding

    def open_position(
        self,
        bar_index: int,
        price: float,
        direction: str,
        capital: float,
        atr_value: float = 0.0,
    ) -> Position | None:
        """
        Open a new position with optional DCA/scale-in setup.

        Args:
            bar_index: Current bar index
            price: Entry price
            direction: "long" or "short"
            capital: Available capital
            atr_value: Current ATR

        Returns:
            Position object if opened, None otherwise
        """
        if not self.can_open_position(direction):
            return None

        cfg = self.config
        position = Position(direction=direction)

        # Calculate base position size
        base_size = self.calculate_position_size(capital, price, direction, atr_value)

        if cfg.dca_enabled and cfg.dca_safety_orders > 0:
            # DCA mode: smaller base order, setup safety orders
            dir_int = 0 if direction == "long" else 1
            prices, sizes = calculate_dca_levels(
                price,
                dir_int,
                cfg.dca_safety_orders,
                cfg.dca_price_deviation,
                cfg.dca_step_scale,
                cfg.dca_volume_scale,
                cfg.dca_base_order_size,
                cfg.dca_safety_order_size,
                capital,
                cfg.leverage,
            )

            # Fill base order immediately
            base_entry = PositionEntry(
                entry_bar=bar_index,
                entry_price=price,
                size=sizes[0],
                direction=direction,
                entry_type="signal",
                is_filled=True,
            )
            position.add_entry(base_entry)

            # Setup pending DCA levels
            for i in range(1, len(prices)):
                position.pending_dca_levels.append((prices[i], sizes[i]))

        elif cfg.scale_in_enabled and len(cfg.scale_in_levels) > 1:
            # Scale-in mode: partial entries
            dir_int = 0 if direction == "long" else 1
            levels = np.array(cfg.scale_in_levels, dtype=np.float64)
            portions = np.array(cfg.scale_in_portions, dtype=np.float64)

            prices, sizes = calculate_scale_in_levels(
                price, dir_int, levels, portions, base_size, price
            )

            # Fill first level immediately (usually at entry price)
            first_entry = PositionEntry(
                entry_bar=bar_index,
                entry_price=prices[0],
                size=sizes[0],
                direction=direction,
                entry_type="scale_in",
                is_filled=True,
            )
            position.add_entry(first_entry)

            # Setup remaining scale-in levels as pending DCA
            for i in range(1, len(prices)):
                position.pending_dca_levels.append((prices[i], sizes[i]))

        else:
            # Simple mode: single entry
            entry = PositionEntry(
                entry_bar=bar_index,
                entry_price=price,
                size=base_size,
                direction=direction,
                entry_type="signal",
                is_filled=True,
            )
            position.add_entry(entry)

        self.active_positions.append(position)
        return position

    def check_dca_fills(
        self, position: Position, low: float, high: float, bar_index: int
    ) -> list[PositionEntry]:
        """
        Check and fill DCA orders based on price action.

        Args:
            position: Active position
            low: Bar low price
            high: Bar high price
            bar_index: Current bar index

        Returns:
            List of filled DCA entries
        """
        filled = []
        remaining_levels = []

        for level_price, level_size in position.pending_dca_levels:
            if position.direction == "long":
                # Long DCA: fill when price drops to level
                if low <= level_price:
                    entry = PositionEntry(
                        entry_bar=bar_index,
                        entry_price=level_price,
                        size=level_size,
                        direction=position.direction,
                        entry_type="dca",
                        is_filled=True,
                    )
                    position.add_entry(entry)
                    position.dca_orders_filled += 1
                    filled.append(entry)
                else:
                    remaining_levels.append((level_price, level_size))
            else:
                # Short DCA: fill when price rises to level
                if high >= level_price:
                    entry = PositionEntry(
                        entry_bar=bar_index,
                        entry_price=level_price,
                        size=level_size,
                        direction=position.direction,
                        entry_type="dca",
                        is_filled=True,
                    )
                    position.add_entry(entry)
                    position.dca_orders_filled += 1
                    filled.append(entry)
                else:
                    remaining_levels.append((level_price, level_size))

        position.pending_dca_levels = remaining_levels
        return filled

    def close_position(self, position: Position) -> bool:
        """
        Close and remove a position.

        Args:
            position: Position to close

        Returns:
            True if closed successfully
        """
        if position in self.active_positions:
            self.active_positions.remove(position)
            return True
        return False

    def partial_close(self, position: Position, close_fraction: float) -> float:
        """
        Partially close a position.

        Args:
            position: Position to partially close
            close_fraction: Fraction to close (0-1)

        Returns:
            Size that was closed
        """
        close_size = position.total_size * close_fraction

        # Reduce all entries proportionally
        for entry in position.entries:
            if entry.is_filled:
                entry.size *= 1 - close_fraction

        position._recalculate_average()
        return close_size

    def reset(self):
        """Reset position manager state."""
        self.active_positions = []

    @staticmethod
    def from_backtest_input(input_data) -> "UniversalPositionManager":
        """
        Create PositionManager from BacktestInput.

        Args:
            input_data: BacktestInput instance

        Returns:
            Configured UniversalPositionManager
        """
        config = PositionConfig(
            position_sizing_mode=getattr(input_data, "position_sizing_mode", "fixed"),
            position_size=getattr(input_data, "position_size", 0.10),
            leverage=getattr(input_data, "leverage", 10),
            risk_per_trade=getattr(input_data, "risk_per_trade", 0.01),
            stop_loss=getattr(input_data, "stop_loss", 0.02),
            kelly_fraction=getattr(input_data, "kelly_fraction", 0.5),
            volatility_target=getattr(input_data, "volatility_target", 0.02),
            min_position_size=getattr(input_data, "min_position_size", 0.01),
            max_position_size=getattr(input_data, "max_position_size", 1.0),
            dca_enabled=getattr(input_data, "dca_enabled", False),
            dca_safety_orders=getattr(input_data, "dca_safety_orders", 0),
            dca_price_deviation=getattr(input_data, "dca_price_deviation", 0.01),
            dca_step_scale=getattr(input_data, "dca_step_scale", 1.4),
            dca_volume_scale=getattr(input_data, "dca_volume_scale", 1.0),
            dca_base_order_size=getattr(input_data, "dca_base_order_size", 0.1),
            dca_safety_order_size=getattr(input_data, "dca_safety_order_size", 0.1),
            scale_in_enabled=getattr(input_data, "scale_in_enabled", False),
            scale_in_levels=getattr(input_data, "scale_in_levels", (0.0,)),
            scale_in_portions=getattr(input_data, "scale_in_portions", (1.0,)),
            pyramiding=getattr(input_data, "pyramiding", 1),
            use_fixed_amount=getattr(input_data, "use_fixed_amount", False),
            fixed_amount=getattr(input_data, "fixed_amount", 0.0),
        )
        return UniversalPositionManager(config)
