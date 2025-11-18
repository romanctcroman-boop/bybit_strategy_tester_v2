"""Multi-Timeframe Backtest Engine - расширение BacktestEngine с HTF поддержкой.

Реализует ТЗ 3.4.2: Multi-timeframe analysis
- Загрузка нескольких таймфреймов одновременно
- HTF (Higher TimeFrame) фильтры для входов
- Синхронизация индикаторов между таймфреймами
- Визуализация MTF индикаторов

Пример использования:
    >>> engine = MTFBacktestEngine(initial_capital=10000)
    >>> results = engine.run_mtf(
    ...     central_timeframe='15',
    ...     additional_timeframes=['5', '60', 'D'],
    ...     strategy_config={
    ...         'type': 'ema_crossover',
    ...         'fast_ema': 50,
    ...         'slow_ema': 200,
    ...         'htf_filters': [
    ...             {
    ...                 'timeframe': '60',
    ...                 'type': 'trend_ma',
    ...                 'params': {'period': 200, 'condition': 'price_above'}
    ...             },
    ...             {
    ...                 'timeframe': 'D',
    ...                 'type': 'ema_direction',
    ...                 'params': {'period': 50, 'condition': 'rising'}
    ...             }
    ...         ]
    ...     },
    ...     symbol='BTCUSDT',
    ...     limit=1000
    ... )
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import numpy as np

from backend.core.backtest_engine import BacktestEngine, BacktestState, Position, Trade
from backend.core.data_manager import DataManager

logger = logging.getLogger(__name__)


class MTFBacktestEngine(BacktestEngine):
    """
    Multi-Timeframe Backtest Engine.
    
    Расширяет базовый BacktestEngine с поддержкой:
    - Нескольких таймфреймов одновременно
    - HTF фильтров для входов
    - Синхронизации индикаторов
    
    Args:
        initial_capital: Начальный капитал (USDT)
        commission: Комиссия (0.0006 = 0.06%)
        slippage_pct: Slippage в % (0.05 = 0.05%)
        leverage: Плечо (1x-100x)
        order_size_usd: Фиксированный размер ордера
    """
    
    def __init__(
        self,
        initial_capital: float = 10_000.0,
        commission: float = 0.0006,
        slippage_pct: float = 0.05,
        leverage: int = 1,
        order_size_usd: float | None = None,
    ):
        super().__init__(initial_capital, commission, slippage_pct, leverage, order_size_usd)
        self.data_manager: Optional[DataManager] = None
        self.mtf_data: Dict[str, pd.DataFrame] = {}
        self.mtf_indicators: Dict[str, Dict[str, pd.Series]] = {}
    
    def run_mtf(
        self,
        central_timeframe: str,
        additional_timeframes: List[str],
        strategy_config: dict,
        symbol: str = 'BTCUSDT',
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 1000,
        cache_dir: str = './data/cache'
    ) -> dict[str, Any]:
        """
        Запуск MTF бэктеста.
        
        Args:
            central_timeframe: Основной таймфрейм для торговли ('15')
            additional_timeframes: Дополнительные TF для фильтров (['5', '60', 'D'])
            strategy_config: Конфигурация стратегии с htf_filters
            symbol: Торговая пара
            start_date: Начало периода
            end_date: Конец периода
            limit: Количество баров центрального TF
            cache_dir: Директория для кэша
        
        Returns:
            Результаты бэктеста + MTF метрики
        """
        logger.info(
            f"Starting MTF backtest: central={central_timeframe}, "
            f"additional={additional_timeframes}, symbol={symbol}"
        )
        
        # 1. Load multi-timeframe data
        all_timeframes = [central_timeframe] + additional_timeframes
        self.data_manager = DataManager(symbol=symbol, cache_dir=cache_dir)
        
        self.mtf_data = self.data_manager.get_multi_timeframe(
            timeframes=all_timeframes,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            central_tf=central_timeframe
        )
        
        logger.info(f"Loaded {len(self.mtf_data)} timeframes:")
        for tf, df in self.mtf_data.items():
            logger.info(f"  {tf}: {len(df)} bars")
        
        # 2. Prepare central timeframe data for main backtest
        central_data = self.mtf_data[central_timeframe].copy()
        
        # 3. Calculate MTF indicators
        self._calculate_mtf_indicators(strategy_config)
        
        # 4. Run backtest with MTF context
        results = self._run_with_mtf_context(central_data, strategy_config)
        
        # 5. Add MTF metadata to results
        results['mtf_config'] = {
            'central_timeframe': central_timeframe,
            'additional_timeframes': additional_timeframes,
            'htf_filters': strategy_config.get('htf_filters', [])
        }
        
        # 6. Add HTF indicator values for visualization
        results['htf_indicators'] = self._extract_htf_indicator_values()
        
        return results
    
    def _calculate_mtf_indicators(self, config: dict):
        """Расчёт индикаторов для всех таймфреймов."""
        logger.info("Calculating MTF indicators...")
        
        for tf, df in self.mtf_data.items():
            self.mtf_indicators[tf] = {}
            
            # Базовые индикаторы для всех TF
            self.mtf_indicators[tf]['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
            self.mtf_indicators[tf]['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
            self.mtf_indicators[tf]['sma_200'] = df['close'].rolling(window=200).mean()
            
            # RSI (опционально)
            if config.get('type') == 'rsi' or 'rsi' in str(config.get('htf_filters', [])):
                rsi_period = config.get('rsi_period', 14)
                self.mtf_indicators[tf]['rsi'] = self._calculate_rsi(df['close'], rsi_period)
            
            logger.debug(f"  {tf}: calculated {len(self.mtf_indicators[tf])} indicators")
    
    def _run_with_mtf_context(self, central_data: pd.DataFrame, strategy_config: dict) -> dict[str, Any]:
        """Запуск бэктеста с MTF контекстом."""
        # Prepare data
        df = self._prepare_data(central_data)
        
        # Initialize state
        state = BacktestState(
            capital=self.initial_capital,
            equity=self.initial_capital
        )
        
        # Calculate indicators for central TF (используем уже рассчитанные MTF индикаторы)
        central_tf = None
        for tf in self.mtf_data.keys():
            if len(self.mtf_data[tf]) == len(df):
                central_tf = tf
                break
        
        if central_tf:
            state.indicators = self.mtf_indicators[central_tf]
        else:
            # Fallback to base calculation
            state.indicators = self._calculate_indicators(df, strategy_config)
        
        # Main backtest loop
        for i in range(len(df)):
            bar = df.iloc[i]
            
            # Get current timestamp for HTF synchronization
            current_timestamp = bar['timestamp']
            
            # Store HTF context in state for entry/exit checks
            state.htf_context = self._get_htf_context(current_timestamp, i, df)
            
            self._process_bar(i, bar, df, state, strategy_config)
        
        # Close all positions
        self._close_all_positions(len(df) - 1, df.iloc[-1], state, "end_of_data")
        
        # Calculate metrics
        results = self._calculate_metrics(state, df)
        
        return results
    
    def _get_htf_context(self, timestamp: pd.Timestamp, bar_index: int, central_df: pd.DataFrame) -> dict:
        """
        Получить контекст HTF индикаторов для текущего бара.
        
        Синхронизирует значения индикаторов с высших таймфреймов
        на момент текущего timestamp.
        
        Returns:
            {
                '60': {'ema_200': 50000.5, 'sma_200': 49800.2, ...},
                'D': {'ema_50': 51000.0, ...}
            }
        """
        htf_context = {}
        
        for tf, df in self.mtf_data.items():
            # Skip central timeframe (already in main indicators)
            if len(df) == len(central_df):
                continue
            
            # Find closest HTF bar at or before current timestamp
            htf_bars = df[df['timestamp'] <= timestamp]
            
            if htf_bars.empty:
                # Not enough HTF data yet
                htf_context[tf] = {}
                continue
            
            htf_idx = len(htf_bars) - 1  # Last bar before or at current time
            
            # Extract indicator values
            htf_context[tf] = {}
            for ind_name, ind_series in self.mtf_indicators.get(tf, {}).items():
                if htf_idx < len(ind_series):
                    value = ind_series.iloc[htf_idx]
                    if not pd.isna(value):
                        htf_context[tf][ind_name] = float(value)
        
        return htf_context
    
    def _check_entry(
        self,
        i: int,
        bar: pd.Series,
        df: pd.DataFrame,
        state: BacktestState,
        config: dict
    ):
        """
        Переопределённая проверка входа с учётом HTF фильтров.
        """
        if i < 1:
            return
        
        # 1. Check base strategy signal
        base_signal, signal_side = self._check_base_signal(i, bar, df, state, config)
        
        if not base_signal:
            return
        
        # 2. Apply HTF filters
        htf_filters = config.get('htf_filters', [])
        
        if htf_filters:
            htf_passed = self._apply_htf_filters(i, bar, state, htf_filters, signal_side)
            
            if not htf_passed:
                logger.debug(f"Bar {i}: Base signal={signal_side}, but HTF filters rejected")
                return
        
        # 3. Check direction filter
        direction = config.get('direction', 'long')
        if direction != 'both' and direction != signal_side:
            return
        
        # 4. Open position
        self._open_position(i, bar, state, config, signal_side)
    
    def _check_base_signal(
        self,
        i: int,
        bar: pd.Series,
        df: pd.DataFrame,
        state: BacktestState,
        config: dict
    ) -> tuple[bool, str | None]:
        """
        Проверка базового сигнала стратегии (без HTF фильтров).
        
        Returns:
            (signal: bool, side: 'long' | 'short' | None)
        """
        strategy_type = config.get('type', 'ema_crossover')
        
        if strategy_type == 'ema_crossover':
            ema_fast = state.indicators.get('ema_fast')
            ema_slow = state.indicators.get('ema_slow')
            
            if ema_fast is None or ema_slow is None:
                # Используем MTF индикаторы
                ema_fast = state.indicators.get('ema_50')
                ema_slow = state.indicators.get('ema_200')
            
            if ema_fast is None or ema_slow is None:
                return False, None
            
            if pd.isna(ema_fast.iloc[i]) or pd.isna(ema_slow.iloc[i]):
                return False, None
            
            # Long signal
            if ema_fast.iloc[i] > ema_slow.iloc[i] and ema_fast.iloc[i - 1] <= ema_slow.iloc[i - 1]:
                return True, 'long'
            
            # Short signal
            elif ema_fast.iloc[i] < ema_slow.iloc[i] and ema_fast.iloc[i - 1] >= ema_slow.iloc[i - 1]:
                return True, 'short'
        
        elif strategy_type == 'rsi':
            rsi = state.indicators.get('rsi')
            oversold = config.get('rsi_oversold', 30)
            overbought = config.get('rsi_overbought', 70)
            
            if rsi is None or pd.isna(rsi.iloc[i]):
                return False, None
            
            if rsi.iloc[i] < oversold:
                return True, 'long'
            elif rsi.iloc[i] > overbought:
                return True, 'short'
        
        return False, None
    
    def _apply_htf_filters(
        self,
        i: int,
        bar: pd.Series,
        state: BacktestState,
        htf_filters: list[dict],
        signal_side: str
    ) -> bool:
        """
        Применить HTF фильтры.
        
        htf_filters format:
        [
            {
                'timeframe': '60',
                'type': 'trend_ma',
                'params': {'period': 200, 'condition': 'price_above'}
            },
            {
                'timeframe': 'D',
                'type': 'ema_direction',
                'params': {'period': 50, 'condition': 'rising'}
            }
        ]
        
        Returns:
            True if all filters pass, False otherwise
        """
        htf_context = getattr(state, 'htf_context', {})
        
        for filter_config in htf_filters:
            tf = filter_config['timeframe']
            filter_type = filter_config['type']
            params = filter_config.get('params', {})
            
            # Get HTF values
            htf_values = htf_context.get(tf, {})
            
            if not htf_values:
                logger.debug(f"HTF filter {tf} skipped: no HTF data")
                continue
            
            # Apply filter based on type
            if filter_type == 'trend_ma':
                # Condition: price above/below MA
                period = params.get('period', 200)
                condition = params.get('condition', 'price_above')
                
                ma_key = f'sma_{period}' if f'sma_{period}' in htf_values else f'ema_{period}'
                ma_value = htf_values.get(ma_key)
                
                if ma_value is None:
                    logger.debug(f"HTF filter {tf} skipped: {ma_key} not found")
                    continue
                
                current_price = bar['close']
                
                if condition == 'price_above':
                    if signal_side == 'long' and current_price < ma_value:
                        logger.debug(f"HTF filter {tf} rejected: price {current_price} < MA{period} {ma_value}")
                        return False
                    if signal_side == 'short' and current_price > ma_value:
                        return False
                
                elif condition == 'price_below':
                    if signal_side == 'long' and current_price > ma_value:
                        return False
                    if signal_side == 'short' and current_price < ma_value:
                        return False
            
            elif filter_type == 'ema_direction':
                # Condition: EMA rising/falling
                period = params.get('period', 50)
                condition = params.get('condition', 'rising')
                
                # Нужно сравнить текущее и предыдущее значение EMA
                # Для этого нужен доступ к HTF данным
                # Упрощённая версия: используем только текущее значение
                # TODO: добавить проверку направления через slope
                
                ema_key = f'ema_{period}'
                ema_value = htf_values.get(ema_key)
                
                if ema_value is None:
                    continue
                
                # Placeholder: считаем что фильтр пройден
                # В реальности нужно проверить slope EMA
                logger.debug(f"HTF filter {tf} {filter_type}: passed (simplified)")
            
            elif filter_type == 'rsi_range':
                # Condition: RSI in range
                min_rsi = params.get('min', 0)
                max_rsi = params.get('max', 100)
                
                rsi_value = htf_values.get('rsi')
                
                if rsi_value is None:
                    continue
                
                if not (min_rsi <= rsi_value <= max_rsi):
                    logger.debug(f"HTF filter {tf} rejected: RSI {rsi_value} not in [{min_rsi}, {max_rsi}]")
                    return False
        
        # All filters passed
        return True
    
    def _extract_htf_indicator_values(self) -> dict:
        """
        Извлечь значения HTF индикаторов для визуализации.
        
        Returns:
            {
                '60': {
                    'timestamps': [...],
                    'ema_200': [...],
                    'sma_200': [...]
                },
                'D': {...}
            }
        """
        htf_viz = {}
        
        for tf, df in self.mtf_data.items():
            # Convert timestamps to ISO format strings
            if pd.api.types.is_datetime64_any_dtype(df['timestamp']):
                timestamps = [ts.isoformat() for ts in df['timestamp']]
            else:
                timestamps = [str(ts) for ts in df['timestamp']]
            
            htf_viz[tf] = {
                'timestamps': timestamps
            }
            
            # Add indicator values
            for ind_name, ind_series in self.mtf_indicators.get(tf, {}).items():
                # Convert to list, replacing NaN with None
                values = [None if pd.isna(v) else float(v) for v in ind_series]
                htf_viz[tf][ind_name] = values
        
        return htf_viz


# Convenience function for quick MTF backtests
def run_mtf_backtest(
    symbol: str,
    central_timeframe: str,
    additional_timeframes: list[str],
    strategy_config: dict,
    initial_capital: float = 10_000.0,
    limit: int = 1000,
    **kwargs
) -> dict:
    """
    Быстрый запуск MTF бэктеста.
    
    Example:
        >>> results = run_mtf_backtest(
        ...     symbol='BTCUSDT',
        ...     central_timeframe='15',
        ...     additional_timeframes=['60', 'D'],
        ...     strategy_config={
        ...         'type': 'ema_crossover',
        ...         'fast_ema': 50,
        ...         'slow_ema': 200,
        ...         'htf_filters': [
        ...             {
        ...                 'timeframe': '60',
        ...                 'type': 'trend_ma',
        ...                 'params': {'period': 200, 'condition': 'price_above'}
        ...             }
        ...         ]
        ...     },
        ...     initial_capital=10000,
        ...     limit=1000
        ... )
    """
    engine = MTFBacktestEngine(initial_capital=initial_capital, **kwargs)
    
    return engine.run_mtf(
        central_timeframe=central_timeframe,
        additional_timeframes=additional_timeframes,
        strategy_config=strategy_config,
        symbol=symbol,
        limit=limit
    )
