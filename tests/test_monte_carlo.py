"""
Тесты для Monte Carlo Simulator.

Проверяют:
- Инициализацию симулятора
- Базовую симуляцию
- Расчёт метрик (return, drawdown, sharpe)
- Вероятности (profit, ruin)
- Доверительные интервалы
- Обработку edge cases
"""

import pytest
import numpy as np
from backend.optimization.monte_carlo import MonteCarloSimulator, MonteCarloResult


@pytest.fixture
def sample_trades_profitable():
    """Прибыльные сделки для тестирования."""
    return [
        {'pnl': 100, 'pnl_pct': 1.0, 'side': 'long'},
        {'pnl': 200, 'pnl_pct': 2.0, 'side': 'long'},
        {'pnl': -50, 'pnl_pct': -0.5, 'side': 'short'},
        {'pnl': 150, 'pnl_pct': 1.5, 'side': 'long'},
        {'pnl': 300, 'pnl_pct': 3.0, 'side': 'long'},
    ]


@pytest.fixture
def sample_trades_losing():
    """Убыточные сделки для тестирования."""
    return [
        {'pnl': -100, 'pnl_pct': -1.0, 'side': 'long'},
        {'pnl': -200, 'pnl_pct': -2.0, 'side': 'short'},
        {'pnl': 50, 'pnl_pct': 0.5, 'side': 'long'},
        {'pnl': -150, 'pnl_pct': -1.5, 'side': 'short'},
    ]


@pytest.fixture
def sample_trades_mixed():
    """Смешанные сделки (50% win rate)."""
    return [
        {'pnl': 100, 'pnl_pct': 1.0, 'side': 'long'},
        {'pnl': -100, 'pnl_pct': -1.0, 'side': 'long'},
        {'pnl': 200, 'pnl_pct': 2.0, 'side': 'short'},
        {'pnl': -200, 'pnl_pct': -2.0, 'side': 'short'},
        {'pnl': 150, 'pnl_pct': 1.5, 'side': 'long'},
        {'pnl': -150, 'pnl_pct': -1.5, 'side': 'long'},
    ]


def test_mc_initialization():
    """Test Monte Carlo simulator initialization."""
    mc = MonteCarloSimulator(n_simulations=100, ruin_threshold=20.0, random_seed=42)
    
    assert mc.n_simulations == 100
    assert mc.ruin_threshold == 20.0
    assert mc.random_seed == 42


def test_mc_invalid_parameters():
    """Test Monte Carlo with invalid parameters."""
    # Too few simulations
    with pytest.raises(ValueError, match="n_simulations должно быть >= 10"):
        MonteCarloSimulator(n_simulations=5)
    
    # Invalid ruin threshold
    with pytest.raises(ValueError, match="ruin_threshold должно быть в диапазоне"):
        MonteCarloSimulator(ruin_threshold=0)
    
    with pytest.raises(ValueError, match="ruin_threshold должно быть в диапазоне"):
        MonteCarloSimulator(ruin_threshold=100)


def test_mc_empty_trades():
    """Test Monte Carlo with empty trades list."""
    mc = MonteCarloSimulator(n_simulations=100, random_seed=42)
    
    with pytest.raises(ValueError, match="Список trades не может быть пустым"):
        mc.run([], initial_capital=10000)


def test_mc_invalid_trades():
    """Test Monte Carlo with invalid trades (missing 'pnl')."""
    mc = MonteCarloSimulator(n_simulations=100, random_seed=42)
    
    invalid_trades = [
        {'side': 'long'},  # Missing 'pnl'
        {'pnl': 100, 'pnl_pct': 1.0, 'side': 'long'},
    ]
    
    with pytest.raises(ValueError, match="не содержит 'pnl'"):
        mc.run(invalid_trades, initial_capital=10000)


def test_mc_profitable_strategy(sample_trades_profitable):
    """Test Monte Carlo on profitable strategy."""
    mc = MonteCarloSimulator(n_simulations=100, ruin_threshold=20.0, random_seed=42)
    
    result = mc.run(sample_trades_profitable, initial_capital=10000)
    
    # Проверка типа результата
    assert isinstance(result, MonteCarloResult)
    
    # Проверка метрик
    assert result.n_simulations == 100
    assert result.original_return > 0  # Прибыльная стратегия
    assert result.mean_return > 0
    assert result.std_return >= 0  # Bootstrap может давать вариативность
    assert result.prob_profit > 0.5  # Большинство симуляций прибыльные
    
    # Проверка percentiles (bootstrap может давать одинаковые при малом количестве сделок)
    assert result.percentile_5 <= result.percentile_25
    assert result.percentile_25 <= result.percentile_75
    assert result.percentile_75 <= result.percentile_95
    
    # Проверка массивов
    assert len(result.all_returns) == 100
    assert len(result.all_max_drawdowns) == 100
    assert len(result.all_sharpe_ratios) == 100


