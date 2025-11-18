# Monte Carlo Simulation (ТЗ 3.5.3)

## Обзор

Monte Carlo Simulation - это метод оценки рисков торговой стратегии через случайную перестановку исторических сделок. Вместо анализа одного исторического сценария, создаём тысячи альтернативных сценариев чтобы понять:
- **Насколько стабильны результаты?**
- **Какова вероятность прибыли?**
- **Какой реальный risk of ruin?**

## Метод Bootstrap

### Как работает

```python
# Оригинальные сделки
trades = [+100, -50, +200, +150, -75]  # PnL каждой сделки

# Bootstrap iteration #1
shuffled = [-50, +200, +100, +150, -75]  # Случайная перестановка

# Bootstrap iteration #2
shuffled = [+100, +100, -50, +200, +150]  # С возвратом (могут повторяться!)

# ... 1000 итераций ...
```

### Почему bootstrap?

1. **Не делаем предположений** о распределении доходности
2. **Сохраняем реальные характеристики** сделок
3. **Учитываем последовательности** wins/losses
4. **Оцениваем вариативность** результатов

## Метрики

### 1. Probability of Profit (Вероятность прибыли)
```python
prob_profit = (количество прибыльных симуляций) / (всего симуляций)
```
- **Хорошо**: > 0.7 (70%+ симуляций прибыльные)
- **Приемлемо**: 0.5-0.7
- **Плохо**: < 0.5

### 2. Probability of Ruin (Вероятность разорения)
```python
prob_ruin = (количество симуляций с DD >= threshold) / (всего симуляций)
```
- **Низкий риск**: < 0.1 (10% симуляций с критической просадкой)
- **Средний риск**: 0.1-0.2
- **Высокий риск**: > 0.2

### 3. Confidence Intervals (Доверительные интервалы)
```python
# 95% CI
CI_95 = [percentile_2.5, percentile_97.5]

# 90% CI
CI_90 = [percentile_5, percentile_95]
```
- Показывает **диапазон возможных доходностей**
- Узкий интервал = стабильная стратегия
- Широкий интервал = высокая вариативность

### 4. Percentile Ranking
```python
percentile = (симуляций хуже оригинала) / (всего симуляций) * 100
```
- **> 50%**: Оригинальная стратегия выше медианы
- **< 50%**: Оригинальная стратегия ниже медианы
- Показывает **насколько типичен** исторический результат

## Использование

### Python API

```python
from backend.optimization import MonteCarloSimulator

# Создание симулятора
mc = MonteCarloSimulator(
    n_simulations=1000,      # Количество симуляций (min 10, recommend 1000+)
    ruin_threshold=20.0,     # Порог разорения в % от капитала
    random_seed=42,          # Для воспроизводимости (optional)
)

# Подготовка сделок
trades = [
    {'pnl': 100, 'pnl_pct': 1.0, 'side': 'long'},
    {'pnl': -50, 'pnl_pct': -0.5, 'side': 'short'},
    {'pnl': 200, 'pnl_pct': 2.0, 'side': 'long'},
    # ... остальные сделки
]

# Запуск симуляции
result = mc.run(
    trades=trades,
    initial_capital=10000,
)

# Анализ результатов
print(f"📊 Monte Carlo Results ({result.n_simulations} simulations)")
print(f"Original Return: {result.original_return:.2f}%")
print(f"Mean Return: {result.mean_return:.2f}% (±{result.std_return:.2f}%)")
print(f"Median Return: {result.percentile_50:.2f}%")
print()
print(f"📈 Percentiles:")
print(f"  5th:  {result.percentile_5:.2f}%")
print(f"  25th: {result.percentile_25:.2f}%")
print(f"  50th: {result.percentile_50:.2f}% (median)")
print(f"  75th: {result.percentile_75:.2f}%")
print(f"  95th: {result.percentile_95:.2f}%")
print()
print(f"🎲 Probabilities:")
print(f"  Profit: {result.prob_profit:.1%}")
print(f"  Ruin (DD >= 20%): {result.prob_ruin:.1%}")
print()
print(f"🏆 Original Percentile: {result.original_percentile:.1f}%")

# Доверительные интервалы
ci_95_lower, ci_95_upper = mc.get_confidence_interval(result, confidence=0.95)
ci_90_lower, ci_90_upper = mc.get_confidence_interval(result, confidence=0.90)

print(f"\n📐 Confidence Intervals:")
print(f"  95% CI: [{ci_95_lower:.2f}%, {ci_95_upper:.2f}%]")
print(f"  90% CI: [{ci_90_lower:.2f}%, {ci_90_upper:.2f}%]")

# Риск разорения
risk_30 = mc.get_risk_of_ruin(result, ruin_level=30.0)
risk_50 = mc.get_risk_of_ruin(result, ruin_level=50.0)

print(f"\n⚠️ Risk of Ruin:")
print(f"  DD >= 30%: {risk_30:.1%}")
print(f"  DD >= 50%: {risk_50:.1%}")

# Генерация сводки
summary = mc.generate_summary(result)

print(f"\n{summary['risk_emoji']} Risk Level: {summary['risk_level']}")
print(f"{summary['recommendation']}")
print(f"\nKey Findings:")
for finding in summary['key_findings']:
    print(f"  • {finding}")
```

