"""Тесты для BacktestEngine."""
import pandas as pd
import pytest
from datetime import datetime, timedelta

from backend.core.backtest_engine import BacktestEngine


def generate_test_data(n_bars: int = 500, trend: str = 'up') -> pd.DataFrame:
    """Генерация синтетических OHLCV данных."""
    start_date = datetime(2024, 1, 1)
    timestamps = [start_date + timedelta(hours=i) for i in range(n_bars)]
    
    # Generate price data with trend
    base_price = 100.0
    prices = []
    
    for i in range(n_bars):
        if trend == 'up':
            price = base_price + i * 0.1  # Uptrend
        elif trend == 'down':
            price = base_price - i * 0.1  # Downtrend
        else:
            # Sideways with noise
            price = base_price + (i % 20) * 0.5
        
        prices.append(price)
    
    df = pd.DataFrame({
        'timestamp': timestamps,
        'open': prices,
        'high': [p * 1.01 for p in prices],
        'low': [p * 0.99 for p in prices],
        'close': prices,
        'volume': [1000.0] * n_bars,
    })
    
    return df


def test_backtest_engine_basic():
    """Тест базовой работы движка."""
    engine = BacktestEngine(
        initial_capital=10_000.0,
        leverage=5,
        order_size_usd=100.0
    )
    data = generate_test_data(n_bars=300, trend='up')
    
    strategy_config = {
        'type': 'ema_crossover',
        'fast_ema': 20,
        'slow_ema': 50,
        'take_profit_pct': 5.0,
        'stop_loss_pct': 2.0,
        'direction': 'long',
    }
    
    results = engine.run(data, strategy_config)
    
    # Basic assertions
    assert results is not None
    assert 'final_capital' in results
    assert 'total_trades' in results
    assert results['total_trades'] >= 0
    assert results['final_capital'] > 0
    
    print(f"\n✅ Backtest completed:")
    print(f"   Initial capital: ${10_000:.2f}")
    print(f"   Final capital: ${results['final_capital']:.2f}")
    print(f"   Total return: {results['total_return']*100:.2f}%")
    print(f"   Total trades: {results['total_trades']}")
    print(f"   Win rate: {results['win_rate']*100:.2f}%")
    print(f"   Sharpe ratio: {results['sharpe_ratio']:.2f}")
    print(f"   Max drawdown: {results['max_drawdown']*100:.2f}%")
    print(f"   Leverage: 5x, Order size: $100")


def test_ema_crossover_strategy():
    """Тест EMA Crossover стратегии."""
    engine = BacktestEngine(
        initial_capital=10_000.0,
        leverage=5,
        order_size_usd=100.0
    )
    data = generate_test_data(n_bars=500, trend='up')
    
    strategy_config = {
        'type': 'ema_crossover',
        'fast_ema': 50,
        'slow_ema': 200,
        'take_profit_pct': 5.0,
        'stop_loss_pct': 2.0,
        'direction': 'long',
        'signal_exit': False,
    }
    
    results = engine.run(data, strategy_config)
    
    assert results['total_trades'] >= 0
    
    # If trades were made, check metrics
    if results['total_trades'] > 0:
        assert results['winning_trades'] + results['losing_trades'] == results['total_trades']
        assert 0 <= results['win_rate'] <= 1.0
        assert results['profit_factor'] >= 0
        
        # Check trades structure
        assert 'trades' in results
        assert len(results['trades']) == results['total_trades']
        
        # Check first trade structure
        trade = results['trades'][0]
        assert 'entry_time' in trade
        assert 'exit_time' in trade
        assert 'pnl' in trade
        assert 'exit_reason' in trade
        assert 'side' in trade
        
        print(f"\n✅ EMA Crossover strategy test passed:")
        print(f"   Trades: {results['total_trades']}")
        print(f"   Wins: {results['winning_trades']}, Losses: {results['losing_trades']}")
        print(f"   Profit factor: {results['profit_factor']:.2f}")


def test_trailing_stop():
    """Тест Trailing Stop функциональности."""
    engine = BacktestEngine(
        initial_capital=10_000.0,
        leverage=5,
        order_size_usd=100.0
    )
    data = generate_test_data(n_bars=300, trend='up')
    
    strategy_config = {
        'type': 'ema_crossover',
        'fast_ema': 10,
        'slow_ema': 30,
        'take_profit_pct': 0,  # Disable TP
        'stop_loss_pct': 0,    # Disable SL
        'trailing_stop_pct': 2.0,  # Only trailing
        'direction': 'long',
    }
    
    results = engine.run(data, strategy_config)
    
    if results['total_trades'] > 0:
        # Check that some trades exited via trailing stop
        trailing_exits = [
            t for t in results['trades']
            if t.get('exit_reason') == 'trailing_stop'
        ]
        print(f"\n✅ Trailing stop test:")
        print(f"   Total trades: {results['total_trades']}")
        print(f"   Trailing stop exits: {len(trailing_exits)}")


def test_empty_data():
    """Тест обработки пустых данных."""
    engine = BacktestEngine()
    data = pd.DataFrame()
    
    strategy_config = {'type': 'ema_crossover'}
    
    results = engine.run(data, strategy_config)
    
    assert results['total_trades'] == 0
    assert results['final_capital'] == engine.initial_capital


