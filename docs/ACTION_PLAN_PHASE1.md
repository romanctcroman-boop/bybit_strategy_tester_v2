# ПЛАН ДЕЙСТВИЙ - ФАЗА 1: КРИТИЧЕСКИЕ ИСПРАВЛЕНИЯ
## Проект: Bybit Strategy Tester v2
## Срок: 1-2 недели
## Приоритет: 🔴 КРИТИЧЕСКИЙ

---

## ЦЕЛЬ ФАЗЫ 1

Привести проект к **100% соответствию ТЗ MVP** с устранением всех критических аномалий.

**Целевая метрика:** MVP 92% → **100%**

---

## ЗАДАЧА 1: КОНСОЛИДАЦИЯ ОПТИМИЗАЦИИ (3 дня)

### Проблема
Найдено **3 реализации** Walk-Forward Optimization:
1. `backend/tasks/optimize_tasks.py` (Celery task)
2. `backend/core/walk_forward_optimizer.py`
3. `backend/optimization/walk_forward.py`

Найдено **2 реализации** Monte Carlo:
1. `backend/optimization/monte_carlo.py`
2. `backend/core/monte_carlo_simulator.py`

### Решение

#### 1.1 Создать единый модуль Walk-Forward

**Файл:** `backend/optimization/walk_forward_optimizer.py`

