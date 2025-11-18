# Walk-Forward Optimization (ТЗ 3.5.2)

## Обзор

Walk-Forward оптимизация - это метод защиты от переобучения (overfitting) в алгоритмической торговле. Вместо оптимизации параметров на всём датасете, WFO разделяет данные на периоды:
- **In-Sample (IS)** - обучающий период для оптимизации
- **Out-of-Sample (OOS)** - тестовый период для валидации

Цикл повторяется с "шагом окна", создавая последовательность IS/OOS периодов.

## Режимы работы

### 1. Rolling Window (Фиксированное окно)
```
Данные: |--------------------------------|
Period 1: [IS====][OOS=]
Period 2:      [IS====][OOS=]
Period 3:           [IS====][OOS=]
```
- Окно фиксированного размера сдвигается вперёд
- Размер IS и OOS не меняется
- **Когда использовать**: Рынок быстро меняется, свежие данные важнее

### 2. Anchored Window (Расширяющееся окно)
```
Данные: |--------------------------------|
Period 1: [IS====][OOS=]
Period 2: [IS=========][OOS=]
Period 3: [IS==============][OOS=]
```
- IS окно начинается всегда с начала данных
- Каждый период IS расширяется, OOS сдвигается
- **Когда использовать**: Долгосрочные тренды, больше данных = лучше

## Метрики

### 1. Efficiency (Эффективность)
```python
efficiency = OOS_metric / IS_metric
```
- **Идеально**: ≈ 1.0 (OOS = IS)
- **Хорошо**: > 0.8 (OOS близок к IS)
- **Плохо**: < 0.5 (сильная деградация на OOS)

### 2. Degradation (Деградация)
```python
degradation = IS_sharpe - OOS_sharpe
```
- **Идеально**: ≈ 0 (нет переобучения)
- **Допустимо**: < 0.5
- **Переобучение**: > 1.0

### 3. Robustness Score (Оценка робастности)
```python
robustness_score = (
    0.40 * avg_efficiency +
    0.30 * consistency_score +
    0.30 * (1 - avg_parameter_variability)
) * 100
```
- **Отлично**: > 70
- **Хорошо**: 50-70
- **Плохо**: < 50

### 4. Consistency Score (Консистентность)
```python
consistency_score = profitable_oos_periods / total_periods
```
- Процент OOS периодов с положительной прибылью
- **Хорошо**: > 0.7 (70%+ периодов профитны)

### 5. Parameter Stability (Стабильность параметров)
```python
stability_score = 1 - (std / (max - min + 1))
```
- **Стабильно**: > 0.7 (параметры мало меняются)
- **Нестабильно**: < 0.5 (параметры скачут)

## Использование

### Python API

```python
from backend.optimization.walk_forward import (
    WalkForwardOptimizer,
    WFOConfig,
    WFOMode,
    ParameterRange,
)

# Конфигурация
config = WFOConfig(
    in_sample_size=252,      # 252 bars для IS (1 год дневных данных)
    out_sample_size=63,      # 63 bars для OOS (3 месяца)
    step_size=63,            # Сдвиг на 3 месяца
    mode=WFOMode.ROLLING,    # или WFOMode.ANCHORED
    min_trades=30,           # Минимум сделок для валидности
    max_drawdown=0.50,       # Максимальная просадка 50%
)

# Параметры для оптимизации
param_ranges = {
    'tp_pct': ParameterRange(1.0, 3.0, 0.5),  # [1.0, 1.5, 2.0, 2.5, 3.0]
    'sl_pct': ParameterRange(0.5, 2.0, 0.5),  # [0.5, 1.0, 1.5, 2.0]
    'trailing_activation_pct': [0.0, 0.5, 1.0],  # Можно передать список
}

# Запуск
wfo = WalkForwardOptimizer(config=config)
results = wfo.optimize(
    data=candles_dataframe,
    param_ranges=param_ranges,
    strategy_config={'strategy_type': 'my_strategy'},
    metric='sharpe_ratio',
)

# Результаты
print(f"Robustness Score: {results['summary']['robustness_score']:.2f}")
print(f"Recommendation: {results['summary']['recommendation']}")
print(f"Total Periods: {results['aggregated_metrics']['total_periods']}")
print(f"Avg Efficiency: {results['aggregated_metrics']['avg_efficiency']:.3f}")
print(f"Consistency: {results['aggregated_metrics']['consistency_score']:.2%}")

# Детали по периодам
for period in results['walk_results']:
    print(f"\nPeriod {period['period_num']}:")
    print(f"  Best Params: {period['best_params']}")
    print(f"  IS Sharpe: {period['is_sharpe']:.3f}")
    print(f"  OOS Sharpe: {period['oos_sharpe']:.3f}")
    print(f"  Efficiency: {period['efficiency']:.3f}")
    print(f"  Degradation: {period['degradation']:.3f}")

# Стабильность параметров
for param, stats in results['parameter_stability'].items():
    print(f"\n{param}:")
    print(f"  Mean: {stats['mean']:.3f}")
    print(f"  Std Dev: {stats['std']:.3f}")
    print(f"  Stability: {stats['stability_score']:.2%}")
```

