"""
🔺 PYRAMIDING SUPPORT MODULE
Поддержка пирамидинга (множественных позиций в одном направлении)
по логике TradingView.

TradingView Pyramiding Rules:
- pyramiding = 0 or 1: только одна позиция, новые сигналы игнорируются
- pyramiding > 1: до N позиций в одном направлении
- Каждая позиция имеет свой entry price, size, allocated capital
- TP/SL рассчитываются от СРЕДНЕВЗВЕШЕННОЙ цены входа
- close_entries_rule: FIFO (first in first out) или ANY (все сразу)
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class PositionEntry:
    """Отдельный вход в позицию (для пирамидинга)"""

    entry_price: float
    size: float  # Количество контрактов/BTC
    allocated_capital: float  # USDT выделено на позицию
    entry_bar_idx: int  # Индекс бара входа
    entry_time: datetime  # Время входа
    entry_id: str = ""  # ID входа (для TV-совместимости)


@dataclass
class PyramidPosition:
    """
    Агрегированная позиция с несколькими входами (пирамидинг).

    Хранит все отдельные входы и рассчитывает:
    - Средневзвешенную цену входа
    - Общий размер позиции
    - Общий выделенный капитал
    """

    direction: str  # "long" или "short"
    entries: list[PositionEntry] = field(default_factory=list)

    @property
    def is_open(self) -> bool:
        """Есть ли открытые входы"""
        return len(self.entries) > 0

    @property
    def entry_count(self) -> int:
        """Количество входов"""
        return len(self.entries)

    @property
    def total_size(self) -> float:
        """Общий размер позиции (сумма всех size)"""
        return sum(e.size for e in self.entries)

    @property
    def total_allocated(self) -> float:
        """Общий выделенный капитал"""
        return sum(e.allocated_capital for e in self.entries)

    @property
    def avg_entry_price(self) -> float:
        """
        Средневзвешенная цена входа (как в TradingView).
        avg_price = sum(price_i * size_i) / sum(size_i)
        """
        if not self.entries:
            return 0.0
        total_value = sum(e.entry_price * e.size for e in self.entries)
        total_size = self.total_size
        return total_value / total_size if total_size > 0 else 0.0

    @property
    def first_entry_bar(self) -> int:
        """Индекс первого входа (для длительности)"""
        if not self.entries:
            return 0
        return min(e.entry_bar_idx for e in self.entries)

    @property
    def first_entry_time(self) -> datetime | None:
        """Время первого входа"""
        if not self.entries:
            return None
        return min(e.entry_time for e in self.entries)

    def add_entry(
        self,
        entry_price: float,
        size: float,
        allocated_capital: float,
        entry_bar_idx: int,
        entry_time: datetime,
        entry_id: str = "",
    ) -> bool:
        """
        Добавить новый вход в позицию.

        Returns:
            True если вход добавлен успешно
        """
        self.entries.append(
            PositionEntry(
                entry_price=entry_price,
                size=size,
                allocated_capital=allocated_capital,
                entry_bar_idx=entry_bar_idx,
                entry_time=entry_time,
                entry_id=entry_id,
            )
        )
        return True

    def close_all(self) -> tuple[float, float, float, int, datetime]:
        """
        Закрыть ВСЕ входы (TV close_entries_rule = "ANY" или после TP/SL).

        Returns:
            (avg_entry_price, total_size, total_allocated, first_bar_idx, first_entry_time)
        """
        if not self.entries:
            return 0.0, 0.0, 0.0, 0, None

        result = (
            self.avg_entry_price,
            self.total_size,
            self.total_allocated,
            self.first_entry_bar,
            self.first_entry_time,
        )
        self.entries.clear()
        return result

    def close_fifo(self) -> PositionEntry | None:
        """
        Закрыть ПЕРВЫЙ вход (FIFO - First In First Out).

        Returns:
            Закрытый вход или None если позиция пуста
        """
        if not self.entries:
            return None
        return self.entries.pop(0)

    def close_lifo(self) -> PositionEntry | None:
        """
        Закрыть ПОСЛЕДНИЙ вход (LIFO - Last In First Out).

        Returns:
            Закрытый вход или None если позиция пуста
        """
        if not self.entries:
            return None
        return self.entries.pop(-1)

    def close_partial(self, portion: float) -> tuple[float, float, float]:
        """
        Частично закрыть позицию (для Multi-level TP).

        Args:
            portion: Доля позиции для закрытия (0.0-1.0)

        Returns:
            (closed_size, closed_allocated, avg_entry_price)
            Размер позиции и капитал уменьшаются пропорционально.
        """
        if not self.entries or portion <= 0:
            return 0.0, 0.0, 0.0

        portion = min(portion, 1.0)
        avg_price = self.avg_entry_price
        total_size = self.total_size
        total_allocated = self.total_allocated

        closed_size = total_size * portion
        closed_allocated = total_allocated * portion

        # Уменьшить каждый вход пропорционально
        for entry in self.entries:
            entry.size *= 1 - portion
            entry.allocated_capital *= 1 - portion

        # Удалить входы с нулевым размером
        self.entries = [e for e in self.entries if e.size > 0.0001]

        return closed_size, closed_allocated, avg_price


class PyramidingManager:
    """
    Менеджер пирамидинга для управления множественными позициями.

    Использование:
        manager = PyramidingManager(pyramiding=3, close_rule="ALL")

        # Добавление входа
        if manager.can_add_entry("long"):
            manager.add_entry("long", price, size, capital, bar_idx, time)

        # Проверка TP/SL
        tp_price = manager.get_tp_price("long", take_profit=0.015)
        sl_price = manager.get_sl_price("long", stop_loss=0.03)

        # Закрытие
        closed = manager.close_position("long", exit_price, bar_idx, time, reason)
    """

    def __init__(
        self,
        pyramiding: int = 1,
        close_rule: str = "ALL",  # "ALL", "FIFO", "LIFO"
    ):
        """
        Args:
            pyramiding: Макс. количество входов в одном направлении (0-99, TV compatible)
                       0 or 1 = single position (pyramiding disabled)
                       2-99 = allow multiple entries
            close_rule: Правило закрытия: ALL (все сразу), FIFO, LIFO
        """
        # TradingView: 0 means same as 1 (single position)
        if pyramiding <= 0:
            self.pyramiding = 1
        else:
            self.pyramiding = min(pyramiding, 99)  # Cap at 99

        self.close_rule = close_rule.upper()

        # Позиции
        self.long_position = PyramidPosition(direction="long")
        self.short_position = PyramidPosition(direction="short")

    @property
    def is_pyramiding_enabled(self) -> bool:
        """Включен ли пирамидинг (> 1 позиции)"""
        return self.pyramiding > 1

    def can_add_entry(self, direction: str) -> bool:
        """
        Можно ли добавить ещё один вход в данном направлении.

        Args:
            direction: "long" или "short"
        """
        pos = self.long_position if direction == "long" else self.short_position
        return pos.entry_count < self.pyramiding

    def has_position(self, direction: str) -> bool:
        """Есть ли открытая позиция в данном направлении"""
        pos = self.long_position if direction == "long" else self.short_position
        return pos.is_open

    def has_any_position(self) -> bool:
        """Есть ли какая-либо открытая позиция"""
        return self.long_position.is_open or self.short_position.is_open

    def get_position(self, direction: str) -> PyramidPosition:
        """Получить позицию по направлению"""
        return self.long_position if direction == "long" else self.short_position

    def add_entry(
        self,
        direction: str,
        entry_price: float,
        size: float,
        allocated_capital: float,
        entry_bar_idx: int,
        entry_time: datetime,
        entry_id: str = "",
    ) -> bool:
        """
        Добавить новый вход.

        Returns:
            True если вход добавлен, False если лимит пирамидинга достигнут
        """
        if not self.can_add_entry(direction):
            return False

        pos = self.get_position(direction)
        return pos.add_entry(
            entry_price=entry_price,
            size=size,
            allocated_capital=allocated_capital,
            entry_bar_idx=entry_bar_idx,
            entry_time=entry_time,
            entry_id=entry_id,
        )

    def get_avg_entry_price(self, direction: str) -> float:
        """Получить средневзвешенную цену входа"""
        return self.get_position(direction).avg_entry_price

    def get_total_size(self, direction: str) -> float:
        """Получить общий размер позиции"""
        return self.get_position(direction).total_size

    def get_total_allocated(self, direction: str) -> float:
        """Получить общий выделенный капитал"""
        return self.get_position(direction).total_allocated

    def get_entry_count(self, direction: str) -> int:
        """Получить количество входов"""
        return self.get_position(direction).entry_count

    def get_tp_price(self, direction: str, take_profit: float) -> float:
        """
        Рассчитать цену Take Profit от средней цены входа.

        Args:
            direction: "long" или "short"
            take_profit: TP в процентах (0.015 = 1.5%)
        """
        avg_price = self.get_avg_entry_price(direction)
        if avg_price == 0:
            return 0.0

        if direction == "long":
            return avg_price * (1 + take_profit)
        else:
            return avg_price * (1 - take_profit)

    def get_sl_price(self, direction: str, stop_loss: float) -> float:
        """
        Рассчитать цену Stop Loss от средней цены входа.

        Args:
            direction: "long" или "short"
            stop_loss: SL в процентах (0.03 = 3%)
        """
        avg_price = self.get_avg_entry_price(direction)
        if avg_price == 0:
            return 0.0

        if direction == "long":
            return avg_price * (1 - stop_loss)
        else:
            return avg_price * (1 + stop_loss)

    def get_atr_tp_price(self, direction: str, atr_value: float, multiplier: float) -> float:
        """
        Рассчитать TP на основе ATR.

        Args:
            direction: "long" или "short"
            atr_value: Текущее значение ATR
            multiplier: Множитель ATR (например, 2.0 = 2*ATR)

        Returns:
            Цена Take Profit
        """
        avg_price = self.get_avg_entry_price(direction)
        if avg_price == 0 or atr_value == 0:
            return 0.0

        if direction == "long":
            return avg_price + atr_value * multiplier
        else:
            return avg_price - atr_value * multiplier

    def get_atr_sl_price(self, direction: str, atr_value: float, multiplier: float) -> float:
        """
        Рассчитать SL на основе ATR.

        Args:
            direction: "long" или "short"
            atr_value: Текущее значение ATR
            multiplier: Множитель ATR (например, 1.5 = 1.5*ATR)

        Returns:
            Цена Stop Loss
        """
        avg_price = self.get_avg_entry_price(direction)
        if avg_price == 0 or atr_value == 0:
            return 0.0

        if direction == "long":
            return avg_price - atr_value * multiplier
        else:
            return avg_price + atr_value * multiplier

    def get_multi_tp_prices(self, direction: str, base_tp: float, tp_levels: tuple[float, ...]) -> list[float]:
        """
        Рассчитать несколько уровней TP (TP1, TP2, TP3, TP4).

        Args:
            direction: "long" или "short"
            base_tp: Базовый TP в процентах (0.01 = 1%)
            tp_levels: Множители уровней (1.0, 2.0, 3.0, 4.0) = TP*1, TP*2, TP*3, TP*4

        Returns:
            Список цен TP [TP1_price, TP2_price, TP3_price, TP4_price]
        """
        avg_price = self.get_avg_entry_price(direction)
        if avg_price == 0:
            return [0.0] * len(tp_levels)

        prices = []
        for level in tp_levels:
            tp_pct = base_tp * level
            if direction == "long":
                prices.append(avg_price * (1 + tp_pct))
            else:
                prices.append(avg_price * (1 - tp_pct))
        return prices

    def get_atr_multi_tp_prices(
        self, direction: str, atr_value: float, tp_multipliers: tuple[float, ...]
    ) -> list[float]:
        """
        Рассчитать несколько уровней TP на основе ATR.

        Args:
            direction: "long" или "short"
            atr_value: Текущее значение ATR
            tp_multipliers: Множители ATR для каждого уровня (1.0, 2.0, 3.0, 4.0)

        Returns:
            Список цен TP [TP1_price, TP2_price, TP3_price, TP4_price]
        """
        avg_price = self.get_avg_entry_price(direction)
        if avg_price == 0 or atr_value == 0:
            return [0.0] * len(tp_multipliers)

        prices = []
        for mult in tp_multipliers:
            if direction == "long":
                prices.append(avg_price + atr_value * mult)
            else:
                prices.append(avg_price - atr_value * mult)
        return prices

    def close_partial(
        self,
        direction: str,
        exit_price: float,
        portion: float,
        exit_bar_idx: int,
        exit_time: datetime,
        exit_reason: str,
        taker_fee: float = 0.0,
    ) -> dict | None:
        """
        Частично закрыть позицию (для Multi-level TP).

        Args:
            direction: "long" или "short"
            exit_price: Цена выхода
            portion: Доля позиции для закрытия (0.0-1.0)
            exit_bar_idx: Индекс бара выхода
            exit_time: Время выхода
            exit_reason: Причина выхода (например "tp1", "tp2")
            taker_fee: Комиссия

        Returns:
            dict с данными о закрытой части или None
        """
        pos = self.get_position(direction)
        if not pos.is_open:
            return None

        first_bar = pos.first_entry_bar
        first_time = pos.first_entry_time

        closed_size, closed_allocated, avg_price = pos.close_partial(portion)

        if closed_size == 0:
            return None

        # Рассчитать P&L
        if direction == "long":
            pnl_pct = (exit_price - avg_price) / avg_price
            gross_pnl = closed_size * (exit_price - avg_price)
        else:
            pnl_pct = (avg_price - exit_price) / avg_price
            gross_pnl = closed_size * (avg_price - exit_price)

        # Комиссии (только за закрываемую часть)
        entry_fee = closed_size * avg_price * taker_fee
        exit_fee = closed_size * exit_price * taker_fee
        fees = entry_fee + exit_fee
        net_pnl = gross_pnl - fees

        return {
            "entry_time": first_time,
            "exit_time": exit_time,
            "direction": direction,
            "entry_price": avg_price,
            "exit_price": exit_price,
            "size": closed_size,
            "allocated": closed_allocated,
            "pnl": net_pnl,
            "pnl_pct": pnl_pct,
            "fees": fees,
            "exit_reason": exit_reason,
            "duration_bars": exit_bar_idx - first_bar,
            "partial": True,
            "portion": portion,
        }

    def close_position(
        self,
        direction: str,
        exit_price: float,
        exit_bar_idx: int,
        exit_time: datetime,
        exit_reason: str,
        taker_fee: float = 0.0,
    ) -> list[dict]:
        """
        Закрыть позицию по правилу close_rule.

        При TP/SL всегда закрываются ВСЕ входы (TV поведение).
        При сигнальном выходе применяется close_rule.

        Returns:
            Список закрытых trades (словарей с данными для TradeRecord)
        """
        pos = self.get_position(direction)
        if not pos.is_open:
            return []

        trades = []

        # Save entry_count before closing (entries will be cleared)
        entry_count_before_close = pos.entry_count

        # TP/SL всегда закрывает ВСЕ входы
        if exit_reason in ("take_profit", "stop_loss", "end_of_data"):
            # Закрыть все сразу
            avg_price, total_size, total_allocated, first_bar, first_time = pos.close_all()

            # Рассчитать P&L
            if direction == "long":
                pnl_pct = (exit_price - avg_price) / avg_price
            else:
                pnl_pct = (avg_price - exit_price) / avg_price

            gross_pnl = (
                total_size * (exit_price - avg_price) if direction == "long" else total_size * (avg_price - exit_price)
            )
            # TradingView-совместимый расчёт комиссий: entry_fee + exit_fee
            entry_fee = total_size * avg_price * taker_fee
            exit_fee = total_size * exit_price * taker_fee
            fees = entry_fee + exit_fee
            net_pnl = gross_pnl - fees

            trades.append(
                {
                    "entry_time": first_time,
                    "exit_time": exit_time,
                    "direction": direction,
                    "entry_price": avg_price,
                    "exit_price": exit_price,
                    "size": total_size,
                    "allocated": total_allocated,
                    "pnl": net_pnl,
                    "pnl_pct": pnl_pct,
                    "fees": fees,
                    "exit_reason": exit_reason,
                    "duration_bars": exit_bar_idx - first_bar,
                    "entry_count": entry_count_before_close,
                }
            )

        elif self.close_rule == "ALL":
            # Закрыть все сразу
            avg_price, total_size, total_allocated, first_bar, first_time = pos.close_all()

            if direction == "long":
                pnl_pct = (exit_price - avg_price) / avg_price
            else:
                pnl_pct = (avg_price - exit_price) / avg_price

            gross_pnl = (
                total_size * (exit_price - avg_price) if direction == "long" else total_size * (avg_price - exit_price)
            )
            # TradingView-совместимый расчёт комиссий: entry_fee + exit_fee
            entry_fee = total_size * avg_price * taker_fee
            exit_fee = total_size * exit_price * taker_fee
            fees = entry_fee + exit_fee
            net_pnl = gross_pnl - fees

            trades.append(
                {
                    "entry_time": first_time,
                    "exit_time": exit_time,
                    "direction": direction,
                    "entry_price": avg_price,
                    "exit_price": exit_price,
                    "size": total_size,
                    "allocated": total_allocated,
                    "pnl": net_pnl,
                    "pnl_pct": pnl_pct,
                    "fees": fees,
                    "exit_reason": exit_reason,
                    "duration_bars": exit_bar_idx - first_bar,
                }
            )

        elif self.close_rule == "FIFO":
            # Закрыть первый вход
            entry = pos.close_fifo()
            if entry:
                if direction == "long":
                    pnl_pct = (exit_price - entry.entry_price) / entry.entry_price
                else:
                    pnl_pct = (entry.entry_price - exit_price) / entry.entry_price

                gross_pnl = (
                    entry.size * (exit_price - entry.entry_price)
                    if direction == "long"
                    else entry.size * (entry.entry_price - exit_price)
                )
                # TradingView-совместимый расчёт комиссий: entry_fee + exit_fee
                entry_fee = entry.size * entry.entry_price * taker_fee
                exit_fee = entry.size * exit_price * taker_fee
                fees = entry_fee + exit_fee
                net_pnl = gross_pnl - fees

                trades.append(
                    {
                        "entry_time": entry.entry_time,
                        "exit_time": exit_time,
                        "direction": direction,
                        "entry_price": entry.entry_price,
                        "exit_price": exit_price,
                        "size": entry.size,
                        "allocated": entry.allocated_capital,
                        "pnl": net_pnl,
                        "pnl_pct": pnl_pct,
                        "fees": fees,
                        "exit_reason": exit_reason,
                        "duration_bars": exit_bar_idx - entry.entry_bar_idx,
                    }
                )

        elif self.close_rule == "LIFO":
            # Закрыть последний вход
            entry = pos.close_lifo()
            if entry:
                if direction == "long":
                    pnl_pct = (exit_price - entry.entry_price) / entry.entry_price
                else:
                    pnl_pct = (entry.entry_price - exit_price) / entry.entry_price

                gross_pnl = (
                    entry.size * (exit_price - entry.entry_price)
                    if direction == "long"
                    else entry.size * (entry.entry_price - exit_price)
                )
                # TradingView-совместимый расчёт комиссий: entry_fee + exit_fee
                entry_fee = entry.size * entry.entry_price * taker_fee
                exit_fee = entry.size * exit_price * taker_fee
                fees = entry_fee + exit_fee
                net_pnl = gross_pnl - fees

                trades.append(
                    {
                        "entry_time": entry.entry_time,
                        "exit_time": exit_time,
                        "direction": direction,
                        "entry_price": entry.entry_price,
                        "exit_price": exit_price,
                        "size": entry.size,
                        "allocated": entry.allocated_capital,
                        "pnl": net_pnl,
                        "pnl_pct": pnl_pct,
                        "fees": fees,
                        "exit_reason": exit_reason,
                        "duration_bars": exit_bar_idx - entry.entry_bar_idx,
                    }
                )

        return trades

    def reset(self):
        """Сброс всех позиций"""
        self.long_position = PyramidPosition(direction="long")
        self.short_position = PyramidPosition(direction="short")
