# ML-оптимизация торговых стратегий через Copilot ↔ Perplexity AI

**Автоматизированная система оптимизации параметров стратегий на основе ML и AI**

## 🎯 Описание

Интеграция ML-библиотек (CatBoost, XGBoost, LightGBM) с Perplexity AI для автоматизации оптимизации торговых стратегий на криптовалютах.

### Схема работы

```
Copilot → Scripts → Perplexity AI (MCP Server) → ML-Optimization → Copilot
    ↓                                                      ↑
   Запрос                                            Результаты
```

## 🚀 Быстрый старт

### 1. Установка зависимостей

```powershell
# ML-библиотеки для оптимизации
pip install -r requirements-ml.txt
```

### 2. Настройка Perplexity API

Создайте файл `.env` в корне проекта:

```env
PERPLEXITY_API_KEY=pplx-your-api-key-here
```

### 3. Запуск E2E теста

```powershell
python test_ml_optimization_e2e.py
```

## 📦 Установленные компоненты

### ML-библиотеки

| Библиотека | Версия | Применение |
|------------|--------|------------|
| **CatBoost** | ≥1.2.5 | Оптимизация временных рядов, DCA стратегий |
| **XGBoost** | ≥2.0.3 | Grid/Bayes поиск, сеточные стратегии |
| **LightGBM** | ≥4.3.0 | Скоростные оптимизации больших данных |
| **scikit-learn** | ≥1.4.2 | Grid/Random Search, кросс-валидация |
| **Optuna** | ≥3.6.1 | Bayesian Optimization |

### Структура проекта

```
backend/ml/
├── __init__.py              # ML-модуль
├── optimizer.py             # ML-оптимизаторы (CatBoost/XGBoost/LightGBM)
└── prompts.py               # Библиотека промптов для Perplexity

ml_optimizer_perplexity.py   # Скрипт взаимодействия с Perplexity AI
test_ml_optimization_e2e.py  # E2E тест полного цикла
requirements-ml.txt          # ML-зависимости
```

## 💡 Использование

### Вариант 1: Автоматическая оптимизация

```python
import asyncio
from backend.core.backtest_engine import BacktestEngine
import pandas as pd

# Загрузить данные
data = pd.read_csv('btc_usdt_1h.csv')

# Создать движок
engine = BacktestEngine(initial_capital=10_000)

# Автоматическая оптимизация
async def optimize():
    result = await engine.auto_optimize(
        data=data,
        strategy_type='sr_rsi',          # 'sr_rsi', 'ema_crossover', 'scalping'
        optimization_goal='sharpe_ratio', # 'sharpe_ratio', 'win_rate', 'total_return'
        quick_mode=False                  # False = точная оптимизация (100 итераций)
    )
    
    print(f"Best Sharpe: {result['best_score']:.2f}")
    print(f"Best params: {result['best_params']}")
    
    return result

result = asyncio.run(optimize())
```

### Вариант 2: Ручная оптимизация

```python
# Определить пространство параметров
param_space = {
    'sr_lookback': [20, 50, 100, 150, 200],
    'sr_threshold': [0.001, 0.002, 0.005, 0.01],
    'rsi_period': [7, 14, 21, 28],
    'rsi_overbought': [65, 70, 75, 80],
    'rsi_oversold': [20, 25, 30, 35],
    'take_profit_pct': [0.01, 0.02, 0.03, 0.05],
    'stop_loss_pct': [0.005, 0.01, 0.015, 0.02],
}

# Запустить ML-оптимизацию
async def manual_optimize():
    result = await engine.ml_optimize(
        data=data,
        param_space=param_space,
        optimization_goal='sharpe_ratio',
        ml_library='catboost',  # 'catboost', 'xgboost', 'lightgbm', 'hybrid'
        method='bayes',         # 'grid', 'random', 'bayes'
        n_trials=100,
        n_jobs=-1               # -1 = все ядра процессора
    )
    
    # Сохранить результаты
    result['optimization_result'].save_to_file('optimization_result.json')
    
    return result

result = asyncio.run(manual_optimize())
```

### Вариант 3: Генерация кода через Perplexity AI

```python
import asyncio
from ml_optimizer_perplexity import PerplexityMLOptimizer

async def generate_optimization_code():
    async with PerplexityMLOptimizer() as perplexity:
        
        # Сгенерировать код оптимизации
        code = await perplexity.generate_optimization_code(
            strategy_description="SR/RSI стратегия с пробоем уровней",
            param_space={'rsi_period': [14, 21], 'sr_lookback': [50, 100]},
            optimization_goal='Sharpe Ratio',
            ml_library='catboost'
        )
        
        # Сохранить код
        with open('generated_optimizer.py', 'w') as f:
            f.write(code)
        
        print(f"✅ Код сгенерирован ({len(code)} символов)")
        
        # Анализировать результаты
        results_json = '{"sharpe": 1.8, "win_rate": 62.5}'
        
        analysis = await perplexity.analyze_optimization_results(
            results_json=results_json,
            strategy_description="SR/RSI стратегия"
        )
        
        print(analysis)

asyncio.run(generate_optimization_code())
```

