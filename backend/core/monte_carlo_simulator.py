"""
Monte Carlo Simulation для оценки устойчивости стратегии.

Реализует:
- Случайную перестановку сделок (trade shuffling)
- Множественные симуляции для статистической значимости
- Расчёт метрик: mean_return, std_return, percentiles, probability of profit/ruin
- Визуализацию распределения доходности

Соответствует ТЗ Раздел 3.5.3: "Оценка устойчивости стратегии через случайную перестановку сделок"
"""

from dataclasses import dataclass
from typing import Optional
import numpy as np
import pandas as pd


@dataclass
class MonteCarloResult:
    """Результаты Monte Carlo симуляции."""
    
    n_simulations: int
    original_return: float
    mean_return: float
    std_return: float
    median_return: float
    percentile_5: float
    percentile_25: float
    percentile_75: float
    percentile_95: float
    prob_profit: float  # Вероятность положительной доходности
    prob_ruin: float    # Вероятность просадки > threshold
    
    # Распределение всех симуляций
    all_returns: np.ndarray
    all_max_drawdowns: np.ndarray
    all_sharpe_ratios: np.ndarray
    
    # Статистика по оригинальной стратегии
    original_percentile: float  # Процентиль оригинальной доходности


class MonteCarloSimulator:
    """
    Monte Carlo симулятор для оценки устойчивости стратегии.
    
    Метод Bootstrap:
    1. Берёт список сделок из бэктеста
    2. Делает случайную выборку с возвращением (bootstrap sampling)
    3. Пересчитывает equity curve и метрики
    4. Повторяет N раз для построения распределения
    5. Оценивает вероятность profit/ruin
    
    Bootstrap позволяет оценить вариативность результатов стратегии
    при разных последовательностях сделок.
    
    Args:
        n_simulations: Количество Monte Carlo симуляций (default: 1000)
        ruin_threshold: Порог просадки для prob_ruin в % (default: 20.0)
        random_seed: Seed для воспроизводимости (default: None)
    """
    
    def __init__(
        self,
        n_simulations: int = 1000,
        ruin_threshold: float = 20.0,
        random_seed: Optional[int] = None
    ):
        if n_simulations < 10:
            raise ValueError("n_simulations должно быть >= 10")
        if ruin_threshold <= 0 or ruin_threshold >= 100:
            raise ValueError("ruin_threshold должно быть в диапазоне (0, 100)")
        
        self.n_simulations = n_simulations
        self.ruin_threshold = ruin_threshold
        self.random_seed = random_seed
        
        if random_seed is not None:
            np.random.seed(random_seed)
    
    def run(
        self,
        trades: list[dict],
        initial_capital: float = 10000.0
    ) -> MonteCarloResult:
        """
        Выполнить Monte Carlo симуляцию на списке сделок.
        
        Args:
            trades: Список сделок из BacktestEngine
                Каждая сделка: {
                    'pnl': float,
                    'pnl_pct': float,
                    'side': str,
                    'entry_time': datetime,
                    'exit_time': datetime,
                    ...
                }
            initial_capital: Начальный капитал
        
        Returns:
            MonteCarloResult с метриками симуляции
        
        Raises:
            ValueError: Если trades пустой или некорректный
        """
        if not trades or len(trades) == 0:
            raise ValueError("Список trades не может быть пустым")
        
        # Валидация trades
        for i, trade in enumerate(trades):
            if 'pnl' not in trade:
                raise ValueError(f"Trade {i} не содержит 'pnl'")
        
        # Сбросить seed перед симуляцией для воспроизводимости
        if self.random_seed is not None:
            np.random.seed(self.random_seed)
        
        print(f"\n🎲 Monte Carlo Simulation:")
        print(f"   Simulations: {self.n_simulations}")
        print(f"   Trades: {len(trades)}")
        print(f"   Initial Capital: ${initial_capital:,.2f}")
        print(f"   Ruin Threshold: {self.ruin_threshold}%")
        
        # Оригинальная доходность (без перемешивания)
        original_return = self._calculate_return(trades, initial_capital)
        
        # Выполнить N симуляций
        all_returns = []
        all_max_drawdowns = []
        all_sharpe_ratios = []
        
        for i in range(self.n_simulations):
            # Случайная перестановка сделок
            shuffled_trades = self._shuffle_trades(trades)
            
            # Пересчитать метрики
            sim_return = self._calculate_return(shuffled_trades, initial_capital)
            sim_drawdown = self._calculate_max_drawdown(shuffled_trades, initial_capital)
            sim_sharpe = self._calculate_sharpe(shuffled_trades)
            
            all_returns.append(sim_return)
            all_max_drawdowns.append(sim_drawdown)
            all_sharpe_ratios.append(sim_sharpe)
            
            # Прогресс
            if (i + 1) % 100 == 0:
                print(f"   Progress: {i + 1}/{self.n_simulations} simulations")
        
        # Преобразовать в numpy arrays
        all_returns = np.array(all_returns)
        all_max_drawdowns = np.array(all_max_drawdowns)
        all_sharpe_ratios = np.array(all_sharpe_ratios)
        
        # Рассчитать метрики
        mean_return = np.mean(all_returns)
        std_return = np.std(all_returns)
        median_return = np.median(all_returns)
        percentile_5 = np.percentile(all_returns, 5)
        percentile_25 = np.percentile(all_returns, 25)
        percentile_75 = np.percentile(all_returns, 75)
        percentile_95 = np.percentile(all_returns, 95)
        
        # Вероятности
        prob_profit = np.sum(all_returns > 0) / self.n_simulations
        prob_ruin = np.sum(all_max_drawdowns > self.ruin_threshold) / self.n_simulations
        
        # Процентиль оригинальной доходности
        original_percentile = np.sum(all_returns <= original_return) / self.n_simulations * 100
        
        print(f"\n   ✅ Simulation Complete!")
        print(f"   Original Return: {original_return:.2f}%")
        print(f"   Mean Return: {mean_return:.2f}%")
        print(f"   Std Return: {std_return:.2f}%")
        print(f"   95% CI: [{percentile_5:.2f}%, {percentile_95:.2f}%]")
        print(f"   Prob Profit: {prob_profit:.1%}")
        print(f"   Prob Ruin: {prob_ruin:.1%}")
        print(f"   Original Percentile: {original_percentile:.1f}%\n")
        
        return MonteCarloResult(
            n_simulations=self.n_simulations,
            original_return=original_return,
            mean_return=mean_return,
            std_return=std_return,
            median_return=median_return,
            percentile_5=percentile_5,
            percentile_25=percentile_25,
            percentile_75=percentile_75,
            percentile_95=percentile_95,
            prob_profit=prob_profit,
            prob_ruin=prob_ruin,
            all_returns=all_returns,
            all_max_drawdowns=all_max_drawdowns,
            all_sharpe_ratios=all_sharpe_ratios,
            original_percentile=original_percentile
        )
    
    def _shuffle_trades(self, trades: list[dict]) -> list[dict]:
        """
        Случайная выборка сделок с возвращением (bootstrap).
        
        Метод bootstrap позволяет получить разные комбинации сделок
        и создать распределение доходности для оценки вариативности.
        
        Args:
            trades: Исходный список сделок
        
        Returns:
            Bootstrap выборка сделок (с возвращением)
        """
        # Bootstrap: случайная выборка того же размера с возвращением
        indices = np.random.choice(len(trades), size=len(trades), replace=True)
        bootstrapped = [trades[i] for i in indices]
        return bootstrapped
    
    def _calculate_return(self, trades: list[dict], initial_capital: float) -> float:
        """
        Рассчитать итоговую доходность в %.
        
        Args:
            trades: Список сделок
            initial_capital: Начальный капитал
        
        Returns:
            Итоговая доходность в %
        """
        capital = initial_capital
        
        for trade in trades:
            capital += trade['pnl']
        
        total_return = ((capital - initial_capital) / initial_capital) * 100
        return total_return
    
    def _calculate_max_drawdown(self, trades: list[dict], initial_capital: float) -> float:
        """
        Рассчитать максимальную просадку в %.
        
        Args:
            trades: Список сделок
            initial_capital: Начальный капитал
        
        Returns:
            Максимальная просадка в %
        """
        capital = initial_capital
        peak = initial_capital
        max_dd = 0.0
        
        for trade in trades:
            capital += trade['pnl']
            
            if capital > peak:
                peak = capital
            
            dd = ((peak - capital) / peak) * 100
            if dd > max_dd:
                max_dd = dd
        
        return max_dd
    
    def _calculate_sharpe(self, trades: list[dict]) -> float:
        """
        Рассчитать Sharpe ratio.
        
        Args:
            trades: Список сделок
        
        Returns:
            Sharpe ratio
        """
        if len(trades) == 0:
            return 0.0
        
        # Доходности сделок в %
        returns = [trade['pnl_pct'] for trade in trades]
        
        if len(returns) < 2:
            return 0.0
        
        mean_return = np.mean(returns)
        std_return = np.std(returns, ddof=1)
        
        if std_return == 0:
            return 0.0
        
        # Sharpe = mean / std (упрощённая версия без risk-free rate)
        sharpe = mean_return / std_return
        
        # Annualized Sharpe (предполагаем ~252 торговых дня)
        sharpe_annualized = sharpe * np.sqrt(252)
        
        return sharpe_annualized
    
    def get_confidence_interval(
        self,
        result: MonteCarloResult,
        confidence: float = 0.95
    ) -> tuple[float, float]:
        """
        Получить доверительный интервал для доходности.
        
        Args:
            result: Результат Monte Carlo симуляции
            confidence: Уровень доверия (default: 0.95)
        
        Returns:
            Tuple (lower_bound, upper_bound) в %
        """
        if confidence <= 0 or confidence >= 1:
            raise ValueError("confidence должно быть в диапазоне (0, 1)")
        
        alpha = 1 - confidence
        lower_percentile = (alpha / 2) * 100
        upper_percentile = (1 - alpha / 2) * 100
        
        lower_bound = np.percentile(result.all_returns, lower_percentile)
        upper_bound = np.percentile(result.all_returns, upper_percentile)
        
        return (lower_bound, upper_bound)
    
    def get_risk_of_ruin(
        self,
        result: MonteCarloResult,
        ruin_level: float
    ) -> float:
        """
        Рассчитать вероятность просадки >= ruin_level.
        
        Args:
            result: Результат Monte Carlo симуляции
            ruin_level: Уровень просадки в % (например, 30.0)
        
        Returns:
            Вероятность (0.0 - 1.0)
        """
        if ruin_level <= 0 or ruin_level >= 100:
            raise ValueError("ruin_level должно быть в диапазоне (0, 100)")
        
        prob = np.sum(result.all_max_drawdowns >= ruin_level) / result.n_simulations
        return prob