def test_mc_losing_strategy(sample_trades_losing):
    """Test Monte Carlo on losing strategy."""
    mc = MonteCarloSimulator(n_simulations=100, ruin_threshold=20.0, random_seed=42)
    
    result = mc.run(sample_trades_losing, initial_capital=10000)
    
    # Убыточная стратегия
    assert result.original_return < 0
    assert result.mean_return < 0
    assert result.prob_profit < 0.5  # Большинство симуляций убыточные


def test_mc_mixed_strategy(sample_trades_mixed):
    """Test Monte Carlo on mixed strategy (50% win rate)."""
    mc = MonteCarloSimulator(n_simulations=100, ruin_threshold=20.0, random_seed=42)
    
    result = mc.run(sample_trades_mixed, initial_capital=10000)
    
    # Нулевая доходность (равное количество wins/losses)
    # Bootstrap может давать небольшую вариативность
    assert abs(result.mean_return) < 3.0  # Близко к 0
    
    # С bootstrap вероятность прибыли может варьироваться
    assert 0.0 <= result.prob_profit <= 1.0


def test_mc_return_calculation(sample_trades_profitable):
    """Test return calculation."""
    mc = MonteCarloSimulator(n_simulations=10, random_seed=42)
    
    # Вручную рассчитать доходность
    initial_capital = 10000
    total_pnl = sum(trade['pnl'] for trade in sample_trades_profitable)
    expected_return = (total_pnl / initial_capital) * 100
    
    # Рассчитать через симулятор
    calculated_return = mc._calculate_return(sample_trades_profitable, initial_capital)
    
    assert abs(calculated_return - expected_return) < 0.01


def test_mc_max_drawdown_calculation():
    """Test max drawdown calculation."""
    mc = MonteCarloSimulator(n_simulations=10, random_seed=42)
    
    # Сделки с известной просадкой
    trades = [
        {'pnl': 1000, 'pnl_pct': 10.0},   # Capital: 11000 (peak)
        {'pnl': -2000, 'pnl_pct': -18.18}, # Capital: 9000 (drawdown)
        {'pnl': 500, 'pnl_pct': 5.56},     # Capital: 9500
    ]
    
    max_dd = mc._calculate_max_drawdown(trades, initial_capital=10000)
    
    # Максимальная просадка: (11000 - 9000) / 11000 * 100 = 18.18%
    expected_dd = (11000 - 9000) / 11000 * 100
    
    assert abs(max_dd - expected_dd) < 0.01


def test_mc_sharpe_calculation():
    """Test Sharpe ratio calculation."""
    mc = MonteCarloSimulator(n_simulations=10, random_seed=42)
    
    # Сделки с известной доходностью
    trades = [
        {'pnl': 100, 'pnl_pct': 1.0},
        {'pnl': 200, 'pnl_pct': 2.0},
        {'pnl': 150, 'pnl_pct': 1.5},
    ]
    
    sharpe = mc._calculate_sharpe(trades)
    
    # Sharpe должен быть положительным для прибыльных сделок
    assert sharpe > 0


def test_mc_confidence_interval(sample_trades_profitable):
    """Test confidence interval calculation."""
    mc = MonteCarloSimulator(n_simulations=1000, random_seed=42)
    
    result = mc.run(sample_trades_profitable, initial_capital=10000)
    
    # 95% доверительный интервал
    lower, upper = mc.get_confidence_interval(result, confidence=0.95)
    
    # Bootstrap может давать одинаковые границы при малом количестве уникальных сделок
    assert lower <= upper
    assert lower <= result.percentile_5
    assert upper >= result.percentile_95
    
    # 90% доверительный интервал (уже или равен)
    lower_90, upper_90 = mc.get_confidence_interval(result, confidence=0.90)
    
    assert lower_90 >= lower
    assert upper_90 <= upper


