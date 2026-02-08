"""
Broker Emulator: Tick-by-Tick Order Execution

Обрабатывает ордера на каждом псевдотике, сгенерированном IntrabarEngine.
Не знает, что тики синтетические - работает как с реальными.

Приоритеты исполнения на каждом тике:
    1. Margin calls / ликвидации (если моделируем плечо)
    2. Обновление SL/TP ордеров (stop/limit/trailing)
    3. Обработка новых сигналов стратегии (market/limit/stop entry)
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class OrderType(str, Enum):
    """Тип ордера."""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TAKE_PROFIT = "take_profit"
    STOP_LOSS = "stop_loss"
    TRAILING_STOP = "trailing_stop"


class OrderSide(str, Enum):
    """Сторона ордера."""

    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    """Статус ордера."""

    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class PositionSide(str, Enum):
    """Сторона позиции."""

    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


@dataclass
class Order:
    """Ордер в системе."""

    id: str
    order_type: OrderType
    side: OrderSide
    price: float  # Цена ордера (для limit/stop)
    size: float  # Размер
    status: OrderStatus = OrderStatus.PENDING
    created_at: int = 0  # timestamp_ms
    filled_at: int = 0
    filled_price: float = 0.0
    filled_size: float = 0.0

    # Для trailing stop
    trail_offset: float = 0.0  # В процентах
    trail_price: float = 0.0  # Текущая цена трейлинга

    # Связь с позицией
    position_id: str = ""
    is_reduce_only: bool = False  # Только закрытие

    # Метаданные
    tag: str = ""  # Для идентификации источника (strategy, sl, tp)


@dataclass
class Position:
    """Открытая позиция."""

    id: str
    side: PositionSide
    entry_price: float
    size: float
    created_at: int = 0

    # PnL
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0

    # Risk management
    stop_loss_price: float | None = None
    take_profit_price: float | None = None
    trailing_stop_offset: float | None = None
    trailing_stop_price: float | None = None

    # MFE/MAE tracking
    max_favorable_price: float = 0.0
    max_adverse_price: float = 0.0
    mfe: float = 0.0  # Maximum Favorable Excursion %
    mae: float = 0.0  # Maximum Adverse Excursion %


@dataclass
class Fill:
    """Исполнение ордера."""

    order_id: str
    timestamp_ms: int
    price: float
    size: float
    side: OrderSide
    fee: float = 0.0
    pnl: float = 0.0  # Для закрывающих сделок


@dataclass
class BrokerConfig:
    """Конфигурация брокера."""

    # Комиссии
    maker_fee: float = 0.0002  # 0.02%
    taker_fee: float = 0.0004  # 0.04%

    # Slippage
    slippage_percent: float = 0.0005  # 0.05%
    slippage_ticks: int = 0
    min_tick: float = 0.01

    # Маржа и плечо
    leverage: float = 1.0
    initial_margin: float = 1.0  # 100% = без маржи
    maintenance_margin: float = 0.5  # 50% = ликвидация

    # Приоритеты
    sl_priority: bool = True  # SL имеет приоритет над TP

    # Gap handling
    fill_on_gap: bool = True
    gap_mode: str = "open_price"  # "open_price", "order_price"


@dataclass
class BrokerState:
    """Состояние брокера."""

    cash: float = 10000.0
    initial_capital: float = 10000.0
    equity: float = 10000.0

    positions: dict[str, Position] = field(default_factory=dict)
    orders: dict[str, Order] = field(default_factory=dict)
    fills: list[Fill] = field(default_factory=list)

    # Текущая цена
    current_price: float = 0.0
    current_time: int = 0

    # Счётчики
    order_counter: int = 0
    position_counter: int = 0


class BrokerEmulator:
    """
    Эмулятор брокера для tick-by-tick бэктестинга.

    Обрабатывает ордера в строгом порядке приоритетов:
        1. Проверка ликвидаций
        2. Исполнение SL/TP
        3. Исполнение entry ордеров
        4. Обновление trailing stops
    """

    def __init__(self, config: BrokerConfig = None, initial_capital: float = 10000.0):
        self.config = config or BrokerConfig()
        self.state = BrokerState(
            cash=initial_capital,
            initial_capital=initial_capital,
            equity=initial_capital,
        )

        # Callbacks для логирования событий
        self.on_fill: Callable[[Fill], None] | None = None
        self.on_liquidation: Callable[[Position], None] | None = None

        logger.info(
            f"[BROKER_EMULATOR] Initialized with capital={initial_capital}, "
            f"leverage={self.config.leverage}x"
        )

    def reset(self, initial_capital: float = None) -> None:
        """Сбросить состояние брокера."""
        capital = initial_capital or self.state.initial_capital
        self.state = BrokerState(
            cash=capital,
            initial_capital=capital,
            equity=capital,
        )

    # =========================================================================
    # TICK PROCESSING
    # =========================================================================

    def process_tick(self, price: float, timestamp_ms: int) -> list[Fill]:
        """
        Обработать один тик (главная точка входа).

        Порядок обработки:
            1. Обновить текущую цену
            2. Проверить ликвидации
            3. Проверить SL/TP ордера
            4. Проверить остальные ордера
            5. Обновить trailing stops
            6. Пересчитать equity

        Args:
            price: Текущая цена
            timestamp_ms: Время тика

        Returns:
            List of fills, произошедших на этом тике
        """
        self.state.current_price = price
        self.state.current_time = timestamp_ms

        fills: list[Fill] = []

        # 1. Проверка ликвидаций
        self._check_liquidations()

        # 2. Обновить MFE/MAE для позиций
        self._update_positions_mfe_mae(price)

        # 3. Проверить SL/TP ордера (приоритет)
        fills.extend(self._process_sl_tp_orders(price, timestamp_ms))

        # 4. Проверить остальные ордера
        fills.extend(self._process_pending_orders(price, timestamp_ms))

        # 5. Обновить trailing stops
        self._update_trailing_stops(price)

        # 6. Пересчитать equity
        self._update_equity(price)

        return fills

    def _check_liquidations(self) -> None:
        """Проверить условия ликвидации для позиций с плечом."""
        if self.config.leverage <= 1.0:
            return

        to_liquidate = []

        for pos_id, pos in self.state.positions.items():
            if pos.side == PositionSide.FLAT:
                continue

            # Рассчитать unrealized PnL
            pnl_pct = self._calculate_position_pnl_percent(pos)

            # Проверить margin
            margin_used = 1.0 / self.config.leverage
            loss_threshold = margin_used * self.config.maintenance_margin

            if pnl_pct <= -loss_threshold:
                to_liquidate.append(pos_id)

        # Ликвидировать
        for pos_id in to_liquidate:
            pos = self.state.positions[pos_id]
            logger.warning(
                f"[BROKER_EMULATOR] LIQUIDATION: {pos_id} at {self.state.current_price}"
            )
            self._close_position(pos_id, self.state.current_price, "liquidation")

            if self.on_liquidation:
                self.on_liquidation(pos)

    def _calculate_position_pnl_percent(self, pos: Position) -> float:
        """Рассчитать PnL позиции в процентах."""
        if pos.side == PositionSide.LONG:
            return (self.state.current_price - pos.entry_price) / pos.entry_price
        elif pos.side == PositionSide.SHORT:
            return (pos.entry_price - self.state.current_price) / pos.entry_price
        return 0.0

    def _update_positions_mfe_mae(self, price: float) -> None:
        """Обновить MFE/MAE для всех открытых позиций."""
        for pos in self.state.positions.values():
            if pos.side == PositionSide.FLAT:
                continue

            if pos.side == PositionSide.LONG:
                # Long: high = favorable, low = adverse
                if price > pos.max_favorable_price:
                    pos.max_favorable_price = price
                    pos.mfe = (price - pos.entry_price) / pos.entry_price * 100
                if price < pos.max_adverse_price or pos.max_adverse_price == 0:
                    pos.max_adverse_price = price
                    pos.mae = (pos.entry_price - price) / pos.entry_price * 100
            else:
                # Short: low = favorable, high = adverse
                if price < pos.max_favorable_price or pos.max_favorable_price == 0:
                    pos.max_favorable_price = price
                    pos.mfe = (pos.entry_price - price) / pos.entry_price * 100
                if price > pos.max_adverse_price:
                    pos.max_adverse_price = price
                    pos.mae = (price - pos.entry_price) / pos.entry_price * 100

    def _process_sl_tp_orders(self, price: float, timestamp_ms: int) -> list[Fill]:
        """Обработать SL/TP ордера с учётом приоритета."""
        fills = []

        for pos in list(self.state.positions.values()):
            if pos.side == PositionSide.FLAT:
                continue

            sl_triggered = False
            tp_triggered = False

            # Проверить SL
            if pos.stop_loss_price is not None:
                if (pos.side == PositionSide.LONG and price <= pos.stop_loss_price) or (pos.side == PositionSide.SHORT and price >= pos.stop_loss_price):
                    sl_triggered = True

            # Проверить TP
            if pos.take_profit_price is not None:
                if (pos.side == PositionSide.LONG and price >= pos.take_profit_price) or (pos.side == PositionSide.SHORT and price <= pos.take_profit_price):
                    tp_triggered = True

            # Проверить Trailing Stop
            if pos.trailing_stop_price is not None:
                if (pos.side == PositionSide.LONG and price <= pos.trailing_stop_price) or (
                    pos.side == PositionSide.SHORT and price >= pos.trailing_stop_price
                ):
                    sl_triggered = True

            # Определить что сработало
            if sl_triggered and tp_triggered:
                # Оба сработали - используем приоритет
                if self.config.sl_priority:
                    fill = self._close_position(
                        pos.id, pos.stop_loss_price, "stop_loss"
                    )
                else:
                    fill = self._close_position(
                        pos.id, pos.take_profit_price, "take_profit"
                    )
                if fill:
                    fills.append(fill)
            elif sl_triggered:
                exit_price = pos.trailing_stop_price or pos.stop_loss_price
                fill = self._close_position(pos.id, exit_price, "stop_loss")
                if fill:
                    fills.append(fill)
            elif tp_triggered:
                fill = self._close_position(
                    pos.id, pos.take_profit_price, "take_profit"
                )
                if fill:
                    fills.append(fill)

        return fills

    def _process_pending_orders(self, price: float, timestamp_ms: int) -> list[Fill]:
        """Обработать pending ордера."""
        fills = []

        for order in list(self.state.orders.values()):
            if order.status != OrderStatus.PENDING:
                continue

            fill = self._try_fill_order(order, price, timestamp_ms)
            if fill:
                fills.append(fill)

        return fills

    def _try_fill_order(
        self, order: Order, price: float, timestamp_ms: int
    ) -> Fill | None:
        """Попытаться исполнить ордер."""
        should_fill = False
        fill_price = price

        if order.order_type == OrderType.MARKET:
            should_fill = True
            # Применить slippage
            if order.side == OrderSide.BUY:
                fill_price = price * (1 + self.config.slippage_percent)
            else:
                fill_price = price * (1 - self.config.slippage_percent)

        elif order.order_type == OrderType.LIMIT:
            if order.side == OrderSide.BUY and price <= order.price:
                should_fill = True
                fill_price = order.price  # Limit исполняется по цене ордера
            elif order.side == OrderSide.SELL and price >= order.price:
                should_fill = True
                fill_price = order.price

        elif order.order_type == OrderType.STOP:
            if order.side == OrderSide.BUY and price >= order.price:
                should_fill = True
                fill_price = max(price, order.price) * (
                    1 + self.config.slippage_percent
                )
            elif order.side == OrderSide.SELL and price <= order.price:
                should_fill = True
                fill_price = min(price, order.price) * (
                    1 - self.config.slippage_percent
                )

        if should_fill:
            return self._execute_order(order, fill_price, timestamp_ms)

        return None

    def _execute_order(
        self, order: Order, fill_price: float, timestamp_ms: int
    ) -> Fill:
        """Исполнить ордер."""
        # Рассчитать комиссию
        fee = abs(order.size * fill_price * self.config.taker_fee)

        # Создать fill
        fill = Fill(
            order_id=order.id,
            timestamp_ms=timestamp_ms,
            price=fill_price,
            size=order.size,
            side=order.side,
            fee=fee,
        )

        # Обновить статус ордера
        order.status = OrderStatus.FILLED
        order.filled_at = timestamp_ms
        order.filled_price = fill_price
        order.filled_size = order.size

        # Обновить позицию или создать новую
        if order.is_reduce_only and order.position_id:
            # Закрытие позиции
            fill.pnl = self._close_position_partial(
                order.position_id, order.size, fill_price
            )
        else:
            # Открытие/увеличение позиции
            self._open_or_increase_position(order, fill_price, timestamp_ms)

        # Обновить cash
        if order.side == OrderSide.BUY:
            self.state.cash -= order.size * fill_price + fee
        else:
            self.state.cash += order.size * fill_price - fee

        # Сохранить fill
        self.state.fills.append(fill)

        # Callback
        if self.on_fill:
            self.on_fill(fill)

        logger.debug(
            f"[BROKER_EMULATOR] Filled {order.id}: {order.side.value} "
            f"{order.size} @ {fill_price:.2f}, fee={fee:.4f}"
        )

        return fill

    def _update_trailing_stops(self, price: float) -> None:
        """Обновить trailing stop цены."""
        for pos in self.state.positions.values():
            if pos.trailing_stop_offset is None:
                continue

            if pos.side == PositionSide.LONG:
                # Trailing stop движется вверх за ценой
                new_trail = price * (1 - pos.trailing_stop_offset)
                if (
                    pos.trailing_stop_price is None
                    or new_trail > pos.trailing_stop_price
                ):
                    pos.trailing_stop_price = new_trail

            elif pos.side == PositionSide.SHORT:
                # Trailing stop движется вниз за ценой
                new_trail = price * (1 + pos.trailing_stop_offset)
                if (
                    pos.trailing_stop_price is None
                    or new_trail < pos.trailing_stop_price
                ):
                    pos.trailing_stop_price = new_trail

    def _update_equity(self, price: float) -> None:
        """Пересчитать equity."""
        unrealized_pnl = 0.0

        for pos in self.state.positions.values():
            if pos.side == PositionSide.LONG:
                unrealized_pnl += (price - pos.entry_price) * pos.size
            elif pos.side == PositionSide.SHORT:
                unrealized_pnl += (pos.entry_price - price) * pos.size

        self.state.equity = self.state.cash + unrealized_pnl

    # =========================================================================
    # POSITION MANAGEMENT
    # =========================================================================

    def _open_or_increase_position(
        self, order: Order, fill_price: float, timestamp_ms: int
    ) -> Position:
        """Открыть новую или увеличить существующую позицию."""
        side = PositionSide.LONG if order.side == OrderSide.BUY else PositionSide.SHORT

        # Проверить есть ли уже позиция в этом направлении
        existing = None
        for pos in self.state.positions.values():
            if pos.side == side:
                existing = pos
                break

        if existing:
            # Усреднить entry price
            total_size = existing.size + order.size
            existing.entry_price = (
                existing.entry_price * existing.size + fill_price * order.size
            ) / total_size
            existing.size = total_size
            return existing
        else:
            # Создать новую позицию
            self.state.position_counter += 1
            pos_id = f"pos_{self.state.position_counter}"

            pos = Position(
                id=pos_id,
                side=side,
                entry_price=fill_price,
                size=order.size,
                created_at=timestamp_ms,
                max_favorable_price=fill_price,
                max_adverse_price=fill_price,
            )

            self.state.positions[pos_id] = pos
            return pos

    def _close_position(
        self, position_id: str, exit_price: float, reason: str
    ) -> Fill | None:
        """Полностью закрыть позицию."""
        if position_id not in self.state.positions:
            return None

        pos = self.state.positions[position_id]

        # Рассчитать PnL
        if pos.side == PositionSide.LONG:
            pnl = (exit_price - pos.entry_price) * pos.size
        else:
            pnl = (pos.entry_price - exit_price) * pos.size

        # Комиссия
        fee = abs(pos.size * exit_price * self.config.taker_fee)
        pnl -= fee

        # Создать fill
        side = OrderSide.SELL if pos.side == PositionSide.LONG else OrderSide.BUY
        fill = Fill(
            order_id=f"close_{position_id}_{reason}",
            timestamp_ms=self.state.current_time,
            price=exit_price,
            size=pos.size,
            side=side,
            fee=fee,
            pnl=pnl,
        )

        # Обновить cash
        self.state.cash += pos.size * exit_price - fee
        if pos.side == PositionSide.SHORT:
            self.state.cash -= pnl  # Корректировка для short

        # Удалить позицию
        del self.state.positions[position_id]

        # Сохранить fill
        self.state.fills.append(fill)

        logger.debug(
            f"[BROKER_EMULATOR] Closed {position_id}: {reason} @ {exit_price:.2f}, "
            f"PnL={pnl:.2f}"
        )

        return fill

    def _close_position_partial(
        self, position_id: str, size: float, exit_price: float
    ) -> float:
        """Частично закрыть позицию. Возвращает realized PnL."""
        if position_id not in self.state.positions:
            return 0.0

        pos = self.state.positions[position_id]
        close_size = min(size, pos.size)

        # Рассчитать PnL для закрываемой части
        if pos.side == PositionSide.LONG:
            pnl = (exit_price - pos.entry_price) * close_size
        else:
            pnl = (pos.entry_price - exit_price) * close_size

        # Обновить позицию
        pos.size -= close_size
        pos.realized_pnl += pnl

        # Если позиция полностью закрыта
        if pos.size <= 0:
            del self.state.positions[position_id]

        return pnl

    # =========================================================================
    # ORDER MANAGEMENT
    # =========================================================================

    def submit_order(
        self,
        order_type: OrderType,
        side: OrderSide,
        size: float,
        price: float = 0.0,
        stop_loss: float = None,
        take_profit: float = None,
        trailing_stop: float = None,
        tag: str = "",
    ) -> Order:
        """Отправить ордер."""
        self.state.order_counter += 1
        order_id = f"order_{self.state.order_counter}"

        order = Order(
            id=order_id,
            order_type=order_type,
            side=side,
            price=price,
            size=size,
            created_at=self.state.current_time,
            tag=tag,
        )

        self.state.orders[order_id] = order

        logger.debug(
            f"[BROKER_EMULATOR] Submitted {order_id}: {order_type.value} "
            f"{side.value} {size} @ {price}"
        )

        return order

    def cancel_order(self, order_id: str) -> bool:
        """Отменить ордер."""
        if order_id not in self.state.orders:
            return False

        order = self.state.orders[order_id]
        if order.status == OrderStatus.PENDING:
            order.status = OrderStatus.CANCELLED
            return True

        return False

    def set_position_sl_tp(
        self,
        position_id: str,
        stop_loss: float = None,
        take_profit: float = None,
        trailing_stop: float = None,
    ) -> bool:
        """Установить SL/TP для позиции."""
        if position_id not in self.state.positions:
            return False

        pos = self.state.positions[position_id]

        if stop_loss is not None:
            pos.stop_loss_price = stop_loss
        if take_profit is not None:
            pos.take_profit_price = take_profit
        if trailing_stop is not None:
            pos.trailing_stop_offset = trailing_stop

        return True

    # =========================================================================
    # GETTERS
    # =========================================================================

    def get_position(self, side: PositionSide = None) -> Position | None:
        """Получить позицию."""
        for pos in self.state.positions.values():
            if side is None or pos.side == side:
                return pos
        return None

    def has_position(self) -> bool:
        """Есть ли открытые позиции."""
        return len(self.state.positions) > 0

    def get_equity_curve(self) -> list[float]:
        """Получить кривую equity (нужно вести отдельный лог)."""
        return [f.pnl for f in self.state.fills]

    def get_total_pnl(self) -> float:
        """Получить общий PnL."""
        return sum(f.pnl for f in self.state.fills)

    def get_trade_count(self) -> int:
        """Количество совершённых сделок."""
        return len([f for f in self.state.fills if f.pnl != 0])


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    # Пример использования
    config = BrokerConfig(
        leverage=10.0,
        taker_fee=0.0004,
        slippage_percent=0.0005,
    )

    broker = BrokerEmulator(config, initial_capital=10000.0)

    # Отправить ордер на покупку
    order = broker.submit_order(
        OrderType.MARKET,
        OrderSide.BUY,
        size=0.1,  # 0.1 BTC
    )

    # Обработать тики
    prices = [50000, 50100, 50200, 49900, 49800, 50500]

    for i, price in enumerate(prices):
        fills = broker.process_tick(price, i * 60000)
        for fill in fills:
            print(f"Fill: {fill.side.value} {fill.size} @ {fill.price:.2f}")

    print(f"\nEquity: ${broker.state.equity:.2f}")
    print(f"Total PnL: ${broker.get_total_pnl():.2f}")