### Пример вывода

```
📊 Monte Carlo Results (1000 simulations)
Original Return: 42.42%
Mean Return: 41.85% (±5.23%)
Median Return: 42.10%

📈 Percentiles:
  5th:  31.50%
  25th: 38.20%
  50th: 42.10% (median)
  75th: 45.70%
  95th: 51.30%

🎲 Probabilities:
  Profit: 95.2%
  Ruin (DD >= 20%): 8.5%

🏆 Original Percentile: 52.3%

📐 Confidence Intervals:
  95% CI: [31.50%, 51.30%]
  90% CI: [33.80%, 49.50%]

⚠️ Risk of Ruin:
  DD >= 30%: 2.1%
  DD >= 50%: 0.3%

🟢 Risk Level: Низкий
✅ Стратегия показывает стабильные результаты

Key Findings:
  • Вероятность прибыли: 95.2%
  • Вероятность разорения (>20.0% DD): 8.5%
  • Средняя доходность: 41.85% (±5.23%)
  • 95% доверительный интервал: [31.50%, 51.30%]
```

## Сериализация результатов

```python
# В JSON
result_dict = result.to_dict()

# Структура
{
    "n_simulations": 1000,
    "original_return": 42.42,
    "mean_return": 41.85,
    "std_return": 5.23,
    "percentile_5": 31.50,
    "percentile_25": 38.20,
    "percentile_50": 42.10,
    "percentile_75": 45.70,
    "percentile_95": 51.30,
    "prob_profit": 0.952,
    "prob_ruin": 0.085,
    "original_percentile": 52.3,
    "distribution": {
        "returns": [42.5, 40.2, 43.1, ...],
        "max_drawdowns": [12.3, 15.8, 10.5, ...],
        "sharpe_ratios": [1.8, 1.5, 2.1, ...]
    }
}
```

## Интерпретация результатов

### Сценарий 1: Стабильная стратегия ✅

```python
result.prob_profit = 0.85       # 85% симуляций прибыльные
result.prob_ruin = 0.05         # 5% симуляций с критической просадкой
result.percentile_95 = 45.2     # 95% CI верхняя граница
result.percentile_5 = 35.8      # 95% CI нижняя граница
# Ширина CI: 45.2 - 35.8 = 9.4%

✅ Высокая вероятность прибыли
✅ Низкий риск разорения
✅ Узкий доверительный интервал
→ Стратегия робастная, можно использовать
```

### Сценарий 2: Нестабильная стратегия ⚠️

```python
result.prob_profit = 0.65       # 65% симуляций прибыльные
result.prob_ruin = 0.15         # 15% симуляций с критической просадкой
result.percentile_95 = 60.5     # 95% CI верхняя граница
result.percentile_5 = -10.2     # 95% CI нижняя граница
# Ширина CI: 60.5 - (-10.2) = 70.7%

⚠️ Средняя вероятность прибыли
⚠️ Средний риск разорения
⚠️ Очень широкий доверительный интервал
→ Результаты сильно зависят от порядка сделок
→ Требуется дополнительная оптимизация
```

### Сценарий 3: Рискованная стратегия ❌

```python
result.prob_profit = 0.45       # 45% симуляций прибыльные
result.prob_ruin = 0.30         # 30% симуляций с критической просадкой
result.percentile_95 = 20.5
result.percentile_5 = -35.8

❌ Низкая вероятность прибыли
❌ Высокий риск разорения
❌ Отрицательный 5-й перцентиль
→ Стратегия НЕ рекомендуется для live trading
→ Требуется полная переработка
```

## Лучшие практики

### Количество симуляций

```python
# Быстрый тест
mc = MonteCarloSimulator(n_simulations=100)

# Стандартный анализ
mc = MonteCarloSimulator(n_simulations=1000)  # ← Рекомендуется

# Финальная валидация
mc = MonteCarloSimulator(n_simulations=5000)

# Исследование
mc = MonteCarloSimulator(n_simulations=10000)
```

### Порог разорения

```python
# Консервативный (для новичков)
mc = MonteCarloSimulator(ruin_threshold=10.0)  # 10% DD

# Стандартный
mc = MonteCarloSimulator(ruin_threshold=20.0)  # 20% DD ← Default

# Агрессивный
mc = MonteCarloSimulator(ruin_threshold=30.0)  # 30% DD
```

### Минимальное количество сделок

- **< 30 сделок**: Результаты ненадёжны
- **30-100 сделок**: Приемлемо для предварительного анализа
- **100-500 сделок**: Хорошо для финальной валидации
- **> 500 сделок**: Отличная статистическая база

