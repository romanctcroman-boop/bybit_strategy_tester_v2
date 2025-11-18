"""
Библиотека готовых промптов для Perplexity AI
Использование в ML-оптимизации торговых стратегий
"""

# ==================== OPTIMIZATION PROMPTS ====================

OPTIMIZATION_TEMPLATE = """
# ML-оптимизация параметров торговой стратегии на Python

## Стратегия
{strategy_description}

## Пространство параметров для оптимизации
```json
{param_space}
```

## Целевая метрика
{optimization_goal}

## ML-библиотека
{ml_library}

## Требования к коду

1. **Импорты**
   - Использовать {ml_library} для оптимизации
   - Использовать scikit-learn для Grid/Bayes search
   - Использовать pandas/numpy для обработки данных

2. **Objective Function**
   - Создать функцию objective(params) -> float
   - Функция запускает backtest с параметрами
   - Возвращает целевую метрику ({optimization_goal})

3. **Оптимизация**
   - Grid Search для небольших пространств
   - Bayesian Optimization (Optuna) для больших пространств
   - Использовать кросс-валидацию walk-forward
   - Защита от переобучения

4. **Результаты**
   - Сохранить лучшие параметры в JSON
   - Создать отчет с метриками
   - Визуализация convergence plot
   - Топ-10 конфигураций

## Формат вывода

Верни полный рабочий Python код с:
- Всеми необходимыми импортами
- Классом или функциями для оптимизации
- Примером использования
- Комментариями на русском
- Обработкой ошибок

Используй проверенные практики алгоритмической торговли 2025 года.
Код должен быть production-ready и работать с async/await.

**ВАЖНО:** Верни только Python код в блоке ```python, без дополнительных объяснений.
"""


FEATURE_ENGINEERING_TEMPLATE = """
# Feature Engineering для Trading Strategy

## Задача
Создать feature engineering код для подготовки данных для ML-оптимизации торговой стратегии.

## Данные
{data_description}

## Тип стратегии
{strategy_type}

## Требования
1. Создать технические индикаторы (SMA, EMA, RSI, MACD, Bollinger Bands)
2. Создать признаки временных рядов (лаги, rolling features)
3. Обработать пропуски и выбросы
4. Нормализовать признаки
5. Выбрать наиболее важные признаки

## Формат вывода
Верни полный Python код с:
- Импортами
- Функцией create_features(df: pd.DataFrame) -> pd.DataFrame
- Комментариями к каждому шагу
- Примером использования

Используй проверенные подходы алгоритмических трейдеров 2025 года.
"""


ANALYSIS_TEMPLATE = """
# Анализ результатов ML-оптимизации торговой стратегии

## Стратегия
{strategy_description}

## Результаты оптимизации
```json
{results_json}
```

## Задача
Проанализировать результаты и дать рекомендации:

1. **Оценка качества оптимизации**
   - Достигнуты ли хорошие метрики?
   - Есть ли признаки переобучения?
   - Стабильны ли результаты?

2. **Анализ параметров**
   - Какие параметры наиболее важны?
   - Есть ли корреляция между параметрами?
   - Какие диапазоны параметров оптимальны?

3. **Рекомендации по улучшению**
   - Как улучшить стратегию?
   - Какие параметры стоит добавить?
   - Какие техники оптимизации попробовать?

4. **Следующие шаги**
   - Какие эксперименты провести?
   - Как валидировать результаты?
   - Что проверить на реальных данных?

Используй опыт профессиональных алгоритмических трейдеров 2025 года.
"""


NEW_STRATEGIES_TEMPLATE = """
# Генерация новых торговых стратегий

## Рыночные данные
{market_data_summary}

## Текущая производительность
{current_strategy_performance}

## Ограничения
{constraints}

## Задача
Предложить 3-5 новых торговых стратегий для криптовалют на основе:
- Современных подходов алгоритмической торговли 2025 года
- ML/AI техник (CatBoost, XGBoost, LightGBM)
- Проверенных паттернов (momentum, mean-reversion, breakout)

Для каждой стратегии предоставь:
1. Название и краткое описание
2. Логику входа/выхода
3. Параметры для оптимизации
4. Пример кода на Python
5. Ожидаемые метрики (Sharpe, Win Rate)

Используй лучшие практики quantitative trading.
"""


# ==================== ADVANCED PROMPTS ====================

WALK_FORWARD_TEMPLATE = """
# Walk-Forward оптимизация и валидация

## Задача
Создать код для Walk-Forward тестирования торговой стратегии:
- In-Sample оптимизация (60% данных)
- Out-Of-Sample валидация (20% данных)
- Forward тестирование (20% данных)

## Стратегия
{strategy_description}

## Параметры
{param_space}

## Требования
1. Разделить данные на периоды (rolling window)
2. Оптимизировать на In-Sample
3. Тестировать на Out-Of-Sample
4. Собрать метрики по всем периодам
5. Проверить стабильность результатов
6. Визуализировать equity curve

Верни production-ready Python код с async/await.
"""


ENSEMBLE_STRATEGIES_TEMPLATE = """
# Ансамбль торговых стратегий

## Задача
Создать систему ансамбля из нескольких стратегий:
- Комбинировать разные типы стратегий
- Взвешивать сигналы по performance
- Диверсификация рисков
- Адаптивные веса через ML

## Доступные стратегии
{available_strategies}

## Требования
1. Класс EnsembleStrategy
2. Методы добавления стратегий
3. Взвешивание сигналов
4. ML для оптимизации весов (CatBoost/XGBoost)
5. Backtesting ансамбля
6. Метрики по каждой стратегии и ансамблю

Верни полный Python код с примером использования.
"""