```python
"""
Walk-Forward Optimization - Единая реализация

Соответствие ТЗ 3.5.2:
- in_sample_size, out_sample_size, step_size в барах
- parameter_stability метрика
- aggregated_metrics
"""

from typing import Any
import pandas as pd
from loguru import logger


class WalkForwardOptimizer:
    """
    ТЗ 3.5.2 - Защита от переобучения через скользящую оптимизацию
    Доступен на Продвинутом уровне
    """
    
    def __init__(
        self,
        in_sample_size: int,   # 252 bars
        out_sample_size: int,  # 63 bars
        step_size: int         # 63 bars (sliding window step)
    ):
        """
        Args:
            in_sample_size: Количество баров для оптимизации
            out_sample_size: Количество баров для тестирования
            step_size: Шаг сдвига окна (в барах)
        """
        self.in_sample_size = in_sample_size
        self.out_sample_size = out_sample_size
        self.step_size = step_size
        
        logger.info(
            f"WalkForwardOptimizer initialized: IS={in_sample_size}, "
            f"OOS={out_sample_size}, step={step_size}"
        )
    
    def run(
        self,
        data: pd.DataFrame,
        param_space: dict[str, list],
        strategy_config: dict,
        metric: str = "sharpe_ratio"
    ) -> dict[str, Any]:
        """
        Запуск Walk-Forward оптимизации
        
        Returns:
            {
                'walk_results': list[dict],      # Результат каждого периода
                'aggregated_metrics': dict,      # Общие метрики
                'parameter_stability': dict      # Стабильность параметров
            }
        """
        walk_results = []
        all_params = []
        
        # Calculate number of walks
        total_bars = len(data)
        num_walks = (total_bars - self.in_sample_size - self.out_sample_size) // self.step_size + 1
        
        logger.info(f"Starting {num_walks} walk-forward iterations")
        
        for walk_idx in range(num_walks):
            start_idx = walk_idx * self.step_size
            is_end = start_idx + self.in_sample_size
            oos_end = is_end + self.out_sample_size
            
            if oos_end > total_bars:
                break
            
            # In-Sample data
            is_data = data.iloc[start_idx:is_end]
            
            # Out-of-Sample data
            oos_data = data.iloc[is_end:oos_end]
            
            # Optimize on IS
            best_params = self._optimize_on_is(
                is_data, param_space, strategy_config, metric
            )
            
            # Test on OOS
            oos_metrics = self._test_on_oos(
                oos_data, best_params, strategy_config
            )
            
            walk_results.append({
                'walk_index': walk_idx,
                'is_start': start_idx,
                'is_end': is_end,
                'oos_start': is_end,
                'oos_end': oos_end,
                'best_params': best_params,
                'is_metric': best_params['score'],
                'oos_metrics': oos_metrics
            })
            
            all_params.append(best_params)
            
            logger.info(
                f"Walk {walk_idx+1}/{num_walks}: IS {metric}={best_params['score']:.3f}, "
                f"OOS {metric}={oos_metrics.get(metric, 0):.3f}"
            )
        
        # Aggregate metrics
        aggregated = self._calculate_aggregated_metrics(walk_results, metric)
        
        # Parameter stability
        stability = self._calculate_parameter_stability(all_params)
        
        return {
            'walk_results': walk_results,
            'aggregated_metrics': aggregated,
            'parameter_stability': stability
        }
    
    def _optimize_on_is(
        self,
        data: pd.DataFrame,
        param_space: dict,
        strategy_config: dict,
        metric: str
    ) -> dict:
        """Grid search на In-Sample данных"""
        from backend.core.engine_adapter import get_engine
        from itertools import product
        
        # Generate all combinations
        param_names = list(param_space.keys())
        param_values = [param_space[name] for name in param_names]
        combinations = list(product(*param_values))
        
        best_score = float('-inf')
        best_params = None
        
        for combo in combinations:
            params = dict(zip(param_names, combo))
            
            # Merge params into strategy_config
            test_config = {**strategy_config, **params}
            
            # Run backtest
            engine = get_engine()
            result = engine.run(data, test_config)
            
            score = result.get(metric, 0)
            
            if score > best_score:
                best_score = score
                best_params = {**params, 'score': score}
        
        return best_params
    
    def _test_on_oos(
        self,
        data: pd.DataFrame,
        params: dict,
        strategy_config: dict
    ) -> dict:
        """Тест на Out-of-Sample данных"""
        from backend.core.engine_adapter import get_engine
        
        # Remove 'score' from params
        test_params = {k: v for k, v in params.items() if k != 'score'}
        test_config = {**strategy_config, **test_params}
        
        engine = get_engine()
        result = engine.run(data, test_config)
        
        return {
            'sharpe_ratio': result.get('sharpe_ratio', 0),
            'total_return': result.get('total_return', 0),
            'max_drawdown': result.get('max_drawdown', 0),
            'win_rate': result.get('win_rate', 0),
            'profit_factor': result.get('profit_factor', 0)
        }
    
    def _calculate_aggregated_metrics(
        self,
        walk_results: list[dict],
        metric: str
    ) -> dict:
        """Агрегированные метрики по всем периодам"""
        import numpy as np
        
        is_scores = [w['is_metric'] for w in walk_results]
        oos_scores = [w['oos_metrics'].get(metric, 0) for w in walk_results]
        
        return {
            'is_mean': np.mean(is_scores),
            'is_std': np.std(is_scores),
            'oos_mean': np.mean(oos_scores),
            'oos_std': np.std(oos_scores),
            'is_oos_ratio': np.mean(oos_scores) / np.mean(is_scores) if np.mean(is_scores) > 0 else 0,
            'num_walks': len(walk_results)
        }
    
    def _calculate_parameter_stability(self, all_params: list[dict]) -> dict:
        """
        Стабильность параметров (ТЗ 3.5.2)
        
        Рассчитывает std deviation каждого параметра по всем периодам.
        Низкий std = стабильные параметры = хорошо.
        """
        import numpy as np
        
        if not all_params:
            return {}
        
        param_names = [k for k in all_params[0].keys() if k != 'score']
        stability = {}
        
        for param_name in param_names:
            values = [p[param_name] for p in all_params]
            stability[param_name] = {
                'mean': np.mean(values),
                'std': np.std(values),
                'min': np.min(values),
                'max': np.max(values),
                'stability_score': 1.0 / (1.0 + np.std(values))  # Higher = more stable
            }
        
        return stability
```

**Действия:**
1. ✅ Создать новый файл `backend/optimization/walk_forward_optimizer.py`
2. ✅ Скопировать лучшие части из 3 реализаций
3. ✅ Добавить `parameter_stability` (отсутствует сейчас)
4. ✅ Использовать bars вместо months
5. ❌ Удалить старые файлы (оставить с пометкой `_deprecated`)
6. ✅ Обновить `backend/tasks/optimize_tasks.py` для использования нового класса
7. ✅ Написать unit tests

**Критерий приёмки:**
- [ ] 1 класс WalkForwardOptimizer работает
- [ ] Все 3 старых реализации deprecated
- [ ] Тесты проходят (100%)
- [ ] `parameter_stability` возвращается в результатах

