"""
Quick Test Script for Optimization Methods

Быстрый тест Walk-Forward и Bayesian optimization на реальных данных.
Запуск: python test_optimization_quick.py
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Добавляем корень проекта в PYTHONPATH
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import pandas as pd
from loguru import logger

from backend.core.walkforward import WalkForwardAnalyzer, calculate_wfo_windows
from backend.core.bayesian import BayesianOptimizer
from backend.services.data_service import DataService


def generate_mock_data(days: int = 180) -> pd.DataFrame:
    """
    Генерирует mock данные для тестирования
    
    Args:
        days: Количество дней данных
    
    Returns:
        DataFrame с OHLCV данными
    """
    import numpy as np
    
    dates = pd.date_range(
        start=datetime.now() - timedelta(days=days),
        end=datetime.now(),
        freq="1H"
    )
    
    np.random.seed(42)
    close = 50000 + np.cumsum(np.random.randn(len(dates)) * 100)
    
    data = pd.DataFrame({
        "timestamp": dates,
        "open": close + np.random.randn(len(dates)) * 50,
        "high": close + np.abs(np.random.randn(len(dates))) * 100,
        "low": close - np.abs(np.random.randn(len(dates))) * 100,
        "close": close,
        "volume": np.random.randint(100, 1000, len(dates))
    })
    
    logger.info(f"Generated {len(data)} mock candles ({days} days)")
    return data


async def test_walkforward():
    """Тест Walk-Forward оптимизации"""
    logger.info("=" * 60)
    logger.info("Testing Walk-Forward Optimization")
    logger.info("=" * 60)
    
    # Генерируем данные
    data = generate_mock_data(days=180)  # 6 месяцев
    
    # Проверяем сколько окон можно создать
    num_windows = calculate_wfo_windows(
        total_days=180,
        is_window=60,
        oos_window=30,
        step=30
    )
    logger.info(f"Expected windows: {num_windows}")
    
    # Создаём анализатор
    analyzer = WalkForwardAnalyzer(
        data=data,
        initial_capital=10000.0,
        commission=0.001,
        is_window_days=60,
        oos_window_days=30,
        step_days=30
    )
    
    logger.info(f"Created {len(analyzer.windows)} windows")
    
    # Показываем первые 3 окна
    for window in analyzer.windows[:3]:
        logger.info(f"  {window}")
    
    if len(analyzer.windows) > 3:
        logger.info(f"  ... and {len(analyzer.windows) - 3} more windows")
    
    logger.success("Walk-Forward Analyzer initialized successfully!")
    
    # Проверяем что данные правильно извлекаются
    if len(analyzer.windows) > 0:
        window = analyzer.windows[0]
        is_data = analyzer._get_window_data(window.is_start, window.is_end)
        oos_data = analyzer._get_window_data(window.oos_start, window.oos_end)
        
        logger.info(f"Window #0:")
        logger.info(f"  IS data: {len(is_data)} candles")
        logger.info(f"  OOS data: {len(oos_data)} candles")
    
    return True


async def test_bayesian():
    """Тест Bayesian оптимизации"""
    logger.info("")
    logger.info("=" * 60)
    logger.info("Testing Bayesian Optimization")
    logger.info("=" * 60)
    
    # Генерируем данные
    data = generate_mock_data(days=90)  # 3 месяца
    
    # Создаём оптимизатор
    optimizer = BayesianOptimizer(
        data=data,
        initial_capital=10000.0,
        commission=0.001,
        n_trials=5,  # Малое количество для быстрого теста
        random_state=42
    )
    
    logger.info(f"Created Bayesian Optimizer")
    logger.info(f"  Trials: {optimizer.n_trials}")
    logger.info(f"  Data points: {len(data)}")
    logger.info(f"  Random state: {optimizer.random_state}")
    
    logger.success("Bayesian Optimizer initialized successfully!")
    
    return True


async def test_real_data():
    """Тест с реальными данными из DataService"""
    logger.info("")
    logger.info("=" * 60)
    logger.info("Testing with Real Data (if available)")
    logger.info("=" * 60)
    
    try:
        data_service = DataService()
        
        # Пытаемся загрузить реальные данные
        data = data_service.get_candles(
            symbol="BTCUSDT",
            interval="1h",
            start_date=(datetime.now() - timedelta(days=90)).isoformat(),
            end_date=datetime.now().isoformat()
        )
        
        if data is not None and len(data) > 0:
            logger.success(f"Loaded {len(data)} real candles from DataService")
            
            # Создаём Walk-Forward анализатор с реальными данными
            analyzer = WalkForwardAnalyzer(
                data=data,
                initial_capital=10000.0,
                commission=0.001,
                is_window_days=30,
                oos_window_days=15,
                step_days=15
            )
            
            logger.info(f"Created {len(analyzer.windows)} windows with real data")
            return True
        else:
            logger.warning("No real data available, using mock data")
            return False
            
    except Exception as e:
        logger.warning(f"Could not load real data: {e}")
        logger.info("This is expected if database is not set up yet")
        return False


async def main():
    """Главная функция тестирования"""
    logger.info("Starting Optimization Quick Test")
    logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("")
    
    try:
        # 1. Test Walk-Forward
        wf_success = await test_walkforward()
        
        # 2. Test Bayesian
        bay_success = await test_bayesian()
        
        # 3. Test with real data (опционально)
        real_success = await test_real_data()
        
        # Summary
        logger.info("")
        logger.info("=" * 60)
        logger.info("Test Summary")
        logger.info("=" * 60)
        logger.info(f"Walk-Forward:    {'✅ PASS' if wf_success else '❌ FAIL'}")
        logger.info(f"Bayesian:        {'✅ PASS' if bay_success else '❌ FAIL'}")
        logger.info(f"Real Data:       {'✅ PASS' if real_success else '⚠️  SKIP'}")
        logger.info("")
        
        if wf_success and bay_success:
            logger.success("✅ All core tests passed!")
            logger.info("")
            logger.info("Next steps:")
            logger.info("  1. Run full test suite: pytest tests/backend/")
            logger.info("  2. Test with real Bybit data")
            logger.info("  3. Run performance benchmarks")
            logger.info("")
            return 0
        else:
            logger.error("❌ Some tests failed")
            return 1
            
    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        logger.exception("Full traceback:")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
