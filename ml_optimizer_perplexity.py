"""
Скрипт взаимодействия Copilot ↔ Perplexity AI ↔ Copilot для ML-оптимизации
Использует MCP-сервер и Perplexity API для генерации кода оптимизации
"""

import asyncio
import logging
import os
import sys
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

import aiohttp
from dotenv import load_dotenv

# Загрузить переменные окружения
load_dotenv()

# Настроить логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Добавить backend в путь для импортов
sys.path.insert(0, str(Path(__file__).parent / 'backend'))


class PerplexityMLOptimizer:
    """
    Автоматизированный ML-оптимизатор через Perplexity AI
    
    Схема работы:
    1. Copilot → Отправляет запрос через этот скрипт
    2. Perplexity AI → Генерирует ML-код оптимизации
    3. Copilot → Применяет сгенерированный код
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: Perplexity API ключ (по умолчанию из .env)
        """
        self.api_key = api_key or os.getenv('PERPLEXITY_API_KEY')
        if not self.api_key:
            raise ValueError("PERPLEXITY_API_KEY not found in environment")
        
        self.api_url = "https://api.perplexity.ai/chat/completions"
        self.model = "sonar-pro"  # Лучшая модель для кода
        
        self.session: Optional[aiohttp.ClientSession] = None
        self.query_history: List[Dict[str, Any]] = []
    
    async def __aenter__(self):
        """Создать HTTP сессию"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Закрыть HTTP сессию"""
        if self.session:
            await self.session.close()
    
    async def generate_optimization_code(
        self,
        strategy_description: str,
        param_space: Dict[str, Any],
        optimization_goal: str = "Sharpe Ratio",
        ml_library: str = "catboost"
    ) -> str:
        """
        Генерировать код оптимизации через Perplexity AI
        
        Args:
            strategy_description: Описание торговой стратегии
            param_space: Пространство параметров для оптимизации
            optimization_goal: Целевая метрика (Sharpe Ratio, Win Rate, etc.)
            ml_library: ML-библиотека ('catboost', 'xgboost', 'lightgbm', 'hybrid')
        
        Returns:
            Сгенерированный Python код оптимизации
        """
        prompt = self._build_optimization_prompt(
            strategy_description, param_space, optimization_goal, ml_library
        )
        
        response = await self._query_perplexity(prompt)
        
        # Извлечь Python код из ответа
        code = self._extract_python_code(response)
        
        return code
    
    async def generate_feature_engineering_code(
        self,
        data_description: str,
        strategy_type: str = "trend-following"
    ) -> str:
        """
        Генерировать код feature engineering через Perplexity AI
        
        Args:
            data_description: Описание доступных данных
            strategy_type: Тип стратегии (trend-following, mean-reversion, scalping)
        
        Returns:
            Сгенерированный код обработки признаков
        """
        prompt = f"""
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
        
        response = await self._query_perplexity(prompt)
        code = self._extract_python_code(response)
        
        return code
    
    async def analyze_optimization_results(
        self,
        results_json: str,
        strategy_description: str
    ) -> str:
        """
        Анализировать результаты оптимизации через Perplexity AI
        
        Args:
            results_json: JSON с результатами оптимизации
            strategy_description: Описание стратегии
        
        Returns:
            Аналитический отчет с рекомендациями
        """
        prompt = f"""
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
        
        response = await self._query_perplexity(prompt)
        
        return response
    
    async def suggest_new_strategies(
        self,
        market_data_summary: str,
        current_strategy_performance: str,
        constraints: Optional[str] = None
    ) -> str:
        """
        Предложить новые торговые стратегии через Perplexity AI
        
        Args:
            market_data_summary: Сводка по рыночным данным
            current_strategy_performance: Текущая производительность
            constraints: Ограничения (риск, капитал, etc.)
        
        Returns:
            Предложения новых стратегий с кодом
        """
        prompt = f"""
# Генерация новых торговых стратегий

## Рыночные данные
{market_data_summary}

## Текущая производительность
{current_strategy_performance}

## Ограничения
{constraints or "Без ограничений"}

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
        
        response = await self._query_perplexity(prompt)
        
        return response
    
    def _build_optimization_prompt(
        self,
        strategy_description: str,
        param_space: Dict[str, Any],
        optimization_goal: str,
        ml_library: str
    ) -> str:
        """Построить промпт для генерации кода оптимизации"""
        
        # Форматировать пространство параметров
        param_space_str = json.dumps(param_space, indent=2, ensure_ascii=False)
        
        prompt = f"""
# ML-оптимизация параметров торговой стратегии на Python

## Стратегия
{strategy_description}

