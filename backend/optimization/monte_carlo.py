"""
Monte Carlo Simulator для оценки рисков торговой стратегии

Реализует ТЗ 3.5.3: Monte Carlo Simulation

Основные возможности:
- Bootstrap permutation (случайная перестановка сделок с возвратом)
- Расчёт доверительных интервалов для доходности
- Оценка вероятности прибыли (Probability of Profit)
- Оценка риска разорения (Probability of Ruin)
- Распределение Sharpe Ratio и Maximum Drawdown

Метод:
1. Берём список исторических сделок
2. Случайно перемешиваем с возвратом (bootstrap)
3. Рассчитываем метрики для каждой перестановки
4. Строим распределение возможных исходов
5. Оцениваем риски и доверительные интервалы
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional


@dataclass
class MonteCarloResult:
    """
    Результаты Monte Carlo симуляции
    
    Attributes:
        n_simulations: Количество симуляций
        original_return: Доходность исходной стратегии (%)
        mean_return: Средняя доходность симуляций (%)
        std_return: Стандартное отклонение доходности (%)
        percentile_5: 5-й перцентиль доходности (%)
        percentile_25: 25-й перцентиль (%)
        percentile_50: Медиана (%)
        percentile_75: 75-й перцентиль (%)
        percentile_95: 95-й перцентиль (%)
        prob_profit: Вероятность прибыли (0-1)
        prob_ruin: Вероятность разорения (0-1)
        original_percentile: Процентиль исходной стратегии (0-100)
        all_returns: Массив всех доходностей симуляций
        all_max_drawdowns: Массив всех максимальных просадок
        all_sharpe_ratios: Массив всех Sharpe ratios
    """
    n_simulations: int
    original_return: float
    mean_return: float
    std_return: float
    percentile_5: float
    percentile_25: float
    percentile_50: float
    percentile_75: float
    percentile_95: float
    prob_profit: float
    prob_ruin: float
    original_percentile: float
    all_returns: np.ndarray
    all_max_drawdowns: np.ndarray
    all_sharpe_ratios: np.ndarray
    
    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь"""
        return {
            'n_simulations': self.n_simulations,
            'original_return': self.original_return,
            'mean_return': self.mean_return,
            'std_return': self.std_return,
            'percentile_5': self.percentile_5,
            'percentile_25': self.percentile_25,
            'percentile_50': self.percentile_50,
            'percentile_75': self.percentile_75,
            'percentile_95': self.percentile_95,
            'prob_profit': self.prob_profit,
            'prob_ruin': self.prob_ruin,
            'original_percentile': self.original_percentile,
            'distribution': {
                'returns': self.all_returns.tolist(),
                'max_drawdowns': self.all_max_drawdowns.tolist(),
                'sharpe_ratios': self.all_sharpe_ratios.tolist(),
            }
        }