## 🔧 ML-оптимизаторы

### CatBoostOptimizer (рекомендация Яндекса)

**Преимущества:**
- ✅ Высокая скорость обучения
- ✅ Автоматическая обработка категориальных признаков
- ✅ Встроенная защита от переобучения
- ✅ Простой синтаксис

**Применение:** Оптимизация параметров временных рядов, DCA стратегий

```python
from backend.ml.optimizer import CatBoostOptimizer

optimizer = CatBoostOptimizer(
    objective_function=my_backtest_function,
    param_space=param_space,
    n_jobs=-1
)

result = await optimizer.optimize(n_trials=100, method='bayes')
```

### XGBoostOptimizer (самая популярная библиотека 2025)

**Преимущества:**
- ✅ Отличная работа с сеточными и DCA стратегиями
- ✅ Хорошая масштабируемость
- ✅ Поддержка GridSearch и early-stopping

**Применение:** Поиск оптимальных параметров скальпинга, сеток

### LightGBMOptimizer (для больших данных)

**Преимущества:**
- ✅ Самая высокая скорость обучения
- ✅ Работа с большими массивами данных
- ✅ Низкое потребление памяти

**Применение:** Скоростные оптимизации с большим объемом данных

### HybridOptimizer (комбинация всех методов)

**Стратегия:**
1. 20% бюджета → Random Search (грубый поиск)
2. 50% бюджета → Bayesian Optimization (умный поиск)
3. 30% бюджета → Local Grid Search (локальная точность)

**Применение:** Комплексная оптимизация сложных стратегий

## 📊 Результаты оптимизации

### OptimizationResult

```python
@dataclass
class OptimizationResult:
    best_params: Dict[str, Any]          # Лучшие параметры
    best_score: float                     # Лучшая метрика
    all_results: pd.DataFrame             # Все итерации
    optimization_time: float              # Время оптимизации (сек)
    method: str                           # Метод ('grid', 'bayes', 'random')
    iterations: int                       # Количество итераций
    
    # Расширенная статистика
    feature_importance: Dict[str, float]  # Важность параметров
    convergence_history: List[float]      # История сходимости
    top_n_configs: List[Dict]             # Топ-N конфигураций
    
    # Метрики стратегии
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_return: float
```

### Сохранение результатов

```python
# Сохранить в JSON + CSV
result.save_to_file('optimization_result.json')

# Создаются файлы:
# - optimization_result.json (метаданные)
# - optimization_result_full_results.csv (все итерации)
```

## 🧠 Perplexity AI промпты

### Готовые промпты

```python
from backend.ml.prompts import (
    get_optimization_prompt,        # Генерация кода оптимизации
    get_feature_engineering_prompt, # Feature engineering
    get_analysis_prompt,            # Анализ результатов
    get_new_strategies_prompt,      # Генерация новых стратегий
)

# Использование
prompt = get_optimization_prompt(
    strategy_description="SR/RSI стратегия",
    param_space={'rsi': [14, 21]},
    optimization_goal="Sharpe Ratio",
    ml_library="catboost"
)
```

### Продвинутые промпты

- `WALK_FORWARD_TEMPLATE` - Walk-Forward оптимизация и валидация
- `ENSEMBLE_STRATEGIES_TEMPLATE` - Ансамбль торговых стратегий
- `RISK_MANAGEMENT_TEMPLATE` - ML-система управления рисками
- `MARKET_REGIME_DETECTION_TEMPLATE` - ML-детектор рыночных режимов
- `HYPERPARAMETER_SEARCH_TEMPLATE` - Multi-objective оптимизация

## 🎓 Примеры использования

### Пример 1: Оптимизация SR/RSI стратегии

```python
# 1. Загрузить данные
data = pd.read_csv('btc_1h.csv', parse_dates=['timestamp'])

# 2. Создать движок
engine = BacktestEngine(initial_capital=10_000)

# 3. Оптимизировать
result = await engine.auto_optimize(
    data=data,
    strategy_type='sr_rsi',
    optimization_goal='sharpe_ratio'
)

# 4. Применить лучшие параметры
best_config = {'type': 'sr_rsi', **result['best_params']}
final_results = engine.run(data, best_config)
```

### Пример 2: Сравнение ML-библиотек

```python
libraries = ['catboost', 'xgboost', 'lightgbm']
results = {}

for lib in libraries:
    result = await engine.ml_optimize(
        data=data,
        param_space=param_space,
        ml_library=lib,
        method='bayes',
        n_trials=50
    )
    results[lib] = result

# Найти лучшую библиотеку
best_lib = max(results.items(), key=lambda x: x[1]['best_score'])
print(f"Best library: {best_lib[0]} (Sharpe: {best_lib[1]['best_score']:.2f})")
```

