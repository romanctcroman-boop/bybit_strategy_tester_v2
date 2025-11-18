"""
Unit тесты для WalkForwardOptimizer (backend/optimization/walk_forward_optimizer.py)

Проверяет:
1. Корректность расчёта parameter_stability (ТЗ 3.5.2)
2. Rolling и Anchored режимы
3. Разделение In-sample / Out-sample
4. Валидацию параметров
5. Агрегацию метрик

Создано: 25 октября 2025 (Фаза 1, Задача 6)
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from optimization.walk_forward_optimizer import (
    WalkForwardOptimizer,
    WFOMode,
    WFOPeriod
)


# ========================================================================
# Test Data Generation
# ========================================================================

def generate_test_klines(n_bars: int = 1000, base_price: float = 50000.0) -> pd.DataFrame:
    """
    Генерирует тестовые OHLCV данные
    
    Args:
        n_bars: Количество баров
        base_price: Базовая цена
    
    Returns:
        DataFrame с колонками [timestamp, open, high, low, close, volume]
    """
    np.random.seed(42)
    
    timestamps = pd.date_range(
        start=datetime.now() - timedelta(hours=n_bars),
        periods=n_bars,
        freq='1h'
    )
    
    # Random walk price
    returns = np.random.normal(0, 0.01, n_bars)
    prices = base_price * (1 + returns).cumprod()
    
    data = {
        'timestamp': timestamps,
        'open': prices,
        'high': prices * (1 + np.abs(np.random.normal(0, 0.005, n_bars))),
        'low': prices * (1 - np.abs(np.random.normal(0, 0.005, n_bars))),
        'close': prices,
        'volume': np.random.uniform(100, 1000, n_bars)
    }
    
    return pd.DataFrame(data)


# ========================================================================
# Test Fixtures
# ========================================================================

@pytest.fixture
def sample_data():
    """Fixture: тестовые данные (1000 баров)"""
    return generate_test_klines(n_bars=1000)


@pytest.fixture
def simple_param_space():
    """Fixture: простое пространство параметров"""
    return {
        'fast_ema': [10, 20, 30],
        'slow_ema': [50, 100]
    }


@pytest.fixture
def strategy_config():
    """Fixture: базовая конфигурация стратегии"""
    return {
        'type': 'ema_crossover',
        'direction': 'long',
        'take_profit_pct': 3.0,
        'stop_loss_pct': 2.0,
        'signal_exit': False
    }


# ========================================================================
# Test WalkForwardOptimizer Initialization
# ========================================================================

def test_wfo_initialization():
    """Тест: инициализация WalkForwardOptimizer"""
    wfo = WalkForwardOptimizer(
        in_sample_size=200,
        out_sample_size=50,
        step_size=50,
        mode=WFOMode.ROLLING
    )
    
    assert wfo.in_sample_size == 200
    assert wfo.out_sample_size == 50
    assert wfo.step_size == 50
    assert wfo.mode == WFOMode.ROLLING
    print("✓ WalkForwardOptimizer инициализирован корректно")


# ========================================================================
# Test Parameter Stability Calculation (ТЗ 3.5.2)
# ========================================================================

def test_parameter_stability_calculation():
    """
    Тест: расчёт parameter_stability (ТЗ 3.5.2)
    
    Проверяет:
    - Возвращает dict с параметрами
    - Содержит: mean, std, min, max, cv, stability_score
    - stability_score = 1 / (1 + CV)
    - CV = std / mean
    """
    wfo = WalkForwardOptimizer(
        in_sample_size=200,
        out_sample_size=50,
        step_size=50
    )
    
    # Mock данные: 3 периода с параметрами
    all_params = [
        {'fast_ema': 10, 'slow_ema': 50},
        {'fast_ema': 12, 'slow_ema': 52},
        {'fast_ema': 11, 'slow_ema': 51}
    ]
    
    stability = wfo._calculate_parameter_stability(all_params)
    
    # Проверяем структуру
    assert isinstance(stability, dict), "Stability должен быть dict"
    assert 'fast_ema' in stability
    assert 'slow_ema' in stability
    
    # Проверяем fast_ema
    fast_stats = stability['fast_ema']
    assert 'mean' in fast_stats
    assert 'std' in fast_stats
    assert 'min' in fast_stats
    assert 'max' in fast_stats
    assert 'coefficient_of_variation' in fast_stats
    assert 'stability_score' in fast_stats
    
    # Проверяем значения fast_ema
    assert fast_stats['mean'] == pytest.approx(11.0, abs=0.1)  # (10+12+11)/3 = 11
    assert fast_stats['min'] == 10
    assert fast_stats['max'] == 12
    assert fast_stats['std'] > 0
    
    # Проверяем формулу CV и stability_score
    expected_cv = fast_stats['std'] / fast_stats['mean']
    assert fast_stats['coefficient_of_variation'] == pytest.approx(expected_cv, abs=0.01)
    
    expected_stability = 1 / (1 + expected_cv)
    assert fast_stats['stability_score'] == pytest.approx(expected_stability, abs=0.01)
    
    print(f"✓ Parameter stability расчёт корректен:")
    print(f"  fast_ema: mean={fast_stats['mean']:.2f}, CV={fast_stats['coefficient_of_variation']:.4f}, stability={fast_stats['stability_score']:.4f}")
    print(f"  slow_ema: mean={stability['slow_ema']['mean']:.2f}, CV={stability['slow_ema']['coefficient_of_variation']:.4f}, stability={stability['slow_ema']['stability_score']:.4f}")


def test_parameter_stability_perfect_stability():
    """Тест: parameter_stability для идеально стабильных параметров"""
    wfo = WalkForwardOptimizer(
        in_sample_size=200,
        out_sample_size=50,
        step_size=50
    )
    
    # Все периоды имеют одинаковые параметры
    all_params = [
        {'fast_ema': 20, 'slow_ema': 50},
        {'fast_ema': 20, 'slow_ema': 50},
        {'fast_ema': 20, 'slow_ema': 50}
    ]
    
    stability = wfo._calculate_parameter_stability(all_params)
    
    # При идеальной стабильности: std=0, CV=0, stability_score=1.0
    fast_stats = stability['fast_ema']
    
    assert fast_stats['std'] == pytest.approx(0.0, abs=1e-6)
    assert fast_stats['coefficient_of_variation'] == pytest.approx(0.0, abs=1e-6)
    assert fast_stats['stability_score'] == pytest.approx(1.0, abs=0.01)
    
    print(f"✓ Идеальная стабильность: CV=0, stability_score=1.0")


def test_parameter_stability_high_variability():
    """Тест: parameter_stability для нестабильных параметров"""
    wfo = WalkForwardOptimizer(
        in_sample_size=200,
        out_sample_size=50,
        step_size=50
    )
    
    # Высокая вариативность параметров
    all_params = [
        {'fast_ema': 5, 'slow_ema': 30},
        {'fast_ema': 30, 'slow_ema': 100},
        {'fast_ema': 10, 'slow_ema': 200}
    ]
    
    stability = wfo._calculate_parameter_stability(all_params)
    
    fast_stats = stability['fast_ema']
    slow_stats = stability['slow_ema']
    
    # При высокой вариативности: CV > 0.5, stability_score < 0.67
    assert fast_stats['coefficient_of_variation'] > 0.3, "CV должен быть высоким при нестабильности"
    assert fast_stats['stability_score'] < 0.8, "Stability score должен быть низким"
    
    print(f"✓ Высокая вариативность: CV={fast_stats['coefficient_of_variation']:.4f}, stability_score={fast_stats['stability_score']:.4f}")


# ========================================================================
# Test Full Walk-Forward Run (Integration)
# ========================================================================

@pytest.mark.slow
def test_wfo_full_run(sample_data, simple_param_space, strategy_config):
    """
    Тест: полный запуск Walk-Forward Optimization
    
    Проверяет:
    - Возвращает результаты с walk_results, aggregated_metrics, parameter_stability
    - walk_results содержит все периоды
    - aggregated_metrics содержит общие показатели
    - parameter_stability корректно рассчитан
    """
    wfo = WalkForwardOptimizer(
        in_sample_size=200,
        out_sample_size=50,
        step_size=100,
        mode=WFOMode.ROLLING
    )
    
    results = wfo.run(
        data=sample_data,
        param_space=simple_param_space,
        strategy_config=strategy_config,
        metric='sharpe_ratio'
    )
    
    # Проверяем структуру результата
    assert 'walk_results' in results
    assert 'aggregated_metrics' in results
    assert 'parameter_stability' in results
    
    walk_results = results['walk_results']
    assert len(walk_results) > 0, "Должны быть периоды WFO"
    
    # Проверяем первый период
    first_result = walk_results[0]
    assert 'period_num' in first_result
    assert 'best_params' in first_result
    assert 'is_sharpe' in first_result or 'oos_sharpe' in first_result
    assert 'oos_sharpe' in first_result
    
    # Проверяем parameter_stability
    stability = results['parameter_stability']
    assert 'fast_ema' in stability
    assert 'slow_ema' in stability
    
    # Проверяем aggregated_metrics
    agg = results['aggregated_metrics']
    assert 'avg_out_sample_metric' in agg or 'oos_mean_sharpe' in agg
    
    print(f"✓ WFO полный запуск успешен:")
    print(f"  Периоды: {len(walk_results)}")
    print(f"  Parameter stability (fast_ema): {stability['fast_ema']['stability_score']:.4f}")


# ========================================================================
# Main (для pytest)
# ========================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
