"""
Простой тест buy_hold_return в BacktestEngine
Проверяет, что buy_hold_return_usdt и buy_hold_return_pct присутствуют в результатах
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Добавить backend в путь
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from core.backtest_engine import BacktestEngine


def test_buy_hold_return_exists():
    """Тест: buy_hold_return должен быть в metrics"""
    
    # Простые данные: 100 свечей, рост от 100 до 110 (+10%)
    timestamps = pd.date_range('2025-01-01', periods=100, freq='1h')
    close_prices = np.linspace(100, 110, 100)
    
    data = pd.DataFrame({
        'timestamp': timestamps,
        'open': close_prices - 0.1,
        'high': close_prices + 0.2,
        'low': close_prices - 0.2,
        'close': close_prices,
        'volume': 1000.0,
    })
    
    # Простая стратегия
    engine = BacktestEngine(initial_capital=10000.0)
    strategy_config = {
        'name': 'Test',
        'entry': {'type': 'ema_cross', 'fast_period': 5, 'slow_period': 10},
        'exit': {
            'take_profit': {'enabled': True, 'percent': 5.0},
            'stop_loss': {'enabled': True, 'percent': 2.0},
            'trailing_stop': {'enabled': False},
        },
    }
    
    results = engine.run(data, strategy_config)
    
    # Проверки
    assert 'metrics' in results, "metrics должен быть в результатах"
    
    metrics = results['metrics']
    assert 'buy_hold_return' in metrics, "buy_hold_return должен быть в metrics"
    assert 'buy_hold_return_pct' in metrics, "buy_hold_return_pct должен быть в metrics"
    
    # Проверка расчета: цена выросла от 100 до 110 (+10%)
    buy_hold_pct = metrics['buy_hold_return_pct']
    buy_hold_usdt = metrics['buy_hold_return']
    
    print(f"✓ buy_hold_return_pct: {buy_hold_pct:.2f}%")
    print(f"✓ buy_hold_return_usdt: ${buy_hold_usdt:.2f}")
    
    # Buy & Hold должен быть примерно +10%
    assert abs(buy_hold_pct - 10.0) < 0.1, f"Expected ~10%, got {buy_hold_pct:.2f}%"
    
    # Buy & Hold в USDT должен быть примерно 1000 (10% от 10000)
    expected_usdt = (buy_hold_pct / 100.0) * 10000.0
    assert abs(buy_hold_usdt - expected_usdt) < 1.0, \
        f"Expected ~{expected_usdt:.2f}, got {buy_hold_usdt:.2f}"
    
    print(f"✓ Формула корректна: {buy_hold_pct}% * 10000 / 100 = ${buy_hold_usdt:.2f}")
    print("✓ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
    
    return True


if __name__ == "__main__":
    try:
        test_buy_hold_return_exists()
        print("\n✅ ТЕСТ УСПЕШНО ПРОЙДЕН")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ ТЕСТ ПРОВАЛЕН: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
