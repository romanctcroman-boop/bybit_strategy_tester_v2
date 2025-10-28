"""
Integration тесты для Walk-Forward Optimization (end-to-end)

Проверяет полный цикл оптимизации:
1. Загрузка данных
2. Разделение на In-Sample / Out-of-Sample периоды
3. Оптимизация параметров на IS
4. Валидация на OOS
5. Расчёт parameter_stability (ТЗ 3.5.2)
6. Агрегация результатов

Использует реальные компоненты:
- DataManager для загрузки данных
- WalkForwardOptimizer для оптимизации
- BacktestEngine для тестирования стратегий

Создано: 25 октября 2025 (Фаза 1, Задача 9)
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import sys
import shutil

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from optimization.walk_forward import WalkForwardOptimizer, WFOMode
from services.data_manager import DataManager
from core.backtest_engine import BacktestEngine


# ========================================================================
# Test Data Generation
# ========================================================================

def generate_realistic_klines(n_bars: int = 2000, trend: str = 'sideways') -> pd.DataFrame:
    """
    Генерирует реалистичные OHLCV данные для тестирования
    
    Args:
        n_bars: Количество баров
        trend: 'up', 'down', 'sideways'
    
    Returns:
        DataFrame с OHLCV данными
    """
    np.random.seed(42)
    
    timestamps = pd.date_range(
        start=datetime.now() - timedelta(hours=n_bars),
        periods=n_bars,
        freq='1h'
    )
    
    base_price = 50000.0
    
    # Тренд
    if trend == 'up':
        drift = np.linspace(0, 0.2, n_bars)  # +20% за период
    elif trend == 'down':
        drift = np.linspace(0, -0.15, n_bars)  # -15% за период
    else:  # sideways
        drift = np.sin(np.linspace(0, 4 * np.pi, n_bars)) * 0.05
    
    # Random walk с трендом
    returns = np.random.normal(0, 0.01, n_bars) + drift / n_bars
    close_prices = base_price * (1 + returns).cumprod()
    
    # OHLC
    high_prices = close_prices * (1 + np.abs(np.random.normal(0, 0.005, n_bars)))
    low_prices = close_prices * (1 - np.abs(np.random.normal(0, 0.005, n_bars)))
    open_prices = np.roll(close_prices, 1)
    open_prices[0] = close_prices[0]
    
    df = pd.DataFrame({
        'timestamp': timestamps,
        'open': open_prices,
        'high': high_prices,
        'low': low_prices,
        'close': close_prices,
        'volume': np.random.uniform(100, 1000, n_bars)
    })
    
    return df


# ========================================================================
# Test Fixtures
# ========================================================================

@pytest.fixture
def temp_cache_dir(tmp_path):
    """Fixture: временная директория для кэша"""
    cache_dir = tmp_path / "wfo_cache"
    cache_dir.mkdir(exist_ok=True)
    yield cache_dir
    # Cleanup
    if cache_dir.exists():
        shutil.rmtree(cache_dir)


@pytest.fixture
def realistic_data():
    """Fixture: реалистичные данные для WFO (2000 баров)"""
    return generate_realistic_klines(n_bars=2000, trend='sideways')


@pytest.fixture
def simple_param_space():
    """Fixture: простое пространство параметров для оптимизации"""
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
# Test Full WFO Cycle (End-to-End)
# ========================================================================

@pytest.mark.integration
def test_wfo_full_cycle_rolling(realistic_data, simple_param_space, strategy_config):
    """
    Integration Test: полный цикл WFO в ROLLING режиме
    
    Workflow:
    1. Создаём WalkForwardOptimizer (ROLLING, IS=400, OOS=100, step=100)
    2. Запускаем оптимизацию на realistic_data
    3. Проверяем результаты:
       - walk_results содержит периоды
       - Каждый период имеет best_params, IS/OOS метрики
       - parameter_stability рассчитан корректно
       - aggregated_metrics присутствуют
    """
    wfo = WalkForwardOptimizer(
        in_sample_size=400,
        out_sample_size=100,
        step_size=100,
        mode=WFOMode.ROLLING
    )
    
    results = wfo.run(
        data=realistic_data,
        param_space=simple_param_space,
        strategy_config=strategy_config,
        metric='sharpe_ratio'
    )
    
    # 1. Проверяем структуру результата
    assert 'walk_results' in results
    assert 'aggregated_metrics' in results
    assert 'parameter_stability' in results
    assert 'num_walks' in results
    
    walk_results = results['walk_results']
    
    # 2. Проверяем, что есть периоды
    assert len(walk_results) > 0, "WFO должен создать хотя бы 1 период"
    print(f"\n✓ WFO создал {len(walk_results)} периодов")
    
    # 3. Проверяем каждый период
    for i, period in enumerate(walk_results):
        assert 'period_num' in period  # Не period_index, а period_num
        assert 'best_params' in period
        assert 'is_sharpe' in period  # In-sample метрика
        assert 'oos_sharpe' in period  # Out-of-sample метрика
        
        # best_params должен содержать оптимизируемые параметры
        best_params = period['best_params']
        assert 'fast_ema' in best_params
        assert 'slow_ema' in best_params
        
        # Параметры должны быть из param_space
        assert best_params['fast_ema'] in simple_param_space['fast_ema']
        assert best_params['slow_ema'] in simple_param_space['slow_ema']
    
    print(f"✓ Все {len(walk_results)} периодов имеют корректную структуру")
    
    # 4. Проверяем parameter_stability (ТЗ 3.5.2)
    stability = results['parameter_stability']
    
    assert 'fast_ema' in stability
    assert 'slow_ema' in stability
    
    for param_name, stats in stability.items():
        assert 'mean' in stats
        assert 'std' in stats
        assert 'coefficient_of_variation' in stats
        assert 'stability_score' in stats
        
        # stability_score должен быть в диапазоне [0, 1]
        assert 0 <= stats['stability_score'] <= 1
    
    print(f"✓ Parameter stability рассчитан:")
    print(f"  fast_ema: CV={stability['fast_ema']['coefficient_of_variation']:.4f}, stability={stability['fast_ema']['stability_score']:.4f}")
    print(f"  slow_ema: CV={stability['slow_ema']['coefficient_of_variation']:.4f}, stability={stability['slow_ema']['stability_score']:.4f}")
    
    # 5. Проверяем aggregated_metrics
    agg = results['aggregated_metrics']
    
    # Должны присутствовать ключевые метрики
    assert 'num_walks' in agg
    assert agg['num_walks'] == len(walk_results)
    
    print(f"✓ Aggregated metrics:")
    print(f"  num_walks: {agg['num_walks']}")


@pytest.mark.integration
def test_wfo_full_cycle_anchored(realistic_data, simple_param_space, strategy_config):
    """
    Integration Test: полный цикл WFO в ANCHORED режиме
    
    В ANCHORED режиме:
    - In-sample начало фиксировано (0)
    - In-sample конец растёт с каждым шагом
    - Out-sample двигается вперёд
    """
    wfo = WalkForwardOptimizer(
        in_sample_size=400,
        out_sample_size=100,
        step_size=100,
        mode=WFOMode.ANCHORED
    )
    
    results = wfo.run(
        data=realistic_data,
        param_space=simple_param_space,
        strategy_config=strategy_config,
        metric='sharpe_ratio'
    )
    
    walk_results = results['walk_results']
    
    assert len(walk_results) > 0
    
    # В ANCHORED режиме in-sample растёт
    # Проверяем, что периоды создаются корректно
    for period in walk_results:
        assert 'best_params' in period
        assert 'is_sharpe' in period
        assert 'oos_sharpe' in period
    
    print(f"\n✓ ANCHORED режим: {len(walk_results)} периодов создано")


# ========================================================================
# Test WFO with DataManager Integration
# ========================================================================

@pytest.mark.integration
def test_wfo_with_data_manager(temp_cache_dir, realistic_data, simple_param_space, strategy_config):
    """
    Integration Test: WFO + DataManager
    
    Workflow:
    1. Сохраняем данные через DataManager
    2. Загружаем через DataManager
    3. Запускаем WFO на загруженных данных
    4. Проверяем, что всё работает end-to-end
    """
    # 1. Сохраняем данные через DataManager
    dm = DataManager(
        symbol='BTCUSDT',
        timeframe='15',
        cache_dir=str(temp_cache_dir)
    )
    
    dm.update_cache(realistic_data)
    
    # 2. Загружаем данные
    loaded_data = dm.load_historical(limit=2000)
    
    assert len(loaded_data) > 0
    print(f"\n✓ DataManager загрузил {len(loaded_data)} bars из кэша")
    
    # 3. Запускаем WFO
    wfo = WalkForwardOptimizer(
        in_sample_size=400,
        out_sample_size=100,
        step_size=100,
        mode=WFOMode.ROLLING
    )
    
    results = wfo.run(
        data=loaded_data,
        param_space=simple_param_space,
        strategy_config=strategy_config,
        metric='sharpe_ratio'
    )
    
    # 4. Проверяем результаты
    assert 'walk_results' in results
    assert len(results['walk_results']) > 0
    
    print(f"✓ WFO успешно обработал данные из DataManager: {len(results['walk_results'])} периодов")


# ========================================================================
# Test WFO Parameter Stability Accuracy
# ========================================================================

@pytest.mark.integration
def test_wfo_parameter_stability_stable_params(realistic_data, strategy_config):
    """
    Integration Test: parameter_stability при стабильных параметрах
    
    Если оптимизация находит одни и те же параметры на каждом периоде,
    stability_score должен быть близок к 1.0
    """
    # Узкое пространство параметров (1 комбинация)
    narrow_param_space = {
        'fast_ema': [20],
        'slow_ema': [50]
    }
    
    wfo = WalkForwardOptimizer(
        in_sample_size=400,
        out_sample_size=100,
        step_size=100,
        mode=WFOMode.ROLLING
    )
    
    results = wfo.run(
        data=realistic_data,
        param_space=narrow_param_space,
        strategy_config=strategy_config,
        metric='sharpe_ratio'
    )
    
    stability = results['parameter_stability']
    
    # С единственной комбинацией параметров stability_score = 1.0
    assert stability['fast_ema']['stability_score'] == pytest.approx(1.0, abs=0.01)
    assert stability['slow_ema']['stability_score'] == pytest.approx(1.0, abs=0.01)
    
    print(f"\n✓ Стабильные параметры: stability_score = 1.0")


@pytest.mark.integration
def test_wfo_parameter_stability_variable_params(realistic_data, strategy_config):
    """
    Integration Test: parameter_stability при вариативных параметрах
    
    Широкое пространство параметров должно дать более низкий stability_score
    """
    # Широкое пространство параметров
    wide_param_space = {
        'fast_ema': [5, 10, 15, 20, 25, 30],
        'slow_ema': [40, 50, 60, 80, 100, 120]
    }
    
    wfo = WalkForwardOptimizer(
        in_sample_size=400,
        out_sample_size=100,
        step_size=100,
        mode=WFOMode.ROLLING
    )
    
    results = wfo.run(
        data=realistic_data,
        param_space=wide_param_space,
        strategy_config=strategy_config,
        metric='sharpe_ratio'
    )
    
    stability = results['parameter_stability']
    
    # Широкое пространство может дать разные параметры на разных периодах
    # stability_score может быть ниже (но всё равно >= 0)
    assert 0 <= stability['fast_ema']['stability_score'] <= 1.0
    assert 0 <= stability['slow_ema']['stability_score'] <= 1.0
    
    print(f"\n✓ Вариативные параметры:")
    print(f"  fast_ema stability: {stability['fast_ema']['stability_score']:.4f}")
    print(f"  slow_ema stability: {stability['slow_ema']['stability_score']:.4f}")


# ========================================================================
# Test WFO In-Sample vs Out-of-Sample Performance
# ========================================================================

@pytest.mark.integration
def test_wfo_in_sample_vs_out_sample(realistic_data, simple_param_space, strategy_config):
    """
    Integration Test: сравнение IS и OOS метрик
    
    Проверяет:
    - IS метрики присутствуют для каждого периода
    - OOS метрики присутствуют для каждого периода
    - IS метрики обычно >= OOS метрики (нормально для оптимизации)
    """
    wfo = WalkForwardOptimizer(
        in_sample_size=400,
        out_sample_size=100,
        step_size=100,
        mode=WFOMode.ROLLING
    )
    
    results = wfo.run(
        data=realistic_data,
        param_space=simple_param_space,
        strategy_config=strategy_config,
        metric='sharpe_ratio'
    )
    
    walk_results = results['walk_results']
    
    is_metrics = []
    oos_metrics = []
    
    for period in walk_results:
        is_metric = period['is_sharpe']  # In-sample Sharpe
        oos_metric = period['oos_sharpe']  # Out-of-sample Sharpe
        
        is_metrics.append(is_metric)
        oos_metrics.append(oos_metric)
    
    avg_is = np.mean(is_metrics)
    avg_oos = np.mean(oos_metrics)
    
    print(f"\n✓ IS vs OOS метрики:")
    print(f"  Avg IS Sharpe: {avg_is:.4f}")
    print(f"  Avg OOS Sharpe: {avg_oos:.4f}")
    print(f"  IS/OOS ratio: {avg_is / avg_oos if avg_oos != 0 else 'N/A'}")
    
    # IS обычно >= OOS (параметры оптимизированы на IS)
    # Но это не строгое правило (может быть OOS > IS)


# ========================================================================
# Test WFO with Different Metrics
# ========================================================================

@pytest.mark.integration
def test_wfo_with_different_metrics(realistic_data, simple_param_space, strategy_config):
    """
    Integration Test: WFO с разными метриками оптимизации
    
    Проверяет, что WFO работает с:
    - sharpe_ratio
    - total_return
    - profit_factor
    """
    metrics_to_test = ['sharpe_ratio', 'total_return', 'profit_factor']
    
    for metric in metrics_to_test:
        wfo = WalkForwardOptimizer(
            in_sample_size=400,
            out_sample_size=100,
            step_size=200,  # Меньше периодов для скорости
            mode=WFOMode.ROLLING
        )
        
        results = wfo.run(
            data=realistic_data,
            param_space=simple_param_space,
            strategy_config=strategy_config,
            metric=metric
        )
        
        assert 'walk_results' in results
        assert len(results['walk_results']) > 0
        
        print(f"✓ Метрика '{metric}': {len(results['walk_results'])} периодов")


# ========================================================================
# Test WFO Edge Cases
# ========================================================================

@pytest.mark.integration
def test_wfo_insufficient_data():
    """
    Integration Test: WFO с недостаточными данными
    
    Если данных меньше, чем in_sample_size + out_sample_size,
    WFO должен вернуть пустой результат или 0 периодов
    """
    small_data = generate_realistic_klines(n_bars=100)  # Только 100 баров
    
    wfo = WalkForwardOptimizer(
        in_sample_size=400,  # Требуется 400 баров
        out_sample_size=100,
        step_size=100,
        mode=WFOMode.ROLLING
    )
    
    param_space = {'fast_ema': [20], 'slow_ema': [50]}
    config = {
        'type': 'ema_crossover',
        'direction': 'long',
        'take_profit_pct': 3.0,
        'stop_loss_pct': 2.0
    }
    
    results = wfo.run(
        data=small_data,
        param_space=param_space,
        strategy_config=config,
        metric='sharpe_ratio'
    )
    
    # Должно быть 0 периодов (недостаточно данных)
    assert len(results['walk_results']) == 0
    
    print(f"\n✓ Недостаточно данных: 0 периодов (ожидается)")


# ========================================================================
# Main (для pytest)
# ========================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "-m", "integration"])