class MonteCarloSimulator:
    """
    Monte Carlo Simulator для оценки рисков
    
    Использует bootstrap permutation (выборка с возвратом) для создания
    множественных сценариев и оценки:
    - Вероятности прибыли
    - Вероятности разорения
    - Доверительных интервалов доходности
    
    Example:
        >>> mc = MonteCarloSimulator(n_simulations=1000, ruin_threshold=20.0)
        >>> result = mc.run(trades, initial_capital=10000)
        >>> print(f"Prob of Profit: {result.prob_profit:.2%}")
        >>> print(f"95% CI: [{result.percentile_5:.2f}%, {result.percentile_95:.2f}%]")
    """
    
    def __init__(
        self,
        n_simulations: int = 1000,
        ruin_threshold: float = 20.0,
        random_seed: Optional[int] = None
    ):
        """
        Инициализация Monte Carlo симулятора
        
        Args:
            n_simulations: Количество симуляций (min 10, recommend 1000+)
            ruin_threshold: Порог разорения в % от капитала (default 20%)
            random_seed: Seed для воспроизводимости результатов
        
        Raises:
            ValueError: Если параметры вне допустимых диапазонов
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
    
    def run(
        self,
        trades: List[Dict[str, Any]],
        initial_capital: float = 10000.0
    ) -> MonteCarloResult:
        """
        Запуск Monte Carlo симуляции
        
        Args:
            trades: Список сделок с полями 'pnl', 'pnl_pct', и опционально 'side'
            initial_capital: Начальный капитал
        
        Returns:
            MonteCarloResult с результатами симуляции
        
        Raises:
            ValueError: Если trades пустой или невалидный
        """
        # Валидация
        if not trades or len(trades) == 0:
            raise ValueError("Список trades не может быть пустым")
        
        for i, trade in enumerate(trades):
            if 'pnl' not in trade:
                raise ValueError(f"Сделка {i} не содержит 'pnl'")
        
        # Сброс seed для воспроизводимости
        if self.random_seed is not None:
            np.random.seed(self.random_seed)
        
        # Расчёт метрик оригинальной стратегии
        original_return = self._calculate_return(trades, initial_capital)
        
        # Массивы для хранения результатов
        all_returns = np.zeros(self.n_simulations)
        all_max_drawdowns = np.zeros(self.n_simulations)
        all_sharpe_ratios = np.zeros(self.n_simulations)
        
        # Monte Carlo симуляции
        n_trades = len(trades)
        for i in range(self.n_simulations):
            # Bootstrap sampling (с возвратом)
            indices = np.random.choice(n_trades, size=n_trades, replace=True)
            shuffled_trades = [trades[idx] for idx in indices]
            
            # Расчёт метрик для симуляции
            all_returns[i] = self._calculate_return(shuffled_trades, initial_capital)
            all_max_drawdowns[i] = self._calculate_max_drawdown(shuffled_trades, initial_capital)
            all_sharpe_ratios[i] = self._calculate_sharpe(shuffled_trades)
        
        # Статистика
        mean_return = np.mean(all_returns)
        std_return = np.std(all_returns)
        
        # Перцентили
        percentile_5 = np.percentile(all_returns, 5)
        percentile_25 = np.percentile(all_returns, 25)
        percentile_50 = np.percentile(all_returns, 50)
        percentile_75 = np.percentile(all_returns, 75)
        percentile_95 = np.percentile(all_returns, 95)
        
        # Вероятности
        prob_profit = np.mean(all_returns > 0)
        prob_ruin = np.mean(all_max_drawdowns >= self.ruin_threshold)
        
        # Процентиль оригинальной стратегии
        original_percentile = (np.sum(all_returns < original_return) / self.n_simulations) * 100
        
        return MonteCarloResult(
            n_simulations=self.n_simulations,
            original_return=original_return,
            mean_return=mean_return,
            std_return=std_return,
            percentile_5=percentile_5,
            percentile_25=percentile_25,
            percentile_50=percentile_50,
            percentile_75=percentile_75,
            percentile_95=percentile_95,
            prob_profit=prob_profit,
            prob_ruin=prob_ruin,
            original_percentile=original_percentile,
            all_returns=all_returns,
            all_max_drawdowns=all_max_drawdowns,
            all_sharpe_ratios=all_sharpe_ratios,
        )
    
    def _calculate_return(self, trades: List[Dict[str, Any]], initial_capital: float) -> float:
        """
        Расчёт доходности в %
        
        Args:
            trades: Список сделок
            initial_capital: Начальный капитал
        
        Returns:
            Доходность в процентах
        """
        total_pnl = sum(trade['pnl'] for trade in trades)
        return (total_pnl / initial_capital) * 100.0
    
    def _calculate_max_drawdown(self, trades: List[Dict[str, Any]], initial_capital: float) -> float:
        """
        Расчёт максимальной просадки в %
        
        Args:
            trades: Список сделок
            initial_capital: Начальный капитал
        
        Returns:
            Максимальная просадка в процентах
        """
        capital = initial_capital
        peak = initial_capital
        max_dd = 0.0
        
        for trade in trades:
            capital += trade['pnl']
            if capital > peak:
                peak = capital
            
            if peak > 0:
                dd = ((peak - capital) / peak) * 100.0
                if dd > max_dd:
                    max_dd = dd
        
        return max_dd
    
    def _calculate_sharpe(self, trades: List[Dict[str, Any]]) -> float:
        """
        Расчёт Sharpe Ratio
        
        Args:
            trades: Список сделок
        
        Returns:
            Sharpe ratio (annualized)
        """
        if not trades or len(trades) < 2:
            return 0.0
        
        # Доходность каждой сделки
        returns = np.array([trade.get('pnl_pct', 0.0) for trade in trades])
        
        if np.std(returns) == 0:
            return 0.0
        
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        # Sharpe = (mean - risk_free_rate) / std
        # Упрощённо: Sharpe = mean / std
        # Annualization: * sqrt(252) для дневных данных
        # Но для универсальности не аннуализируем
        sharpe = mean_return / std_return if std_return > 0 else 0.0
        
        return sharpe
    
    def get_confidence_interval(
        self,
        result: MonteCarloResult,
        confidence: float = 0.95
    ) -> Tuple[float, float]:
        """
        Получить доверительный интервал для доходности
        
        Args:
            result: Результаты Monte Carlo
            confidence: Уровень доверия (0.90, 0.95, 0.99)
        
        Returns:
            Tuple (lower_bound, upper_bound) в процентах
        
        Raises:
            ValueError: Если confidence вне диапазона (0, 1)
        """
        if not (0 < confidence < 1.0):
            raise ValueError("confidence должно быть в диапазоне (0, 1)")
        
        alpha = (1 - confidence) / 2
        lower_percentile = alpha * 100
        upper_percentile = (1 - alpha) * 100
        
        lower = np.percentile(result.all_returns, lower_percentile)
        upper = np.percentile(result.all_returns, upper_percentile)
        
        return (lower, upper)
    
    def get_risk_of_ruin(
        self,
        result: MonteCarloResult,
        ruin_level: float = 30.0
    ) -> float:
        """
        Вероятность просадки >= ruin_level
        
        Args:
            result: Результаты Monte Carlo
            ruin_level: Уровень просадки в % (default 30%)
        
        Returns:
            Вероятность разорения (0-1)
        
        Raises:
            ValueError: Если ruin_level вне диапазона (0, 100)
        """
        if not (0 < ruin_level < 100):
            raise ValueError("ruin_level должно быть в диапазоне (0, 100)")
        
        return np.mean(result.all_max_drawdowns >= ruin_level)
    
    def generate_summary(self, result: MonteCarloResult) -> Dict[str, Any]:
        """
        Генерация текстовой сводки результатов
        
        Args:
            result: Результаты Monte Carlo
        
        Returns:
            Словарь с интерпретацией результатов
        """
        # Оценка риска
        if result.prob_profit >= 0.7:
            risk_level = "Низкий"
            risk_emoji = "🟢"
        elif result.prob_profit >= 0.5:
            risk_level = "Средний"
            risk_emoji = "🟡"
        else:
            risk_level = "Высокий"
            risk_emoji = "🔴"
        
        # Рекомендация
        if result.prob_profit >= 0.7 and result.prob_ruin < 0.1:
            recommendation = "✅ Стратегия показывает стабильные результаты"
        elif result.prob_profit >= 0.5 and result.prob_ruin < 0.2:
            recommendation = "⚠️ Стратегия приемлема, но требует мониторинга"
        else:
            recommendation = "❌ Стратегия имеет высокий риск, не рекомендуется"
        
        # 95% доверительный интервал
        ci_lower, ci_upper = self.get_confidence_interval(result, 0.95)
        
        return {
            'risk_level': risk_level,
            'risk_emoji': risk_emoji,
            'recommendation': recommendation,
            'summary': {
                'simulations': result.n_simulations,
                'original_return': f"{result.original_return:.2f}%",
                'mean_return': f"{result.mean_return:.2f}%",
                'std_return': f"{result.std_return:.2f}%",
                'prob_profit': f"{result.prob_profit:.1%}",
                'prob_ruin': f"{result.prob_ruin:.1%}",
                'confidence_interval_95': f"[{ci_lower:.2f}%, {ci_upper:.2f}%]",
            },
            'key_findings': [
                f"Вероятность прибыли: {result.prob_profit:.1%}",
                f"Вероятность разорения (>{self.ruin_threshold}% DD): {result.prob_ruin:.1%}",
                f"Средняя доходность: {result.mean_return:.2f}% (±{result.std_return:.2f}%)",
                f"95% доверительный интервал: [{ci_lower:.2f}%, {ci_upper:.2f}%]",
            ]
        }