### Celery Task API

```python
from backend.tasks.optimize_tasks import walk_forward_task

# Запустить асинхронно
task = walk_forward_task.delay(
    optimization_id=123,
    strategy_config={'strategy_type': 'breakout'},
    param_space={
        'tp_pct': [1.0, 1.5, 2.0, 2.5, 3.0],
        'sl_pct': [0.5, 1.0, 1.5, 2.0],
    },
    symbol='BTCUSDT',
    interval='1h',
    start_date='2024-01-01',
    end_date='2024-12-31',
    train_size=252,
    test_size=63,
    step_size=63,
    mode='rolling',  # или 'anchored'
    metric='sharpe_ratio',
)

# Проверить статус
print(task.state)  # PENDING, PROGRESS, SUCCESS, FAILURE

# Получить результат
result = task.get(timeout=3600)  # Таймаут 1 час
print(result['results']['summary']['robustness_score'])
```

### REST API (FastAPI)

```bash
# Создать оптимизацию
curl -X POST http://localhost:8000/api/optimizations \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_id": 1,
    "optimization_type": "walk_forward",
    "symbol": "BTCUSDT",
    "timeframe": "1h",
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "param_ranges": {
      "tp_pct": {"start": 1.0, "stop": 3.0, "step": 0.5},
      "sl_pct": {"start": 0.5, "stop": 2.0, "step": 0.5}
    },
    "metric": "sharpe_ratio",
    "config": {
      "mode": "rolling",
      "train_size": 252,
      "test_size": 63,
      "step_size": 63
    }
  }'

# Запустить WFO задачу
curl -X POST http://localhost:8000/api/optimizations/1/run/walk-forward

# Получить результаты
curl http://localhost:8000/api/optimizations/1
```

## Интерпретация результатов

### Пример вывода
```python
{
  "summary": {
    "robustness_score": 75.3,
    "recommendation": "✅ Strong robustness. Parameters are stable across periods.",
    "key_findings": [
      "Average efficiency: 0.85 (strong IS→OOS transfer)",
      "Low degradation: 0.15 (minimal overfitting)",
      "High consistency: 0.80 (80% periods profitable)"
    ]
  },
  "aggregated_metrics": {
    "total_periods": 4,
    "avg_efficiency": 0.85,
    "avg_degradation": 0.15,
    "oos_total_return_pct": 12.5,
    "oos_avg_sharpe": 1.4,
    "consistency_score": 0.80
  },
  "parameter_stability": {
    "tp_pct": {
      "mean": 2.0,
      "std": 0.3,
      "stability_score": 0.85,
      "values": [2.0, 1.5, 2.5, 2.0]
    }
  }
}
```

### Как читать:

#### 🟢 Robustness Score > 70
- Стратегия **робастная**
- Можно использовать для live trading
- Низкий риск переобучения

#### 🟡 Robustness Score 50-70
- Стратегия **умеренная**
- Нужна дополнительная валидация
- Рассмотреть упрощение стратегии

#### 🔴 Robustness Score < 50
- Стратегия **слабая**
- Высокий риск переобучения
- Требуется переработка

