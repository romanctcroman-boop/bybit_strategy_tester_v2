"""
Event-Driven Backtest Engine — очередь событий, один код для backtest и live.

Архитектура (ROADMAP_REMAINING_TASKS):
    EventQueue (FIFO) ← DataHandler | Strategy | ExecutionHandler
         ↓
    Portfolio ← OrderEvents, FillEvents

Без lookahead bias: события обрабатываются строго по timestamp.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

# =============================================================================
# Events
# =============================================================================


class EventType(Enum):
    """Типы событий."""

    BAR = "bar"
    TICK = "tick"
    ORDER = "order"
    FILL = "fill"
    SIGNAL = "signal"


@dataclass
class Event:
    """Базовое событие с временной меткой."""

    timestamp: float  # Unix ms
    event_type: EventType
    payload: dict[str, Any] = field(default_factory=dict)

    def __lt__(self, other: "Event") -> bool:
        return self.timestamp < other.timestamp


@dataclass
class BarEvent(Event):
    """Событие нового бара OHLCV."""

    def __post_init__(self):
        self.event_type = EventType.BAR

    @property
    def open(self) -> float:
        return self.payload.get("open", 0.0)

    @property
    def high(self) -> float:
        return self.payload.get("high", 0.0)

    @property
    def low(self) -> float:
        return self.payload.get("low", 0.0)

    @property
    def close(self) -> float:
        return self.payload.get("close", 0.0)

    @property
    def volume(self) -> float:
        return self.payload.get("volume", 0.0)


@dataclass
class OrderEvent(Event):
    """Событие ордера (заявка от стратегии)."""

    def __post_init__(self):
        self.event_type = EventType.ORDER

    @property
    def symbol(self) -> str:
        return self.payload.get("symbol", "")

    @property
    def side(self) -> str:
        return self.payload.get("side", "buy")

    @property
    def qty(self) -> float:
        return self.payload.get("qty", 0.0)

    @property
    def order_type(self) -> str:
        return self.payload.get("order_type", "market")


@dataclass
class FillEvent(Event):
    """Событие исполнения ордера."""

    def __post_init__(self):
        self.event_type = EventType.FILL

    @property
    def order_id(self) -> str:
        return self.payload.get("order_id", "")

    @property
    def fill_price(self) -> float:
        return self.payload.get("fill_price", 0.0)

    @property
    def fill_qty(self) -> float:
        return self.payload.get("fill_qty", 0.0)


# =============================================================================
# Event Queue
# =============================================================================


class EventQueue:
    """
    Очередь событий FIFO по timestamp.

    События обрабатываются строго в порядке времени — нет lookahead.
    """

    def __init__(self):
        self._events: list[Event] = []
        self._current_time: float = 0.0

    def push(self, event: Event) -> None:
        """Добавить событие (сортировка по timestamp)."""
        self._events.append(event)
        self._events.sort(key=lambda e: e.timestamp)

    def pop(self) -> Event | None:
        """Извлечь следующее событие."""
        if not self._events:
            return None
        event = self._events.pop(0)
        self._current_time = event.timestamp
        return event

    def peek(self) -> Event | None:
        """Посмотреть следующее без извлечения."""
        return self._events[0] if self._events else None

    def empty(self) -> bool:
        return len(self._events) == 0

    @property
    def current_time(self) -> float:
        return self._current_time


# =============================================================================
# Execution Handler
# =============================================================================


class ExecutionHandler(ABC):
    """Abstract execution handler: OrderEvent → FillEvent(s)."""

    @abstractmethod
    def execute(
        self,
        order: OrderEvent,
        bars_df: pd.DataFrame,
        bar_index: int,
        reference_price: float,
    ) -> list[FillEvent]:
        """Convert order to fill event(s). Return empty list if rejected."""
        ...


@dataclass
class SimulationConfig:
    """Execution simulation parameters."""

    slippage_bps: float = 10.0  # 10 bps = 0.1%
    latency_bars: int = 0  # 0 = immediate, 1 = next bar
    fill_ratio: float = 1.0  # 1.0 = full fill, 0.8 = 80% partial
    reject_probability: float = 0.0  # 0 = no rejection
    use_high_low_slippage: bool = True  # Buy at high, sell at low (worse price)


class SimulationExecutionHandler(ExecutionHandler):
    """
    Realistic execution simulation: latency, slippage, partial fills, rejections.
    """

    def __init__(self, config: SimulationConfig | None = None):
        self.config = config or SimulationConfig()
        self._order_counter = 0

    def execute(
        self,
        order: OrderEvent,
        bars_df: pd.DataFrame,
        bar_index: int,
        reference_price: float,
    ) -> list[FillEvent]:
        if order.qty <= 0 or reference_price <= 0:
            return []

        # Rejection
        if self.config.reject_probability > 0 and np.random.random() < self.config.reject_probability:
            return []

        # Latency: fill at bar_index + latency_bars
        fill_bar_idx = min(bar_index + self.config.latency_bars, len(bars_df) - 1)
        if fill_bar_idx < 0 or fill_bar_idx >= len(bars_df):
            return []

        row = bars_df.iloc[fill_bar_idx]
        open_p = float(row.get("open", reference_price))
        high_p = float(row.get("high", open_p))
        low_p = float(row.get("low", open_p))
        close_p = float(row.get("close", open_p))

        # Fill price with slippage
        slippage = self.config.slippage_bps / 10000.0
        side = str(order.side).lower()
        if self.config.use_high_low_slippage:
            fill_price = high_p * (1 + slippage) if side == "buy" else low_p * (1 - slippage)
        else:
            fill_price = close_p * (1 + slippage) if side == "buy" else close_p * (1 - slippage)

        # Partial fill
        fill_qty = order.qty * self.config.fill_ratio
        if fill_qty <= 0:
            return []

        self._order_counter += 1
        order_id = order.payload.get("order_id") or f"ord_{self._order_counter}"

        ts = order.timestamp
        if fill_bar_idx > bar_index and "open_time" in bars_df.columns:
            ts_row = bars_df.iloc[fill_bar_idx].get("open_time")
            if hasattr(ts_row, "timestamp"):
                ts = float(ts_row.timestamp() * 1000)
            elif isinstance(ts_row, (int, float)) and ts_row > 0:
                ts = float(ts_row) if ts_row > 1e12 else ts_row * 1000

        return [
            FillEvent(
                timestamp=ts,
                event_type=EventType.FILL,
                payload={
                    "order_id": order_id,
                    "fill_price": fill_price,
                    "fill_qty": fill_qty,
                    "side": side,
                    "pnl": 0.0,
                },
            )
        ]


# =============================================================================
# Event-Driven Engine
# =============================================================================


class EventDrivenEngine:
    """
    Event-driven движок бэктеста.

    Цикл: EventQueue → BarEvent → Strategy.on_bar() → OrderEvent → ExecutionHandler → FillEvent → Portfolio.
    """

    def __init__(
        self,
        initial_capital: float = 10000.0,
        on_bar: Callable[[BarEvent], list[OrderEvent]] | None = None,
        execution_handler: ExecutionHandler | None = None,
    ):
        self.initial_capital = initial_capital
        self.on_bar = on_bar or (lambda e: [])
        self.execution_handler = execution_handler
        self.queue = EventQueue()
        self.equity: float = initial_capital
        self.trades: list[dict[str, Any]] = []
        self._bars_df: pd.DataFrame | None = None
        self._bar_index: int = 0

    def load_bars(self, df: pd.DataFrame, timestamp_col: str = "open_time") -> None:
        """Загрузить бары как BarEvent в очередь."""
        self._bars_df = df.copy()
        for i in range(len(df)):
            row = df.iloc[i]
            ts = row.get(timestamp_col, i)
            if hasattr(ts, "timestamp"):
                ts = int(ts.timestamp() * 1000)
            elif isinstance(ts, (int, float)) and ts < 1e12:
                ts = int(ts * 1000) if ts < 1e10 else int(ts)
            event = BarEvent(
                timestamp=float(ts),
                event_type=EventType.BAR,
                payload={
                    "open": float(row.get("open", 0)),
                    "high": float(row.get("high", 0)),
                    "low": float(row.get("low", 0)),
                    "close": float(row.get("close", 0)),
                    "volume": float(row.get("volume", 0)),
                    "index": i,
                },
            )
            self.queue.push(event)

    def run(self) -> dict[str, Any]:
        """
        Запустить цикл обработки событий.

        Returns:
            dict с equity, trades, metrics
        """
        self.equity = self.initial_capital
        self.trades = []
        bar_count = 0
        last_close = 0.0
        bars_df = self._bars_df

        while not self.queue.empty():
            event = self.queue.pop()
            if event is None:
                break

            if isinstance(event, BarEvent):
                bar_count += 1
                self._bar_index = int(event.payload.get("index", bar_count - 1))
                last_close = event.close
                orders = self.on_bar(event)
                for order in orders:
                    if isinstance(order, OrderEvent):
                        self.queue.push(order)
                    elif isinstance(order, dict):
                        self.queue.push(
                            OrderEvent(
                                timestamp=event.timestamp,
                                event_type=EventType.ORDER,
                                payload=order,
                            )
                        )
            elif isinstance(event, OrderEvent):
                if self.execution_handler and bars_df is not None and len(bars_df) > 0:
                    fills = self.execution_handler.execute(
                        event,
                        bars_df,
                        self._bar_index,
                        last_close or 0.0,
                    )
                    for fill in fills:
                        self.queue.push(fill)
                else:
                    fill_price = last_close or 0.0
                    fill = FillEvent(
                        timestamp=event.timestamp,
                        event_type=EventType.FILL,
                        payload={
                            "order_id": event.payload.get("order_id", "gen"),
                            "fill_price": fill_price,
                            "fill_qty": event.qty,
                            "pnl": 0.0,
                        },
                    )
                    self.queue.push(fill)
            elif isinstance(event, FillEvent):
                pnl = event.payload.get("pnl", 0.0)
                self.equity += pnl
                self.trades.append(
                    {
                        "timestamp": event.timestamp,
                        "fill_price": event.fill_price,
                        "fill_qty": event.fill_qty,
                        "pnl": pnl,
                        "equity": self.equity,
                    }
                )

        return {
            "final_equity": self.equity,
            "total_return": (self.equity - self.initial_capital) / self.initial_capital
            if self.initial_capital > 0
            else 0,
            "trades": self.trades,
            "bar_count": bar_count,
        }


# =============================================================================
# StrategyBuilderAdapter integration
# =============================================================================


def create_on_bar_from_adapter(
    adapter: "StrategyBuilderAdapter",
    df: pd.DataFrame,
    symbol: str = "BTCUSDT",
    position_pct: float = 0.95,
) -> Callable[[BarEvent], list[OrderEvent]]:
    """
    Create an on_bar callback that uses StrategyBuilderAdapter signals.

    Pre-computes signals via adapter.generate_signals(df), then for each bar
    emits OrderEvents when entry/exit signals trigger.
    """

    result = adapter.generate_signals(df)
    entries = result.entries if hasattr(result.entries, "values") else pd.Series()
    exits = result.exits if hasattr(result.exits, "values") else pd.Series()
    short_entries = result.short_entries if hasattr(result.short_entries, "values") else pd.Series()
    short_exits = result.short_exits if hasattr(result.short_exits, "values") else pd.Series()

    position = 0  # -1 short, 0 flat, 1 long

    def on_bar(event: BarEvent) -> list[OrderEvent]:
        nonlocal position
        orders: list[OrderEvent] = []
        idx = int(event.payload.get("index", -1))
        if idx < 0 or idx >= len(df):
            return orders

        close = float(event.close)
        n = len(df)
        capital_per_trade = 10000.0 * position_pct
        qty = capital_per_trade / close if close > 0 else 0.0

        def add_order(side: str):
            orders.append(
                OrderEvent(
                    timestamp=event.timestamp,
                    event_type=EventType.ORDER,
                    payload={
                        "symbol": symbol,
                        "side": side,
                        "qty": qty,
                        "order_type": "market",
                    },
                )
            )

        try:
            long_entry = bool(entries.iloc[idx]) if idx < len(entries) else False
            long_exit = bool(exits.iloc[idx]) if idx < len(exits) else False
            short_entry = bool(short_entries.iloc[idx]) if idx < len(short_entries) else False
            short_exit = bool(short_exits.iloc[idx]) if idx < len(short_exits) else False
        except (IndexError, KeyError):
            return orders

        if position == 0:
            if long_entry:
                add_order("buy")
                position = 1
            elif short_entry:
                add_order("sell")
                position = -1
        elif position == 1:
            if long_exit or short_entry:
                add_order("sell")
                position = 0
        elif position == -1:
            if short_exit or long_entry:
                add_order("buy")
                position = 0

        return orders

    return on_bar


def run_event_driven_with_adapter(
    adapter: "StrategyBuilderAdapter",
    df: pd.DataFrame,
    initial_capital: float = 10000.0,
    symbol: str = "BTCUSDT",
    timestamp_col: str = "open_time",
    execution_config: SimulationConfig | None = None,
) -> dict[str, Any]:
    """
    Run event-driven backtest using StrategyBuilderAdapter.

    Args:
        execution_config: Optional simulation config (slippage, latency, etc.)

    Returns:
        dict with final_equity, total_return, trades, bar_count
    """

    on_bar = create_on_bar_from_adapter(adapter, df, symbol=symbol)
    handler = SimulationExecutionHandler(execution_config) if execution_config else None
    engine = EventDrivenEngine(
        initial_capital=initial_capital,
        on_bar=on_bar,
        execution_handler=handler,
    )
    engine.load_bars(df, timestamp_col=timestamp_col)
    return engine.run()
