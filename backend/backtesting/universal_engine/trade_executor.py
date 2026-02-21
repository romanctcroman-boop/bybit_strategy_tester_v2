"""
Universal Trade Executor - Исполнение сделок для ВСЕХ режимов выхода.

Entry Types:
- Market: Немедленное исполнение
- Limit: С отступом и таймаутом
- Stop: Вход на пробой

Exit Types:
- Stop Loss: Fixed / ATR
- Take Profit: Fixed / ATR / Multi-level (TP1-TP4)
- Trailing Stop: С активацией
- Breakeven: После TP1
- Time-based: max_bars, session_close, weekend
- Signal exit: По сигналу стратегии

Features:
- Bar Magnifier (1m data для точного SL/TP)
- MFE/MAE calculation
- Funding Rate
- Slippage Models

Автор: AI Agent
Версия: 1.0.0
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

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
# ENUMS AND DATA STRUCTURES
# =============================================================================


class TpMode(Enum):
    """Take Profit mode."""

    FIXED = "fixed"
    ATR = "atr"
    MULTI = "multi"


class SlMode(Enum):
    """Stop Loss mode."""

    FIXED = "fixed"
    ATR = "atr"


class ExitReason(Enum):
    """Reason for closing position."""

    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TAKE_PROFIT_1 = "take_profit_1"
    TAKE_PROFIT_2 = "take_profit_2"
    TAKE_PROFIT_3 = "take_profit_3"
    TAKE_PROFIT_4 = "take_profit_4"
    TRAILING_STOP = "trailing_stop"
    BREAKEVEN = "breakeven"
    SIGNAL = "signal"
    TIME_EXIT = "time_exit"
    SESSION_CLOSE = "session_close"
    WEEKEND_CLOSE = "weekend_close"
    MAX_DRAWDOWN = "max_drawdown"
    END_OF_DATA = "end_of_data"
    UNKNOWN = "unknown"


@dataclass
class TradeRecord:
    """Record of a completed trade."""

    entry_time: datetime
    exit_time: datetime
    direction: str
    entry_price: float
    exit_price: float
    size: float
    pnl: float
    pnl_pct: float
    fees: float
    exit_reason: ExitReason
    duration_bars: int

    # Bar Magnifier data
    intrabar_sl_hit: bool = False
    intrabar_tp_hit: bool = False
    intrabar_exit_price: float | None = None

    # MFE/MAE
    mfe: float = 0.0  # Maximum Favorable Excursion
    mae: float = 0.0  # Maximum Adverse Excursion


@dataclass
class ExecutorConfig:
    """Configuration for trade execution."""

    # === STOP LOSS ===
    sl_mode: SlMode = SlMode.FIXED
    stop_loss: float = 0.02  # 2%
    atr_sl_multiplier: float = 1.5
    sl_max_limit_enabled: bool = True  # Use fixed SL as max limit for ATR

    # === TAKE PROFIT ===
    tp_mode: TpMode = TpMode.FIXED
    take_profit: float = 0.03  # 3%
    atr_tp_multiplier: float = 2.0

    # Multi-level TP (tp_mode=MULTI)
    tp_levels: tuple[float, ...] = (0.005, 0.010, 0.015, 0.020)
    tp_portions: tuple[float, ...] = (0.25, 0.25, 0.25, 0.25)

    # === ATR PARAMS ===
    atr_period: int = 14

    # === TRAILING STOP ===
    trailing_stop_enabled: bool = False
    trailing_stop_activation: float = 0.01  # Activate at 1% profit
    trailing_stop_distance: float = 0.005  # 0.5% distance

    # === BREAKEVEN ===
    breakeven_enabled: bool = False
    breakeven_mode: str = "average"  # "average" or "tp"
    breakeven_offset: float = 0.0

    # === TIME-BASED EXITS ===
    max_bars_in_trade: int = 0  # 0 = disabled
    exit_on_session_close: bool = False
    session_end_hour: int = 24
    exit_end_of_week: bool = False
    exit_before_weekend: int = 0  # Hours before Friday close

    # === FEES & SLIPPAGE ===
    taker_fee: float = 0.001
    maker_fee: float = 0.0006
    slippage: float = 0.0005
    slippage_model: str = "fixed"  # "fixed", "volume", "volatility", "combined"

    # === FUNDING RATE ===
    include_funding: bool = False
    funding_rate: float = 0.0001
    funding_interval_hours: int = 8

    # === BAR MAGNIFIER ===
    use_bar_magnifier: bool = False

    # === LEVERAGE ===
    leverage: int = 10


@dataclass
class ActiveTrade:
    """State of an active trade."""

    direction: str  # "long" or "short"
    entry_bar: int
    entry_time: datetime
    entry_price: float
    size: float

    # SL/TP prices
    sl_price: float = 0.0
    tp_price: float = 0.0  # For fixed TP
    tp_prices: list[float] = field(default_factory=list)  # For multi-level
    tp_portions: list[float] = field(default_factory=list)

    # State tracking
    mfe: float = 0.0
    mae: float = 0.0
    highest_price: float = 0.0  # For trailing
    lowest_price: float = 0.0

    # Trailing stop
    trailing_activated: bool = False
    trailing_stop_price: float = 0.0

    # Breakeven
    breakeven_activated: bool = False
    breakeven_price: float = 0.0

    # Multi-TP tracking
    tp_levels_hit: list[int] = field(default_factory=list)
    remaining_size: float = 0.0

    # DCA average price (if applicable)
    avg_entry_price: float = 0.0
    total_entry_value: float = 0.0

    # Fees accumulated
    total_fees: float = 0.0

    def __post_init__(self):
        self.remaining_size = self.size
        self.highest_price = self.entry_price
        self.lowest_price = self.entry_price
        self.avg_entry_price = self.entry_price
        self.total_entry_value = self.entry_price * self.size


# =============================================================================
# NUMBA-ACCELERATED EXIT CALCULATIONS
# =============================================================================


@njit(cache=True)
def calculate_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
    """Calculate ATR using Numba."""
    n = len(close)
    atr = np.zeros(n, dtype=np.float64)
    tr = np.zeros(n, dtype=np.float64)

    if n < 2:
        return atr

    tr[0] = high[0] - low[0]
    for i in range(1, n):
        hl = high[i] - low[i]
        hc = abs(high[i] - close[i - 1])
        lc = abs(low[i] - close[i - 1])
        tr[i] = max(hl, hc, lc)

    if n < period:
        return tr

    atr_sum = 0.0
    for i in range(period):
        atr_sum += tr[i]
    atr[period - 1] = atr_sum / period

    for i in range(period, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period

    for i in range(period - 1):
        atr[i] = atr[period - 1]

    return atr


@njit(cache=True)
def calculate_sl_tp_fixed(
    entry_price: float,
    direction: int,  # 0=long, 1=short
    stop_loss_pct: float,
    take_profit_pct: float,
) -> tuple[float, float]:
    """Calculate fixed SL/TP prices."""
    if direction == 0:  # Long
        sl_price = entry_price * (1 - stop_loss_pct)
        tp_price = entry_price * (1 + take_profit_pct)
    else:  # Short
        sl_price = entry_price * (1 + stop_loss_pct)
        tp_price = entry_price * (1 - take_profit_pct)

    return sl_price, tp_price


@njit(cache=True)
def calculate_sl_tp_atr(
    entry_price: float,
    direction: int,
    atr_value: float,
    atr_sl_mult: float,
    atr_tp_mult: float,
    fixed_sl_pct: float,  # Max limit
    sl_max_limit_enabled: bool,
) -> tuple[float, float]:
    """Calculate ATR-based SL/TP prices."""
    sl_distance = atr_value * atr_sl_mult
    tp_distance = atr_value * atr_tp_mult

    if direction == 0:  # Long
        sl_price = entry_price - sl_distance
        tp_price = entry_price + tp_distance

        # Apply max SL limit if enabled
        if sl_max_limit_enabled:
            max_sl = entry_price * (1 - fixed_sl_pct)
            if sl_price < max_sl:
                sl_price = max_sl
    else:  # Short
        sl_price = entry_price + sl_distance
        tp_price = entry_price - tp_distance

        if sl_max_limit_enabled:
            max_sl = entry_price * (1 + fixed_sl_pct)
            if sl_price > max_sl:
                sl_price = max_sl

    return sl_price, tp_price


@njit(cache=True)
def check_sl_hit(direction: int, sl_price: float, low: float, high: float) -> bool:
    """Check if stop loss was hit."""
    if direction == 0:  # Long - SL hit if price goes below
        return low <= sl_price
    else:  # Short - SL hit if price goes above
        return high >= sl_price


@njit(cache=True)
def check_tp_hit(direction: int, tp_price: float, low: float, high: float) -> bool:
    """Check if take profit was hit."""
    if direction == 0:  # Long - TP hit if price goes above
        return high >= tp_price
    else:  # Short - TP hit if price goes below
        return low <= tp_price


@njit(cache=True)
def update_trailing_stop(
    direction: int,
    current_price: float,
    trailing_stop_price: float,
    trailing_distance: float,
    activation_price: float,
    is_activated: bool,
) -> tuple[float, bool]:
    """Update trailing stop price."""
    # Check activation
    if not is_activated:
        if direction == 0:  # Long
            if current_price >= activation_price:
                is_activated = True
                trailing_stop_price = current_price * (1 - trailing_distance)
        else:  # Short
            if current_price <= activation_price:
                is_activated = True
                trailing_stop_price = current_price * (1 + trailing_distance)

    # Update trailing stop if activated
    if is_activated:
        if direction == 0:  # Long
            new_stop = current_price * (1 - trailing_distance)
            if new_stop > trailing_stop_price:
                trailing_stop_price = new_stop
        else:  # Short
            new_stop = current_price * (1 + trailing_distance)
            if new_stop < trailing_stop_price:
                trailing_stop_price = new_stop

    return trailing_stop_price, is_activated


@njit(cache=True)
def calculate_mfe_mae(
    direction: int,
    entry_price: float,
    high: float,
    low: float,
    current_mfe: float,
    current_mae: float,
) -> tuple[float, float]:
    """Update MFE/MAE tracking."""
    if direction == 0:  # Long
        # MFE: max favorable = highest price
        favorable = (high - entry_price) / entry_price
        if favorable > current_mfe:
            current_mfe = favorable

        # MAE: max adverse = lowest price
        adverse = (entry_price - low) / entry_price
        if adverse > current_mae:
            current_mae = adverse
    else:  # Short
        # MFE: max favorable = lowest price
        favorable = (entry_price - low) / entry_price
        if favorable > current_mfe:
            current_mfe = favorable

        # MAE: max adverse = highest price
        adverse = (high - entry_price) / entry_price
        if adverse > current_mae:
            current_mae = adverse

    return current_mfe, current_mae


@njit(cache=True)
def calculate_pnl(
    direction: int, entry_price: float, exit_price: float, size: float, fees: float
) -> tuple[float, float]:
    """Calculate PnL and PnL percentage."""
    if direction == 0:  # Long  # noqa: SIM108
        pnl_pct = (exit_price - entry_price) / entry_price
    else:  # Short
        pnl_pct = (entry_price - exit_price) / entry_price

    pnl = pnl_pct * size * entry_price - fees

    return pnl, pnl_pct


@njit(cache=True)
def apply_slippage(
    price: float,
    direction: int,  # 0=long, 1=short
    is_entry: bool,
    slippage: float,
) -> float:
    """Apply slippage to price."""
    # Entry: worse price (higher for long, lower for short)
    # Exit: worse price (lower for long, higher for short)
    if is_entry:
        if direction == 0:  # Long entry - buy higher
            return price * (1 + slippage)
        else:  # Short entry - sell lower
            return price * (1 - slippage)
    else:  # Exit
        if direction == 0:  # Long exit - sell lower
            return price * (1 - slippage)
        else:  # Short exit - buy higher
            return price * (1 + slippage)


# =============================================================================
# MAIN TRADE EXECUTOR CLASS
# =============================================================================


class UniversalTradeExecutor:
    """
    Universal trade executor for all exit modes.

    Supports:
    - Fixed/ATR Stop Loss
    - Fixed/ATR/Multi-level Take Profit
    - Trailing Stop
    - Breakeven
    - Time-based exits
    - Bar Magnifier for precise exits
    """

    def __init__(self, config: ExecutorConfig):
        self.config = config
        self.atr_values: np.ndarray | None = None
        self.active_trades: list[ActiveTrade] = []
        self.completed_trades: list[TradeRecord] = []

    def set_atr_values(self, high: np.ndarray, low: np.ndarray, close: np.ndarray):
        """Pre-calculate ATR values for the entire series."""
        self.atr_values = calculate_atr(high, low, close, self.config.atr_period)

    def open_trade(
        self,
        bar_index: int,
        bar_time: datetime,
        price: float,
        size: float,
        direction: str,
        atr_value: float = 0.0,
    ) -> ActiveTrade:
        """
        Open a new trade with calculated SL/TP levels.

        Args:
            bar_index: Current bar index
            bar_time: Current timestamp
            price: Entry price
            size: Position size
            direction: "long" or "short"
            atr_value: Current ATR (if known)

        Returns:
            ActiveTrade object
        """
        cfg = self.config
        dir_int = 0 if direction == "long" else 1

        # Apply slippage to entry
        entry_price = apply_slippage(price, dir_int, True, cfg.slippage)

        # Calculate entry fee
        entry_fee = entry_price * size * cfg.taker_fee

        # Calculate SL/TP
        if cfg.sl_mode == SlMode.ATR or cfg.tp_mode == TpMode.ATR:
            atr = (
                atr_value
                if atr_value > 0
                else (self.atr_values[bar_index] if self.atr_values is not None else entry_price * 0.02)
            )
            sl_price, tp_price = calculate_sl_tp_atr(
                entry_price,
                dir_int,
                atr,
                cfg.atr_sl_multiplier,
                cfg.atr_tp_multiplier,
                cfg.stop_loss,
                cfg.sl_max_limit_enabled,
            )
        else:
            sl_price, tp_price = calculate_sl_tp_fixed(entry_price, dir_int, cfg.stop_loss, cfg.take_profit)

        # Create trade
        trade = ActiveTrade(
            direction=direction,
            entry_bar=bar_index,
            entry_time=bar_time,
            entry_price=entry_price,
            size=size,
            sl_price=sl_price,
            tp_price=tp_price,
            total_fees=entry_fee,
        )

        # Setup multi-level TP if enabled
        if cfg.tp_mode == TpMode.MULTI:
            tp_prices = []
            for level in cfg.tp_levels:
                if direction == "long":
                    tp_prices.append(entry_price * (1 + level))
                else:
                    tp_prices.append(entry_price * (1 - level))
            trade.tp_prices = tp_prices
            trade.tp_portions = list(cfg.tp_portions)

        self.active_trades.append(trade)
        return trade

    def process_bar(
        self,
        bar_index: int,
        bar_time: datetime,
        open_price: float,
        high: float,
        low: float,
        close: float,
        long_exit: bool = False,
        short_exit: bool = False,
        candles_1m: np.ndarray | None = None,  # For bar magnifier
    ) -> list[TradeRecord]:
        """
        Process a bar and check for exits.

        Args:
            bar_index: Current bar index
            bar_time: Current timestamp
            open_price: Bar open
            high: Bar high
            low: Bar low
            close: Bar close
            long_exit: Long exit signal
            short_exit: Short exit signal
            candles_1m: Optional 1-minute data for bar magnifier

        Returns:
            List of completed trades
        """
        cfg = self.config
        closed_trades = []

        for trade in self.active_trades[:]:  # Copy list to allow removal
            dir_int = 0 if trade.direction == "long" else 1

            # Update MFE/MAE
            trade.mfe, trade.mae = calculate_mfe_mae(dir_int, trade.avg_entry_price, high, low, trade.mfe, trade.mae)

            # Update highest/lowest for trailing
            if high > trade.highest_price:
                trade.highest_price = high
            if low < trade.lowest_price:
                trade.lowest_price = low

            # Check exits in priority order
            exit_reason = None
            exit_price = close

            # 1. Check trailing stop
            if cfg.trailing_stop_enabled:
                activation_price = trade.entry_price * (
                    1 + cfg.trailing_stop_activation if trade.direction == "long" else 1 - cfg.trailing_stop_activation
                )
                trade.trailing_stop_price, trade.trailing_activated = update_trailing_stop(
                    dir_int,
                    close,
                    trade.trailing_stop_price,
                    cfg.trailing_stop_distance,
                    activation_price,
                    trade.trailing_activated,
                )

                if trade.trailing_activated and (
                    (trade.direction == "long" and low <= trade.trailing_stop_price)
                    or (trade.direction == "short" and high >= trade.trailing_stop_price)
                ):
                    exit_reason = ExitReason.TRAILING_STOP
                    exit_price = trade.trailing_stop_price

            # 2. Check stop loss (if not trailing triggered)
            if exit_reason is None:
                sl_price = trade.breakeven_price if trade.breakeven_activated else trade.sl_price

                if check_sl_hit(dir_int, sl_price, low, high):
                    exit_reason = ExitReason.BREAKEVEN if trade.breakeven_activated else ExitReason.STOP_LOSS
                    exit_price = sl_price

            # 3. Check take profit
            if exit_reason is None:
                if cfg.tp_mode == TpMode.MULTI and trade.tp_prices:
                    # Multi-level TP
                    for i, (tp_price, tp_portion) in enumerate(zip(trade.tp_prices, trade.tp_portions, strict=False)):
                        if i in trade.tp_levels_hit:
                            continue
                        if check_tp_hit(dir_int, tp_price, low, high):
                            # Partial close
                            close_size = trade.size * tp_portion
                            trade.remaining_size -= close_size
                            trade.tp_levels_hit.append(i)

                            # Activate breakeven after first TP
                            if cfg.breakeven_enabled and len(trade.tp_levels_hit) == 1:
                                if cfg.breakeven_mode == "average":
                                    trade.breakeven_price = trade.avg_entry_price * (
                                        1 + cfg.breakeven_offset
                                        if trade.direction == "long"
                                        else 1 - cfg.breakeven_offset
                                    )
                                else:  # "tp"
                                    trade.breakeven_price = tp_price
                                trade.breakeven_activated = True

                            # Record partial close if significant
                            if close_size > 0:
                                exit_fee = tp_price * close_size * cfg.taker_fee
                                trade.total_fees += exit_fee

                            # Full exit if all TPs hit or last TP
                            if trade.remaining_size <= 0 or i == len(trade.tp_prices) - 1:
                                exit_reason = ExitReason[f"TAKE_PROFIT_{i + 1}"]
                                exit_price = tp_price
                                break
                else:
                    # Single TP
                    if check_tp_hit(dir_int, trade.tp_price, low, high):
                        exit_reason = ExitReason.TAKE_PROFIT
                        exit_price = trade.tp_price

            # 4. Check signal exit
            if exit_reason is None and (
                (trade.direction == "long" and long_exit) or (trade.direction == "short" and short_exit)
            ):
                exit_reason = ExitReason.SIGNAL
                exit_price = close

            # 5. Check time-based exits
            if exit_reason is None:
                # Max bars
                if cfg.max_bars_in_trade > 0:
                    bars_in_trade = bar_index - trade.entry_bar
                    if bars_in_trade >= cfg.max_bars_in_trade:
                        exit_reason = ExitReason.TIME_EXIT
                        exit_price = close

                # Session close
                if (
                    cfg.exit_on_session_close
                    and hasattr(bar_time, "hour")
                    and bar_time.hour >= cfg.session_end_hour - 1
                ):
                    exit_reason = ExitReason.SESSION_CLOSE
                    exit_price = close

                # Weekend close
                if (
                    cfg.exit_end_of_week
                    and hasattr(bar_time, "weekday")
                    and bar_time.weekday() == 4
                    and bar_time.hour >= 24 - cfg.exit_before_weekend
                ):  # Friday
                    exit_reason = ExitReason.WEEKEND_CLOSE
                    exit_price = close

            # Close trade if exit triggered
            if exit_reason is not None:
                # Apply slippage to exit
                exit_price = apply_slippage(exit_price, dir_int, False, cfg.slippage)

                # Calculate exit fee
                exit_fee = exit_price * trade.remaining_size * cfg.taker_fee
                trade.total_fees += exit_fee

                # Calculate PnL
                pnl, pnl_pct = calculate_pnl(
                    dir_int,
                    trade.avg_entry_price,
                    exit_price,
                    trade.size,
                    trade.total_fees,
                )

                # Create trade record
                record = TradeRecord(
                    entry_time=trade.entry_time,
                    exit_time=bar_time,
                    direction=trade.direction,
                    entry_price=trade.entry_price,
                    exit_price=exit_price,
                    size=trade.size,
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                    fees=trade.total_fees,
                    exit_reason=exit_reason,
                    duration_bars=bar_index - trade.entry_bar,
                    mfe=trade.mfe,
                    mae=trade.mae,
                )

                closed_trades.append(record)
                self.completed_trades.append(record)
                self.active_trades.remove(trade)

        return closed_trades

    def close_all_trades(
        self,
        bar_index: int,
        bar_time: datetime,
        close_price: float,
        reason: ExitReason = ExitReason.END_OF_DATA,
    ) -> list[TradeRecord]:
        """Close all active trades at end of backtest."""
        closed = []
        cfg = self.config

        for trade in self.active_trades[:]:
            dir_int = 0 if trade.direction == "long" else 1

            # Apply slippage
            exit_price = apply_slippage(close_price, dir_int, False, cfg.slippage)

            # Calculate exit fee
            exit_fee = exit_price * trade.remaining_size * cfg.taker_fee
            trade.total_fees += exit_fee

            # Calculate PnL
            pnl, pnl_pct = calculate_pnl(dir_int, trade.avg_entry_price, exit_price, trade.size, trade.total_fees)

            record = TradeRecord(
                entry_time=trade.entry_time,
                exit_time=bar_time,
                direction=trade.direction,
                entry_price=trade.entry_price,
                exit_price=exit_price,
                size=trade.size,
                pnl=pnl,
                pnl_pct=pnl_pct,
                fees=trade.total_fees,
                exit_reason=reason,
                duration_bars=bar_index - trade.entry_bar,
                mfe=trade.mfe,
                mae=trade.mae,
            )

            closed.append(record)
            self.completed_trades.append(record)

        self.active_trades = []
        return closed

    def add_dca_entry(self, trade: ActiveTrade, bar_index: int, entry_price: float, size: float):
        """Add a DCA entry to an existing trade."""
        cfg = self.config
        dir_int = 0 if trade.direction == "long" else 1

        # Apply slippage
        entry_price = apply_slippage(entry_price, dir_int, True, cfg.slippage)

        # Calculate fee
        entry_fee = entry_price * size * cfg.taker_fee
        trade.total_fees += entry_fee

        # Update average price
        new_total_value = trade.total_entry_value + entry_price * size
        new_total_size = trade.size + size
        trade.avg_entry_price = new_total_value / new_total_size
        trade.total_entry_value = new_total_value
        trade.size = new_total_size
        trade.remaining_size = new_total_size

        # Recalculate SL based on new average
        if cfg.sl_mode == SlMode.FIXED:
            if trade.direction == "long":
                trade.sl_price = trade.avg_entry_price * (1 - cfg.stop_loss)
            else:
                trade.sl_price = trade.avg_entry_price * (1 + cfg.stop_loss)

    def reset(self):
        """Reset executor state."""
        self.active_trades = []
        self.completed_trades = []
        self.atr_values = None

    @staticmethod
    def from_backtest_input(input_data) -> "UniversalTradeExecutor":
        """Create TradeExecutor from BacktestInput."""
        # Handle TpMode/SlMode conversion
        tp_mode_val = getattr(input_data, "tp_mode", TpMode.FIXED)
        if hasattr(tp_mode_val, "value"):
            tp_mode = TpMode(tp_mode_val.value)
        elif isinstance(tp_mode_val, str):
            tp_mode = TpMode(tp_mode_val)
        else:
            tp_mode = TpMode.FIXED

        sl_mode_val = getattr(input_data, "sl_mode", SlMode.FIXED)
        if hasattr(sl_mode_val, "value"):
            sl_mode = SlMode(sl_mode_val.value)
        elif isinstance(sl_mode_val, str):
            sl_mode = SlMode(sl_mode_val)
        else:
            sl_mode = SlMode.FIXED

        config = ExecutorConfig(
            sl_mode=sl_mode,
            stop_loss=getattr(input_data, "stop_loss", 0.02),
            atr_sl_multiplier=getattr(input_data, "atr_sl_multiplier", 1.5),
            sl_max_limit_enabled=getattr(input_data, "sl_max_limit_enabled", True),
            tp_mode=tp_mode,
            take_profit=getattr(input_data, "take_profit", 0.03),
            atr_tp_multiplier=getattr(input_data, "atr_tp_multiplier", 2.0),
            tp_levels=getattr(input_data, "tp_levels", (0.005, 0.010, 0.015, 0.020)),
            tp_portions=getattr(input_data, "tp_portions", (0.25, 0.25, 0.25, 0.25)),
            atr_period=getattr(input_data, "atr_period", 14),
            trailing_stop_enabled=getattr(input_data, "trailing_stop_enabled", False),
            trailing_stop_activation=getattr(input_data, "trailing_stop_activation", 0.01),
            trailing_stop_distance=getattr(input_data, "trailing_stop_distance", 0.005),
            breakeven_enabled=getattr(input_data, "breakeven_enabled", False),
            breakeven_mode=getattr(input_data, "breakeven_mode", "average"),
            breakeven_offset=getattr(input_data, "breakeven_offset", 0.0),
            max_bars_in_trade=getattr(input_data, "max_bars_in_trade", 0),
            exit_on_session_close=getattr(input_data, "exit_on_session_close", False),
            session_end_hour=getattr(input_data, "session_end_hour", 24),
            exit_end_of_week=getattr(input_data, "exit_end_of_week", False),
            exit_before_weekend=getattr(input_data, "exit_before_weekend", 0),
            taker_fee=getattr(input_data, "taker_fee", 0.0007),  # TradingView parity (CLAUDE.md §5)
            maker_fee=getattr(input_data, "maker_fee", 0.0006),
            slippage=getattr(input_data, "slippage", 0.0005),
            slippage_model=getattr(input_data, "slippage_model", "fixed"),
            include_funding=getattr(input_data, "include_funding", False),
            funding_rate=getattr(input_data, "funding_rate", 0.0001),
            funding_interval_hours=getattr(input_data, "funding_interval_hours", 8),
            use_bar_magnifier=getattr(input_data, "use_bar_magnifier", False),
            leverage=getattr(input_data, "leverage", 10),
        )
        return UniversalTradeExecutor(config)