### Признаки переобучения:
- ❌ Efficiency < 0.5
- ❌ Degradation > 1.0
- ❌ Consistency < 0.5
- ❌ Parameter Stability < 0.5

### Признаки робастности:
- ✅ Efficiency > 0.8
- ✅ Degradation < 0.3
- ✅ Consistency > 0.7
- ✅ Parameter Stability > 0.7

## Примеры использования

### 1. Быстрый тест стратегии
```python
config = WFOConfig(
    in_sample_size=100,
    out_sample_size=50,
    step_size=50,
    mode=WFOMode.ROLLING,
)
```

### 2. Долгосрочный анализ
```python
config = WFOConfig(
    in_sample_size=365,  # 1 год
    out_sample_size=90,  # 3 месяца
    step_size=90,
    mode=WFOMode.ANCHORED,
)
```

### 3. Высокочастотная стратегия
```python
config = WFOConfig(
    in_sample_size=1000,  # 1000 баров
    out_sample_size=200,  # 200 баров
    step_size=200,
    mode=WFOMode.ROLLING,
    min_trades=100,  # Больше сделок для HFT
)
```

## Рекомендации

### Размер окон
- **Минимум IS**: 100 баров (для статистической значимости)
- **Соотношение IS:OOS**: 3:1 или 4:1
- **Step size**: = OOS size (без перекрытия)

### Параметры
- Начинайте с **широких диапазонов**
- Ограничивайте **3-5 параметрами** (curse of dimensionality)
- Используйте **крупные шаги** (step) для ускорения

### Метрики
- **Sharpe Ratio**: Универсальная метрика
- **Profit Factor**: Для фокуса на прибыльности
- **Win Rate**: Для психологического комфорта

## Миграция со старого WalkForwardAnalyzer

```python
# Старый код (backend.core.walkforward)
from backend.core.walkforward import WalkForwardAnalyzer

analyzer = WalkForwardAnalyzer(
    data=data,
    initial_capital=10000,
    commission=0.001,
    is_window_days=120,
    oos_window_days=60,
    step_days=30,
)
results = await analyzer.run_async(strategy_config, param_space, metric)

# Новый код (backend.optimization.walk_forward)
from backend.optimization.walk_forward import WalkForwardOptimizer, WFOConfig, WFOMode

config = WFOConfig(
    in_sample_size=120,
    out_sample_size=60,
    step_size=30,
    mode=WFOMode.ROLLING,
)
wfo = WalkForwardOptimizer(config=config)
results = wfo.optimize(data, param_ranges, strategy_config, metric, engine)
```

### Ключевые отличия:
1. **Синхронный API** (не async) - проще в использовании
2. **Больше метрик**: efficiency, degradation, robustness_score
3. **Anchored mode** - новый режим для расширяющихся окон
4. **Parameter stability** - анализ стабильности параметров
5. **Recommendations** - автоматические рекомендации

## Тестирование

```bash
# Запустить тесты
pytest tests/test_walk_forward_optimizer.py -v

# Конкретный тест
pytest tests/test_walk_forward_optimizer.py::test_wfo_rolling_mode -v

# С покрытием
pytest tests/test_walk_forward_optimizer.py --cov=backend.optimization.walk_forward --cov-report=html
```

## Troubleshooting

### "Not enough data for walk-forward analysis"
- **Причина**: `len(data) < in_sample_size + out_sample_size`
- **Решение**: Загрузите больше данных или уменьшите размеры окон

### "No valid results found in any period"
- **Причина**: min_trades или max_drawdown слишком строгие
- **Решение**: Уменьшите min_trades или увеличьте max_drawdown

### "Grid search returned None"
- **Причина**: Ни одна комбинация параметров не прошла валидацию
- **Решение**: Проверьте param_ranges и ослабьте ограничения

### Медленная работа
- **Причина**: Слишком много комбинаций параметров
- **Решение**: Увеличьте step в ParameterRange или используйте меньше параметров

## См. также
- [GridOptimizer](./README_GRID.md) - Простая Grid Search оптимизация
- [MonteCarloSimulator](./README_MONTE_CARLO.md) - Оценка рисков
- [ТЗ 3.5.2](../../ТЗ.md#352-walk-forward-optimization) - Техническое задание
