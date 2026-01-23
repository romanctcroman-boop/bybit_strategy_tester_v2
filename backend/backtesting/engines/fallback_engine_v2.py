"""
🎯 FALLBACK ENGINE V2 - Эталонный движок с полной точностью

Особенности:
- 100% точность (эталон для сравнения)
- Полная поддержка Bar Magnifier (тиковые вычисления)
- SL/TP с High/Low внутри бара
- Все метрики

Скорость: ~1x (базовая)
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
import time

from backend.backtesting.interfaces import (
    BaseBacktestEngine,
    BacktestInput,
    BacktestOutput,
    BacktestMetrics,
    TradeRecord,
    TradeDirection,
    ExitReason,
)


class FallbackEngineV2(BaseBacktestEngine):
    """
    Fallback Engine V2 - Эталонный Python-based движок.

    Преимущества:
    - Максимальная точность
    - Полная поддержка Bar Magnifier
    - Детальное логирование
    - Легко отлаживать

    Недостатки:
    - Медленный (Python loops)
    """

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

        # Timestamps
        if isinstance(candles.index, pd.DatetimeIndex):
            timestamps = candles.index.to_numpy()
        else:
            timestamps = pd.to_datetime(candles.index).to_numpy()

        # Сигналы
        long_entries = (
            input_data.long_entries
            if input_data.long_entries is not None
            else np.zeros(n, dtype=bool)
        )
        long_exits = (
            input_data.long_exits
            if input_data.long_exits is not None
            else np.zeros(n, dtype=bool)
        )
        short_entries = (
            input_data.short_entries
            if input_data.short_entries is not None
            else np.zeros(n, dtype=bool)
        )
        short_exits = (
            input_data.short_exits
            if input_data.short_exits is not None
            else np.zeros(n, dtype=bool)
        )

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
        trades: List[TradeRecord] = []

        # Позиции
        in_long = False
        in_short = False
        long_entry_price = 0.0
        short_entry_price = 0.0
        long_entry_idx = 0
        short_entry_idx = 0
        long_size = 0.0
        short_size = 0.0
        long_allocated = 0.0  # Сколько выделено на long позицию
        short_allocated = 0.0  # Сколько выделено на short позицию

        # TV-style pending exit (exit on next candle after TP/SL trigger)
        pending_long_exit = False
        pending_long_exit_reason = None
        pending_long_exit_price = 0.0
        pending_short_exit = False
        pending_short_exit_reason = None
        pending_short_exit_price = 0.0

        # Bar Magnifier индекс (для 1m данных)
        bar_magnifier_index = (
            self._build_bar_magnifier_index(candles, candles_1m)
            if use_bar_magnifier
            else None
        )

        # === ОСНОВНОЙ ЦИКЛ ===
        for i in range(1, n):
            current_time = timestamps[i]
            open_price = open_prices[i]
            high_price = high_prices[i]
            low_price = low_prices[i]
            close_price = close_prices[i]

            # === ВЫПОЛНЕНИЕ ОТЛОЖЕННОГО ВЫХОДА (TV-style: record on next candle) ===
            # Long pending exit (in_long cleared at trigger time, so just check pending flag)
            if pending_long_exit:
                # Use saved exit price (SL/TP level), not open of next candle
                exit_price = pending_long_exit_price
                pnl, pnl_pct, fees = self._calculate_pnl(
                    is_long=True,
                    entry_price=long_entry_price,
                    exit_price=exit_price,
                    size=long_size,
                    taker_fee=taker_fee,
                )

                cash += long_allocated + pnl

                mfe, mae = self._calculate_mfe_mae(
                    is_long=True,
                    entry_price=long_entry_price,
                    high=high_prices[i - 1] if i > 0 else high_price,
                    low=low_prices[i - 1] if i > 0 else low_price,
                    size=long_size,
                )

                trades.append(
                    TradeRecord(
                        entry_time=timestamps[long_entry_idx],
                        exit_time=current_time,  # Exit recorded at this candle's open
                        direction="long",
                        entry_price=long_entry_price,
                        exit_price=exit_price,
                        size=long_size,
                        pnl=pnl,
                        pnl_pct=pnl_pct,
                        fees=fees,
                        exit_reason=pending_long_exit_reason,
                        duration_bars=i - long_entry_idx,
                        mfe=mfe,
                        mae=mae,
                        intrabar_sl_hit=False,
                        intrabar_tp_hit=False,
                    )
                )

                in_long = False
                long_size = 0.0
                pending_long_exit = False
                pending_long_exit_reason = None

            # Short pending exit (in_short cleared at trigger time, so just check pending flag)
            if pending_short_exit:
                # Use saved exit price (SL/TP level), not open of next candle
                exit_price = pending_short_exit_price
                pnl, pnl_pct, fees = self._calculate_pnl(
                    is_long=False,
                    entry_price=short_entry_price,
                    exit_price=exit_price,
                    size=short_size,
                    taker_fee=taker_fee,
                )

                cash += short_allocated + pnl

                mfe, mae = self._calculate_mfe_mae(
                    is_long=False,
                    entry_price=short_entry_price,
                    high=high_prices[i - 1] if i > 0 else high_price,
                    low=low_prices[i - 1] if i > 0 else low_price,
                    size=short_size,
                )

                trades.append(
                    TradeRecord(
                        entry_time=timestamps[short_entry_idx],
                        exit_time=current_time,
                        direction="short",
                        entry_price=short_entry_price,
                        exit_price=exit_price,
                        size=short_size,
                        pnl=pnl,
                        pnl_pct=pnl_pct,
                        fees=fees,
                        exit_reason=pending_short_exit_reason,
                        duration_bars=i - short_entry_idx,
                        mfe=mfe,
                        mae=mae,
                        intrabar_sl_hit=False,
                        intrabar_tp_hit=False,
                    )
                )

                in_short = False
                short_size = 0.0
                pending_short_exit = False
                pending_short_exit_reason = None

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
                    # TV-style: immediately free position for new entry on same bar
                    in_long = False

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
                    # TV-style: immediately free position for new entry on same bar
                    in_short = False

            # === ВХОД В LONG ===
            # TradingView с TP/SL: новая позиция открывается ТОЛЬКО если нет открытых позиций
            # Skip entry on last bar (would immediately close as END_OF_DATA)
            # Note: pending_exit is NOT checked - TV allows new signal on same bar as TP/SL
            if (
                not in_long
                and not in_short
                and long_entries[i]
                and direction in (TradeDirection.LONG, TradeDirection.BOTH)
                and i < n - 2
                and i > 0
            ):
                # TV entry: at open of NEXT candle after signal (i+1)
                entry_price = open_prices[i + 1]

                # TradingView-style: fixed USDT amount OR percentage of capital
                if use_fixed_amount and fixed_amount > 0:
                    # Fixed amount mode: allocate fixed USDT (like TV's base_cash_usdt)
                    allocated = min(
                        fixed_amount, cash
                    )  # Can't allocate more than we have
                else:
                    # Percentage mode: allocate % of current cash
                    allocated = cash * position_size

                # Skip if allocated is too small (prevents micro-positions)
                if allocated >= 1.0:
                    notional = allocated * leverage  # Notional value с leverage
                    size = notional / entry_price
                    # Entry fee will be deducted from PnL at exit (TV style)

                    cash -= allocated  # Вычитаем только выделенный капитал

                    in_long = True
                    long_entry_price = entry_price
                    long_entry_idx = i
                    long_size = size
                    long_allocated = allocated

            # === ВХОД В SHORT ===
            # TradingView с TP/SL: новая позиция открывается ТОЛЬКО если нет открытых позиций
            # Skip entry on last bar (would immediately close as END_OF_DATA)
            # Note: pending_exit is NOT checked - TV allows new signal on same bar as TP/SL
            if (
                not in_short
                and not in_long
                and short_entries[i]
                and direction in (TradeDirection.SHORT, TradeDirection.BOTH)
                and i < n - 2
                and i > 0
            ):
                # TV entry: at open of NEXT candle after signal (i+1)
                entry_price = open_prices[i + 1]

                # TradingView-style: fixed USDT amount OR percentage of capital
                if use_fixed_amount and fixed_amount > 0:
                    allocated = min(fixed_amount, cash)
                else:
                    allocated = cash * position_size

                # Skip if allocated is too small (prevents micro-positions)
                if allocated >= 1.0:
                    notional = allocated * leverage
                    size = notional / entry_price
                    # Entry fee will be deducted from PnL at exit (TV style)

                    cash -= allocated  # Вычитаем только выделенный капитал

                    in_short = True
                    short_entry_price = entry_price
                    short_entry_idx = i
                    short_size = size
                    short_allocated = allocated

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
            pnl, pnl_pct, fees = self._calculate_pnl(
                True, long_entry_price, exit_price, long_size, taker_fee
            )
            trades.append(
                TradeRecord(
                    entry_time=timestamps[long_entry_idx],
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
            pnl, pnl_pct, fees = self._calculate_pnl(
                False, short_entry_price, exit_price, short_size, taker_fee
            )
            trades.append(
                TradeRecord(
                    entry_time=timestamps[short_entry_idx],
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
        metrics = self._calculate_metrics(trades, equity_array, capital)

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
        param_ranges: Dict[str, List[Any]],
        metric: str = "sharpe_ratio",
        top_n: int = 10,
    ) -> List[Tuple[Dict[str, Any], BacktestOutput]]:
        """Оптимизация (последовательная)"""
        from itertools import product

        results = []

        # Генерация всех комбинаций
        param_names = list(param_ranges.keys())
        param_values = list(param_ranges.values())

        for combo in product(*param_values):
            params = dict(zip(param_names, combo))

            # Применяем параметры к input
            modified_input = self._apply_params(input_data, params)

            # Запуск бэктеста
            result = self.run(modified_input)

            if result.is_valid and result.metrics.total_trades > 0:
                results.append((params, result))

        # Сортировка по метрике
        results.sort(key=lambda x: getattr(x[1].metrics, metric, 0), reverse=True)

        return results[:top_n]

    def _build_bar_magnifier_index(
        self, candles: pd.DataFrame, candles_1m: pd.DataFrame
    ) -> Dict[int, Tuple[int, int]]:
        """
        Построение индекса для Bar Magnifier.
        Возвращает словарь: bar_idx -> (start_1m_idx, end_1m_idx)
        """
        if candles_1m is None:
            return {}

        index = {}

        # Получаем timestamps
        bar_times = (
            candles.index
            if isinstance(candles.index, pd.DatetimeIndex)
            else pd.to_datetime(candles.index)
        )
        m1_times = (
            candles_1m.index
            if isinstance(candles_1m.index, pd.DatetimeIndex)
            else pd.to_datetime(candles_1m.index)
        )

        # Для каждого бара основного таймфрейма находим соответствующие 1m бары
        for i in range(len(candles)):
            bar_start = bar_times[i]
            bar_end = (
                bar_times[i + 1]
                if i + 1 < len(candles)
                else bar_times[i] + pd.Timedelta(hours=1)
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
        bar_magnifier_index: Optional[Dict],
        bar_idx: int,
        candles_1m: Optional[pd.DataFrame],
    ) -> Tuple[Optional[ExitReason], float]:
        """
        Проверка условий выхода с поддержкой Bar Magnifier.

        TV Broker Emulator intrabar logic:
        - If open closer to high: order is open → high → low → close
        - If open closer to low: order is open → low → high → close

        Возвращает: (exit_reason, exit_price) или (None, 0)
        """
        if is_long:
            sl_price = entry_price * (1 - stop_loss) if stop_loss > 0 else 0
            tp_price = (
                entry_price * (1 + take_profit) if take_profit > 0 else float("inf")
            )
        else:
            sl_price = entry_price * (1 + stop_loss) if stop_loss > 0 else float("inf")
            tp_price = entry_price * (1 - take_profit) if take_profit > 0 else 0

        # === BAR MAGNIFIER: Точное определение порядка SL/TP ===
        if use_bar_magnifier and bar_magnifier_index and bar_idx in bar_magnifier_index:
            start_idx, end_idx = bar_magnifier_index[bar_idx]
            m1_highs = candles_1m["high"].values[start_idx:end_idx]
            m1_lows = candles_1m["low"].values[start_idx:end_idx]

            for m1_high, m1_low in zip(m1_highs, m1_lows):
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
    ) -> Tuple[float, float, float]:
        """Расчёт PnL, PnL%, и комиссий (entry + exit как в TV)"""
        if is_long:
            pnl = (exit_price - entry_price) * size
        else:
            pnl = (entry_price - exit_price) * size

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
    ) -> Tuple[float, float]:
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
        trades: List[TradeRecord],
        equity_curve: np.ndarray,
        initial_capital: float,
    ) -> BacktestMetrics:
        """Расчёт всех метрик"""
        metrics = BacktestMetrics()

        if len(trades) == 0:
            return metrics

        # Основные
        pnls = [t.pnl for t in trades]
        metrics.net_profit = sum(pnls)
        metrics.total_return = (
            (equity_curve[-1] - initial_capital) / initial_capital * 100
        )

        # Gross profit/loss
        metrics.gross_profit = sum(p for p in pnls if p > 0)
        metrics.gross_loss = abs(sum(p for p in pnls if p < 0))

        # Drawdown - calculate in USDT for TV parity (TV reports in absolute USDT)
        peak = np.maximum.accumulate(equity_curve)
        drawdown_pct = (peak - equity_curve) / peak * 100
        drawdown_usdt = peak - equity_curve  # Absolute drawdown in USDT
        metrics.max_drawdown = np.max(drawdown_usdt)  # In USDT for TV parity
        metrics.max_drawdown_pct = np.max(drawdown_pct)  # Keep percentage version too
        metrics.avg_drawdown = np.mean(drawdown_pct)

        # Trades
        metrics.total_trades = len(trades)
        metrics.winning_trades = sum(1 for t in trades if t.pnl > 0)
        metrics.losing_trades = sum(1 for t in trades if t.pnl < 0)
        metrics.win_rate = (
            metrics.winning_trades / metrics.total_trades
            if metrics.total_trades > 0
            else 0
        )

        # Profit factor
        metrics.profit_factor = (
            metrics.gross_profit / metrics.gross_loss
            if metrics.gross_loss > 0
            else 10.0
        )

        # Averages
        wins = [t.pnl for t in trades if t.pnl > 0]
        losses = [t.pnl for t in trades if t.pnl < 0]

        metrics.avg_win = np.mean(wins) if wins else 0
        metrics.avg_loss = np.mean(losses) if losses else 0
        metrics.avg_trade = np.mean(pnls)
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
        metrics.long_win_rate = (
            len(long_wins) / len(long_trades_list) if long_trades_list else 0
        )
        metrics.long_gross_profit = sum(t.pnl for t in long_wins)
        metrics.long_gross_loss = abs(sum(t.pnl for t in long_losses))
        metrics.long_profit = sum(t.pnl for t in long_trades_list)
        metrics.long_profit_factor = (
            metrics.long_gross_profit / metrics.long_gross_loss
            if metrics.long_gross_loss > 0
            else 10.0
        )
        metrics.long_avg_win = np.mean([t.pnl for t in long_wins]) if long_wins else 0
        metrics.long_avg_loss = (
            np.mean([t.pnl for t in long_losses]) if long_losses else 0
        )

        # Short metrics
        metrics.short_trades = len(short_trades_list)
        short_wins = [t for t in short_trades_list if t.pnl > 0]
        short_losses = [t for t in short_trades_list if t.pnl < 0]
        metrics.short_winning_trades = len(short_wins)
        metrics.short_losing_trades = len(short_losses)
        metrics.short_win_rate = (
            len(short_wins) / len(short_trades_list) if short_trades_list else 0
        )
        metrics.short_gross_profit = sum(t.pnl for t in short_wins)
        metrics.short_gross_loss = abs(sum(t.pnl for t in short_losses))
        metrics.short_profit = sum(t.pnl for t in short_trades_list)
        metrics.short_profit_factor = (
            metrics.short_gross_profit / metrics.short_gross_loss
            if metrics.short_gross_loss > 0
            else 10.0
        )
        metrics.short_avg_win = (
            np.mean([t.pnl for t in short_wins]) if short_wins else 0
        )
        metrics.short_avg_loss = (
            np.mean([t.pnl for t in short_losses]) if short_losses else 0
        )

        # Duration
        durations = [t.duration_bars for t in trades]
        metrics.avg_trade_duration = np.mean(durations) if durations else 0

        winning_durations = [t.duration_bars for t in trades if t.pnl > 0]
        losing_durations = [t.duration_bars for t in trades if t.pnl < 0]
        metrics.avg_winning_duration = (
            np.mean(winning_durations) if winning_durations else 0
        )
        metrics.avg_losing_duration = (
            np.mean(losing_durations) if losing_durations else 0
        )

        # Sharpe Ratio
        returns = np.diff(equity_curve) / equity_curve[:-1]
        returns = np.nan_to_num(returns, nan=0, posinf=0, neginf=0)
        if len(returns) > 1 and np.std(returns) > 0:
            metrics.sharpe_ratio = (
                np.mean(returns) / np.std(returns) * np.sqrt(252 * 24)
            )  # Hourly

        # Sortino Ratio
        downside_returns = returns[returns < 0]
        if len(downside_returns) > 1:
            downside_std = np.std(downside_returns)
            if downside_std > 0:
                metrics.sortino_ratio = (
                    np.mean(returns) / downside_std * np.sqrt(252 * 24)
                )

        # Calmar Ratio
        if metrics.max_drawdown > 0:
            annual_return = metrics.total_return * (365 * 24 / len(equity_curve))
            metrics.calmar_ratio = annual_return / metrics.max_drawdown

        # Expectancy
        metrics.expectancy = (
            metrics.win_rate * metrics.avg_win
            + (1 - metrics.win_rate) * metrics.avg_loss
        )

        # Payoff ratio
        if metrics.avg_loss != 0:
            metrics.payoff_ratio = abs(metrics.avg_win / metrics.avg_loss)

        # Recovery factor
        if metrics.max_drawdown > 0:
            metrics.recovery_factor = metrics.net_profit / (
                initial_capital * metrics.max_drawdown / 100
            )

        return metrics

    def _apply_params(
        self, input_data: BacktestInput, params: Dict[str, Any]
    ) -> BacktestInput:
        """Применение параметров к input"""
        from dataclasses import replace

        modified = replace(input_data)

        for key, value in params.items():
            if hasattr(modified, key):
                setattr(modified, key, value)

        return modified