### Пример 3: Walk-Forward оптимизация

```python
# Разделить данные на периоды
periods = [
    data.iloc[:300],   # In-Sample
    data.iloc[300:400], # Out-Of-Sample
    data.iloc[400:],    # Forward Test
]

results = []

for i, period_data in enumerate(periods):
    result = await engine.auto_optimize(
        data=period_data,
        strategy_type='sr_rsi',
        quick_mode=True
    )
    results.append(result)
    print(f"Period {i+1} Sharpe: {result['best_score']:.2f}")

# Проверить стабильность
sharpes = [r['best_score'] for r in results]
print(f"Sharpe стабильность: {np.std(sharpes):.2f}")
```

## 📈 Метрики оптимизации

### Целевые метрики

| Метрика | Описание | Применение |
|---------|----------|------------|
| `sharpe_ratio` | Risk-adjusted return | Универсальная метрика |
| `sortino_ratio` | Downside risk только | Для консервативных стратегий |
| `win_rate` | % выигрышных сделок | Для скальпинга |
| `profit_factor` | Gross Profit / Gross Loss | Для агрессивных стратегий |
| `total_return` | Общая доходность | Для long-term стратегий |
| `max_drawdown` | Максимальная просадка | Минимизация риска |

### Штрафы за малое количество сделок

```python
# Автоматически применяются штрафы:
if total_trades < 10:
    score *= 0.1  # Сильный штраф
elif total_trades < 30:
    score *= 0.5  # Средний штраф
```

## 🔍 Отладка и анализ

### Просмотр истории оптимизации

```python
# Получить DataFrame со всеми итерациями
history = optimizer.get_optimization_history()

# Визуализация
import matplotlib.pyplot as plt

plt.figure(figsize=(12, 6))
plt.plot(history['score'])
plt.title('Convergence History')
plt.xlabel('Iteration')
plt.ylabel('Sharpe Ratio')
plt.show()
```

### Топ-N конфигураций

```python
# Получить топ-10 конфигураций
top_configs = result.top_n_configs

for i, config in enumerate(top_configs, 1):
    print(f"{i}. Score: {config['score']:.2f}")
    print(f"   Params: {config}")
```

### Feature Importance

```python
# Важность параметров (если доступно)
if result.feature_importance:
    for param, importance in result.feature_importance.items():
        print(f"{param}: {importance:.3f}")
```

## ⚠️ Важные замечания

### Защита от переобучения

1. **Walk-Forward валидация** обязательна для production
2. **Out-Of-Sample тестирование** на 20-30% данных
3. **Минимум 30+ сделок** для статистической значимости
4. **Регуляризация параметров** через ограничение пространства поиска

### Оптимальные настройки

| Размер данных | ML-библиотека | Метод | Итераций |
|---------------|---------------|-------|----------|
| < 500 баров | LightGBM | Random | 30 |
| 500-2000 баров | XGBoost | Bayes | 50-100 |
| > 2000 баров | CatBoost | Bayes | 100-200 |
| Комплексная | Hybrid | Mixed | 150-300 |

### Производительность

```python
# Параллелизация (рекомендуется)
result = await engine.ml_optimize(
    ...,
    n_jobs=-1  # Все ядра процессора
)

# Быстрый режим для тестирования
result = await engine.auto_optimize(
    ...,
    quick_mode=True  # 30 итераций вместо 100
)
```

## 🚀 Следующие шаги

### 1. Установка зависимостей

```powershell
pip install -r requirements-ml.txt
```

### 2. Настройка Perplexity API

Получите ключ на [perplexity.ai](https://perplexity.ai) и добавьте в `.env`

### 3. Запуск демо

```powershell
# E2E тест
python test_ml_optimization_e2e.py

# Демо Perplexity интеграции
python ml_optimizer_perplexity.py
```

### 4. Интеграция в production

```python
# Ваш production код
from backend.core.backtest_engine import BacktestEngine

engine = BacktestEngine()
result = await engine.auto_optimize(data, strategy_type='sr_rsi')

# Применить лучшие параметры
best_strategy = {'type': 'sr_rsi', **result['best_params']}
```

## 📚 Дополнительные ресурсы

- [CatBoost Documentation](https://catboost.ai/docs/)
- [XGBoost Documentation](https://xgboost.readthedocs.io/)
- [LightGBM Documentation](https://lightgbm.readthedocs.io/)
- [Optuna Documentation](https://optuna.readthedocs.io/)
- [Perplexity AI API](https://docs.perplexity.ai/)

## 🎯 Проверенные подходы 2025 года

Все ML-библиотеки и техники оптимизации основаны на рекомендациях профессиональных алгоритмических трейдеров и проверены на практике в 2025 году.

---

**Создано:** Copilot через интеграцию с Perplexity AI  
**Схема работы:** Copilot ↔ Perplexity AI (MCP Server) ↔ Copilot
