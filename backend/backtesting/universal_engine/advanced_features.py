"""
Advanced Features для Universal Math Engine.

Включает:
1. Scale-in / Pyramiding - добавление к позиции
2. Partial Close - частичное закрытие (Multi-TP)
3. Time-based Exit - выход по времени
4. Slippage Models - модели проскальзывания
5. Funding Rate - учёт фандинга
6. Hedge Mode - одновременно Long + Short

Автор: AI Agent
Версия: 1.0.0
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np
from numba import njit

try:
    from numba import prange

    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    prange = range

    def njit(*args, **kwargs):
        def decorator(func):
            return func

        if len(args) == 1 and callable(args[0]):
            return args[0]
        return decorator


# =============================================================================
# ENUMS
# =============================================================================


class ScaleInMode(Enum):
    """Режимы Scale-in."""

    NONE = "none"
    FIXED_LEVELS = "fixed_levels"  # Фиксированные уровни (+1%, +2%, +3%)
    ATR_BASED = "atr_based"  # На основе ATR
    PRICE_ACTION = "price_action"  # По паттернам


class SlippageModel(Enum):
    """Модели проскальзывания."""

    NONE = "none"
    FIXED = "fixed"  # Фиксированное значение
    PERCENTAGE = "percentage"  # Процент от цены
    VOLUME_BASED = "volume_based"  # На основе объёма
    VOLATILITY_BASED = "volatility_based"  # На основе волатильности


class TimeExitMode(Enum):
    """Режимы выхода по времени."""

    NONE = "none"
    MAX_BARS = "max_bars"  # Максимум баров в сделке
    SESSION_CLOSE = "session_close"  # Закрытие в конце сессии
    WEEKEND_CLOSE = "weekend_close"  # Закрытие перед выходными
    SPECIFIC_TIME = "specific_time"  # Конкретное время


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class ScaleInConfig:
    """Конфигурация Scale-in/Pyramiding."""

    enabled: bool = False
    mode: ScaleInMode = ScaleInMode.FIXED_LEVELS
    max_additions: int = 3  # Максимум добавлений

    # Fixed levels mode
    profit_levels: List[float] = field(default_factory=lambda: [0.01, 0.02, 0.03])
    size_multipliers: List[float] = field(default_factory=lambda: [0.5, 0.3, 0.2])

    # ATR-based mode
    atr_multiplier: float = 1.0

    # Risk management
    max_position_size: float = 1.0  # Максимальный размер позиции
    move_sl_to_breakeven: bool = (
        True  # Переносить SL в безубыток после первого scale-in
    )


@dataclass
class PartialCloseConfig:
    """Конфигурация частичного закрытия (Multi-TP)."""

    enabled: bool = False

    # Уровни TP и размеры закрытия
    tp_levels: List[float] = field(default_factory=lambda: [0.01, 0.02, 0.03])
    close_percentages: List[float] = field(default_factory=lambda: [0.25, 0.50, 0.25])

    # Trailing после первого TP
    enable_trailing_after_tp1: bool = True
    trailing_distance: float = 0.005


@dataclass
class TimeExitConfig:
    """Конфигурация выхода по времени."""

    enabled: bool = False
    mode: TimeExitMode = TimeExitMode.MAX_BARS

    # Max bars mode
    max_bars_in_trade: int = 100

    # Session close
    session_end_hour: int = 23
    session_end_minute: int = 0

    # Weekend close
    friday_close_hour: int = 22

    # Force close if in loss after N bars
    force_close_after_bars: Optional[int] = None
    force_close_only_if_profit: bool = False


@dataclass
class SlippageConfig:
    """Конфигурация проскальзывания."""

    model: SlippageModel = SlippageModel.FIXED

    # Fixed model
    fixed_slippage: float = 0.0001  # 0.01%

    # Percentage model
    percentage: float = 0.0005  # 0.05%

    # Volume-based model
    volume_impact: float = 0.00001  # Impact per volume unit
    min_slippage: float = 0.0001
    max_slippage: float = 0.005

    # Volatility-based
    volatility_multiplier: float = 0.5


@dataclass
class FundingConfig:
    """Конфигурация Funding Rate."""

    enabled: bool = False

    # Funding параметры
    funding_rate: float = 0.0001  # 0.01% каждые 8 часов
    funding_interval_hours: int = 8

    # Применять funding
    apply_to_longs: bool = True
    apply_to_shorts: bool = True


@dataclass
class HedgeConfig:
    """Конфигурация Hedge Mode."""

    enabled: bool = False

    # Режим хеджирования
    allow_simultaneous: bool = True  # Long + Short одновременно
    max_long_size: float = 1.0
    max_short_size: float = 1.0

    # Корреляция между позициями
    auto_close_on_profit: bool = False
    profit_threshold: float = 0.01


# =============================================================================
# NUMBA-ACCELERATED FUNCTIONS
# =============================================================================


@njit(cache=True)
def calculate_scale_in_levels(
    entry_price: float,
    direction: int,  # 1 = long, -1 = short
    profit_levels: np.ndarray,
) -> np.ndarray:
    """
    Рассчитать ценовые уровни для Scale-in.

    Args:
        entry_price: Цена входа
        direction: 1 для long, -1 для short
        profit_levels: Массив уровней профита (например [0.01, 0.02, 0.03])

    Returns:
        Массив ценовых уровней для scale-in
    """
    n = len(profit_levels)
    levels = np.zeros(n, dtype=np.float64)

    for i in range(n):
        if direction == 1:  # Long
            levels[i] = entry_price * (1 + profit_levels[i])
        else:  # Short
            levels[i] = entry_price * (1 - profit_levels[i])

    return levels


@njit(cache=True)
def calculate_partial_close_levels(
    entry_price: float,
    direction: int,
    tp_levels: np.ndarray,
) -> np.ndarray:
    """
    Рассчитать уровни для частичного закрытия.
    """
    n = len(tp_levels)
    levels = np.zeros(n, dtype=np.float64)

    for i in range(n):
        if direction == 1:  # Long
            levels[i] = entry_price * (1 + tp_levels[i])
        else:  # Short
            levels[i] = entry_price * (1 - tp_levels[i])

    return levels


@njit(cache=True)
def calculate_slippage_fixed(
    price: float,
    fixed_slippage: float,
    is_buy: bool,
) -> float:
    """Рассчитать проскальзывание (fixed model)."""
    if is_buy:
        return price * (1 + fixed_slippage)
    else:
        return price * (1 - fixed_slippage)


@njit(cache=True)
def calculate_slippage_volume_based(
    price: float,
    volume: float,
    avg_volume: float,
    volume_impact: float,
    min_slippage: float,
    max_slippage: float,
    is_buy: bool,
) -> float:
    """Рассчитать проскальзывание на основе объёма."""
    # Если объём выше среднего - больше проскальзывание
    volume_ratio = volume / avg_volume if avg_volume > 0 else 1.0
    slippage = volume_impact * volume_ratio

    # Clamp
    slippage = max(min_slippage, min(max_slippage, slippage))

    if is_buy:
        return price * (1 + slippage)
    else:
        return price * (1 - slippage)


@njit(cache=True)
def calculate_slippage_volatility_based(
    price: float,
    atr: float,
    volatility_multiplier: float,
    is_buy: bool,
) -> float:
    """Рассчитать проскальзывание на основе волатильности."""
    slippage_pct = (atr / price) * volatility_multiplier

    if is_buy:
        return price * (1 + slippage_pct)
    else:
        return price * (1 - slippage_pct)


@njit(cache=True)
def calculate_funding_cost(
    position_value: float,
    funding_rate: float,
    hours_held: float,
    funding_interval_hours: int,
    is_long: bool,
) -> float:
    """
    Рассчитать стоимость фандинга.

    Для long: платим если funding_rate > 0
    Для short: получаем если funding_rate > 0
    """
    # Количество интервалов фандинга
    n_intervals = int(hours_held / funding_interval_hours)

    if n_intervals <= 0:
        return 0.0

    # Для long: платим funding, для short: получаем
    if is_long:
        return -position_value * funding_rate * n_intervals
    else:
        return position_value * funding_rate * n_intervals


@njit(cache=True)
def check_time_exit(
    bar_index: int,
    entry_bar: int,
    max_bars: int,
    current_hour: int,
    session_end_hour: int,
    day_of_week: int,  # 0=Monday, 4=Friday
    friday_close_hour: int,
    time_exit_mode: int,  # 0=none, 1=max_bars, 2=session, 3=weekend
) -> bool:
    """
    Проверить условия выхода по времени.

    Returns:
        True если нужно закрыть позицию
    """
    if time_exit_mode == 0:  # None
        return False

    if time_exit_mode == 1:  # Max bars
        bars_in_trade = bar_index - entry_bar
        return bars_in_trade >= max_bars

    if time_exit_mode == 2:  # Session close
        return current_hour >= session_end_hour

    if time_exit_mode == 3:  # Weekend close
        return day_of_week == 4 and current_hour >= friday_close_hour

    return False


@njit(cache=True)
def simulate_scale_in_trade(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    entry_bar: int,
    entry_price: float,
    direction: int,
    initial_size: float,
    stop_loss: float,
    take_profit: float,
    scale_in_levels: np.ndarray,
    scale_in_sizes: np.ndarray,
    max_additions: int,
) -> Tuple[int, float, float, int]:
    """
    Симулировать сделку с Scale-in.

    Returns:
        (exit_bar, exit_price, total_pnl, n_additions)
    """
    n = len(close)

    current_size = initial_size
    avg_entry_price = entry_price
    total_cost = initial_size * entry_price
    additions_made = 0

    # SL/TP prices
    if direction == 1:  # Long
        sl_price = entry_price * (1 - stop_loss)
        tp_price = entry_price * (1 + take_profit)
    else:  # Short
        sl_price = entry_price * (1 + stop_loss)
        tp_price = entry_price * (1 - take_profit)

    for i in range(entry_bar + 1, n):
        # Check scale-in levels
        if additions_made < max_additions and additions_made < len(scale_in_levels):
            level = scale_in_levels[additions_made]

            if direction == 1:  # Long - price goes up
                if high[i] >= level:
                    # Add to position
                    add_size = scale_in_sizes[additions_made]
                    add_price = level

                    total_cost += add_size * add_price
                    current_size += add_size
                    avg_entry_price = total_cost / current_size
                    additions_made += 1

                    # Move SL to breakeven
                    sl_price = avg_entry_price * 0.999  # Small buffer
            else:  # Short - price goes down
                if low[i] <= level:
                    add_size = scale_in_sizes[additions_made]
                    add_price = level

                    total_cost += add_size * add_price
                    current_size += add_size
                    avg_entry_price = total_cost / current_size
                    additions_made += 1

                    sl_price = avg_entry_price * 1.001

        # Check SL/TP
        if direction == 1:  # Long
            if low[i] <= sl_price:
                # Hit SL
                pnl = (sl_price - avg_entry_price) * current_size
                return i, sl_price, pnl, additions_made

            if high[i] >= tp_price:
                # Hit TP
                pnl = (tp_price - avg_entry_price) * current_size
                return i, tp_price, pnl, additions_made
        else:  # Short
            if high[i] >= sl_price:
                pnl = (avg_entry_price - sl_price) * current_size
                return i, sl_price, pnl, additions_made

            if low[i] <= tp_price:
                pnl = (avg_entry_price - tp_price) * current_size
                return i, tp_price, pnl, additions_made

    # Exit at last bar
    exit_price = close[n - 1]
    if direction == 1:
        pnl = (exit_price - avg_entry_price) * current_size
    else:
        pnl = (avg_entry_price - exit_price) * current_size

    return n - 1, exit_price, pnl, additions_made


@njit(cache=True)
def simulate_partial_close_trade(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    entry_bar: int,
    entry_price: float,
    direction: int,
    initial_size: float,
    stop_loss: float,
    tp_levels: np.ndarray,
    close_percentages: np.ndarray,
) -> Tuple[int, float, float, int]:
    """
    Симулировать сделку с частичным закрытием.

    Returns:
        (exit_bar, avg_exit_price, total_pnl, n_partial_closes)
    """
    n = len(close)

    remaining_size = initial_size
    total_pnl = 0.0
    partial_closes = 0

    # Calculate TP price levels
    n_levels = len(tp_levels)
    tp_prices = np.zeros(n_levels, dtype=np.float64)

    for j in range(n_levels):
        if direction == 1:
            tp_prices[j] = entry_price * (1 + tp_levels[j])
        else:
            tp_prices[j] = entry_price * (1 - tp_levels[j])

    # SL price
    if direction == 1:
        sl_price = entry_price * (1 - stop_loss)
    else:
        sl_price = entry_price * (1 + stop_loss)

    level_hit = np.zeros(n_levels, dtype=np.bool_)

    for i in range(entry_bar + 1, n):
        # Check partial close levels
        for j in range(n_levels):
            if level_hit[j]:
                continue

            if direction == 1:  # Long
                if high[i] >= tp_prices[j]:
                    # Partial close
                    close_size = initial_size * close_percentages[j]
                    close_size = min(close_size, remaining_size)

                    pnl = (tp_prices[j] - entry_price) * close_size
                    total_pnl += pnl
                    remaining_size -= close_size
                    level_hit[j] = True
                    partial_closes += 1

                    # Move SL to breakeven after first TP
                    if partial_closes == 1:
                        sl_price = entry_price * 1.001
            else:  # Short
                if low[i] <= tp_prices[j]:
                    close_size = initial_size * close_percentages[j]
                    close_size = min(close_size, remaining_size)

                    pnl = (entry_price - tp_prices[j]) * close_size
                    total_pnl += pnl
                    remaining_size -= close_size
                    level_hit[j] = True
                    partial_closes += 1

                    if partial_closes == 1:
                        sl_price = entry_price * 0.999

        # All closed?
        if remaining_size <= 0.0001:
            return i, tp_prices[n_levels - 1], total_pnl, partial_closes

        # Check SL for remaining
        if direction == 1:
            if low[i] <= sl_price:
                pnl = (sl_price - entry_price) * remaining_size
                total_pnl += pnl
                return i, sl_price, total_pnl, partial_closes
        else:
            if high[i] >= sl_price:
                pnl = (entry_price - sl_price) * remaining_size
                total_pnl += pnl
                return i, sl_price, total_pnl, partial_closes

    # Exit remaining at last bar
    exit_price = close[n - 1]
    if direction == 1:
        pnl = (exit_price - entry_price) * remaining_size
    else:
        pnl = (entry_price - exit_price) * remaining_size
    total_pnl += pnl

    return n - 1, exit_price, total_pnl, partial_closes


# =============================================================================
# MAIN ADVANCED FEATURES CLASS
# =============================================================================


class AdvancedFeatures:
    """
    Менеджер продвинутых функций для Universal Math Engine.
    """

    def __init__(
        self,
        scale_in_config: Optional[ScaleInConfig] = None,
        partial_close_config: Optional[PartialCloseConfig] = None,
        time_exit_config: Optional[TimeExitConfig] = None,
        slippage_config: Optional[SlippageConfig] = None,
        funding_config: Optional[FundingConfig] = None,
        hedge_config: Optional[HedgeConfig] = None,
    ):
        self.scale_in = scale_in_config or ScaleInConfig()
        self.partial_close = partial_close_config or PartialCloseConfig()
        self.time_exit = time_exit_config or TimeExitConfig()
        self.slippage = slippage_config or SlippageConfig()
        self.funding = funding_config or FundingConfig()
        self.hedge = hedge_config or HedgeConfig()

    def apply_slippage(
        self,
        price: float,
        is_buy: bool,
        volume: float = 0.0,
        avg_volume: float = 0.0,
        atr: float = 0.0,
    ) -> float:
        """Применить проскальзывание к цене."""
        model = self.slippage.model

        if model == SlippageModel.NONE:
            return price

        if model == SlippageModel.FIXED:
            return calculate_slippage_fixed(price, self.slippage.fixed_slippage, is_buy)

        if model == SlippageModel.PERCENTAGE:
            return calculate_slippage_fixed(price, self.slippage.percentage, is_buy)

        if model == SlippageModel.VOLUME_BASED:
            return calculate_slippage_volume_based(
                price,
                volume,
                avg_volume,
                self.slippage.volume_impact,
                self.slippage.min_slippage,
                self.slippage.max_slippage,
                is_buy,
            )

        if model == SlippageModel.VOLATILITY_BASED:
            return calculate_slippage_volatility_based(
                price, atr, self.slippage.volatility_multiplier, is_buy
            )

        return price

    def calculate_funding(
        self,
        position_value: float,
        hours_held: float,
        is_long: bool,
    ) -> float:
        """Рассчитать стоимость фандинга."""
        if not self.funding.enabled:
            return 0.0

        if is_long and not self.funding.apply_to_longs:
            return 0.0

        if not is_long and not self.funding.apply_to_shorts:
            return 0.0

        return calculate_funding_cost(
            position_value,
            self.funding.funding_rate,
            hours_held,
            self.funding.funding_interval_hours,
            is_long,
        )

    def get_scale_in_levels(
        self,
        entry_price: float,
        direction: int,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Получить уровни и размеры для scale-in."""
        if not self.scale_in.enabled:
            return np.array([]), np.array([])

        levels = calculate_scale_in_levels(
            entry_price,
            direction,
            np.array(self.scale_in.profit_levels, dtype=np.float64),
        )

        sizes = np.array(self.scale_in.size_multipliers, dtype=np.float64)

        return levels, sizes

    def get_partial_close_levels(
        self,
        entry_price: float,
        direction: int,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Получить уровни и размеры для частичного закрытия."""
        if not self.partial_close.enabled:
            return np.array([]), np.array([])

        levels = calculate_partial_close_levels(
            entry_price,
            direction,
            np.array(self.partial_close.tp_levels, dtype=np.float64),
        )

        percentages = np.array(self.partial_close.close_percentages, dtype=np.float64)

        return levels, percentages

    def should_exit_by_time(
        self,
        bar_index: int,
        entry_bar: int,
        timestamp: int,  # Unix timestamp in ms
    ) -> bool:
        """Проверить нужно ли выходить по времени."""
        if not self.time_exit.enabled:
            return False

        mode = self.time_exit.mode

        if mode == TimeExitMode.NONE:
            return False

        if mode == TimeExitMode.MAX_BARS:
            bars_in_trade = bar_index - entry_bar
            return bars_in_trade >= self.time_exit.max_bars_in_trade

        # Для других режимов нужен timestamp
        import datetime

        dt = datetime.datetime.fromtimestamp(timestamp / 1000)

        if mode == TimeExitMode.SESSION_CLOSE:
            return (
                dt.hour >= self.time_exit.session_end_hour
                and dt.minute >= self.time_exit.session_end_minute
            )

        if mode == TimeExitMode.WEEKEND_CLOSE:
            return dt.weekday() == 4 and dt.hour >= self.time_exit.friday_close_hour

        return False


# =============================================================================
# HEDGE MODE MANAGER
# =============================================================================


@dataclass
class HedgePosition:
    """Hedge позиция."""

    long_size: float = 0.0
    long_entry: float = 0.0
    short_size: float = 0.0
    short_entry: float = 0.0
    long_pnl: float = 0.0
    short_pnl: float = 0.0

    @property
    def net_size(self) -> float:
        """Чистый размер позиции."""
        return self.long_size - self.short_size

    @property
    def total_pnl(self) -> float:
        """Общий PnL."""
        return self.long_pnl + self.short_pnl

    def update_pnl(self, current_price: float) -> None:
        """Обновить PnL."""
        if self.long_size > 0:
            self.long_pnl = (current_price - self.long_entry) * self.long_size
        if self.short_size > 0:
            self.short_pnl = (self.short_entry - current_price) * self.short_size


class HedgeManager:
    """
    Менеджер Hedge Mode.

    Позволяет держать Long и Short одновременно.
    """

    def __init__(self, config: Optional[HedgeConfig] = None):
        self.config = config or HedgeConfig()
        self.position = HedgePosition()

    def can_open_long(self, size: float) -> bool:
        """Можно ли открыть Long."""
        if not self.config.enabled:
            return self.position.short_size == 0

        return self.position.long_size + size <= self.config.max_long_size

    def can_open_short(self, size: float) -> bool:
        """Можно ли открыть Short."""
        if not self.config.enabled:
            return self.position.long_size == 0

        return self.position.short_size + size <= self.config.max_short_size

    def open_long(self, price: float, size: float) -> bool:
        """Открыть Long."""
        if not self.can_open_long(size):
            return False

        # Если есть short - частично закрываем
        if self.position.short_size > 0 and not self.config.allow_simultaneous:
            close_size = min(size, self.position.short_size)
            self.position.short_pnl += (self.position.short_entry - price) * close_size
            self.position.short_size -= close_size
            size -= close_size

        if size > 0:
            # Усреднение цены входа
            total_cost = (
                self.position.long_entry * self.position.long_size + price * size
            )
            self.position.long_size += size
            self.position.long_entry = (
                total_cost / self.position.long_size
                if self.position.long_size > 0
                else 0
            )

        return True

    def open_short(self, price: float, size: float) -> bool:
        """Открыть Short."""
        if not self.can_open_short(size):
            return False

        if self.position.long_size > 0 and not self.config.allow_simultaneous:
            close_size = min(size, self.position.long_size)
            self.position.long_pnl += (price - self.position.long_entry) * close_size
            self.position.long_size -= close_size
            size -= close_size

        if size > 0:
            total_cost = (
                self.position.short_entry * self.position.short_size + price * size
            )
            self.position.short_size += size
            self.position.short_entry = (
                total_cost / self.position.short_size
                if self.position.short_size > 0
                else 0
            )

        return True

    def close_all(self, price: float) -> float:
        """Закрыть все позиции."""
        pnl = 0.0

        if self.position.long_size > 0:
            pnl += (price - self.position.long_entry) * self.position.long_size
            self.position.long_size = 0
            self.position.long_entry = 0

        if self.position.short_size > 0:
            pnl += (self.position.short_entry - price) * self.position.short_size
            self.position.short_size = 0
            self.position.short_entry = 0

        total_pnl = pnl + self.position.long_pnl + self.position.short_pnl
        self.position.long_pnl = 0
        self.position.short_pnl = 0

        return total_pnl

    def reset(self) -> None:
        """Сбросить состояние."""
        self.position = HedgePosition()