## Комбинация с Walk-Forward

Используйте Monte Carlo **ПОСЛЕ** Walk-Forward для максимальной надёжности:

```python
from backend.optimization import WalkForwardOptimizer, MonteCarloSimulator, WFOConfig

# 1. Walk-Forward для проверки overfitting
wfo = WalkForwardOptimizer(config=WFOConfig(mode=WFOMode.ROLLING))
wfo_results = wfo.optimize(data, param_ranges, strategy_config, 'sharpe_ratio')

# 2. Берём OOS сделки из всех периодов
all_oos_trades = []
for period in wfo_results['walk_results']:
    all_oos_trades.extend(period['oos_trades'])  # Гипотетически

# 3. Monte Carlo на OOS сделках
mc = MonteCarloSimulator(n_simulations=1000, ruin_threshold=20.0)
mc_results = mc.run(all_oos_trades, initial_capital=10000)

# 4. Двойная валидация
print(f"WFO Robustness Score: {wfo_results['summary']['robustness_score']:.1f}")
print(f"MC Probability of Profit: {mc_results.prob_profit:.1%}")

if wfo_results['summary']['robustness_score'] > 70 and mc_results.prob_profit > 0.7:
    print("✅ Стратегия прошла обе валидации!")
else:
    print("⚠️ Требуется доработка")
```

## Визуализация

### Distribution Plot (гистограмма доходностей)

```python
import matplotlib.pyplot as plt

plt.figure(figsize=(12, 6))

# Histogram
plt.hist(result.all_returns, bins=50, alpha=0.7, edgecolor='black')

# Vertical lines
plt.axvline(result.original_return, color='red', linestyle='--', linewidth=2, label='Original')
plt.axvline(result.percentile_5, color='orange', linestyle=':', linewidth=1.5, label='5th percentile')
plt.axvline(result.percentile_95, color='orange', linestyle=':', linewidth=1.5, label='95th percentile')
plt.axvline(result.mean_return, color='blue', linestyle='-', linewidth=2, label='Mean')

plt.xlabel('Return (%)')
plt.ylabel('Frequency')
plt.title(f'Monte Carlo Return Distribution ({result.n_simulations} simulations)')
plt.legend()
plt.grid(alpha=0.3)
plt.show()
```

### Cone of Uncertainty (веер неопределённости)

```python
import numpy as np
import matplotlib.pyplot as plt

# Симуляция equity curves
n_trades = len(trades)
equity_curves = []

for i in range(100):  # 100 случайных путей
    indices = np.random.choice(n_trades, size=n_trades, replace=True)
    shuffled = [trades[idx] for idx in indices]
    
    equity = [initial_capital]
    for trade in shuffled:
        equity.append(equity[-1] + trade['pnl'])
    
    equity_curves.append(equity)

# Plot
plt.figure(figsize=(14, 8))

for eq in equity_curves:
    plt.plot(eq, alpha=0.1, color='blue')

# Percentiles
equity_array = np.array(equity_curves)
p5 = np.percentile(equity_array, 5, axis=0)
p95 = np.percentile(equity_array, 95, axis=0)

plt.fill_between(range(len(p5)), p5, p95, alpha=0.3, color='orange', label='90% CI')
plt.plot(p5, color='red', linestyle='--', label='5th percentile')
plt.plot(p95, color='green', linestyle='--', label='95th percentile')

plt.xlabel('Trade Number')
plt.ylabel('Equity ($)')
plt.title('Monte Carlo Cone of Uncertainty')
plt.legend()
plt.grid(alpha=0.3)
plt.show()
```

## Тестирование

```bash
# Запустить все тесты
pytest tests/test_monte_carlo.py -v

# Конкретный тест
pytest tests/test_monte_carlo.py::test_mc_profitable_strategy -v

# С покрытием
pytest tests/test_monte_carlo.py --cov=backend.optimization.monte_carlo --cov-report=html
```

## Troubleshooting

### "Список trades не может быть пустым"
- **Причина**: Передан пустой список сделок
- **Решение**: Убедитесь что backtest сгенерировал хотя бы одну сделку

### "Сделка X не содержит 'pnl'"
- **Причина**: В сделке отсутствует поле `pnl`
- **Решение**: Убедитесь что каждая сделка имеет поле `pnl` (profit/loss в USDT)

### Низкая вариативность (std_return ≈ 0)
- **Причина**: Слишком мало уникальных сделок (< 10)
- **Решение**: Проведите backtest на большем периоде данных

### Все симуляции идентичны
- **Причина**: Только одна сделка в списке
- **Решение**: Bootstrap с одной сделкой всегда даёт одинаковый результат. Нужно минимум 10+ сделок.

## См. также
- [WalkForwardOptimizer](./README_WALK_FORWARD.md) - Защита от overfitting
- [GridOptimizer](./README.md) - Базовая оптимизация
- [ТЗ 3.5.3](../../ТЗ.md#353-monte-carlo-simulation) - Техническое задание
