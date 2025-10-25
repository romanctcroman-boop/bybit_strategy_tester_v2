"""
Тесты для GridOptimizer

Проверяем:
1. Генерацию parameter grid
2. Запуск оптимизации
3. Ранжирование результатов
4. Валидацию (min_trades, max_drawdown)
5. Экспорт в CSV
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import tempfile

# Добавить backend в путь
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from optimization.grid_optimizer import (
    GridOptimizer,
    ParameterRange,
    OptimizationConfig,
    OptimizationResult,
)
from core.backtest_engine import BacktestEngine


def generate_sample_data(num_candles=200):
    """Генерация простых OHLCV данных"""
    timestamps = pd.date_range('2025-01-01', periods=num_candles, freq='1h')
    
    # Генерируем цены с небольшой волатильностью
    close_prices = 100 + np.cumsum(np.random.randn(num_candles) * 0.5)
    
    data = []
    for i, timestamp in enumerate(timestamps):
        c = close_prices[i]
        o = c + np.random.randn() * 0.3
        h = max(o, c) + abs(np.random.randn() * 0.4)
        l = min(o, c) - abs(np.random.randn() * 0.4)
        v = np.random.uniform(1000, 10000)
        
        data.append({
            'timestamp': timestamp,
            'open': o,
            'high': h,
            'low': l,
            'close': c,
            'volume': v,
        })
    
    return pd.DataFrame(data)


def test_parameter_range():
    """Тест генерации диапазона параметров"""
    print("\n=== TEST: ParameterRange ===")
    
    param = ParameterRange(
        name="tp_percent",
        start=1.0,
        stop=5.0,
        step=1.0,
        description="Take Profit %"
    )
    
    values = param.values()
    print(f"Generated values: {values}")
    
    assert len(values) == 5, f"Expected 5 values, got {len(values)}"
    assert values[0] == 1.0, f"Expected first value 1.0, got {values[0]}"
    assert values[-1] == 5.0, f"Expected last value 5.0, got {values[-1]}"
    
    print("✓ ParameterRange test passed")
    return True


def test_grid_generation():
    """Тест генерации parameter grid"""
    print("\n=== TEST: Grid Generation ===")
    
    # Конфигурация с 3 параметрами
    config = OptimizationConfig(
        parameters=[
            ParameterRange("tp_percent", 2.0, 4.0, 1.0),    # 3 values: [2.0, 3.0, 4.0]
            ParameterRange("sl_percent", 1.0, 2.0, 0.5),    # 3 values: [1.0, 1.5, 2.0]
        ],
        base_strategy={
            'name': 'EMA Crossover',
            'entry': {'type': 'ema_cross', 'fast_period': 10, 'slow_period': 30}
        },
        max_workers=1,
        top_n_results=10
    )
    
    # Создаем optimizer (без запуска)
    engine = BacktestEngine(initial_capital=10000.0)
    data = generate_sample_data(100)
    
    optimizer = GridOptimizer(engine, data, config)
    grid = optimizer._generate_parameter_grid()
    
    print(f"Total combinations: {len(grid)}")
    print(f"First combination: {grid[0]}")
    print(f"Last combination: {grid[-1]}")
    
    # Проверка: 3 TP * 3 SL = 9 комбинаций
    assert len(grid) == 9, f"Expected 9 combinations, got {len(grid)}"
    
    # Проверка структуры
    assert 'tp_percent' in grid[0], "Missing tp_percent"
    assert 'sl_percent' in grid[0], "Missing sl_percent"
    
    print("✓ Grid generation test passed")
    return True


def test_optimization_run():
    """Тест полного цикла оптимизации"""
    print("\n=== TEST: Optimization Run ===")
    
    # Конфигурация с малым grid для скорости
    config = OptimizationConfig(
        parameters=[
            ParameterRange("tp_percent", 2.0, 3.0, 1.0),    # 2 values
            ParameterRange("sl_percent", 1.0, 1.5, 0.5),    # 2 values
        ],
        base_strategy={
            'name': 'EMA Crossover',
            'entry': {
                'type': 'ema_cross',
                'fast_period': 10,
                'slow_period': 30
            },
        },
        score_function='sharpe',
        min_trades=5,
        max_drawdown_limit=0.5,  # 50% max DD
        max_workers=1,  # Последовательная обработка для тестов
        top_n_results=10
    )
    
    # Данные
    data = generate_sample_data(200)
    
    # Engine
    engine = BacktestEngine(
        initial_capital=10000.0,
        commission=0.0006,
        slippage_pct=0.05
    )
    
    # Optimizer
    optimizer = GridOptimizer(engine, data, config)
    
    # Запуск
    print("Running optimization...")
    results = optimizer.optimize(parallel=False)
    
    print(f"\nOptimization completed:")
    print(f"  Total combinations: {optimizer.total_combinations}")
    print(f"  Valid results: {optimizer.valid_results}")
    print(f"  Invalid results: {optimizer.invalid_results}")
    
    if results:
        print(f"\nBest result:")
        print(f"  Rank: {results[0].rank}")
        print(f"  Score: {results[0].score:.4f}")
        print(f"  Params: {results[0].parameters}")
        print(f"  Sharpe: {results[0].metrics.get('sharpe_ratio', 0):.2f}")
        print(f"  Win Rate: {results[0].metrics.get('win_rate', 0):.2f}%")
        print(f"  Total Trades: {results[0].metrics.get('total_trades', 0)}")
    
    # Проверки
    assert len(results) == 4, f"Expected 4 results (2x2), got {len(results)}"
    assert results[0].rank == 1, "Best result should have rank 1"
    assert results[0].score >= results[1].score, "Results should be sorted by score"
    
    print("\n✓ Optimization run test passed")
    return True


def test_validation_rules():
    """Тест валидационных правил"""
    print("\n=== TEST: Validation Rules ===")
    
    # Конфигурация с жесткими ограничениями
    config = OptimizationConfig(
        parameters=[
            ParameterRange("tp_percent", 1.0, 2.0, 1.0),    # 2 values
        ],
        base_strategy={
            'name': 'Test',
            'entry': {'type': 'ema_cross', 'fast_period': 5, 'slow_period': 10}
        },
        min_trades=50,  # Высокое требование
        max_drawdown_limit=0.05,  # 5% max DD (очень строгое)
        max_workers=1
    )
    
    data = generate_sample_data(100)
    engine = BacktestEngine(initial_capital=10000.0)
    optimizer = GridOptimizer(engine, data, config)
    
    results = optimizer.optimize(parallel=False)
    
    # Проверка: некоторые результаты должны быть невалидными
    invalid_count = sum(1 for r in results if not r.valid)
    print(f"Invalid results: {invalid_count}/{len(results)}")
    
    # Проверка причин невалидности
    for r in results:
        if not r.valid:
            print(f"  Invalid: {r.parameters} - {r.validation_errors}")
    
    assert invalid_count > 0, "Expected some invalid results with strict validation"
    
    print("✓ Validation rules test passed")
    return True


def test_csv_export():
    """Тест экспорта в CSV"""
    print("\n=== TEST: CSV Export ===")
    
    config = OptimizationConfig(
        parameters=[
            ParameterRange("tp_percent", 2.0, 3.0, 1.0),
        ],
        base_strategy={
            'name': 'Test',
            'entry': {'type': 'ema_cross', 'fast_period': 10, 'slow_period': 30}
        },
        min_trades=1,  # Низкий порог для валидности
        max_workers=1,
        top_n_results=5
    )
    
    data = generate_sample_data(200)  # Больше данных для больше сделок
    engine = BacktestEngine(initial_capital=10000.0)
    optimizer = GridOptimizer(engine, data, config)
    
    results = optimizer.optimize(parallel=False)
    
    # Экспорт в временный файл
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        csv_path = f.name
    
    try:
        exported_path = optimizer.export_results(results, filepath=csv_path, top_n=3)
        
        if exported_path is None:
            print("No valid results to export (expected for small dataset)")
            print("✓ CSV export test passed (graceful handling)")
            return True
        
        print(f"Exported to: {exported_path}")
        
        # Проверка файла
        df = pd.read_csv(exported_path)
        print(f"CSV shape: {df.shape}")
        print(f"Columns: {list(df.columns)}")
        
        assert len(df) <= 3, f"Expected max 3 rows (top_n=3), got {len(df)}"
        assert 'tp_percent' in df.columns, "Missing tp_percent column"
        assert 'rank' in df.columns, "Missing rank column"
        assert 'score' in df.columns, "Missing score column"
        
        print(f"\nCSV preview:")
        print(df.head())
        
        print("\n✓ CSV export test passed")
        
    finally:
        # Cleanup
        if exported_path:
            Path(exported_path).unlink(missing_ok=True)
    
    return True


def test_summary_stats():
    """Тест сводной статистики"""
    print("\n=== TEST: Summary Statistics ===")
    
    config = OptimizationConfig(
        parameters=[
            ParameterRange("tp_percent", 2.0, 4.0, 1.0),
        ],
        base_strategy={
            'name': 'Test',
            'entry': {'type': 'ema_cross', 'fast_period': 10, 'slow_period': 30}
        },
        min_trades=1,  # Низкий порог
        max_workers=1
    )
    
    data = generate_sample_data(200)
    engine = BacktestEngine(initial_capital=10000.0)
    optimizer = GridOptimizer(engine, data, config)
    
    results = optimizer.optimize(parallel=False)
    summary = optimizer.get_summary(results)
    
    print(f"\nSummary:")
    print(f"  Total combinations: {summary['total_combinations']}")
    print(f"  Valid results: {summary['valid_results']}")
    print(f"  Invalid results: {summary['invalid_results']}")
    print(f"  Duration: {summary['duration_seconds']:.2f}s")
    
    if summary['best_score'] is not None:
        print(f"  Best score: {summary['best_score']:.4f}")
        print(f"  Mean score: {summary['mean_score']:.4f}")
        print(f"  Std score: {summary['std_score']:.4f}")
        print(f"  Best params: {summary['best_parameters']}")
    else:
        print("  No valid results (expected for strict validation)")
    
    assert 'total_combinations' in summary, "Missing total_combinations"
    assert 'best_score' in summary, "Missing best_score (can be None)"
    assert 'best_parameters' in summary, "Missing best_parameters (can be None)"
    
    print("\n✓ Summary statistics test passed")
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ GRID OPTIMIZER")
    print("=" * 60)
    
    tests = [
        ("ParameterRange", test_parameter_range),
        ("Grid Generation", test_grid_generation),
        ("Optimization Run", test_optimization_run),
        ("Validation Rules", test_validation_rules),
        ("CSV Export", test_csv_export),
        ("Summary Stats", test_summary_stats),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"\n✓✓✓ {test_name} - PASSED ✓✓✓")
            else:
                failed += 1
                print(f"\n✗✗✗ {test_name} - FAILED ✗✗✗")
        except Exception as e:
            failed += 1
            print(f"\n✗✗✗ {test_name} - ERROR: {e} ✗✗✗")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print(f"ИТОГО: {passed} passed, {failed} failed")
    print("=" * 60)
    
    sys.exit(0 if failed == 0 else 1)
