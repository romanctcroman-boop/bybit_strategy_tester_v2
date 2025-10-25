"""
Monte Carlo Simulator - Единая консолидированная реализация

Соответствие ТЗ 3.5.3:
- Bootstrap permutation (случайная перестановка сделок с возвратом)
- Расчёт доверительных интервалов для доходности
- prob_profit: Вероятность прибыли (ТЗ требует, была отсутствующей)
- prob_ruin: Вероятность разорения (ТЗ требует, была отсутствующей)
- Распределение Sharpe Ratio и Maximum Drawdown
- Доступен на Продвинутом уровне

Метод:
1. Берём список исторических сделок из BacktestEngine
2. Случайно перемешиваем с возвратом (bootstrap)
3. Рассчитываем метрики для каждой перестановки
4. Строим распределение возможных исходов
5. Оцениваем prob_profit и prob_ruin

Создано: 25 октября 2025 (Фаза 1, Задача 1)
Консолидирует:
- backend/optimization/monte_carlo.py
- backend/core/monte_carlo_simulator.py
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
from loguru import logger


@dataclass
class MonteCarloResult:
    """
    Результаты Monte Carlo симуляции
    
    Attributes:
        simulations: list[dict] - Результат каждой симуляции
        statistics: dict - Агрегированная статистика
            - mean_return: Средняя доходность (%)
            - std_return: Стандартное отклонение (%)
            - percentile_5: 5-й перцентиль (пессимистичный сценарий)
            - percentile_95: 95-й перцентиль (оптимистичный сценарий)
            - prob_profit: ✅ Вероятность прибыли (0-1)
            - prob_ruin: ✅ Вероятность краха (0-1)
            - median_return: Медиана
            - best_case: Лучший сценарий
            - worst_case: Худший сценарий
    """
    simulations: list[dict]
    statistics: dict[str, float]
    
    def to_dict(self) -> dict:
        """Сериализация в словарь"""
        return {
            'simulations': self.simulations,
            'statistics': self.statistics
        }


class MonteCarloSimulator:
    """
    ТЗ 3.5.3 - Оценка робастности через случайные перестановки
    Доступен на Продвинутом уровне
    
    Использует bootstrap permutation (выборка с возвратом) для создания
    множественных сценариев и оценки:
    - ✅ Вероятности прибыли (prob_profit)
    - ✅ Вероятности разорения (prob_ruin)
    - Доверительных интервалов доходности
    
    Args:
        n_simulations: Количество симуляций (min 10, recommend 1000+)
        ruin_threshold: Порог разорения в % от капитала (default 50%)
            Пример: 50% означает, что если capital падает ниже 50% начального - это ruin
        random_seed: Seed для воспроизводимости результатов
    
    Example:
        >>> mc = MonteCarloSimulator(n_simulations=1000, ruin_threshold=50.0)
        >>> result = mc.run(trades, initial_capital=10000)
        >>> print(f"Prob of Profit: {result.statistics['prob_profit']:.2%}")
        >>> print(f"Prob of Ruin: {result.statistics['prob_ruin']:.2%}")
        >>> print(f"95% CI: [{result.statistics['percentile_5']:.2f}%, {result.statistics['percentile_95']:.2f}%]")
    """
    
    def __init__(
        self,
        n_simulations: int = 1000,
        ruin_threshold: float = 50.0,
        random_seed: int | None = None
    ):
        """
        Args:
            n_simulations: Количество симуляций (по умолчанию 1000)
            ruin_threshold: Порог разорения в % от начального капитала (default 50%)
            random_seed: Seed для воспроизводимости
        """
        if n_simulations < 10:
            raise ValueError("n_simulations должно быть >= 10")
        if not (1.0 <= ruin_threshold < 100.0):
            raise ValueError("ruin_threshold должно быть в диапазоне [1.0, 100.0)")
        
        self.n_simulations = n_simulations
        self.ruin_threshold = ruin_threshold
        self.random_seed = random_seed
        
        if random_seed is not None:
            np.random.seed(random_seed)
        
        logger.info(
            f"MonteCarloSimulator initialized: {n_simulations} simulations, "
            f"ruin_threshold={ruin_threshold}%"
        )
    
    def run(
        self,
        trades: list[dict],
        initial_capital: float = 10000.0
    ) -> dict[str, Any]:
        """
        Запуск Monte Carlo симуляции
        
        Args:
            trades: Список сделок из BacktestEngine
                Каждая сделка должна содержать:
                {
                    'pnl': float,  # P&L в USDT
                    'pnl_pct': float,  # P&L в %
                    'side': str,  # 'long' или 'short'
                    ...
                }
            initial_capital: Начальный капитал
        
        Returns:
            {
                'simulations': list[dict],   # Результат каждой симуляции
                'statistics': {
                    'mean_return': float,
                    'std_return': float,
                    'percentile_5': float,   # Пессимистичный сценарий
                    'percentile_95': float,  # Оптимистичный
                    'prob_profit': float,    # ✅ NEW: Вероятность прибыли
                    'prob_ruin': float       # ✅ NEW: Вероятность краха
                }
            }
        """
        if not trades:
            logger.warning("No trades provided for Monte Carlo simulation")
            return self._empty_result()
        
        logger.info(f"Starting Monte Carlo: {self.n_simulations} simulations, {len(trades)} trades")
        
        # Сбросить seed для воспроизводимости
        if self.random_seed is not None:
            np.random.seed(self.random_seed)
        
        simulations = []
        final_capitals = []
        
        for sim_idx in range(self.n_simulations):
            # Случайная выборка сделок с возвратом (bootstrap)
            shuffled_trades = np.random.choice(trades, size=len(trades), replace=True)
            
            # Рассчитать equity curve
            capital = initial_capital
            equity_curve = [capital]
            min_capital = capital  # Для расчета prob_ruin
            
            for trade in shuffled_trades:
                pnl = trade.get('pnl', 0)
                capital += pnl
                equity_curve.append(capital)
                
                # Отслеживаем минимум для prob_ruin
                if capital < min_capital:
                    min_capital = capital
            
            final_capital = capital
            total_return = (final_capital - initial_capital) / initial_capital
            max_drawdown = self._calculate_max_drawdown(equity_curve, initial_capital)
            sharpe_ratio = self._calculate_sharpe(shuffled_trades)
            
            # Проверка на ruin (если капитал упал ниже порога)
            ruin_level = initial_capital * (1 - self.ruin_threshold / 100)
            is_ruin = min_capital < ruin_level
            
            simulations.append({
                'simulation_index': sim_idx,
                'final_capital': final_capital,
                'total_return': total_return,
                'max_drawdown': max_drawdown,
                'sharpe_ratio': sharpe_ratio,
                'is_ruin': is_ruin  # ✅ NEW: Флаг разорения
            })
            
            final_capitals.append(final_capital)
            
            # Прогресс каждые 100 симуляций
            if (sim_idx + 1) % 100 == 0:
                logger.debug(f"Progress: {sim_idx + 1}/{self.n_simulations} simulations")
        
        # Расчёт статистики
        final_capitals = np.array(final_capitals)
        returns = (final_capitals - initial_capital) / initial_capital
        
        # ✅ NEW: Probability calculations (ТЗ 3.5.3)
        prob_profit = np.sum(final_capitals > initial_capital) / self.n_simulations
        
        # Ruin: если минимальный капитал упал ниже порога
        num_ruined = sum(1 for sim in simulations if sim['is_ruin'])
        prob_ruin = num_ruined / self.n_simulations
        
        statistics = {
            'mean_return': float(np.mean(returns)),
            'std_return': float(np.std(returns)),
            'percentile_5': float(np.percentile(returns, 5)),
            'percentile_95': float(np.percentile(returns, 95)),
            'prob_profit': float(prob_profit),      # ✅ NEW
            'prob_ruin': float(prob_ruin),          # ✅ NEW
            'median_return': float(np.median(returns)),
            'best_case': float(np.max(returns)),
            'worst_case': float(np.min(returns)),
            'num_simulations': self.n_simulations,
            'ruin_threshold_pct': self.ruin_threshold
        }
        
        logger.info(
            f"MC completed: mean_return={statistics['mean_return']:.2%}, "
            f"prob_profit={prob_profit:.1%}, prob_ruin={prob_ruin:.1%}"
        )
        
        return {
            'simulations': simulations,
            'statistics': statistics
        }
    
    def _calculate_max_drawdown(self, equity_curve: list[float], initial: float) -> float:
        """
        Рассчитать максимальную просадку из equity curve
        
        Args:
            equity_curve: Список значений капитала
            initial: Начальный капитал
        
        Returns:
            Max drawdown в процентах (0-100)
        """
        peak = initial
        max_dd = 0.0
        
        for equity in equity_curve:
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
        
        return max_dd * 100  # В процентах
    
    def _calculate_sharpe(self, trades: list[dict]) -> float:
        """
        Рассчитать Sharpe ratio из сделок
        
        Formula: mean(returns) / std(returns) * sqrt(252)
        
        Args:
            trades: Список сделок с полем 'pnl_pct'
        
        Returns:
            Annualized Sharpe ratio
        """
        returns = [t.get('pnl_pct', 0) / 100 for t in trades]  # Convert % to decimal
        
        if len(returns) < 2:
            return 0.0
        
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0.0
        
        # Annualized Sharpe (assuming 252 trading days)
        sharpe = (mean_return / std_return) * np.sqrt(252)
        
        return float(sharpe)
    
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
                'prob_ruin': 0.0,
                'median_return': 0.0,
                'best_case': 0.0,
                'worst_case': 0.0,
                'num_simulations': 0,
                'ruin_threshold_pct': self.ruin_threshold
            }
        }