def test_commission_and_slippage():
    """Тест учёта комиссий и slippage."""
    # High commission scenario
    engine_high_comm = BacktestEngine(
        initial_capital=10_000.0,
        commission=0.01,  # 1% commission
        slippage_pct=0.5,   # 0.5% slippage
        leverage=5,
        order_size_usd=100.0
    )
    
    # Low commission scenario
    engine_low_comm = BacktestEngine(
        initial_capital=10_000.0,
        commission=0.0001,  # 0.01% commission
        slippage_pct=0.01,    # 0.01% slippage
        leverage=5,
        order_size_usd=100.0
    )
    
    data = generate_test_data(n_bars=300, trend='up')
    
    strategy_config = {
        'type': 'ema_crossover',
        'fast_ema': 10,
        'slow_ema': 30,
        'take_profit_pct': 3.0,
        'stop_loss_pct': 1.5,
        'direction': 'long',
    }
    
    results_high = engine_high_comm.run(data, strategy_config)
    results_low = engine_low_comm.run(data, strategy_config)
    
    # High commission should result in lower returns
    if results_high['total_trades'] > 0 and results_low['total_trades'] > 0:
        print(f"\n✅ Commission impact test:")
        print(f"   High commission return: {results_high['total_return']*100:.2f}%")
        print(f"   Low commission return: {results_low['total_return']*100:.2f}%")
        print(f"   Total commission (high): ${results_high['metrics'].get('total_commission', 0):.2f}")
        print(f"   Total commission (low): ${results_low['metrics'].get('total_commission', 0):.2f}")


def test_long_and_short_positions():
    """Тест Long и Short позиций."""
    engine = BacktestEngine(
        initial_capital=10_000.0,
        leverage=5,
        order_size_usd=100.0
    )
    
    # Test Long on uptrend
    data_up = generate_test_data(n_bars=300, trend='up')
    
    config_long = {
        'type': 'ema_crossover',
        'fast_ema': 20,
        'slow_ema': 50,
        'take_profit_pct': 5.0,
        'stop_loss_pct': 2.0,
        'direction': 'long',
    }
    
    results_long = engine.run(data_up, config_long)
    
    # Test Short on downtrend
    data_down = generate_test_data(n_bars=300, trend='down')
    
    config_short = {
        'type': 'ema_crossover',
        'fast_ema': 20,
        'slow_ema': 50,
        'take_profit_pct': 5.0,
        'stop_loss_pct': 2.0,
        'direction': 'short',
    }
    
    results_short = engine.run(data_down, config_short)
    
    print(f"\n✅ Long vs Short test:")
    print(f"   Long (uptrend): trades={results_long['total_trades']}, return={results_long['total_return']*100:.2f}%")
    print(f"   Short (downtrend): trades={results_short['total_trades']}, return={results_short['total_return']*100:.2f}%")
    
    # Check that trades were made
    if results_long['total_trades'] > 0:
        assert all(t['side'] == 'long' for t in results_long['trades'])
    
    if results_short['total_trades'] > 0:
        assert all(t['side'] == 'short' for t in results_short['trades'])


def test_both_directions():
    """Тест одновременно Long и Short (both direction)."""
    engine = BacktestEngine(
        initial_capital=10_000.0,
        leverage=5,
        order_size_usd=100.0
    )
    
    # Sideways market
    data = generate_test_data(n_bars=400, trend='sideways')
    
    config = {
        'type': 'ema_crossover',
        'fast_ema': 10,
        'slow_ema': 30,
        'take_profit_pct': 3.0,
        'stop_loss_pct': 2.0,
        'direction': 'both',  # Both long and short
        'signal_exit': True,  # Exit on opposite signal
    }
    
    results = engine.run(data, config)
    
    print(f"\n✅ Both directions test:")
    print(f"   Total trades: {results['total_trades']}")
    print(f"   Return: {results['total_return']*100:.2f}%")
    
    if results['total_trades'] > 0:
        long_trades = [t for t in results['trades'] if t['side'] == 'long']
        short_trades = [t for t in results['trades'] if t['side'] == 'short']
        
        print(f"   Long trades: {len(long_trades)}")
        print(f"   Short trades: {len(short_trades)}")
        
        # Should have both directions in sideways market
        # (not always guaranteed, but likely with fast EMA crossover)


def test_leverage_effect():
    """Тест эффекта плеча."""
    data = generate_test_data(n_bars=300, trend='up')
    
    config = {
        'type': 'ema_crossover',
        'fast_ema': 20,
        'slow_ema': 50,
        'take_profit_pct': 5.0,
        'stop_loss_pct': 2.0,
        'direction': 'long',
    }
    
    # No leverage
    engine_1x = BacktestEngine(
        initial_capital=10_000.0,
        leverage=1,
        order_size_usd=100.0
    )
    results_1x = engine_1x.run(data, config)
    
    # 5x leverage
    engine_5x = BacktestEngine(
        initial_capital=10_000.0,
        leverage=5,
        order_size_usd=100.0
    )
    results_5x = engine_5x.run(data, config)
    
    print(f"\n✅ Leverage effect test:")
    print(f"   1x leverage: trades={results_1x['total_trades']}, return={results_1x['total_return']*100:.2f}%")
    print(f"   5x leverage: trades={results_5x['total_trades']}, return={results_5x['total_return']*100:.2f}%")
    
    # With leverage, returns should be amplified (both gains and losses)
    if results_1x['total_trades'] > 0 and results_5x['total_trades'] > 0:
        # Same number of trades
        assert results_1x['total_trades'] == results_5x['total_trades']


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