---

#### 1.2 Создать единый модуль Monte Carlo

**Файл:** `backend/optimization/monte_carlo_simulator.py`

```python
"""
Monte Carlo Simulation - Единая реализация

Соответствие ТЗ 3.5.3:
- num_simulations (1000)
- prob_profit, prob_ruin (ТЗ требует, сейчас отсутствует)
- percentile_5, percentile_95
"""

import numpy as np
from typing import Any
from loguru import logger


class MonteCarloSimulator:
    """
    ТЗ 3.5.3 - Оценка робастности через случайные перестановки
    Доступен на Продвинутом уровне
    """
    
    def run(
        self,
        trades: list[dict],
        num_simulations: int = 1000,
        initial_capital: float = 10000.0
    ) -> dict[str, Any]:
        """
        Запуск Monte Carlo симуляции
        
        Args:
            trades: Список сделок из BacktestEngine
            num_simulations: Количество итераций (по умолчанию 1000)
            initial_capital: Начальный капитал
        
        Returns:
            {
                'simulations': list[dict],   # Результат каждой симуляции
                'statistics': {
                    'mean_return': float,
                    'std_return': float,
                    'percentile_5': float,   # Пессимистичный сценарий
                    'percentile_95': float,  # Оптимистичный
                    'prob_profit': float,    # Вероятность прибыли ✅ NEW
                    'prob_ruin': float       # Вероятность краха ✅ NEW
                }
            }
        """
        if not trades:
            logger.warning("No trades provided for Monte Carlo simulation")
            return self._empty_result()
        
        logger.info(f"Starting Monte Carlo: {num_simulations} simulations, {len(trades)} trades")
        
        simulations = []
        final_capitals = []
        
        for sim_idx in range(num_simulations):
            # Randomly shuffle trades
            shuffled_trades = np.random.choice(trades, size=len(trades), replace=True)
            
            # Calculate equity curve
            capital = initial_capital
            equity_curve = [capital]
            
            for trade in shuffled_trades:
                pnl = trade.get('pnl', 0)
                capital += pnl
                equity_curve.append(capital)
            
            final_capital = capital
            total_return = (final_capital - initial_capital) / initial_capital
            max_drawdown = self._calculate_max_drawdown(equity_curve, initial_capital)
            
            simulations.append({
                'simulation_index': sim_idx,
                'final_capital': final_capital,
                'total_return': total_return,
                'max_drawdown': max_drawdown
            })
            
            final_capitals.append(final_capital)
        
        # Calculate statistics
        final_capitals = np.array(final_capitals)
        returns = (final_capitals - initial_capital) / initial_capital
        
        # ✅ NEW: Probability calculations
        prob_profit = np.sum(final_capitals > initial_capital) / num_simulations
        prob_ruin = np.sum(final_capitals < initial_capital * 0.5) / num_simulations  # 50% loss = ruin
        
        statistics = {
            'mean_return': float(np.mean(returns)),
            'std_return': float(np.std(returns)),
            'percentile_5': float(np.percentile(returns, 5)),
            'percentile_95': float(np.percentile(returns, 95)),
            'prob_profit': float(prob_profit),      # ✅ NEW
            'prob_ruin': float(prob_ruin),          # ✅ NEW
            'median_return': float(np.median(returns)),
            'best_case': float(np.max(returns)),
            'worst_case': float(np.min(returns))
        }
        
        logger.info(
            f"MC completed: mean={statistics['mean_return']:.2%}, "
            f"prob_profit={prob_profit:.1%}, prob_ruin={prob_ruin:.1%}"
        )
        
        return {
            'simulations': simulations,
            'statistics': statistics
        }
    
    def _calculate_max_drawdown(self, equity_curve: list[float], initial: float) -> float:
        """Calculate maximum drawdown from equity curve"""
        peak = initial
        max_dd = 0.0
        
        for equity in equity_curve:
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
        
        return max_dd
    
    def _empty_result(self) -> dict:
        """Empty result for no trades case"""
        return {
            'simulations': [],
            'statistics': {
                'mean_return': 0.0,
                'std_return': 0.0,
                'percentile_5': 0.0,
                'percentile_95': 0.0,
                'prob_profit': 0.0,
                'prob_ruin': 0.0
            }
        }
```

