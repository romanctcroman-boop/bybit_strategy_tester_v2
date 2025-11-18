"""
Тесты интеграции системы стратегий с BacktestEngine

Проверяет:
1. Создание стратегий через StrategyFactory
2. Интеграция стратегий с BacktestEngine
3. Генерация сигналов и исполнение сделок
4. Совместимость с legacy стратегиями (EMA, RSI)
"""
import sys
import pandas as pd
import numpy as np

# IMPORTANT: Avoid importing server.py which triggers MCP STDIO
from backend.core.backtest_engine import BacktestEngine
from backend.strategies import StrategyFactory, BollingerMeanReversionStrategy


def create_bollinger_test_data(periods=200, volatility=100):
    """
    Создать синтетические данные для Bollinger Bands стратегии
    
    Паттерн: Цена колеблется вокруг среднего с периодическими выходами за границы
    """
    np.random.seed(42)
    base_price = 50000
    prices = [base_price]
    
    for i in range(periods - 1):
        # Mean-reversion: цена тянется к базовой
        change = np.random.randn() * volatility
        
        # Усиленная mean-reversion для генерации сигналов
        if prices[-1] > base_price + 300:
            change -= 150  # Сильное притяжение вниз
        elif prices[-1] < base_price - 300:
            change += 150  # Сильное притяжение вверх
        else:
            # Случайные выбросы для касания границ Bollinger Bands
            if i % 20 == 0:
                change += 200 if np.random.rand() > 0.5 else -200
        
        prices.append(prices[-1] + change)
    
    df = pd.DataFrame({
        'timestamp': pd.date_range(start='2024-01-01', periods=len(prices), freq='5min'),
        'open': prices,
        'high': [p * 1.002 for p in prices],
        'low': [p * 0.998 for p in prices],
        'close': prices,
        'volume': [1000] * len(prices)
    })
    
    return df


def test_strategy_factory_creation():
    """Тест 1: Создание стратегии через Factory"""
    print("\n" + "=" * 80)
    print("ТЕСТ 1: Strategy Factory Creation")
    print("=" * 80)
    
    config = {
        'bb_period': 20,
        'bb_std_dev': 2.0,
        'entry_threshold_pct': 0.1,
        'stop_loss_pct': 1.0,
        'max_holding_bars': 48
    }
    
    try:
        strategy = StrategyFactory.create('bollinger', config)
        print(f"✅ Strategy created: {strategy}")
        print(f"   Config: {strategy.config}")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False


def test_strategy_factory_validation():
    """Тест 2: Валидация конфигурации"""
    print("\n" + "=" * 80)
    print("ТЕСТ 2: Config Validation")
    print("=" * 80)
    
    # Valid config
    valid_config = {
        'bb_period': 20,
        'bb_std_dev': 2.0,
        'entry_threshold_pct': 0.1,
        'stop_loss_pct': 1.0,
        'max_holding_bars': 48
    }
    
    try:
        strategy = StrategyFactory.create('bollinger', valid_config)
        print(f"✅ Valid config accepted")
    except Exception as e:
        print(f"❌ Valid config rejected: {e}")
        return False
    
    # Invalid config (negative bb_period)
    invalid_config = valid_config.copy()
    invalid_config['bb_period'] = -5
    
    try:
        strategy = StrategyFactory.create('bollinger', invalid_config)
        print(f"❌ Invalid config accepted (should fail!)")
        return False
    except ValueError as e:
        print(f"✅ Invalid config rejected: {e}")
    
    return True