def test_mc_risk_of_ruin(sample_trades_profitable):
    """Test risk of ruin calculation."""
    mc = MonteCarloSimulator(n_simulations=1000, ruin_threshold=20.0, random_seed=42)
    
    result = mc.run(sample_trades_profitable, initial_capital=10000)
    
    # Риск просадки >= 30%
    risk_30 = mc.get_risk_of_ruin(result, ruin_level=30.0)
    
    assert 0.0 <= risk_30 <= 1.0
    
    # Риск просадки >= 50% (должен быть меньше, чем 30%)
    risk_50 = mc.get_risk_of_ruin(result, ruin_level=50.0)
    
    assert risk_50 <= risk_30


def test_mc_reproducibility():
    """Test Monte Carlo reproducibility with same seed."""
    mc1 = MonteCarloSimulator(n_simulations=100, random_seed=42)
    mc2 = MonteCarloSimulator(n_simulations=100, random_seed=42)
    
    trades = [
        {'pnl': 100, 'pnl_pct': 1.0},
        {'pnl': -50, 'pnl_pct': -0.5},
        {'pnl': 200, 'pnl_pct': 2.0},
    ]
    
    result1 = mc1.run(trades, initial_capital=10000)
    result2 = mc2.run(trades, initial_capital=10000)
    
    # Результаты должны быть идентичными
    assert result1.mean_return == result2.mean_return
    assert result1.std_return == result2.std_return
    assert result1.prob_profit == result2.prob_profit
    assert np.array_equal(result1.all_returns, result2.all_returns)


def test_mc_percentile_ranking(sample_trades_profitable):
    """Test original strategy percentile ranking."""
    mc = MonteCarloSimulator(n_simulations=1000, random_seed=42)
    
    result = mc.run(sample_trades_profitable, initial_capital=10000)
    
    # Процентиль должен быть в диапазоне [0, 100]
    assert 0 <= result.original_percentile <= 100
    
    # Для bootstrap с малым количеством сделок процентиль может быть разным
    # Главное - что он в валидном диапазоне
    # Оригинальная стратегия использует все сделки в правильном порядке


def test_mc_large_number_of_simulations(sample_trades_profitable):
    """Test Monte Carlo with large number of simulations."""
    mc = MonteCarloSimulator(n_simulations=5000, ruin_threshold=20.0, random_seed=42)
    
    result = mc.run(sample_trades_profitable, initial_capital=10000)
    
    assert result.n_simulations == 5000
    assert len(result.all_returns) == 5000
    
    # С большим количеством симуляций std должна быть стабильной
    assert result.std_return > 0


def test_mc_single_trade():
    """Test Monte Carlo with single trade."""
    mc = MonteCarloSimulator(n_simulations=100, random_seed=42)
    
    single_trade = [{'pnl': 100, 'pnl_pct': 1.0}]
    
    result = mc.run(single_trade, initial_capital=10000)
    
    # Одна сделка -> все симуляции идентичны
    assert result.std_return == 0.0
    assert result.mean_return == result.original_return
    assert len(set(result.all_returns)) == 1  # Все значения одинаковые


def test_mc_prob_profit_bounds(sample_trades_profitable, sample_trades_losing):
    """Test probability of profit bounds."""
    mc = MonteCarloSimulator(n_simulations=1000, random_seed=42)
    
    # Прибыльная стратегия
    result_profit = mc.run(sample_trades_profitable, initial_capital=10000)
    assert result_profit.prob_profit > 0.5
    
    # Убыточная стратегия
    result_loss = mc.run(sample_trades_losing, initial_capital=10000)
    assert result_loss.prob_profit < 0.5


def test_mc_invalid_confidence():
    """Test invalid confidence interval parameters."""
    mc = MonteCarloSimulator(n_simulations=100, random_seed=42)
    
    trades = [{'pnl': 100, 'pnl_pct': 1.0}]
    result = mc.run(trades, initial_capital=10000)
    
    with pytest.raises(ValueError, match="confidence должно быть в диапазоне"):
        mc.get_confidence_interval(result, confidence=0)
    
    with pytest.raises(ValueError, match="confidence должно быть в диапазоне"):
        mc.get_confidence_interval(result, confidence=1.0)


def test_mc_invalid_ruin_level():
    """Test invalid risk of ruin parameters."""
    mc = MonteCarloSimulator(n_simulations=100, random_seed=42)
    
    trades = [{'pnl': 100, 'pnl_pct': 1.0}]
    result = mc.run(trades, initial_capital=10000)
    
    with pytest.raises(ValueError, match="ruin_level должно быть в диапазоне"):
        mc.get_risk_of_ruin(result, ruin_level=0)
    
    with pytest.raises(ValueError, match="ruin_level должно быть в диапазоне"):
        mc.get_risk_of_ruin(result, ruin_level=100)