## Пространство параметров для оптимизации
```json
{param_space_str}
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
        
        return prompt
    
    async def _query_perplexity(self, prompt: str) -> str:
        """
        Отправить запрос в Perplexity API
        
        Args:
            prompt: Промпт для генерации
        
        Returns:
            Ответ от Perplexity AI
        """
        if not self.session:
            raise RuntimeError("Session not initialized. Use 'async with' context manager")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert quantitative trading developer. Generate production-ready Python code for algorithmic trading optimization."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.2,  # Низкая температура для более точного кода
            "max_tokens": 4000,
        }
        
        start_time = datetime.now()
        
        try:
            async with self.session.post(
                self.api_url, 
                headers=headers, 
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(f"Perplexity API error {response.status}: {error_text}")
                
                data = await response.json()
                
                # Извлечь ответ
                content = data['choices'][0]['message']['content']
                
                # Извлечь цитаты (если есть)
                citations = data.get('citations', [])
                
                # Сохранить в историю
                query_time = (datetime.now() - start_time).total_seconds()
                self.query_history.append({
                    'timestamp': datetime.now().isoformat(),
                    'prompt': prompt[:200] + '...',
                    'response_length': len(content),
                    'citations_count': len(citations),
                    'query_time': query_time
                })
                
                logger.info(f"Perplexity query completed in {query_time:.2f}s, {len(citations)} citations")
                
                return content
        
        except asyncio.TimeoutError:
            logger.error("Perplexity API request timeout")
            raise
        except Exception as e:
            logger.error(f"Perplexity API request failed: {e}")
            raise
    
    def _extract_python_code(self, response: str) -> str:
        """
        Извлечь Python код из ответа Perplexity
        
        Args:
            response: Ответ от Perplexity AI
        
        Returns:
            Извлеченный Python код
        """
        # Паттерн для блоков кода Python
        pattern = r'```python\n(.*?)```'
        matches = re.findall(pattern, response, re.DOTALL)
        
        if matches:
            # Взять первый или самый длинный блок кода
            code = max(matches, key=len)
            logger.info(f"Extracted Python code: {len(code)} characters")
            return code.strip()
        
        # Если не найдено блоков, попробовать найти код без маркеров
        if 'import' in response or 'def ' in response or 'class ' in response:
            logger.warning("No ```python blocks found, returning full response")
            return response.strip()
        
        logger.error("No Python code found in response")
        raise ValueError("No Python code found in Perplexity response")
    
    def save_query_history(self, filepath: str = "perplexity_query_history.json"):
        """Сохранить историю запросов"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.query_history, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Query history saved to {filepath}")


async def demo_ml_optimization_workflow():
    """
    Демонстрация полного цикла: Copilot → Perplexity → ML-оптимизация → Copilot
    """
    
    print("\n" + "="*80)
    print("🚀 DEMO: ML-оптимизация через Copilot ↔ Perplexity AI ↔ Copilot")
    print("="*80 + "\n")
    
    # Шаг 1: Определить задачу оптимизации
    strategy_description = """
Торговая стратегия: Support/Resistance + RSI
- Вход: Пробой уровня поддержки/сопротивления + RSI сигнал
- Выход: Фиксированный take-profit или stop-loss
- Таймфрейм: 1 час
- Инструмент: BTC/USDT
"""
    
    param_space = {
        "sr_lookback": [20, 50, 100, 150, 200],
        "sr_threshold": [0.001, 0.002, 0.005, 0.01],
        "rsi_period": [7, 14, 21, 28],
        "rsi_overbought": [65, 70, 75, 80],
        "rsi_oversold": [20, 25, 30, 35],
        "take_profit_pct": [0.01, 0.02, 0.03, 0.05],
        "stop_loss_pct": [0.005, 0.01, 0.015, 0.02],
    }
    
    optimization_goal = "Sharpe Ratio"
    ml_library = "catboost"
    
    print("📋 ЗАДАЧА ОПТИМИЗАЦИИ")
    print(f"Стратегия: {strategy_description.strip()}")
    print(f"Параметров: {len(param_space)}")
    print(f"Комбинаций: {np.prod([len(v) for v in param_space.values()]):,}")
    print(f"Целевая метрика: {optimization_goal}")
    print(f"ML-библиотека: {ml_library}")
    print()
    
    # Шаг 2: Copilot → Perplexity (генерация кода)
    print("⚙️  ШАГ 1: Copilot → Perplexity AI (генерация кода оптимизации)")
    
    async with PerplexityMLOptimizer() as optimizer:
        try:
            optimization_code = await optimizer.generate_optimization_code(
                strategy_description=strategy_description,
                param_space=param_space,
                optimization_goal=optimization_goal,
                ml_library=ml_library
            )
            
            print(f"✅ Код сгенерирован: {len(optimization_code)} символов")
            
            # Сохранить сгенерированный код
            code_filepath = "generated_ml_optimization.py"
            with open(code_filepath, 'w', encoding='utf-8') as f:
                f.write(optimization_code)
            
            print(f"💾 Код сохранен: {code_filepath}")
            print()
            
            # Показать превью кода
            lines = optimization_code.split('\n')
            print("📄 ПРЕВЬЮ КОДА (первые 20 строк):")
            print("-" * 80)
            for i, line in enumerate(lines[:20], 1):
                print(f"{i:3d} | {line}")
            print(f"... ({len(lines)} строк всего)")
            print("-" * 80)
            print()
            
            # Шаг 3: Feature Engineering (опционально)
            print("⚙️  ШАГ 2: Генерация Feature Engineering кода")
            
            data_description = """
