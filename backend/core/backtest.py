"""
Backtest Engine - Mock Implementation for Testing

Временная заглушка для BacktestEngine, чтобы можно было тестировать
оптимизацию. Полная реализация будет в Phase 3.
"""

from typing import Dict, Any, Optional
import pandas as pd
from loguru import logger


class BacktestEngine:
    """
    Mock BacktestEngine для тестирования оптимизации
    
    В продакшене будет полноценный движок бэктестинга с:
    - Управлением позициями
    - Расчётом PnL
    - Комиссиями и проскальзыванием
    - Метриками производительности
    """
    
    def __init__(
        self,
        data: pd.DataFrame,
        initial_capital: float = 10000.0,
        commission: float = 0.001,
        **kwargs
    ):
        """
        Инициализация mock engine
        
        Args:
            data: OHLCV данные
            initial_capital: Начальный капитал
            commission: Комиссия за сделку
        """
        self.data = data
        self.initial_capital = initial_capital
        self.commission = commission
        self.kwargs = kwargs
        
        logger.debug(
            f"BacktestEngine (MOCK) created: "
            f"{len(data)} candles, ${initial_capital:.2f} capital"
        )
    
    async def run_async(
        self,
        strategy_name: str,
        strategy_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Запуск бэктеста (MOCK)
        
        Возвращает случайные метрики для тестирования оптимизации
        
        Args:
            strategy_name: Название стратегии
            strategy_params: Параметры стратегии
        
        Returns:
            Словарь с метриками
        """
        import random
        import numpy as np
        
        # Генерируем "правдоподобные" метрики на основе параметров
        # В реальности это будет результат полноценного бэктеста
        
        # Используем параметры для создания seed (чтобы результаты были стабильными)
        seed = hash(frozenset(strategy_params.items())) % 10000
        random.seed(seed)
        np.random.seed(seed)
        
        # Генерируем метрики
        total_return = random.uniform(-20, 80)  # -20% to +80%
        sharpe_ratio = random.uniform(-0.5, 3.0)
        max_drawdown = random.uniform(5, 40)
        win_rate = random.uniform(30, 70)
        profit_factor = random.uniform(0.5, 3.0)
        
        metrics = {
            "total_return": round(total_return, 2),
            "sharpe_ratio": round(sharpe_ratio, 3),
            "sortino_ratio": round(sharpe_ratio * 1.2, 3),
            "max_drawdown": round(max_drawdown, 2),
            "win_rate": round(win_rate, 2),
            "profit_factor": round(profit_factor, 3),
            "total_trades": random.randint(50, 500),
            "avg_trade": round(total_return / random.randint(50, 500), 3),
            "final_capital": round(self.initial_capital * (1 + total_return / 100), 2)
        }
        
        logger.debug(
            f"Backtest (MOCK) completed: {strategy_name} with {strategy_params} -> "
            f"Return: {metrics['total_return']}%, Sharpe: {metrics['sharpe_ratio']}"
        )
        
        return metrics
    
    def run(
        self,
        strategy_name: str,
        strategy_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Синхронная версия run_async
        
        Args:
            strategy_name: Название стратегии
            strategy_params: Параметры стратегии
        
        Returns:
            Словарь с метриками
        """
        # Используем напрямую синхронную логику для mock
        # В продакшене это будет полноценный синхронный бэктест
        import random
        import numpy as np
        
        seed = hash(frozenset(strategy_params.items())) % 10000
        random.seed(seed)
        np.random.seed(seed)
        
        total_return = random.uniform(-20, 80)
        sharpe_ratio = random.uniform(-0.5, 3.0)
        max_drawdown = random.uniform(5, 40)
        win_rate = random.uniform(30, 70)
        profit_factor = random.uniform(0.5, 3.0)
        
        metrics = {
            "total_return": round(total_return, 2),
            "sharpe_ratio": round(sharpe_ratio, 3),
            "sortino_ratio": round(sharpe_ratio * 1.2, 3),
            "max_drawdown": round(max_drawdown, 2),
            "win_rate": round(win_rate, 2),
            "profit_factor": round(profit_factor, 3),
            "total_trades": random.randint(50, 500),
            "avg_trade": round(total_return / random.randint(50, 500), 3),
            "final_capital": round(self.initial_capital * (1 + total_return / 100), 2)
        }
        
        logger.debug(
            f"Backtest (MOCK) completed: {strategy_name} with {strategy_params} -> "
            f"Return: {metrics['total_return']}%, Sharpe: {metrics['sharpe_ratio']}"
        )
        
        return metrics


# Для совместимости со старым кодом
class BacktestResult:
    """Mock результата бэктеста"""
    
    def __init__(self, metrics: Dict[str, Any]):
        self.metrics = metrics
        
    def get_metrics(self) -> Dict[str, Any]:
        return self.metrics
