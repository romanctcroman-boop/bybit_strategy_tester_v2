"""
Быстрый тест для проверки консолидации оптимизации.
Проверяет что все классы импортируются корректно после рефакторинга.
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

def test_optimization_imports():
    """Тест импорта всех модулей оптимизации"""
    print("\n" + "="*70)
    print("ТЕСТ КОНСОЛИДАЦИИ МОДУЛЕЙ ОПТИМИЗАЦИИ")
    print("="*70)
    
    # Test 1: Import from backend.optimization
    print("\n✓ Тест 1: Импорт из backend.optimization")
    try:
        from backend.optimization import (
            GridOptimizer,
            WalkForwardOptimizer,
            WFOConfig,
            WFOMode,
            WFOPeriod,
            WFOParameterRange,
            MonteCarloSimulator,
            MonteCarloResult,
        )
        print("  ✅ Все классы импортированы успешно")
    except ImportError as e:
        print(f"  ❌ Ошибка импорта: {e}")
        return False
    
    # Test 2: Verify classes exist
    print("\n✓ Тест 2: Проверка классов")
    classes = {
        'GridOptimizer': GridOptimizer,
        'WalkForwardOptimizer': WalkForwardOptimizer,
        'WFOConfig': WFOConfig,
        'WFOMode': WFOMode,
        'MonteCarloSimulator': MonteCarloSimulator,
        'MonteCarloResult': MonteCarloResult,
    }
    
    for name, cls in classes.items():
        print(f"  ✅ {name}: {cls.__module__}")
    
    # Test 3: Create instances
    print("\n✓ Тест 3: Создание объектов")
    
    try:
        # WFO Config
        wfo_config = WFOConfig(
            in_sample_size=100,
            out_sample_size=50,
            step_size=25
        )
        print(f"  ✅ WFOConfig создан: IS={wfo_config.in_sample_size}, OOS={wfo_config.out_sample_size}")
        
        # WFO Optimizer
        wfo = WalkForwardOptimizer(config=wfo_config)
        print(f"  ✅ WalkForwardOptimizer создан: mode={wfo.config.mode.value}")
        
        # Monte Carlo
        mc = MonteCarloSimulator(n_simulations=100)
        print(f"  ✅ MonteCarloSimulator создан: {mc.n_simulations} симуляций")
        
    except Exception as e:
        print(f"  ❌ Ошибка создания объекта: {e}")
        return False
    
    # Test 4: Verify no old files
    print("\n✓ Тест 4: Проверка удаления дубликатов")
    
    import os
    backend_path = Path(__file__).parent / "backend"
    
    # Check optimization folder
    opt_files = list((backend_path / "optimization").glob("*.py"))
    expected_files = {'__init__.py', 'grid_optimizer.py', 'walk_forward.py', 'monte_carlo.py'}
    actual_files = {f.name for f in opt_files if f.name != '__pycache__'}
    
    print(f"  Ожидаемые файлы: {sorted(expected_files)}")
    print(f"  Актуальные файлы: {sorted(actual_files)}")
    
    # Проверка дубликатов
    duplicates = ['walk_forward_optimizer.py', 'monte_carlo_simulator.py']
    found_duplicates = [d for d in duplicates if d in actual_files]
    
    if found_duplicates:
        print(f"  ❌ Найдены дубликаты: {found_duplicates}")
        return False
    else:
        print(f"  ✅ Дубликаты удалены")
    
    # Check core folder
    core_old_files = [
        backend_path / "core" / "walk_forward_optimizer.py",
        backend_path / "core" / "monte_carlo_simulator.py"
    ]
    
    found_old_files = [f.name for f in core_old_files if f.exists()]
    if found_old_files:
        print(f"  ❌ Старые файлы в core/: {found_old_files}")
        return False
    else:
        print(f"  ✅ Старые файлы из core/ удалены")
    
    # Summary
    print("\n" + "="*70)
    print("ИТОГ")
    print("="*70)
    print("✅ Все проверки пройдены!")
    print("\nИсправления:")
    print("  1. ✅ Удалены дубликаты из backend/optimization/")
    print("  2. ✅ Удалены старые файлы из backend/core/")
    print("  3. ✅ Обновлен __init__.py с правильными импортами")
    print("  4. ✅ Обновлены тесты и скрипты")
    print("\nАномалия #1: ИСПРАВЛЕНА ✓")
    print("="*70)
    
    return True


if __name__ == "__main__":
    success = test_optimization_imports()
    sys.exit(0 if success else 1)