**Действия:**
1. ✅ Создать `backend/optimization/monte_carlo_simulator.py`
2. ✅ Добавить `prob_profit` и `prob_ruin` (сейчас отсутствуют)
3. ✅ Объединить логику из 2 реализаций
4. ❌ Удалить дубликаты
5. ✅ Написать unit tests

**Критерий приёмки:**
- [ ] `prob_profit` и `prob_ruin` рассчитываются
- [ ] Все старые реализации deprecated
- [ ] Тесты проходят

---

## ЗАДАЧА 2: СОЗДАТЬ DATAMANAGER КЛАСС (2 дня)

### Проблема
ТЗ 3.1.2 явно требует:
```python
class DataManager:
    def load_historical(limit=1000) -> pd.DataFrame
    def update_cache() -> None
    def get_multi_timeframe(timeframes: list) -> dict
```

Текущая реализация: функционал разбросан между `BybitAdapter` и `DataService`.

### Решение

**Файл:** `backend/services/data_manager.py`

```python
"""
DataManager - Фасад для работы с историческими данными

Соответствие ТЗ 3.1:
- Централизованное управление данными
- Кэширование (Parquet + DB)
- Multi-timeframe support
"""

import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
from loguru import logger

from backend.services.adapters.bybit import BybitAdapter
from backend.services.data_service import DataService


class DataManager:
    """
    ТЗ 3.1.2 - Управляет загрузкой, кэшированием и синхронизацией исторических данных
    
    Параметры:
    - symbol: str - Торговая пара (BTCUSDT, ETHUSDT, etc.)
    - timeframe: str - Таймфрейм ('1', '5', '15', '60', '240', 'D')
    - start_date: datetime - Начало исторического периода
    - end_date: datetime - Конец периода
    - cache_dir: str - Директория для локального кэша
    
    Методы:
    - load_historical(limit=1000) -> pd.DataFrame
    - update_cache() -> None
    - get_multi_timeframe(timeframes: list) -> dict[str, pd.DataFrame]
    """
    
    def __init__(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        cache_dir: str = "data/ohlcv"
    ):
        self.symbol = symbol.upper()
        self.timeframe = timeframe
        self.start_date = start_date or (datetime.now() - timedelta(days=365))
        self.end_date = end_date or datetime.now()
        self.cache_dir = Path(cache_dir)
        
        # Initialize adapters
        self.bybit = BybitAdapter()
        
        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(
            f"DataManager initialized: {self.symbol} @ {self.timeframe}, "
            f"cache={self.cache_dir}"
        )
    
    def load_historical(self, limit: int = 1000) -> pd.DataFrame:
        """
        Загрузить исторические данные
        
        1. Пытается загрузить из Parquet кэша
        2. Если нет - запрашивает из Bybit API
        3. Сохраняет в кэш
        
        Args:
            limit: Количество баров (максимум)
        
        Returns:
            DataFrame с колонками [timestamp, open, high, low, close, volume]
        """
        logger.info(f"Loading historical data for {self.symbol} @ {self.timeframe}, limit={limit}")
        
        # Try to load from Parquet cache
        cache_path = self._get_cache_path()
        
        if cache_path.exists():
            logger.info(f"Loading from cache: {cache_path}")
            df = pd.read_parquet(cache_path)
            
            # Filter by date range
            df = df[
                (df['timestamp'] >= self.start_date) &
                (df['timestamp'] <= self.end_date)
            ]
            
            if len(df) >= limit:
                logger.info(f"Cache hit: {len(df)} bars loaded")
                return df.tail(limit)
            else:
                logger.warning(f"Cache has only {len(df)} bars, need {limit}. Fetching from API...")
        
        # Fetch from Bybit API
        logger.info(f"Fetching from Bybit API: {self.symbol} @ {self.timeframe}")
        klines = self.bybit.get_klines(
            symbol=self.symbol,
            interval=self.timeframe,
            limit=limit
        )
        
        if not klines:
            logger.error("No data returned from Bybit API")
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(klines)
        
        # Normalize columns
        df = df.rename(columns={
            'open_time': 'timestamp',
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'volume': 'volume'
        })
        
        # Ensure timestamp is datetime
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Save to cache
        self.update_cache(df)
        
        logger.info(f"Loaded {len(df)} bars from API")
        return df
    
    def update_cache(self, data: pd.DataFrame | None = None) -> None:
        """
        Обновить Parquet кэш
        
        Args:
            data: DataFrame для сохранения (если None, загружает с API)
        """
        if data is None:
            data = self.load_historical()
        
        cache_path = self._get_cache_path()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save to Parquet
        data.to_parquet(cache_path, compression='snappy', index=False)
        
        logger.info(f"Cache updated: {cache_path}, {len(data)} bars")
    
    def get_multi_timeframe(self, timeframes: list[str]) -> dict[str, pd.DataFrame]:
        """
        Загрузить данные по нескольким таймфреймам
        
        Args:
            timeframes: Список таймфреймов ['1', '5', '15', '60']
        
        Returns:
            dict[timeframe, DataFrame]
        """
        logger.info(f"Loading multi-timeframe data: {timeframes}")
        
        result = {}
        
        for tf in timeframes:
            # Create DataManager for each timeframe
            dm = DataManager(
                symbol=self.symbol,
                timeframe=tf,
                start_date=self.start_date,
                end_date=self.end_date,
                cache_dir=str(self.cache_dir)
            )
            
            df = dm.load_historical()
            result[tf] = df
            
            logger.info(f"  {tf}: {len(df)} bars")
        
        return result
    
    def _get_cache_path(self) -> Path:
        """
        Получить путь к Parquet кэшу
        
        Format: data/ohlcv/{symbol}/{timeframe}.parquet
        """
        return self.cache_dir / self.symbol / f"{self.timeframe}.parquet"
```

