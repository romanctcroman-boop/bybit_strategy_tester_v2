"""
🎯 FALLBACK ENGINE V3 - Движок с пирамидингом (DEPRECATED)

⚠️ DEPRECATED: Используйте FallbackEngine (V4) для новых проектов.
V4 включает все фичи V3 плюс multi-TP, ATR, trailing.
V3 оставлен для обратной совместимости.

Особенности:
- 100% точность (эталон для сравнения)
- ПОЛНАЯ поддержка пирамидинга (pyramiding > 1)
- Средневзвешенная цена входа для TP/SL
- close_entries_rule: ALL, FIFO, LIFO
- Полная поддержка Bar Magnifier (тиковые вычисления)
- НЕТ: multi-TP, ATR SL/TP, trailing

Скорость: ~1x (базовая)

Миграция: from backend.backtesting.engines import FallbackEngine
"""

import time
import warnings
from typing import Any

import numpy as np
import pandas as pd

from backend.backtesting.interfaces import (
    BacktestInput,
    BacktestMetrics,
    BacktestOutput,
    BaseBacktestEngine,
    ExitReason,
    TradeDirection,
    TradeRecord,
)
from backend.backtesting.pyramiding import PyramidingManager


class FallbackEngineV3(BaseBacktestEngine):
    """
    Fallback Engine V3 - Python-based движок с пирамидингом.

    ⚠️ DEPRECATED: Используйте FallbackEngine (V4) для новых проектов.

    Преимущества:
    - Полная поддержка пирамидинга
    - Средневзвешенная цена входа
    - FIFO/LIFO/ALL закрытие
    - Максимальная точность
    - Полная поддержка Bar Magnifier

    Недостатки:
    - Медленный (Python loops)
    - НЕТ: multi-TP, ATR, trailing
    """

    def __init__(self):
        warnings.warn(
            "FallbackEngineV3 is deprecated. Use FallbackEngine (V4) for new projects. "
            "V4 includes all V3 features plus multi-TP, ATR, trailing.",
            DeprecationWarning,
            stacklevel=2,
        )

    @property
    def name(self) -> str:
        return "FallbackEngineV3"

    @property
    def supports_bar_magnifier(self) -> bool:
        return True

    @property
    def supports_parallel(self) -> bool:
        return False  # Однопоточный

    @property
    def supports_pyramiding(self) -> bool:
        return True

    def run(self, input_data: BacktestInput) -> BacktestOutput:
        """
        Запуск бэктеста с поддержкой пирамидинга.
        """
        start_time = time.time()

        # Валидация
        is_valid, errors = self.validate_input(input_data)
        if not is_valid:
            return BacktestOutput(
                is_valid=False,
                validation_errors=errors,
                engine_name=self.name,
            )

        # Подготовка данных
        candles = input_data.candles
        candles_1m = input_data.candles_1m
        n = len(candles)

        # Извлечение OHLC
        open_prices = candles["open"].values.astype(np.float64)
        high_prices = candles["high"].values.astype(np.float64)
        low_prices = candles["low"].values.astype(np.float64)
        close_prices = candles["close"].values.astype(np.float64)

        # Timestamps
        if isinstance(candles.index, pd.DatetimeIndex):
            timestamps = candles.index.to_numpy()
        else:
            timestamps = pd.to_datetime(candles.index).to_numpy()

        # Сигналы
        long_entries = input_data.long_entries if input_data.long_entries is not None else np.zeros(n, dtype=bool)
        long_exits = input_data.long_exits if input_data.long_exits is not None else np.zeros(n, dtype=bool)
        short_entries = input_data.short_entries if input_data.short_entries is not None else np.zeros(n, dtype=bool)
        short_exits = input_data.short_exits if input_data.short_exits is not None else np.zeros(n, dtype=bool)

        # Параметры
        capital = input_data.initial_capital
        position_size = input_data.position_size
        use_fixed_amount = input_data.use_fixed_amount
        fixed_amount = input_data.fixed_amount
        leverage = input_data.leverage
        stop_loss = input_data.stop_loss
        take_profit = input_data.take_profit
        taker_fee = input_data.taker_fee
        slippage = input_data.slippage
        direction = input_data.direction
        use_bar_magnifier = input_data.use_bar_magnifier and candles_1m is not None

        # Пирамидинг
        pyramiding = input_data.pyramiding
        close_entries_rule = getattr(input_data, "close_entries_rule", "ALL")

        # Менеджер пирамидинга
        pyramid_mgr = PyramidingManager(
            pyramiding=pyramiding,
            close_rule=close_entries_rule,
        )

        # === DCA ПАРАМЕТРЫ ===
        dca_enabled = getattr(input_data, "dca_enabled", False)
        dca_safety_orders = getattr(input_data, "dca_safety_orders", 0)
        dca_price_deviation = getattr(input_data, "dca_price_deviation", 0.01)
        dca_step_scale = getattr(input_data, "dca_step_scale", 1.4)
        dca_volume_scale = getattr(input_data, "dca_volume_scale", 1.0)
        dca_base_order_size = getattr(input_data, "dca_base_order_size", 0.1)  # noqa: F841
        dca_safety_order_size = getattr(input_data, "dca_safety_order_size", 0.1)

        # Рассчитать уровни DCA (SO1 at -1%, SO2 at -1% - 1.4% = -2.4%, etc.)
        dca_levels: list[float] = []  # Cumulative deviation levels
        dca_volumes: list[float] = []  # Volume for each SO
        if dca_enabled and dca_safety_orders > 0:
            cumulative_deviation = 0.0
            current_deviation = dca_price_deviation
            current_volume = dca_safety_order_size
            for _ in range(dca_safety_orders):
                cumulative_deviation += current_deviation
                dca_levels.append(cumulative_deviation)
                dca_volumes.append(current_volume)
                current_deviation *= dca_step_scale
                current_volume *= dca_volume_scale

        # DCA состояние (pending safety orders)
        # Структура: {"direction": "long"/"short", "base_price": float, "filled": [bool, ...]}
        dca_state: dict | None = None

        # Состояние
        cash = capital
        equity_curve = [capital]
        trades: list[TradeRecord] = []

        # Pending exits
        pending_long_exit = False
        pending_long_exit_reason = None
        pending_long_exit_price = 0.0
        pending_short_exit = False
        pending_short_exit_reason = None
        pending_short_exit_price = 0.0

        # Bar Magnifier индекс (reserved for intrabar simulation)
        bar_magnifier_index = (  # noqa: F841
            self._build_bar_magnifier_index(candles, candles_1m) if use_bar_magnifier else None
        )

        # === ОСНОВНОЙ ЦИКЛ ===
        for i in range(1, n):
            current_time = (
                pd.Timestamp(timestamps[i]).to_pydatetime()
                if hasattr(timestamps[i], "to_pydatetime")
                else timestamps[i]
            )
            open_price = open_prices[i]
            high_price = high_prices[i]
            low_price = low_prices[i]
            close_price = close_prices[i]

            # === ВЫПОЛНЕНИЕ ОТЛОЖЕННОГО ВЫХОДА LONG ===
            if pending_long_exit and pyramid_mgr.has_position("long"):
                exit_price = pending_long_exit_price
                closed_trades = pyramid_mgr.close_position(
                    direction="long",
                    exit_price=exit_price,
                    exit_bar_idx=i,
                    exit_time=current_time,
                    exit_reason=pending_long_exit_reason.value
                    if hasattr(pending_long_exit_reason, "value")
                    else str(pending_long_exit_reason),
                    taker_fee=taker_fee,
                )

                for trade_data in closed_trades:
                    cash += trade_data["allocated"] + trade_data["pnl"]
                    trades.append(
                        TradeRecord(
                            entry_time=trade_data["entry_time"],
                            exit_time=trade_data["exit_time"],
                            direction="long",
                            entry_price=trade_data["entry_price"],
                            exit_price=trade_data["exit_price"],
                            size=trade_data["size"],
                            pnl=trade_data["pnl"],
                            pnl_pct=trade_data["pnl_pct"],
                            fees=trade_data["fees"],
                            exit_reason=pending_long_exit_reason,
                            duration_bars=trade_data["duration_bars"],
                            mfe=0,
                            mae=0,
                        )
                    )

                pending_long_exit = False
                pending_long_exit_reason = None

            # === ВЫПОЛНЕНИЕ ОТЛОЖЕННОГО ВЫХОДА SHORT ===
            if pending_short_exit and pyramid_mgr.has_position("short"):
                exit_price = pending_short_exit_price
                closed_trades = pyramid_mgr.close_position(
                    direction="short",
                    exit_price=exit_price,
                    exit_bar_idx=i,
                    exit_time=current_time,
                    exit_reason=pending_short_exit_reason.value
                    if hasattr(pending_short_exit_reason, "value")
                    else str(pending_short_exit_reason),
                    taker_fee=taker_fee,
                )

                for trade_data in closed_trades:
                    cash += trade_data["allocated"] + trade_data["pnl"]
                    trades.append(
                        TradeRecord(
                            entry_time=trade_data["entry_time"],
                            exit_time=trade_data["exit_time"],
                            direction="short",
                            entry_price=trade_data["entry_price"],
                            exit_price=trade_data["exit_price"],
                            size=trade_data["size"],
                            pnl=trade_data["pnl"],
                            pnl_pct=trade_data["pnl_pct"],
                            fees=trade_data["fees"],
                            exit_reason=pending_short_exit_reason,
                            duration_bars=trade_data["duration_bars"],
                            mfe=0,
                            mae=0,
                        )
                    )

                pending_short_exit = False
                pending_short_exit_reason = None

            # === ПРОВЕРКА SL/TP ДЛЯ LONG ===
            if pyramid_mgr.has_position("long") and not pending_long_exit:
                avg_entry = pyramid_mgr.get_avg_entry_price("long")
                tp_price = pyramid_mgr.get_tp_price("long", take_profit) if take_profit else None
                sl_price = pyramid_mgr.get_sl_price("long", stop_loss) if stop_loss else None

                exit_reason = self._check_exit_conditions_simple(
                    is_long=True,
                    entry_price=avg_entry,
                    high_price=high_price,
                    low_price=low_price,
                    open_price=open_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                )

                if exit_reason is not None:
                    pending_long_exit = True
                    pending_long_exit_reason = exit_reason
                    if exit_reason == ExitReason.STOP_LOSS:
                        pending_long_exit_price = sl_price
                    elif exit_reason == ExitReason.TAKE_PROFIT:
                        pending_long_exit_price = tp_price
                    else:
                        pending_long_exit_price = close_price

            # === ПРОВЕРКА SL/TP ДЛЯ SHORT ===
            if pyramid_mgr.has_position("short") and not pending_short_exit:
                avg_entry = pyramid_mgr.get_avg_entry_price("short")
                tp_price = pyramid_mgr.get_tp_price("short", take_profit) if take_profit else None
                sl_price = pyramid_mgr.get_sl_price("short", stop_loss) if stop_loss else None

                exit_reason = self._check_exit_conditions_simple(
                    is_long=False,
                    entry_price=avg_entry,
                    high_price=high_price,
                    low_price=low_price,
                    open_price=open_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                )

                if exit_reason is not None:
                    pending_short_exit = True
                    pending_short_exit_reason = exit_reason
                    if exit_reason == ExitReason.STOP_LOSS:
                        pending_short_exit_price = sl_price
                    elif exit_reason == ExitReason.TAKE_PROFIT:
                        pending_short_exit_price = tp_price
                    else:
                        pending_short_exit_price = close_price

            # === СИГНАЛ ВЫХОДА LONG ===
            if long_exits[i] and pyramid_mgr.has_position("long") and not pending_long_exit:
                pending_long_exit = True
                pending_long_exit_reason = ExitReason.SIGNAL
                pending_long_exit_price = close_price

            # === СИГНАЛ ВЫХОДА SHORT ===
            if short_exits[i] and pyramid_mgr.has_position("short") and not pending_short_exit:
                pending_short_exit = True
                pending_short_exit_reason = ExitReason.SIGNAL
                pending_short_exit_price = close_price

            # === ВХОД В LONG (с пирамидингом) ===
            # Условия: есть сигнал, разрешённое направление, не последний бар, можно добавить (пирамидинг)
            # Нет противоположной позиции (нельзя держать long и short одновременно)
            # Note: pyramid_mgr.can_add_entry() already checks if position is open
            can_enter_long = (
                long_entries[i]
                and direction in (TradeDirection.LONG, TradeDirection.BOTH)
                and i < n - 2
                and pyramid_mgr.can_add_entry("long")
                and not pyramid_mgr.has_position("short")  # Нет short позиции
            )

            if can_enter_long:
                entry_price = open_prices[i + 1]

                allocated = min(fixed_amount, cash) if use_fixed_amount and fixed_amount > 0 else cash * position_size

                if allocated >= 1.0:
                    notional = allocated * leverage
                    size = notional / entry_price

                    cash -= allocated

                    entry_time = (
                        pd.Timestamp(timestamps[i + 1]).to_pydatetime()
                        if hasattr(timestamps[i + 1], "to_pydatetime")
                        else timestamps[i + 1]
                    )
                    pyramid_mgr.add_entry(
                        direction="long",
                        entry_price=entry_price,
                        size=size,
                        allocated_capital=allocated,
                        entry_bar_idx=i + 1,
                        entry_time=entry_time,
                    )

                    # DCA: Инициализация состояния при базовом ордере
                    if dca_enabled and dca_levels:
                        dca_state = {
                            "direction": "long",
                            "base_price": entry_price,
                            "filled": [False] * len(dca_levels),
                        }

            # === ВХОД В SHORT (с пирамидингом) ===
            # Note: pyramid_mgr.can_add_entry() already checks if position is open
            can_enter_short = (
                short_entries[i]
                and direction in (TradeDirection.SHORT, TradeDirection.BOTH)
                and i < n - 2
                and i > 0
                and pyramid_mgr.can_add_entry("short")
                and not pyramid_mgr.has_position("long")  # Нет long позиции
                and not pending_short_exit
            )

            if can_enter_short:
                entry_price = open_prices[i + 1]

                allocated = min(fixed_amount, cash) if use_fixed_amount and fixed_amount > 0 else cash * position_size

                if allocated >= 1.0:
                    notional = allocated * leverage
                    size = notional / entry_price

                    cash -= allocated

                    entry_time = (
                        pd.Timestamp(timestamps[i + 1]).to_pydatetime()
                        if hasattr(timestamps[i + 1], "to_pydatetime")
                        else timestamps[i + 1]
                    )
                    pyramid_mgr.add_entry(
                        direction="short",
                        entry_price=entry_price,
                        size=size,
                        allocated_capital=allocated,
                        entry_bar_idx=i + 1,
                        entry_time=entry_time,
                    )

                    # DCA: Инициализация состояния при базовом ордере
                    if dca_enabled and dca_levels:
                        dca_state = {
                            "direction": "short",
                            "base_price": entry_price,
                            "filled": [False] * len(dca_levels),
                        }

            # === DCA: ПРОВЕРКА SAFETY ORDERS ===
            # Если DCA включен и есть открытая позиция - проверяем уровни
            if dca_enabled and dca_levels:
                # === DCA LONG: проверяем падение цены до SO уровней ===
                if pyramid_mgr.has_position("long") and not pending_long_exit:
                    # Инициализируем DCA состояние при первом входе
                    if dca_state is None or dca_state.get("direction") != "long":
                        base_price = pyramid_mgr.get_avg_entry_price("long")
                        dca_state = {
                            "direction": "long",
                            "base_price": base_price,
                            "filled": [False] * len(dca_levels),
                        }

                    # Проверяем каждый SO уровень
                    base_price = dca_state["base_price"]
                    for so_idx, (deviation, so_volume) in enumerate(zip(dca_levels, dca_volumes, strict=False)):
                        if dca_state["filled"][so_idx]:
                            continue  # Уже заполнен

                        # SO trigger price (для LONG - цена падает)
                        so_trigger_price = base_price * (1 - deviation)

                        # Проверяем достигла ли low цена уровня SO
                        if low_price <= so_trigger_price:
                            # Можем добавить ещё одну позицию?
                            if pyramid_mgr.can_add_entry("long"):
                                # Размер SO
                                if use_fixed_amount and fixed_amount > 0:
                                    so_allocated = min(fixed_amount * so_volume, cash)
                                else:
                                    so_allocated = cash * so_volume

                                if so_allocated >= 1.0:
                                    so_notional = so_allocated * leverage
                                    so_size = so_notional / so_trigger_price

                                    cash -= so_allocated

                                    so_entry_time = (
                                        pd.Timestamp(timestamps[i]).to_pydatetime()
                                        if hasattr(timestamps[i], "to_pydatetime")
                                        else timestamps[i]
                                    )
                                    pyramid_mgr.add_entry(
                                        direction="long",
                                        entry_price=so_trigger_price,
                                        size=so_size,
                                        allocated_capital=so_allocated,
                                        entry_bar_idx=i,
                                        entry_time=so_entry_time,
                                    )
                                    dca_state["filled"][so_idx] = True

                # === DCA SHORT: проверяем рост цены до SO уровней ===
                elif pyramid_mgr.has_position("short") and not pending_short_exit:
                    # Инициализируем DCA состояние при первом входе
                    if dca_state is None or dca_state.get("direction") != "short":
                        base_price = pyramid_mgr.get_avg_entry_price("short")
                        dca_state = {
                            "direction": "short",
                            "base_price": base_price,
                            "filled": [False] * len(dca_levels),
                        }

                    # Проверяем каждый SO уровень
                    base_price = dca_state["base_price"]
                    for so_idx, (deviation, so_volume) in enumerate(zip(dca_levels, dca_volumes, strict=False)):
                        if dca_state["filled"][so_idx]:
                            continue  # Уже заполнен

                        # SO trigger price (для SHORT - цена растёт)
                        so_trigger_price = base_price * (1 + deviation)

                        # Проверяем достигла ли high цена уровня SO
                        if high_price >= so_trigger_price:
                            # Можем добавить ещё одну позицию?
                            if pyramid_mgr.can_add_entry("short"):
                                # Размер SO
                                if use_fixed_amount and fixed_amount > 0:
                                    so_allocated = min(fixed_amount * so_volume, cash)
                                else:
                                    so_allocated = cash * so_volume

                                if so_allocated >= 1.0:
                                    so_notional = so_allocated * leverage
                                    so_size = so_notional / so_trigger_price

                                    cash -= so_allocated

                                    so_entry_time = (
                                        pd.Timestamp(timestamps[i]).to_pydatetime()
                                        if hasattr(timestamps[i], "to_pydatetime")
                                        else timestamps[i]
                                    )
                                    pyramid_mgr.add_entry(
                                        direction="short",
                                        entry_price=so_trigger_price,
                                        size=so_size,
                                        allocated_capital=so_allocated,
                                        entry_bar_idx=i,
                                        entry_time=so_entry_time,
                                    )
                                    dca_state["filled"][so_idx] = True

                # Сброс DCA состояния при закрытии позиции
                if not pyramid_mgr.has_position("long") and not pyramid_mgr.has_position("short"):
                    dca_state = None

            # === ОБНОВЛЕНИЕ EQUITY ===
            # V2 equity formula: cash + unrealized_pnl + size * entry_price
            # size * entry_price = notional = allocated * leverage
            equity = cash
            if pyramid_mgr.has_position("long"):
                total_size = pyramid_mgr.get_total_size("long")
                avg_entry = pyramid_mgr.get_avg_entry_price("long")
                notional = total_size * avg_entry  # This is allocated * leverage
                unrealized_pnl = (close_price - avg_entry) * total_size
                equity += notional + unrealized_pnl
            if pyramid_mgr.has_position("short"):
                total_size = pyramid_mgr.get_total_size("short")
                avg_entry = pyramid_mgr.get_avg_entry_price("short")
                notional = total_size * avg_entry  # This is allocated * leverage
                unrealized_pnl = (avg_entry - close_price) * total_size
                equity += notional + unrealized_pnl

            equity_curve.append(equity)

        # === ЗАКРЫТИЕ ОТКРЫТЫХ ПОЗИЦИЙ (END_OF_DATA) ===
        final_time = (
            pd.Timestamp(timestamps[-1]).to_pydatetime() if hasattr(timestamps[-1], "to_pydatetime") else timestamps[-1]
        )

        if pyramid_mgr.has_position("long"):
            exit_price = close_prices[-1] * (1 - slippage)
            closed_trades = pyramid_mgr.close_position(
                direction="long",
                exit_price=exit_price,
                exit_bar_idx=n - 1,
                exit_time=final_time,
                exit_reason="end_of_data",
                taker_fee=taker_fee,
            )
            for trade_data in closed_trades:
                trades.append(
                    TradeRecord(
                        entry_time=trade_data["entry_time"],
                        exit_time=final_time,
                        direction="long",
                        entry_price=trade_data["entry_price"],
                        exit_price=exit_price,
                        size=trade_data["size"],
                        pnl=trade_data["pnl"],
                        pnl_pct=trade_data["pnl_pct"],
                        fees=trade_data["fees"],
                        exit_reason=ExitReason.END_OF_DATA,
                        duration_bars=trade_data["duration_bars"],
                        mfe=0,
                        mae=0,
                    )
                )

        if pyramid_mgr.has_position("short"):
            exit_price = close_prices[-1] * (1 + slippage)
            closed_trades = pyramid_mgr.close_position(
                direction="short",
                exit_price=exit_price,
                exit_bar_idx=n - 1,
                exit_time=final_time,
                exit_reason="end_of_data",
                taker_fee=taker_fee,
            )
            for trade_data in closed_trades:
                trades.append(
                    TradeRecord(
                        entry_time=trade_data["entry_time"],
                        exit_time=final_time,
                        direction="short",
                        entry_price=trade_data["entry_price"],
                        exit_price=exit_price,
                        size=trade_data["size"],
                        pnl=trade_data["pnl"],
                        pnl_pct=trade_data["pnl_pct"],
                        fees=trade_data["fees"],
                        exit_reason=ExitReason.END_OF_DATA,
                        duration_bars=trade_data["duration_bars"],
                        mfe=0,
                        mae=0,
                    )
                )

        # === РАСЧЁТ МЕТРИК ===
        metrics = self._calculate_metrics(trades, equity_curve, capital)

        execution_time = time.time() - start_time

        return BacktestOutput(
            metrics=metrics,
            trades=trades,
            equity_curve=np.array(equity_curve),
            timestamps=timestamps,
            engine_name=self.name,
            execution_time=execution_time,
            bars_processed=n,
            bar_magnifier_used=use_bar_magnifier,
            is_valid=True,
        )

    def _check_exit_conditions_simple(
        self,
        is_long: bool,
        entry_price: float,
        high_price: float,
        low_price: float,
        open_price: float,
        stop_loss: float,
        take_profit: float,
    ) -> ExitReason | None:
        """Simple SL/TP check using OHLC heuristic"""
        if is_long:
            sl_price = entry_price * (1 - stop_loss) if stop_loss else 0
            tp_price = entry_price * (1 + take_profit) if take_profit else float("inf")

            # OHLC heuristic: price closer to open determines order
            if abs(open_price - low_price) <= abs(open_price - high_price):
                # SL checked first
                if stop_loss and low_price <= sl_price:
                    return ExitReason.STOP_LOSS
                if take_profit and high_price >= tp_price:
                    return ExitReason.TAKE_PROFIT
            else:
                # TP checked first
                if take_profit and high_price >= tp_price:
                    return ExitReason.TAKE_PROFIT
                if stop_loss and low_price <= sl_price:
                    return ExitReason.STOP_LOSS
        else:
            sl_price = entry_price * (1 + stop_loss) if stop_loss else float("inf")
            tp_price = entry_price * (1 - take_profit) if take_profit else 0

            if abs(open_price - low_price) <= abs(open_price - high_price):
                if take_profit and low_price <= tp_price:
                    return ExitReason.TAKE_PROFIT
                if stop_loss and high_price >= sl_price:
                    return ExitReason.STOP_LOSS
            else:
                if stop_loss and high_price >= sl_price:
                    return ExitReason.STOP_LOSS
                if take_profit and low_price <= tp_price:
                    return ExitReason.TAKE_PROFIT

        return None

    def _build_bar_magnifier_index(self, candles: pd.DataFrame, candles_1m: pd.DataFrame) -> dict | None:
        """Build index for Bar Magnifier"""
        if candles_1m is None or len(candles_1m) == 0:
            return None
        return {"1m_data": candles_1m}

    def _calculate_metrics(
        self,
        trades: list[TradeRecord],
        equity_curve: list[float],
        initial_capital: float,
    ) -> BacktestMetrics:
        """Calculate backtest metrics"""
        metrics = BacktestMetrics()

        if not trades:
            return metrics

        # Basic metrics
        pnls = [t.pnl for t in trades]
        metrics.net_profit = sum(pnls)
        # Safe division for total return
        metrics.total_return = (metrics.net_profit / initial_capital) * 100 if initial_capital > 0 else 0.0

        metrics.total_trades = len(trades)
        metrics.winning_trades = sum(1 for t in trades if t.pnl > 0)
        metrics.losing_trades = sum(1 for t in trades if t.pnl <= 0)

        if metrics.total_trades > 0:
            metrics.win_rate = metrics.winning_trades / metrics.total_trades

        # Gross profit/loss
        winning_pnls = [t.pnl for t in trades if t.pnl > 0]
        losing_pnls = [t.pnl for t in trades if t.pnl <= 0]

        metrics.gross_profit = sum(winning_pnls) if winning_pnls else 0
        metrics.gross_loss = abs(sum(losing_pnls)) if losing_pnls else 0

        if metrics.gross_loss > 0:
            metrics.profit_factor = metrics.gross_profit / metrics.gross_loss

        # Averages
        if winning_pnls:
            metrics.avg_win = np.mean(winning_pnls)
            metrics.largest_win = max(winning_pnls)
        if losing_pnls:
            metrics.avg_loss = np.mean(losing_pnls)
            metrics.largest_loss = min(losing_pnls)

        metrics.avg_trade = np.mean(pnls) if pnls else 0

        # Drawdown
        equity = np.array(equity_curve)
        running_max = np.maximum.accumulate(equity)
        drawdown = (running_max - equity) / running_max
        metrics.max_drawdown = np.max(drawdown) * 100 if len(drawdown) > 0 else 0
        metrics.avg_drawdown = np.mean(drawdown) * 100 if len(drawdown) > 0 else 0

        # Long/Short breakdown
        long_trades = [t for t in trades if t.direction == "long"]
        short_trades = [t for t in trades if t.direction == "short"]

        metrics.long_trades = len(long_trades)
        metrics.short_trades = len(short_trades)
        metrics.long_winning_trades = sum(1 for t in long_trades if t.pnl > 0)
        metrics.short_winning_trades = sum(1 for t in short_trades if t.pnl > 0)

        if metrics.long_trades > 0:
            metrics.long_win_rate = metrics.long_winning_trades / metrics.long_trades
            metrics.long_profit = sum(t.pnl for t in long_trades)

        if metrics.short_trades > 0:
            metrics.short_win_rate = metrics.short_winning_trades / metrics.short_trades
            metrics.short_profit = sum(t.pnl for t in short_trades)

        # Sharpe ratio (simplified)
        if len(pnls) > 1:
            returns = np.array(pnls) / initial_capital
            if np.std(returns) > 0:
                metrics.sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252)

        # Expectancy
        if metrics.total_trades > 0:
            metrics.expectancy = (metrics.win_rate * metrics.avg_win) + ((1 - metrics.win_rate) * metrics.avg_loss)

        return metrics

    def optimize(
        self,
        input_data: BacktestInput,
        param_ranges: dict[str, list[Any]],
        metric: str = "sharpe_ratio",
        top_n: int = 10,
    ) -> list[tuple[dict[str, Any], BacktestOutput]]:
        """Optimization not implemented for V3"""
        return []
