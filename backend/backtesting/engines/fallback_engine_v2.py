"""
🎯 FALLBACK ENGINE V2 - Базовый движок (DEPRECATED)

⚠️ DEPRECATED: Используйте FallbackEngine (V4) для новых проектов.
V2 оставлен для обратной совместимости и паритет-тестов.

Особенности:
- 100% точность (эталон для сравнения)
- Полная поддержка Bar Magnifier (тиковые вычисления)
- SL/TP с High/Low внутри бара
- Все метрики
- НЕТ: pyramiding, multi-TP, ATR SL/TP, trailing

Скорость: ~1x (базовая)

Миграция: from backend.backtesting.engines import FallbackEngine
"""

import time
import warnings
from typing import Any

import numpy as np
import pandas as pd

from backend.backtesting.formulas import (
    calc_sharpe_monthly_tv,
    calc_sortino_monthly_tv,
)
from backend.backtesting.interfaces import (
    BacktestInput,
    BacktestMetrics,
    BacktestOutput,
    BaseBacktestEngine,
    ExitReason,
    TradeDirection,
    TradeRecord,
)


class FallbackEngineV2(BaseBacktestEngine):
    """
    Fallback Engine V2 - Базовый Python-based движок.

    ⚠️ DEPRECATED: Используйте FallbackEngine (V4) для новых проектов.

    Преимущества:
    - Максимальная точность
    - Полная поддержка Bar Magnifier
    - Детальное логирование
    - Легко отлаживать

    Недостатки:
    - Медленный (Python loops)
    - НЕТ: pyramiding, multi-TP, ATR, trailing
    """

    def __init__(self):
        warnings.warn(
            "FallbackEngineV2 is deprecated. Use FallbackEngine (V4) for new projects. "
            "V2 is kept for backward compatibility and parity tests.",
            DeprecationWarning,
            stacklevel=2,
        )

    @property
    def name(self) -> str:
        return "FallbackEngineV2"

    @property
    def supports_bar_magnifier(self) -> bool:
        return True

    @property
    def supports_parallel(self) -> bool:
        return False  # Однопоточный

    def run(self, input_data: BacktestInput) -> BacktestOutput:
        """
        Запуск бэктеста.
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

        # Timestamps - приоритет отдаём колонке 'timestamp', затем индексу
        if "timestamp" in candles.columns:
            timestamps = pd.to_datetime(candles["timestamp"]).to_numpy()
        elif isinstance(candles.index, pd.DatetimeIndex):
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

        # Состояние
        cash = capital
        equity_curve = [capital]
        trades: list[TradeRecord] = []

        # Позиции
        in_long = False
        in_short = False
        long_entry_price = 0.0
        short_entry_price = 0.0
        long_entry_idx = 0
        long_entry_exec_idx = 0  # Execution bar index (i+1), for entry_time display
        short_entry_idx = 0
        short_entry_exec_idx = 0  # Execution bar index (i+1), for entry_time display
        long_size = 0.0
        short_size = 0.0
        long_allocated = 0.0  # Сколько выделено на long позицию
        short_allocated = 0.0  # Сколько выделено на short позицию

        # MFE/MAE accumulation for Bar Magnifier mode (tracks max excursion during position lifetime)
        long_accumulated_mfe = 0.0  # Maximum favorable excursion (best unrealized profit)
        long_accumulated_mae = 0.0  # Maximum adverse excursion (worst unrealized loss)
        short_accumulated_mfe = 0.0
        short_accumulated_mae = 0.0

        # TV-style pending exit (exit on next candle after TP/SL trigger)
        pending_long_exit = False
        pending_long_exit_reason = None
        pending_long_exit_price = 0.0
        # Values saved when pending is set (for trade recording on next bar)
        pending_long_pnl = 0.0
        pending_long_pnl_pct = 0.0
        pending_long_fees = 0.0
        pending_long_size = 0.0
        pending_long_entry_idx = 0
        pending_long_entry_exec_idx = 0  # Execution bar (i+1), used for entry_time display
        pending_long_entry_price_saved = 0.0
        pending_long_mfe = 0.0
        pending_long_mae = 0.0

        pending_short_exit = False
        pending_short_exit_reason = None
        pending_short_exit_price = 0.0
        # Values saved when pending is set (for trade recording on next bar)
        pending_short_pnl = 0.0
        pending_short_pnl_pct = 0.0
        pending_short_fees = 0.0
        pending_short_size = 0.0
        pending_short_entry_idx = 0
        pending_short_entry_exec_idx = 0  # Execution bar (i+1), used for entry_time display
        pending_short_entry_price_saved = 0.0
        pending_short_mfe = 0.0
        pending_short_mae = 0.0

        # Bar Magnifier индекс (для 1m данных)
        bar_magnifier_index = self._build_bar_magnifier_index(candles, candles_1m) if use_bar_magnifier else None

        # === ОСНОВНОЙ ЦИКЛ ===
        for i in range(1, n):
            current_time = timestamps[i]
            open_price = open_prices[i]
            high_price = high_prices[i]
            low_price = low_prices[i]
            close_price = close_prices[i]

            # TV-style: No entry on same bar as exit (prevents TP/SL → immediate re-entry)
            exited_this_bar = False

            # === ВЫПОЛНЕНИЕ ОТЛОЖЕННОГО ВЫХОДА (TV-style: record on next candle) ===
            # Long pending exit (in_long cleared at trigger time, so just check pending flag)
            # NOTE: Cash was already updated when pending was set (for equity parity)
            if pending_long_exit:
                # Use saved values from when pending was set
                trades.append(
                    TradeRecord(
                        entry_time=timestamps[pending_long_entry_exec_idx],
                        exit_time=current_time,  # Exit recorded at this candle's open
                        direction="long",
                        entry_price=pending_long_entry_price_saved,
                        exit_price=pending_long_exit_price,
                        size=pending_long_size,
                        pnl=pending_long_pnl,
                        pnl_pct=pending_long_pnl_pct,
                        fees=pending_long_fees,
                        exit_reason=pending_long_exit_reason,  # type: ignore[arg-type]
                        duration_bars=i - pending_long_entry_idx,
                        mfe=pending_long_mfe,
                        mae=pending_long_mae,
                        intrabar_sl_hit=False,
                        intrabar_tp_hit=False,
                    )
                )

                pending_long_exit = False
                pending_long_exit_reason = None
                # Reset accumulated values
                long_accumulated_mfe = 0.0
                long_accumulated_mae = 0.0

            # Short pending exit (in_short cleared at trigger time, so just check pending flag)
            # NOTE: Cash was already updated when pending was set (for equity parity)
            if pending_short_exit:
                # Use saved values from when pending was set
                trades.append(
                    TradeRecord(
                        entry_time=timestamps[pending_short_entry_exec_idx],
                        exit_time=current_time,
                        direction="short",
                        entry_price=pending_short_entry_price_saved,
                        exit_price=pending_short_exit_price,
                        size=pending_short_size,
                        pnl=pending_short_pnl,
                        pnl_pct=pending_short_pnl_pct,
                        fees=pending_short_fees,
                        exit_reason=pending_short_exit_reason,  # type: ignore[arg-type]
                        duration_bars=i - pending_short_entry_idx,
                        mfe=pending_short_mfe,
                        mae=pending_short_mae,
                        intrabar_sl_hit=False,
                        intrabar_tp_hit=False,
                    )
                )

                pending_short_exit = False
                pending_short_exit_reason = None
                # Reset accumulated values
                short_accumulated_mfe = 0.0
                short_accumulated_mae = 0.0

            # === BAR MAGNIFIER: Accumulate MFE/MAE for open positions ===
            # When Bar Magnifier is enabled, track max excursion using 1m data
            # NOTE: This MUST happen BEFORE exit condition checks so we capture the bar's data
            if use_bar_magnifier and bar_magnifier_index and i in bar_magnifier_index:
                start_idx, end_idx = bar_magnifier_index[i]  # type: ignore[index, misc]
                m1_highs = candles_1m["high"].values[start_idx:end_idx]  # type: ignore[index]
                m1_lows = candles_1m["low"].values[start_idx:end_idx]  # type: ignore[index]

                # Accumulate for Long position
                if in_long and long_size > 0:
                    for m1_high, m1_low in zip(m1_highs, m1_lows, strict=False):
                        # MFE: max favorable excursion (high - entry for long)
                        current_mfe = max(0, (m1_high - long_entry_price) * long_size)
                        long_accumulated_mfe = max(long_accumulated_mfe, current_mfe)
                        # MAE: max adverse excursion (entry - low for long)
                        current_mae = max(0, (long_entry_price - m1_low) * long_size)
                        long_accumulated_mae = max(long_accumulated_mae, current_mae)

                # Accumulate for Short position
                if in_short and short_size > 0:
                    for m1_high, m1_low in zip(m1_highs, m1_lows, strict=False):
                        # MFE: max favorable excursion (entry - low for short)
                        current_mfe = max(0, (short_entry_price - m1_low) * short_size)
                        short_accumulated_mfe = max(short_accumulated_mfe, current_mfe)
                        # MAE: max adverse excursion (high - entry for short)
                        current_mae = max(0, (m1_high - short_entry_price) * short_size)
                        short_accumulated_mae = max(short_accumulated_mae, current_mae)
            else:
                # === STANDARD MODE: Accumulate MFE/MAE using HTF High/Low ===
                # When Bar Magnifier is disabled, use the current bar's High/Low
                # Accumulate for Long position
                if in_long and long_size > 0:
                    current_mfe = max(0, (high_price - long_entry_price) * long_size)
                    long_accumulated_mfe = max(long_accumulated_mfe, current_mfe)
                    current_mae = max(0, (long_entry_price - low_price) * long_size)
                    long_accumulated_mae = max(long_accumulated_mae, current_mae)

                # Accumulate for Short position
                if in_short and short_size > 0:
                    current_mfe = max(0, (short_entry_price - low_price) * short_size)
                    short_accumulated_mfe = max(short_accumulated_mfe, current_mfe)
                    current_mae = max(0, (high_price - short_entry_price) * short_size)
                    short_accumulated_mae = max(short_accumulated_mae, current_mae)

            # === ПРОВЕРКА УСЛОВИЙ ВЫХОДА (TV-style: set pending, execute next bar) ===
            # Check Long exit conditions
            if in_long and not pending_long_exit:
                exit_reason, _ = self._check_exit_conditions(
                    is_long=True,
                    entry_price=long_entry_price,
                    open_price=open_price,  # For TV intrabar simulation
                    high=high_price,
                    low=low_price,
                    close=close_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    signal_exit=long_exits[i],
                    slippage=slippage,
                    use_bar_magnifier=use_bar_magnifier,
                    bar_magnifier_index=bar_magnifier_index,
                    bar_idx=i,
                    candles_1m=candles_1m,
                )

                if exit_reason is not None:
                    # Mark for exit on next bar (TV behavior)
                    pending_long_exit = True
                    pending_long_exit_reason = exit_reason
                    # Calculate exit price (SL/TP level)
                    if exit_reason == ExitReason.STOP_LOSS:
                        pending_long_exit_price = long_entry_price * (1 - stop_loss)
                    elif exit_reason == ExitReason.TAKE_PROFIT:
                        pending_long_exit_price = long_entry_price * (1 + take_profit)
                    else:
                        pending_long_exit_price = close_price

                    # FIXED: Calculate PnL and update cash IMMEDIATELY (for equity parity)
                    # Trade will still be recorded on next bar
                    pending_long_pnl, pending_long_pnl_pct, pending_long_fees = self._calculate_pnl(
                        is_long=True,
                        entry_price=long_entry_price,
                        exit_price=pending_long_exit_price,
                        size=long_size,
                        taker_fee=taker_fee,
                    )
                    # Update cash immediately
                    cash += long_allocated + pending_long_pnl
                    # Store values for trade recording
                    pending_long_size = long_size
                    pending_long_entry_idx = long_entry_idx
                    pending_long_entry_exec_idx = min(long_entry_idx + 1, n - 1)  # Execution bar
                    pending_long_entry_price_saved = long_entry_price
                    pending_long_mfe = long_accumulated_mfe
                    pending_long_mae = long_accumulated_mae

                    # TV-style: immediately free position for new entry on same bar
                    in_long = False
                    long_allocated = 0.0  # Reset for new position
                    exited_this_bar = True  # Prevent new entry on same bar

            # Check Short exit conditions
            if in_short and not pending_short_exit:
                exit_reason, _ = self._check_exit_conditions(
                    is_long=False,
                    entry_price=short_entry_price,
                    open_price=open_price,  # For TV intrabar simulation
                    high=high_price,
                    low=low_price,
                    close=close_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    signal_exit=short_exits[i],
                    slippage=slippage,
                    use_bar_magnifier=use_bar_magnifier,
                    bar_magnifier_index=bar_magnifier_index,
                    bar_idx=i,
                    candles_1m=candles_1m,
                )

                if exit_reason is not None:
                    pending_short_exit = True
                    pending_short_exit_reason = exit_reason
                    # Calculate exit price (SL/TP level)
                    if exit_reason == ExitReason.STOP_LOSS:
                        pending_short_exit_price = short_entry_price * (1 + stop_loss)
                    elif exit_reason == ExitReason.TAKE_PROFIT:
                        pending_short_exit_price = short_entry_price * (1 - take_profit)
                    else:
                        pending_short_exit_price = close_price

                    # FIXED: Calculate PnL and update cash IMMEDIATELY (for equity parity)
                    # Trade will still be recorded on next bar
                    pending_short_pnl, pending_short_pnl_pct, pending_short_fees = self._calculate_pnl(
                        is_long=False,
                        entry_price=short_entry_price,
                        exit_price=pending_short_exit_price,
                        size=short_size,
                        taker_fee=taker_fee,
                    )
                    # Update cash immediately
                    cash += short_allocated + pending_short_pnl
                    # Store values for trade recording
                    pending_short_size = short_size
                    pending_short_entry_idx = short_entry_idx
                    pending_short_entry_exec_idx = min(short_entry_idx + 1, n - 1)  # Execution bar
                    pending_short_entry_price_saved = short_entry_price
                    pending_short_mfe = short_accumulated_mfe
                    pending_short_mae = short_accumulated_mae

                    # TV-style: immediately free position for new entry on same bar
                    in_short = False
                    short_allocated = 0.0  # Reset for new position
                    exited_this_bar = True  # Prevent new entry on same bar

            # === ВХОД В LONG ===
            # TradingView с TP/SL: новая позиция открывается ТОЛЬКО если нет открытых позиций
            # Skip entry on last bar (would immediately close as END_OF_DATA)
            # Note: pending_exit is NOT checked - TV allows new signal on same bar as TP/SL
            # TV-style: No entry on same bar as exit (exited_this_bar flag)
            if (
                not in_long
                and not in_short
                and not exited_this_bar  # TV-style: No entry on same bar as exit
                and long_entries[i]
                and direction in (TradeDirection.LONG, TradeDirection.BOTH)
                and i < n - 2
                and i > 0
            ):
                # TV entry: at open of NEXT candle after signal (i+1)
                entry_price = open_prices[i + 1]

                # TradingView-style: fixed USDT amount OR percentage of capital
                allocated = min(fixed_amount, cash) if use_fixed_amount and fixed_amount > 0 else cash * position_size

                # Skip if allocated is too small (prevents micro-positions)
                if allocated >= 1.0:
                    notional = allocated * leverage  # Notional value с leverage
                    size = notional / entry_price
                    # Entry fee will be deducted from PnL at exit (TV style)

                    cash -= allocated  # Вычитаем только выделенный капитал

                    in_long = True
                    long_entry_price = entry_price
                    long_entry_idx = i
                    long_entry_exec_idx = i + 1  # Execution bar (entry at open[i+1])
                    long_size = size
                    long_allocated = allocated
                    # Reset accumulated MFE/MAE for new position
                    long_accumulated_mfe = 0.0
                    long_accumulated_mae = 0.0

            # === ВХОД В SHORT ===
            # TradingView с TP/SL: новая позиция открывается ТОЛЬКО если нет открытых позиций
            # Skip entry on last bar (would immediately close as END_OF_DATA)
            # Note: pending_exit is NOT checked - TV allows new signal on same bar as TP/SL
            # TV-style: No entry on same bar as exit (exited_this_bar flag)
            if (
                not in_short
                and not in_long
                and not exited_this_bar  # TV-style: No entry on same bar as exit
                and short_entries[i]
                and direction in (TradeDirection.SHORT, TradeDirection.BOTH)
                and i < n - 2
                and i > 0
            ):
                # TV entry: at open of NEXT candle after signal (i+1)
                entry_price = open_prices[i + 1]

                # TradingView-style: fixed USDT amount OR percentage of capital
                allocated = min(fixed_amount, cash) if use_fixed_amount and fixed_amount > 0 else cash * position_size

                # Skip if allocated is too small (prevents micro-positions)
                if allocated >= 1.0:
                    notional = allocated * leverage
                    size = notional / entry_price
                    # Entry fee will be deducted from PnL at exit (TV style)

                    cash -= allocated  # Вычитаем только выделенный капитал

                    in_short = True
                    short_entry_price = entry_price
                    short_entry_idx = i
                    short_entry_exec_idx = i + 1  # Execution bar (entry at open[i+1])
                    short_size = size
                    short_allocated = allocated
                    # Reset accumulated MFE/MAE for new position
                    short_accumulated_mfe = 0.0
                    short_accumulated_mae = 0.0

            # === ОБНОВЛЕНИЕ EQUITY ===
            equity = cash
            if in_long:
                unrealized_pnl = (close_price - long_entry_price) * long_size
                equity += unrealized_pnl + long_size * long_entry_price
            if in_short:
                unrealized_pnl = (short_entry_price - close_price) * short_size
                equity += unrealized_pnl + short_size * short_entry_price

            equity_curve.append(equity)

        # === ЗАКРЫТИЕ ОТКРЫТЫХ ПОЗИЦИЙ ===
        if in_long:
            exit_price = close_prices[-1] * (1 - slippage)
            pnl, pnl_pct, fees = self._calculate_pnl(True, long_entry_price, exit_price, long_size, taker_fee)
            trades.append(
                TradeRecord(
                    entry_time=timestamps[long_entry_exec_idx],
                    exit_time=timestamps[-1],
                    direction="long",
                    entry_price=long_entry_price,
                    exit_price=exit_price,
                    size=long_size,
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                    fees=fees,
                    exit_reason=ExitReason.END_OF_DATA,
                    duration_bars=n - 1 - long_entry_idx,
                    mfe=0,
                    mae=0,
                )
            )

        if in_short:
            exit_price = close_prices[-1] * (1 + slippage)
            pnl, pnl_pct, fees = self._calculate_pnl(False, short_entry_price, exit_price, short_size, taker_fee)
            trades.append(
                TradeRecord(
                    entry_time=timestamps[short_entry_exec_idx],
                    exit_time=timestamps[-1],
                    direction="short",
                    entry_price=short_entry_price,
                    exit_price=exit_price,
                    size=short_size,
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                    fees=fees,
                    exit_reason=ExitReason.END_OF_DATA,
                    duration_bars=n - 1 - short_entry_idx,
                    mfe=0,
                    mae=0,
                )
            )

        # === РАСЧЁТ МЕТРИК ===
        equity_array = np.array(equity_curve)
        metrics = self._calculate_metrics(trades, equity_array, capital, candles_index=candles.index)

        execution_time = time.time() - start_time

        return BacktestOutput(
            metrics=metrics,
            trades=trades,
            equity_curve=equity_array,
            timestamps=timestamps,
            engine_name=self.name,
            execution_time=execution_time,
            bars_processed=n,
            bar_magnifier_used=use_bar_magnifier,
            is_valid=True,
        )

    def optimize(
        self,
        input_data: BacktestInput,
        param_ranges: dict[str, list[Any]],
        metric: str = "sharpe_ratio",
        top_n: int = 10,
    ) -> list[tuple[dict[str, Any], BacktestOutput]]:
        """Оптимизация (последовательная)"""
        from itertools import product

        results = []

        # Генерация всех комбинаций
        param_names = list(param_ranges.keys())
        param_values = list(param_ranges.values())

        for combo in product(*param_values):
            params = dict(zip(param_names, combo, strict=False))

            # Применяем параметры к input
            modified_input = self._apply_params(input_data, params)

            # Запуск бэктеста
            result = self.run(modified_input)

            if result.is_valid and result.metrics.total_trades > 0:
                results.append((params, result))

        # Сортировка по метрике
        results.sort(key=lambda x: getattr(x[1].metrics, metric, 0), reverse=True)

        return results[:top_n]

    def _build_bar_magnifier_index(self, candles: pd.DataFrame, candles_1m: pd.DataFrame) -> dict[int, tuple[int, int]]:
        """
        Построение индекса для Bar Magnifier.
        Возвращает словарь: bar_idx -> (start_1m_idx, end_1m_idx)
        """
        if candles_1m is None:
            return {}

        index = {}

        # Получаем timestamps - приоритет отдаём колонке 'timestamp', затем индексу
        if "timestamp" in candles.columns:
            bar_times = pd.to_datetime(candles["timestamp"])
        elif isinstance(candles.index, pd.DatetimeIndex):
            bar_times = candles.index
        else:
            bar_times = pd.to_datetime(candles.index)

        if "timestamp" in candles_1m.columns:
            m1_times = pd.to_datetime(candles_1m["timestamp"])
        elif isinstance(candles_1m.index, pd.DatetimeIndex):
            m1_times = candles_1m.index
        else:
            m1_times = pd.to_datetime(candles_1m.index)

        # Для каждого бара основного таймфрейма находим соответствующие 1m бары
        for i in range(len(candles)):
            bar_start = bar_times.iloc[i] if hasattr(bar_times, "iloc") else bar_times[i]
            bar_end = (
                bar_times.iloc[i + 1]
                if i + 1 < len(candles) and hasattr(bar_times, "iloc")
                else bar_times[i + 1]
                if i + 1 < len(candles)
                else bar_start + pd.Timedelta(hours=1)
            )

            # Найти 1m бары в этом диапазоне
            mask = (m1_times >= bar_start) & (m1_times < bar_end)
            matching_indices = np.where(mask)[0]

            if len(matching_indices) > 0:
                index[i] = (matching_indices[0], matching_indices[-1] + 1)

        return index

    def _check_exit_conditions(
        self,
        is_long: bool,
        entry_price: float,
        open_price: float,  # Added for TV intrabar simulation
        high: float,
        low: float,
        close: float,
        stop_loss: float,
        take_profit: float,
        signal_exit: bool,
        slippage: float,
        use_bar_magnifier: bool,
        bar_magnifier_index: dict | None,
        bar_idx: int,
        candles_1m: pd.DataFrame | None,
    ) -> tuple[ExitReason | None, float]:
        """
        Проверка условий выхода с поддержкой Bar Magnifier.

        TV Broker Emulator intrabar logic:
        - If open closer to high: order is open → high → low → close
        - If open closer to low: order is open → low → high → close

        Возвращает: (exit_reason, exit_price) или (None, 0)
        """
        if is_long:
            sl_price = entry_price * (1 - stop_loss) if stop_loss > 0 else 0
            tp_price = entry_price * (1 + take_profit) if take_profit > 0 else float("inf")
        else:
            sl_price = entry_price * (1 + stop_loss) if stop_loss > 0 else float("inf")
            tp_price = entry_price * (1 - take_profit) if take_profit > 0 else 0

        # === BAR MAGNIFIER: Точное определение порядка SL/TP ===
        if use_bar_magnifier and bar_magnifier_index and bar_idx in bar_magnifier_index:
            start_idx, end_idx = bar_magnifier_index[bar_idx]  # type: ignore[index, misc]
            m1_highs = candles_1m["high"].values[start_idx:end_idx]  # type: ignore[index]
            m1_lows = candles_1m["low"].values[start_idx:end_idx]  # type: ignore[index]

            for m1_high, m1_low in zip(m1_highs, m1_lows, strict=False):
                if is_long:
                    # Long: сначала проверяем SL (low), потом TP (high)
                    if sl_price > 0 and m1_low <= sl_price:
                        return ExitReason.STOP_LOSS, sl_price
                    if tp_price < float("inf") and m1_high >= tp_price:
                        return ExitReason.TAKE_PROFIT, tp_price
                else:
                    # Short: сначала проверяем SL (high), потом TP (low)
                    if sl_price < float("inf") and m1_high >= sl_price:
                        return ExitReason.STOP_LOSS, sl_price
                    if tp_price > 0 and m1_low <= tp_price:
                        return ExitReason.TAKE_PROFIT, tp_price

        # === FALLBACK: TV-style intrabar simulation based on open position ===
        # Determine check order based on where open is relative to high/low
        open_closer_to_high = abs(open_price - high) < abs(open_price - low)

        if is_long:
            # Long: SL triggers on low reaching sl_price, TP triggers on high reaching tp_price
            sl_hit = sl_price > 0 and low <= sl_price
            tp_hit = tp_price < float("inf") and high >= tp_price

            if sl_hit and tp_hit:
                # Both hit - check order based on open position
                if open_closer_to_high:
                    # Order: open → high → low → close
                    # TP (at high) checked before SL (at low)
                    return ExitReason.TAKE_PROFIT, tp_price
                else:
                    # Order: open → low → high → close
                    # SL (at low) checked before TP (at high)
                    return ExitReason.STOP_LOSS, sl_price
            elif sl_hit:
                return ExitReason.STOP_LOSS, sl_price
            elif tp_hit:
                return ExitReason.TAKE_PROFIT, tp_price
        else:
            # Short: SL triggers on high reaching sl_price, TP triggers on low reaching tp_price
            sl_hit = sl_price < float("inf") and high >= sl_price
            tp_hit = tp_price > 0 and low <= tp_price

            if sl_hit and tp_hit:
                # Both hit - check order based on open position
                if open_closer_to_high:
                    # Order: open → high → low → close
                    # SL (at high) checked before TP (at low)
                    return ExitReason.STOP_LOSS, sl_price
                else:
                    # Order: open → low → high → close
                    # TP (at low) checked before SL (at high)
                    return ExitReason.TAKE_PROFIT, tp_price
            elif sl_hit:
                return ExitReason.STOP_LOSS, sl_price
            elif tp_hit:
                return ExitReason.TAKE_PROFIT, tp_price

        # Сигнальный выход
        if signal_exit:
            exit_price = close
            return ExitReason.SIGNAL, exit_price

        return None, 0.0

    def _calculate_pnl(
        self,
        is_long: bool,
        entry_price: float,
        exit_price: float,
        size: float,
        taker_fee: float,
    ) -> tuple[float, float, float]:
        """Расчёт PnL, PnL%, и комиссий (entry + exit как в TV)"""
        pnl = (exit_price - entry_price) * size if is_long else (entry_price - exit_price) * size

        # TradingView считает комиссию на ОБЕИХ сторонах: entry + exit
        entry_value = entry_price * size
        exit_value = exit_price * size
        entry_fee = entry_value * taker_fee
        exit_fee = exit_value * taker_fee
        fees = entry_fee + exit_fee  # Total: entry + exit

        # TV вычитает ОБЕ комиссии из отображаемого PnL
        # entry_fee НЕ вычитается из cash при входе (изменим логику входа)
        pnl -= fees  # Вычитаем обе комиссии

        pnl_pct = pnl / (entry_price * size) * 100 if entry_price * size > 0 else 0

        return pnl, pnl_pct, fees

    def _calculate_mfe_mae(
        self,
        is_long: bool,
        entry_price: float,
        high: float,
        low: float,
        size: float,
    ) -> tuple[float, float]:
        """Расчёт Maximum Favorable/Adverse Excursion"""
        if is_long:
            mfe = (high - entry_price) * size
            mae = (entry_price - low) * size
        else:
            mfe = (entry_price - low) * size
            mae = (high - entry_price) * size

        return max(0, mfe), max(0, mae)

    def _calculate_metrics(
        self,
        trades: list[TradeRecord],
        equity_curve: np.ndarray,
        initial_capital: float,
        candles_index=None,
    ) -> BacktestMetrics:
        """Расчёт всех метрик"""
        metrics = BacktestMetrics()

        if len(trades) == 0:
            return metrics

        # Основные
        pnls = [t.pnl for t in trades]
        metrics.net_profit = sum(pnls)
        metrics.total_return = (equity_curve[-1] - initial_capital) / initial_capital * 100

        # Gross profit/loss
        metrics.gross_profit = sum(p for p in pnls if p > 0)
        metrics.gross_loss = abs(sum(p for p in pnls if p < 0))

        # Drawdown - calculate as percentage (consistent with other engines)
        peak = np.maximum.accumulate(equity_curve)
        drawdown_pct = (peak - equity_curve) / peak * 100
        drawdown_usdt = peak - equity_curve  # Absolute drawdown in USDT
        metrics.max_drawdown = float(np.max(drawdown_pct))  # Percentage for consistency
        metrics.max_drawdown_pct = float(np.max(drawdown_pct))  # Keep percentage version
        metrics.max_drawdown_usdt = float(np.max(drawdown_usdt))  # USDT version for display
        metrics.avg_drawdown = float(np.mean(drawdown_pct))

        # Trades
        metrics.total_trades = len(trades)
        metrics.winning_trades = sum(1 for t in trades if t.pnl > 0)
        metrics.losing_trades = sum(1 for t in trades if t.pnl < 0)
        metrics.win_rate = metrics.winning_trades / metrics.total_trades if metrics.total_trades > 0 else 0

        # Profit factor
        metrics.profit_factor = metrics.gross_profit / metrics.gross_loss if metrics.gross_loss > 0 else 10.0

        # Averages
        wins = [t.pnl for t in trades if t.pnl > 0]
        losses = [t.pnl for t in trades if t.pnl < 0]

        metrics.avg_win = float(np.mean(wins)) if wins else 0
        metrics.avg_loss = float(np.mean(losses)) if losses else 0
        metrics.avg_trade = float(np.mean(pnls))
        metrics.largest_win = max(pnls) if pnls else 0
        metrics.largest_loss = min(pnls) if pnls else 0

        # Long/Short breakdown - detailed metrics for TV parity
        long_trades_list = [t for t in trades if t.direction == "long"]
        short_trades_list = [t for t in trades if t.direction == "short"]

        # Long metrics
        metrics.long_trades = len(long_trades_list)
        long_wins = [t for t in long_trades_list if t.pnl > 0]
        long_losses = [t for t in long_trades_list if t.pnl < 0]
        metrics.long_winning_trades = len(long_wins)
        metrics.long_losing_trades = len(long_losses)
        metrics.long_win_rate = len(long_wins) / len(long_trades_list) if long_trades_list else 0
        metrics.long_gross_profit = float(sum(t.pnl for t in long_wins))
        metrics.long_gross_loss = float(abs(sum(t.pnl for t in long_losses)))
        metrics.long_profit = float(sum(t.pnl for t in long_trades_list))
        metrics.long_profit_factor = (
            metrics.long_gross_profit / metrics.long_gross_loss if metrics.long_gross_loss > 0 else 10.0
        )
        metrics.long_avg_win = float(np.mean([t.pnl for t in long_wins])) if long_wins else 0
        metrics.long_avg_loss = float(np.mean([t.pnl for t in long_losses])) if long_losses else 0

        # Short metrics
        metrics.short_trades = len(short_trades_list)
        short_wins = [t for t in short_trades_list if t.pnl > 0]
        short_losses = [t for t in short_trades_list if t.pnl < 0]
        metrics.short_winning_trades = len(short_wins)
        metrics.short_losing_trades = len(short_losses)
        metrics.short_win_rate = len(short_wins) / len(short_trades_list) if short_trades_list else 0
        metrics.short_gross_profit = float(sum(t.pnl for t in short_wins))
        metrics.short_gross_loss = float(abs(sum(t.pnl for t in short_losses)))
        metrics.short_profit = float(sum(t.pnl for t in short_trades_list))
        metrics.short_profit_factor = (
            metrics.short_gross_profit / metrics.short_gross_loss if metrics.short_gross_loss > 0 else 10.0
        )
        metrics.short_avg_win = float(np.mean([t.pnl for t in short_wins])) if short_wins else 0
        metrics.short_avg_loss = float(np.mean([t.pnl for t in short_losses])) if short_losses else 0

        # Duration
        durations = [t.duration_bars for t in trades]
        metrics.avg_trade_duration = float(np.mean(durations)) if durations else 0

        winning_durations = [t.duration_bars for t in trades if t.pnl > 0]
        losing_durations = [t.duration_bars for t in trades if t.pnl < 0]
        metrics.avg_winning_duration = float(np.mean(winning_durations)) if winning_durations else 0
        metrics.avg_losing_duration = float(np.mean(losing_durations)) if losing_durations else 0

        # Sharpe / Sortino (TradingView monthly formula — trade PnL bucketed by entry month)
        metrics.sharpe_ratio = calc_sharpe_monthly_tv(equity_curve, candles_index, initial_capital, trades=trades)
        metrics.sortino_ratio = calc_sortino_monthly_tv(equity_curve, candles_index, initial_capital, trades=trades)
        try:
            from backend.backtesting.formulas import _aggregate_monthly_equity_returns_from_trades as _agg_m

            _m_samples = len(_agg_m(trades, initial_capital)) if trades else 0
        except Exception:
            _m_samples = 0
        metrics.sharpe_samples = int(_m_samples)
        metrics.sharpe_method = "monthly" if _m_samples >= 2 else "fallback"

        # Calmar Ratio
        if metrics.max_drawdown > 0:
            annual_return = metrics.total_return * (365 * 24 / len(equity_curve))
            metrics.calmar_ratio = annual_return / metrics.max_drawdown

        # Expectancy
        metrics.expectancy = metrics.win_rate * metrics.avg_win + (1 - metrics.win_rate) * metrics.avg_loss

        # Payoff ratio
        if metrics.avg_loss != 0:
            metrics.payoff_ratio = abs(metrics.avg_win / metrics.avg_loss)

        # Recovery factor
        if metrics.max_drawdown > 0:
            metrics.recovery_factor = metrics.net_profit / (initial_capital * metrics.max_drawdown / 100)

        return metrics

    def _apply_params(self, input_data: BacktestInput, params: dict[str, Any]) -> BacktestInput:
        """Применение параметров к input"""
        from dataclasses import replace

        modified = replace(input_data)

        for key, value in params.items():
            if hasattr(modified, key):
                setattr(modified, key, value)

        return modified