**Действия:**
1. ✅ Создать `backend/services/data_manager.py`
2. ✅ Реализовать 3 метода из ТЗ
3. ✅ Добавить Parquet кэширование (ТЗ 7.3)
4. ✅ Интегрировать с BybitAdapter
5. ✅ Обновить все места использования (BacktestEngine, optimize_tasks)
6. ✅ Написать unit tests

**Критерий приёмки:**
- [ ] Класс `DataManager` существует
- [ ] 3 метода работают корректно
- [ ] Parquet кэш создаётся в `data/ohlcv/{symbol}/{timeframe}.parquet`
- [ ] Тесты проходят

---

## ЗАДАЧА 3: BUY & HOLD RETURN (1 день)

### Проблема
ТЗ 4.2 требует метрику "Buy & hold return":
```python
'Buy & hold return': float  # (last_price - first_price) / first_price * 100
```

Поле есть в Pydantic модели, но расчёт не реализован.

### Решение

**Файл:** `backend/services/report_generator.py`

**Найти строку:**
```python
def generate_performance_csv(self) -> str:
    # ... existing code ...
    
    # ❌ Отсутствует расчёт Buy & hold
```

**Заменить на:**
```python
def generate_performance_csv(self) -> str:
    # ... existing code ...
    
    # ✅ Calculate Buy & hold return
    buy_hold_return_usdt, buy_hold_return_pct = self._calculate_buy_hold_return()
    
    # ... use in CSV generation
```

**Добавить метод:**
```python
def _calculate_buy_hold_return(self) -> tuple[float, float]:
    """
    Рассчитать пассивную доходность (Buy & Hold)
    
    Formula (ТЗ 4.2):
    buy_hold_return = (last_price - first_price) / first_price * 100
    
    Returns:
        (usdt, percent)
    """
    if not self.all_trades:
        return 0.0, 0.0
    
    # Get first and last prices from trades
    first_trade = self.all_trades[0]
    last_trade = self.all_trades[-1]
    
    first_price = first_trade.get('entry_price', 0)
    last_price = last_trade.get('exit_price', first_trade.get('entry_price', 0))
    
    if first_price == 0:
        return 0.0, 0.0
    
    # Calculate return
    price_change = last_price - first_price
    pct_change = (price_change / first_price) * 100
    
    # Calculate USDT value (assuming same position size)
    position_value = first_trade.get('position_size_value', self.initial_capital)
    usdt_return = (price_change / first_price) * position_value
    
    logger.debug(
        f"Buy & hold: {first_price:.2f} → {last_price:.2f} = "
        f"{pct_change:.2f}% (${usdt_return:.2f})"
    )
    
    return usdt_return, pct_change
```

