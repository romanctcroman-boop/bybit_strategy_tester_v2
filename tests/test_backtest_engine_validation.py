"""
Интеграционный тест: BacktestEngine + Pydantic валидация
Проверяет, что движок бэктестирования корректно валидирует результаты
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Добавить backend в путь
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from core.backtest_engine import BacktestEngine


def generate_sample_ohlcv(num_candles=100):
    """Генерация простых OHLCV данных для тестирования"""
    timestamps = pd.date_range('2025-01-01', periods=num_candles, freq='15min')
    
    # Генерируем случайные цены с трендом вверх
    close_prices = 100 + np.cumsum(np.random.randn(num_candles) * 0.5)
    
    data = []
    for i, timestamp in enumerate(timestamps):
        c = close_prices[i]
        o = c + np.random.randn() * 0.2
        h = max(o, c) + abs(np.random.randn() * 0.3)
        l = min(o, c) - abs(np.random.randn() * 0.3)
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


def test_backtest_engine_validation():
    """Тест полного цикла: OHLCV → BacktestEngine → Pydantic валидация"""
    print("\n=== ИНТЕГРАЦИОННЫЙ ТЕСТ: BacktestEngine + Pydantic ===\n")
    
    # 1. Генерируем данные
    print("1. Генерация OHLCV данных...")
    df = generate_sample_ohlcv(500)
    print(f"   ✓ Создано {len(df)} свечей от {df['timestamp'].min()} до {df['timestamp'].max()}")
    
    # 2. Создаем BacktestEngine
    print("\n2. Инициализация BacktestEngine...")
    engine = BacktestEngine(
        initial_capital=10000.0,
        commission=0.0006,
        slippage_pct=0.05,
        leverage=1,
        order_size_usd=1000.0,
    )
    print("   ✓ BacktestEngine создан")
    
    # 3. Конфигурация простой EMA crossover стратегии
    print("\n3. Создание конфигурации стратегии...")
    strategy_config = {
        'name': 'EMA Crossover',
        'entry': {
            'type': 'ema_cross',
            'fast_period': 10,
            'slow_period': 30,
        },
        'exit': {
            'take_profit': {
                'enabled': True,
                'percent': 2.0,  # 2% TP
            },
            'stop_loss': {
                'enabled': True,
                'percent': 1.0,  # 1% SL
            },
            'trailing_stop': {
                'enabled': False,
            },
        },
    }
    print("   ✓ Стратегия EMA(10/30) с TP=2%, SL=1%")
    
    # 4. Запуск бэктеста
    print("\n4. Запуск бэктеста...")
    try:
        results = engine.run(df, strategy_config)
        print("   ✓ Бэктест завершен успешно")
    except Exception as e:
        print(f"   ✗ ОШИБКА при выполнении бэктеста: {e}")
        return False
    
    # 5. Проверка структуры результатов
    print("\n5. Валидация структуры результатов...")
    
    required_fields = [
        'final_capital', 'total_return', 'total_trades',
        'winning_trades', 'losing_trades', 'win_rate',
        'sharpe_ratio', 'sortino_ratio', 'max_drawdown',
        'profit_factor', 'metrics', 'trades', 'equity_curve'
    ]
    
    missing_fields = [f for f in required_fields if f not in results]
    if missing_fields:
        print(f"   ✗ Отсутствуют поля: {missing_fields}")
        return False
    
    print("   ✓ Все обязательные поля присутствуют")
    
    # 6. Проверка метрик
    print("\n6. Проверка метрик...")
    print(f"   Final Capital: ${results['final_capital']:.2f}")
    print(f"   Total Return: {results['total_return']*100:.2f}%")
    print(f"   Total Trades: {results['total_trades']}")
    print(f"   Win Rate: {results['win_rate']:.2f}%")
    print(f"   Sharpe Ratio: {results['sharpe_ratio']:.3f}")
    print(f"   Max Drawdown: {results['max_drawdown']*100:.2f}%")
    
    # 7. Проверка наличия buy_hold_return
    print("\n7. Проверка buy_hold_return...")
    metrics = results.get('metrics', {})
    
    if 'buy_hold_return' not in metrics:
        print("   ✗ ОШИБКА: buy_hold_return отсутствует в metrics!")
        return False
    
    if 'buy_hold_return_pct' not in metrics:
        print("   ✗ ОШИБКА: buy_hold_return_pct отсутствует в metrics!")
        return False
    
    print(f"   ✓ buy_hold_return: ${metrics['buy_hold_return']:.2f}")
    print(f"   ✓ buy_hold_return_pct: {metrics['buy_hold_return_pct']:.2f}%")
    
    # 8. Проверка Pydantic валидации (автоматически в BacktestEngine)
    print("\n8. Проверка Pydantic валидации...")
    
    # Импорт напрямую из модуля, чтобы избежать конфликта с SQLAlchemy
    import sys
    from pathlib import Path
    data_types_path = Path(__file__).parent.parent / "backend" / "models"
    
    try:
        # Прямой импорт модуля data_types
        import importlib.util
        spec = importlib.util.spec_from_file_location("data_types", data_types_path / "data_types.py")
        data_types_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(data_types_module)
        
        BacktestResults = data_types_module.BacktestResults
        
        validated = BacktestResults(**results)
        print(f"   ✓ Ручная валидация прошла успешно")
        print(f"   ✓ Validated trades: {validated.total_trades}")
        print(f"   ✓ Validated win rate: {validated.win_rate:.2f}%")
    except Exception as e:
        print(f"   ✗ ОШИБКА валидации: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 9. Проверка сделок
    print("\n9. Проверка списка сделок...")
    trades = results.get('trades', [])
    print(f"   Всего сделок: {len(trades)}")
    
    if trades:
        first_trade = trades[0]
        print(f"   Первая сделка:")
        print(f"     Entry: {first_trade['entry_time']}")
        print(f"     Exit: {first_trade['exit_time']}")
        print(f"     Side: {first_trade['side']}")
        print(f"     P&L: ${first_trade['pnl']:.2f} ({first_trade['pnl_pct']:.2f}%)")
        print(f"     Exit reason: {first_trade['exit_reason']}")
    
    # 10. Проверка equity curve
    print("\n10. Проверка equity curve...")
    equity_curve = results.get('equity_curve', [])
    print(f"   Точек на кривой: {len(equity_curve)}")
    
    if equity_curve:
        first_point = equity_curve[0]
        last_point = equity_curve[-1]
        print(f"   Начальный капитал: ${first_point['equity']:.2f}")
        print(f"   Конечный капитал: ${last_point['equity']:.2f}")
    
    print("\n" + "=" * 60)
    print("✓✓✓ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ УСПЕШНО ✓✓✓")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    success = test_backtest_engine_validation()
    sys.exit(0 if success else 1)