Доступные данные:
- OHLCV (Open, High, Low, Close, Volume) - 1 час
- Исторические данные: 2 года
- Инструмент: BTC/USDT
"""
            
            feature_code = await optimizer.generate_feature_engineering_code(
                data_description=data_description,
                strategy_type="trend-following"
            )
            
            print(f"✅ Feature Engineering код сгенерирован: {len(feature_code)} символов")
            
            feature_filepath = "generated_feature_engineering.py"
            with open(feature_filepath, 'w', encoding='utf-8') as f:
                f.write(feature_code)
            
            print(f"💾 Код сохранен: {feature_filepath}")
            print()
            
            # Шаг 4: Симуляция результатов оптимизации
            print("⚙️  ШАГ 3: Симуляция ML-оптимизации (в реальности запускается сгенерированный код)")
            
            # В реальности здесь запускается сгенерированный код
            # Для демо создадим фейковые результаты
            simulated_results = {
                "best_params": {
                    "sr_lookback": 100,
                    "sr_threshold": 0.002,
                    "rsi_period": 14,
                    "rsi_overbought": 70,
                    "rsi_oversold": 30,
                    "take_profit_pct": 0.02,
                    "stop_loss_pct": 0.01
                },
                "best_score": 1.87,
                "method": "catboost_bayes",
                "iterations": 150,
                "optimization_time": 324.5,
                "metrics": {
                    "sharpe_ratio": 1.87,
                    "max_drawdown": -0.15,
                    "win_rate": 0.58,
                    "profit_factor": 1.95,
                    "total_return": 0.67
                }
            }
            
            results_json = json.dumps(simulated_results, indent=2)
            
            print("✅ Оптимизация завершена")
            print(f"Лучший Sharpe Ratio: {simulated_results['best_score']:.2f}")
            print(f"Итераций: {simulated_results['iterations']}")
            print(f"Время: {simulated_results['optimization_time']:.1f}s")
            print()
            
            # Шаг 5: Perplexity → Copilot (анализ результатов)
            print("⚙️  ШАГ 4: Perplexity AI → Copilot (анализ результатов)")
            
            analysis = await optimizer.analyze_optimization_results(
                results_json=results_json,
                strategy_description=strategy_description
            )
            
            print("✅ Анализ получен")
            print()
            print("📊 АНАЛИЗ РЕЗУЛЬТАТОВ:")
            print("-" * 80)
            print(analysis[:1000] + "..." if len(analysis) > 1000 else analysis)
            print("-" * 80)
            print()
            
            # Сохранить анализ
            analysis_filepath = "optimization_analysis.md"
            with open(analysis_filepath, 'w', encoding='utf-8') as f:
                f.write(f"# Анализ результатов ML-оптимизации\n\n")
                f.write(f"**Дата:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write(f"## Результаты\n\n```json\n{results_json}\n```\n\n")
                f.write(f"## Анализ от Perplexity AI\n\n{analysis}\n")
            
            print(f"💾 Анализ сохранен: {analysis_filepath}")
            print()
            
            # Сохранить историю запросов
            optimizer.save_query_history("ml_optimization_query_history.json")
            
        except Exception as e:
            logger.error(f"Ошибка в workflow: {e}")
            raise
    
    print("\n" + "="*80)
    print("✅ DEMO завершен успешно!")
    print("="*80 + "\n")
    
    print("📁 СОЗДАННЫЕ ФАЙЛЫ:")
    print("  1. generated_ml_optimization.py - Код ML-оптимизации")
    print("  2. generated_feature_engineering.py - Код Feature Engineering")
    print("  3. optimization_analysis.md - Анализ результатов")
    print("  4. ml_optimization_query_history.json - История запросов")
    print()
    
    print("🚀 СЛЕДУЮЩИЕ ШАГИ:")
    print("  1. Запустить generated_ml_optimization.py на реальных данных")
    print("  2. Применить найденные параметры в стратегии")
    print("  3. Провести walk-forward тестирование")
    print("  4. Использовать generated_feature_engineering.py для улучшения признаков")
    print()


if __name__ == "__main__":
    # Для работы требуется NumPy
    import numpy as np
    
    asyncio.run(demo_ml_optimization_workflow())