**Действия:**
1. ✅ Добавить метод `_calculate_buy_hold_return`
2. ✅ Интегрировать в `generate_performance_csv`
3. ✅ Обновить тесты в `tests/test_report_generator.py`
4. ✅ Проверить соответствие ТЗ формуле

**Критерий приёмки:**
- [ ] Buy & hold return рассчитывается
- [ ] Значение присутствует в Performance.csv
- [ ] Тесты проходят (16/16)

---

## ЗАДАЧА 4: SIGNAL EXIT (2 дня)

### Проблема
ТЗ 3.2.2 требует выход по сигналу:
```python
'signal_exit': {
    'enabled': True,
    'signals': ['opposite_signal', 'reversal_pattern']
}
```

Сейчас отсутствует.

### Решение

#### 4.1 Обновить Pydantic модель

**Файл:** `backend/models/data_types.py`

**Найти:**
```python
class ExitConditions(BaseModel):
    take_profit: TakeProfitConfig
    stop_loss: StopLossConfig
    trailing_stop: TrailingStopConfig
    time_exit: TimeExitConfig
```

**Добавить:**
```python
class SignalExitConfig(BaseModel):
    """Конфигурация выхода по сигналу"""
    enabled: bool
    signals: list[str] = Field(
        default_factory=lambda: ['opposite_signal'],
        description="Типы сигналов выхода"
    )


class ExitConditions(BaseModel):
    take_profit: TakeProfitConfig
    stop_loss: StopLossConfig
    trailing_stop: TrailingStopConfig
    time_exit: TimeExitConfig
    signal_exit: SignalExitConfig  # ✅ NEW
```

#### 4.2 Реализовать в BacktestEngine

**Файл:** `backend/core/backtest_engine.py`

**Найти метод `_check_exit_conditions`:**
```python
def _check_exit_conditions(self, position, bar, bar_index, config):
    # ... existing TP/SL/Trailing logic ...
    
    # ✅ NEW: Signal exit
    if config.get('signal_exit', {}).get('enabled', False):
        exit_signals = config['signal_exit'].get('signals', [])
        
        if 'opposite_signal' in exit_signals:
            # Check for opposite signal
            if self._has_opposite_signal(position, bar_index):
                return True, 'opposite_signal'
        
        if 'reversal_pattern' in exit_signals:
            # Check for reversal pattern
            if self._has_reversal_pattern(bar_index):
                return True, 'reversal_pattern'
    
    return False, None


def _has_opposite_signal(self, position: Position, bar_index: int) -> bool:
    """Check if opposite signal occurred"""
    strategy_type = self.config.get('type', 'ema_crossover')
    
    if strategy_type == 'ema_crossover':
        ema_fast = self.state.indicators['ema_fast'].iloc[bar_index]
        ema_slow = self.state.indicators['ema_slow'].iloc[bar_index]
        
        if position.side == 'long':
            # Exit long when fast crosses below slow
            prev_fast = self.state.indicators['ema_fast'].iloc[bar_index - 1]
            prev_slow = self.state.indicators['ema_slow'].iloc[bar_index - 1]
            
            return prev_fast >= prev_slow and ema_fast < ema_slow
        
        elif position.side == 'short':
            # Exit short when fast crosses above slow
            prev_fast = self.state.indicators['ema_fast'].iloc[bar_index - 1]
            prev_slow = self.state.indicators['ema_slow'].iloc[bar_index - 1]
            
            return prev_fast <= prev_slow and ema_fast > ema_slow
    
    return False
```

**Действия:**
1. ✅ Добавить `SignalExitConfig` в Pydantic модели
2. ✅ Реализовать `_has_opposite_signal` в BacktestEngine
3. ✅ Реализовать `_has_reversal_pattern` (опционально)
4. ✅ Интегрировать в `_check_exit_conditions`
5. ✅ Обновить тесты

**Критерий приёмки:**
- [ ] Signal exit работает
- [ ] Opposite signal корректно детектируется
- [ ] Тесты проходят
- [ ] Exit reason = 'opposite_signal' в trades

---