RISK_MANAGEMENT_TEMPLATE = """
# ML-система управления рисками

## Задача
Создать систему risk management с ML-оптимизацией:
- Динамический sizing позиций
- Адаптивные stop-loss/take-profit
- ML-модель для оценки риска
- Защита от просадок

## Данные
{market_data_description}

## Требования
1. Класс MLRiskManager
2. Методы для sizing (Kelly Criterion, ML-based)
3. Адаптивные стопы на основе волатильности
4. CatBoost/XGBoost для предсказания риска
5. Интеграция с BacktestEngine
6. Метрики: Max DD, Sharpe, Sortino

Используй лучшие практики quantitative risk management 2025.
"""


MARKET_REGIME_DETECTION_TEMPLATE = """
# ML-детектор рыночных режимов

## Задача
Создать систему определения рыночных режимов через ML:
- Trending (восходящий/нисходящий тренд)
- Ranging (флэт, консолидация)
- Volatile (высокая волатильность)
- Low Volume (низкий объем)

## Применение
Адаптация стратегии под текущий режим:
- Trend-following в трендах
- Mean-reversion в флэте
- Закрытие позиций при высокой волатильности

## Требования
1. Класс MarketRegimeDetector
2. Feature engineering для режимов
3. ML-модель (CatBoost/LightGBM)
4. Обучение на исторических данных
5. Real-time детекция режима
6. Интеграция с BacktestEngine

Верни production-ready код с примерами.
"""


HYPERPARAMETER_SEARCH_TEMPLATE = """
# Продвинутый Hyperparameter Search

## Задача
Создать систему гиперпараметрической оптимизации:
- Multi-objective optimization (Sharpe + Win Rate + Max DD)
- Параллельное выполнение
- Ранняя остановка плохих конфигураций
- Визуализация Pareto Front

## ML-фреймворки
- Optuna (TPE, CMA-ES, GP)
- Ray Tune (Hyperband, BOHB)
- Scikit-Optimize (Bayesian)

## Требования
1. Класс HyperparameterOptimizer
2. Поддержка multi-objective
3. Параллельное выполнение (async)
4. Pruning плохих trials
5. Визуализация optimization history
6. Экспорт результатов в JSON/CSV

Используй современные подходы AutoML 2025.
"""


# ==================== DEBUGGING & ANALYSIS PROMPTS ====================

OVERFITTING_DETECTION_TEMPLATE = """
# Детекция переобучения в торговых стратегиях

## Проблема
Оптимизированная стратегия показывает отличные результаты на бэктесте,
но fails на forward testing.

## Результаты оптимизации
```json
{optimization_results}
```

## Задача
Проанализировать признаки переобучения:
1. In-Sample vs Out-Of-Sample метрики
2. Слишком сложные параметры
3. Малое количество сделок
4. Curve fitting
5. Look-ahead bias

Дать рекомендации:
- Как исправить переобучение
- Какие техники регуляризации применить
- Как улучшить валидацию

Верни детальный анализ с конкретными рекомендациями.
"""


STRATEGY_COMPARISON_TEMPLATE = """
# Сравнение торговых стратегий

## Задача
Сравнить несколько оптимизированных стратегий:

## Стратегии
{strategies_json}

## Метрики сравнения
- Sharpe Ratio (risk-adjusted return)
- Sortino Ratio (downside risk)
- Calmar Ratio (return / max DD)
- Win Rate
- Profit Factor
- Max Drawdown
- Recovery Time
- Consistency

## Требования
1. Таблица сравнения всех метрик
2. Визуализация equity curves
3. Statistical tests (t-test, Mann-Whitney)
4. Корреляция между стратегиями
5. Рекомендации по выбору

Дать объективную оценку с обоснованием.
"""


# ==================== HELPER FUNCTIONS ====================

def get_optimization_prompt(
    strategy_description: str,
    param_space: dict,
    optimization_goal: str,
    ml_library: str
) -> str:
    """Получить промпт для оптимизации"""
    import json
    return OPTIMIZATION_TEMPLATE.format(
        strategy_description=strategy_description,
        param_space=json.dumps(param_space, indent=2, ensure_ascii=False),
        optimization_goal=optimization_goal,
        ml_library=ml_library
    )


def get_feature_engineering_prompt(
    data_description: str,
    strategy_type: str
) -> str:
    """Получить промпт для feature engineering"""
    return FEATURE_ENGINEERING_TEMPLATE.format(
        data_description=data_description,
        strategy_type=strategy_type
    )


def get_analysis_prompt(
    strategy_description: str,
    results_json: str
) -> str:
    """Получить промпт для анализа результатов"""
    return ANALYSIS_TEMPLATE.format(
        strategy_description=strategy_description,
        results_json=results_json
    )


def get_new_strategies_prompt(
    market_data_summary: str,
    current_strategy_performance: str,
    constraints: str = "Без ограничений"
) -> str:
    """Получить промпт для генерации новых стратегий"""
    return NEW_STRATEGIES_TEMPLATE.format(
        market_data_summary=market_data_summary,
        current_strategy_performance=current_strategy_performance,
        constraints=constraints
    )


# ==================== EXAMPLE USAGE ====================

if __name__ == "__main__":
    # Пример использования промптов
    
    strategy = "SR/RSI стратегия: Пробой уровней + RSI фильтр"
    params = {
        "sr_lookback": [50, 100, 150],
        "rsi_period": [14, 21],
        "take_profit_pct": [0.02, 0.03]
    }
    
    prompt = get_optimization_prompt(
        strategy_description=strategy,
        param_space=params,
        optimization_goal="Sharpe Ratio",
        ml_library="catboost"
    )
    
    print("OPTIMIZATION PROMPT:")
    print("=" * 80)
    print(prompt)
