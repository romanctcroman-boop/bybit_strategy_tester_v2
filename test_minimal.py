"""
Minimal Quick Test for Optimization Core Logic

Тестирует только core логику оптимизации без зависимостей от БД и API.
Запуск: python test_minimal.py
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Добавляем корень проекта в PYTHONPATH
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import pandas as pd
import numpy as np
from loguru import logger


def generate_mock_data(days: int = 180) -> pd.DataFrame:
    """Генерирует mock OHLCV данные с корректными OHLC значениями"""
    dates = pd.date_range(
        start=datetime.now() - timedelta(days=days),
        end=datetime.now(),
        freq="h"  # Changed from "1H" to "h" to avoid FutureWarning
    )
    
    np.random.seed(42)
    close = 50000 + np.cumsum(np.random.randn(len(dates)) * 100)
    open_prices = close + np.random.randn(len(dates)) * 50
    
    # Правильная генерация OHLC: high = max, low = min
    high_offset = np.abs(np.random.randn(len(dates))) * 100
    low_offset = np.abs(np.random.randn(len(dates))) * 100
    
    high = np.maximum(open_prices, close) + high_offset
    low = np.minimum(open_prices, close) - low_offset
    
    data = pd.DataFrame({
        "timestamp": dates,
        "open": open_prices,
        "high": high,
        "low": low,
        "close": close,
        "volume": np.random.randint(100, 1000, len(dates))
    })
    
    return data


def test_walk_forward_windows():
    """Тест создания Walk-Forward окон"""
    logger.info("=" * 60)
    logger.info("Test 1: Walk-Forward Window Creation")
    logger.info("=" * 60)
    
    try:
        from backend.core.walkforward import calculate_wfo_windows, WalkForwardWindow
        
        # Проверяем расчёт количества окон
        num_windows = calculate_wfo_windows(
            total_days=180,  # 6 месяцев
            is_window=60,    # 2 месяца тренировки
            oos_window=30,   # 1 месяц валидации
            step=30          # Шаг 1 месяц
        )
        
        logger.info(f"Calculated windows: {num_windows}")
        assert num_windows > 0, "Should calculate at least one window"
        
        # Проверяем создание окна
        window = WalkForwardWindow(
            window_id=0,
            is_start=datetime(2024, 1, 1),
            is_end=datetime(2024, 3, 1),
            oos_start=datetime(2024, 3, 1),
            oos_end=datetime(2024, 4, 1)
        )
        
        logger.info(f"Created window: {window}")
        assert window.window_id == 0, f"Expected window_id 0, got {window.window_id}"
        
        # Проверяем длительность окон
        is_days = (window.is_end - window.is_start).days
        oos_days = (window.oos_end - window.oos_start).days
        
        logger.info(f"IS days: {is_days}, OOS days: {oos_days}")
        assert is_days == 60, f"Expected 60 IS days, got {is_days}"
        assert oos_days == 31, f"Expected 31 OOS days, got {oos_days}"
        
        logger.success("✅ Walk-Forward windows test PASSED")
        return True
        
    except Exception as e:
        logger.error(f"❌ Walk-Forward windows test FAILED: {e}")
        logger.exception("Traceback:")
        return False


def test_bayesian_optimizer_init():
    """Тест инициализации Bayesian оптимизатора"""
    logger.info("")
    logger.info("=" * 60)
    logger.info("Test 2: Bayesian Optimizer Initialization")
    logger.info("=" * 60)
    
    try:
        from backend.core.bayesian import BayesianOptimizer
        
        # Генерируем данные
        data = generate_mock_data(days=90)
        logger.info(f"Generated {len(data)} candles")
        
        # Создаём оптимизатор
        optimizer = BayesianOptimizer(
            data=data,
            initial_capital=10000.0,
            commission=0.001,
            n_trials=10,
            random_state=42
        )
        
        logger.info(f"Created optimizer:")
        logger.info(f"  Trials: {optimizer.n_trials}")
        logger.info(f"  Data points: {len(optimizer.data)}")
        logger.info(f"  Random state: {optimizer.random_state}")
        
        assert optimizer.n_trials == 10
        assert len(optimizer.data) == len(data)
        assert optimizer.random_state == 42
        
        logger.success("✅ Bayesian optimizer init test PASSED")
        return True
        
    except Exception as e:
        logger.error(f"❌ Bayesian optimizer init test FAILED: {e}")
        logger.exception("Traceback:")
        return False


def test_mock_backtest():
    """Тест mock BacktestEngine"""
    logger.info("")
    logger.info("=" * 60)
    logger.info("Test 3: Mock BacktestEngine")
    logger.info("=" * 60)
    
    try:
        from backend.core.backtest import BacktestEngine
        
        # Генерируем данные
        data = generate_mock_data(days=30)
        logger.info(f"Generated {len(data)} candles")
        
        # Создаём engine
        engine = BacktestEngine(
            data=data,
            initial_capital=10000.0,
            commission=0.001
        )
        
        # Запускаем бэктест
        result = engine.run(
            strategy_name="MA_Crossover",
            strategy_params={"fast_period": 10, "slow_period": 20}
        )
        
        logger.info("Backtest result:")
        for key, value in result.items():
            logger.info(f"  {key}: {value}")
        
        # Проверяем что есть все нужные метрики
        required_metrics = ["total_return", "sharpe_ratio", "max_drawdown", "win_rate"]
        for metric in required_metrics:
            assert metric in result, f"Missing metric: {metric}"
        
        logger.success("✅ Mock BacktestEngine test PASSED")
        return True
        
    except Exception as e:
        logger.error(f"❌ Mock BacktestEngine test FAILED: {e}")
        logger.exception("Traceback:")
        return False


def test_data_validation():
    """Тест валидации OHLCV данных"""
    logger.info("")
    logger.info("=" * 60)
    logger.info("Test 4: Data Validation")
    logger.info("=" * 60)
    
    try:
        # Генерируем данные
        data = generate_mock_data(days=7)
        
        # Проверяем наличие всех колонок
        required_cols = ["timestamp", "open", "high", "low", "close", "volume"]
        for col in required_cols:
            assert col in data.columns, f"Missing column: {col}"
        
        logger.info(f"✓ All required columns present")
        
        # Проверяем что данные отсортированы по времени
        assert data["timestamp"].is_monotonic_increasing, "Timestamps not sorted"
        logger.info(f"✓ Timestamps sorted correctly")
        
        # Проверяем корректность OHLC
        invalid_ohlc = (
            (data["high"] < data["low"]) |
            (data["high"] < data["open"]) |
            (data["high"] < data["close"]) |
            (data["low"] > data["open"]) |
            (data["low"] > data["close"])
        ).sum()
        
        assert invalid_ohlc == 0, f"Found {invalid_ohlc} invalid OHLC rows"
        logger.info(f"✓ OHLC data valid")
        
        logger.info(f"Data shape: {data.shape}")
        logger.info(f"Date range: {data['timestamp'].min()} to {data['timestamp'].max()}")
        
        logger.success("✅ Data validation test PASSED")
        return True
        
    except Exception as e:
        logger.error(f"❌ Data validation test FAILED: {e}")
        logger.exception("Traceback:")
        return False


async def main():
    """Главная функция"""
    logger.info("Starting Minimal Optimization Tests")
    logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("")
    
    results = []
    
    # Запускаем тесты
    results.append(("Data Validation", test_data_validation()))
    results.append(("Walk-Forward Windows", test_walk_forward_windows()))
    results.append(("Bayesian Optimizer Init", test_bayesian_optimizer_init()))
    results.append(("Mock BacktestEngine", test_mock_backtest()))
    
    # Итоги
    logger.info("")
    logger.info("=" * 60)
    logger.info("Test Summary")
    logger.info("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status:12} {name}")
    
    logger.info("")
    logger.info(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        logger.success("🎉 All tests passed!")
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. Run full pytest suite: pytest tests/backend/")
        logger.info("  2. Test API endpoints")
        logger.info("  3. Test with real data")
        return 0
    else:
        logger.error(f"❌ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