## ТЕСТИРОВАНИЕ ФАЗЫ 1

### Unit Tests

Создать/обновить тесты:

1. ✅ `tests/test_walk_forward_optimizer.py`
   ```python
   def test_parameter_stability():
       """Test that parameter_stability is calculated"""
       # ...
   ```

2. ✅ `tests/test_monte_carlo_simulator.py`
   ```python
   def test_prob_profit_and_prob_ruin():
       """Test that probabilities are calculated"""
       # ...
   ```

3. ✅ `tests/test_data_manager.py`
   ```python
   def test_load_historical_from_cache():
       """Test Parquet cache loading"""
       # ...
   
   def test_multi_timeframe():
       """Test multi-TF loading"""
       # ...
   ```

4. ✅ `tests/test_report_generator.py` (обновить)
   ```python
   def test_buy_hold_return_calculation():
       """Test Buy & hold return formula"""
       # ...
   ```

5. ✅ `tests/test_backtest_engine.py` (обновить)
   ```python
   def test_signal_exit_opposite():
       """Test exit on opposite signal"""
       # ...
   ```

### Integration Tests

6. ✅ `tests/integration/test_wfo_end_to_end.py`
   ```python
   def test_walk_forward_full_cycle():
       """Test WFO from API to results"""
       # ...
   ```

---

## КРИТЕРИИ ПРИЁМКИ ФАЗЫ 1

### Checklist

- [ ] **Задача 1**: Консолидация оптимизации
  - [ ] WalkForwardOptimizer единый класс
  - [ ] MonteCarloSimulator единый класс
  - [ ] parameter_stability реализован
  - [ ] prob_profit/prob_ruin реализованы
  - [ ] Старые реализации deprecated
  - [ ] Тесты: 20/20 passing

- [ ] **Задача 2**: DataManager класс
  - [ ] Класс создан
  - [ ] 3 метода работают (load_historical, update_cache, get_multi_timeframe)
  - [ ] Parquet кэш создаётся
  - [ ] Интеграция с BacktestEngine
  - [ ] Тесты: 15/15 passing

- [ ] **Задача 3**: Buy & hold return
  - [ ] Метод реализован
  - [ ] Значение в Performance.csv
  - [ ] Формула соответствует ТЗ
  - [ ] Тесты: 16/16 passing (test_report_generator)

- [ ] **Задача 4**: Signal exit
  - [ ] SignalExitConfig модель
  - [ ] Логика в BacktestEngine
  - [ ] opposite_signal работает
  - [ ] Exit reason сохраняется
  - [ ] Тесты: 30/30 passing

### Метрики успеха

| Метрика | До Фазы 1 | После Фазы 1 | Цель |
|---------|-----------|--------------|------|
| Соответствие ТЗ MVP | 92% | 100% | ✅ 100% |
| Покрытие тестами | 75% | 85% | ✅ 85% |
| Критические баги | 4 | 0 | ✅ 0 |
| Дублирование кода | 5 мест | 0 | ✅ 0 |

---

## TIMELINE

### Неделя 1

**День 1-2:** Задача 1 (WFO + Monte Carlo)
- Создать новые классы
- Миграция логики
- Написать тесты

**День 3:** Задача 2 (DataManager)
- Создать класс
- Parquet кэш
- Тесты

**День 4:** Задача 3 + 4 (Buy & hold + Signal exit)
- Реализовать обе задачи
- Тесты

**День 5:** Code review + QA
- Проверка всех тестов
- Интеграционное тестирование
- Документация

### Неделя 2 (buffer)

**День 6-7:** Баг-фиксы
- Исправление найденных проблем
- Оптимизация

**День 8-10:** Подготовка к Фазе 2
- Planning
- Documentation
- Sprint review

---

## NEXT STEPS ПОСЛЕ ФАЗЫ 1

После успешного завершения:

1. ✅ **Release v0.9-beta** (MVP ready)
2. 🟡 **Начать Фазу 2**: Уровни доступа + Commission модель
3. 📊 **Performance benchmarks**: Проверить ТЗ 9.2 требования
4. 📝 **Update документация**: README, API docs

**Дата начала Фазы 1:** 25 октября 2025  
**Целевая дата завершения:** 8 ноября 2025  
**Ответственный:** Development Team