def test_bollinger_strategy_with_backtest_engine():
    """Тест 3: Интеграция Bollinger стратегии с BacktestEngine"""
    print("\n" + "=" * 80)
    print("ТЕСТ 3: Bollinger Strategy + BacktestEngine Integration")
    print("=" * 80)
    
    # Создать данные
    data = create_bollinger_test_data(periods=500, volatility=120)
    
    # Конфигурация стратегии
    strategy_config = {
        'type': 'bollinger',  # NEW: Использовать новую систему стратегий
        'bb_period': 20,
        'bb_std_dev': 2.0,
        'entry_threshold_pct': 0.1,
        'stop_loss_pct': 1.5,
        'max_holding_bars': 50
    }
    
    # Запуск бэктеста
    engine = BacktestEngine(
        initial_capital=10000.0,
        commission=0.0006,
        leverage=1
    )
    
    try:
        results = engine.run(data, strategy_config)
        
        print(f"\n📊 Результаты бэктеста:")
        print(f"  Начальный капитал: $10,000.00")
        print(f"  Конечный капитал:  ${results['final_capital']:,.2f}")
        print(f"  Доходность:         {results['total_return'] * 100:.2f}%")
        print(f"  Всего сделок:       {results['total_trades']}")
        print(f"  Прибыльных:         {results['winning_trades']}")
        print(f"  Убыточных:          {results['losing_trades']}")
        print(f"  Win Rate:           {results['win_rate']:.2f}%")
        print(f"  Profit Factor:      {results['profit_factor']:.2f}")
        print(f"  Sharpe Ratio:       {results['sharpe_ratio']:.2f}")
        print(f"  Max Drawdown:       {results['max_drawdown'] * 100:.2f}%")
        
        # Проверки
        assert results['total_trades'] > 0, "❌ Нет сделок!"
        assert results['final_capital'] != 10000.0, "❌ Капитал не изменился!"
        
        print(f"\n✅ ТЕСТ 3 PASSED")
        return True
        
    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_legacy_ema_strategy_compatibility():
    """Тест 4: Совместимость с legacy EMA стратегией"""
    print("\n" + "=" * 80)
    print("ТЕСТ 4: Legacy EMA Strategy Compatibility")
    print("=" * 80)
    
    # Создать uptrend данные
    data = pd.DataFrame({
        'timestamp': pd.date_range(start='2024-01-01', periods=200, freq='1h'),
        'close': [100 + i * 0.5 for i in range(200)]  # Uptrend
    })
    
    # Legacy EMA config
    strategy_config = {
        'type': 'ema_crossover',  # LEGACY strategy
        'fast_ema': 10,
        'slow_ema': 30,
        'direction': 'long'
    }
    
    engine = BacktestEngine(initial_capital=10000.0)
    
    try:
        results = engine.run(data, strategy_config)
        
        print(f"\n📊 Legacy EMA Results:")
        print(f"  Total trades: {results['total_trades']}")
        print(f"  Final capital: ${results['final_capital']:,.2f}")
        print(f"  Return: {results['total_return'] * 100:.2f}%")
        
        assert results['total_trades'] > 0, "❌ Нет сделок!"
        
        print(f"\n✅ ТЕСТ 4 PASSED (Legacy compatibility working)")
        return True
        
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False


def test_strategy_signal_generation():
    """Тест 5: Прямая генерация сигналов стратегией"""
    print("\n" + "=" * 80)
    print("ТЕСТ 5: Direct Strategy Signal Generation")
    print("=" * 80)
    
    # Создать данные с явным паттерном mean-reversion
    data = create_bollinger_test_data(periods=100, volatility=150)
    
    # Создать стратегию
    config = {
        'bb_period': 20,
        'bb_std_dev': 2.0,
        'entry_threshold_pct': 0.05,
        'stop_loss_pct': 1.0,
        'max_holding_bars': 50
    }
    
    strategy = BollingerMeanReversionStrategy(config)
    strategy.on_start(data)
    
    # Симуляция bar-by-bar
    signals = []
    for i in range(20, len(data)):  # Start after BB warmup
        bar = data.iloc[i]
        signal = strategy.on_bar(bar, i, data[:i+1])
        
        if signal:
            signals.append({
                'bar': i,
                'action': signal['action'],
                'price': bar['close'],
                'reason': signal.get('reason', 'N/A')
            })
    
    print(f"\n📊 Generated {len(signals)} signals:")
    for sig in signals[:5]:  # Show first 5
        print(f"  Bar {sig['bar']}: {sig['action']} at ${sig['price']:.2f} - {sig['reason']}")
    
    if len(signals) > 5:
        print(f"  ... and {len(signals) - 5} more signals")
    
    assert len(signals) > 0, "❌ Нет сигналов!"
    
    print(f"\n✅ ТЕСТ 5 PASSED")
    return True


def run_all_tests():
    """Запустить все тесты"""
    print("\n")
    print("🚀 " * 40)
    print("INTEGRATION TESTS: Strategy System + BacktestEngine")
    print("🚀 " * 40)
    
    tests = [
        test_strategy_factory_creation,
        test_strategy_factory_validation,
        test_strategy_signal_generation,
        test_bollinger_strategy_with_backtest_engine,
        test_legacy_ema_strategy_compatibility,
    ]
    
    results = []
    for test in tests:
        try:
            passed = test()
            results.append(passed)
        except Exception as e:
            print(f"\n❌ Test crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    print("\n" + "=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
    else:
        print(f"\n⚠️  {total - passed} тестов провалены")
    
    return passed == total


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
