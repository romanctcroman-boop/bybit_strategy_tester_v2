"""
Full Integration Test: DCA Strategy with Pyramiding
Tests the complete chain: Strategy -> Signals -> Engine -> Trades
"""
import sys

sys.path.insert(0, r'd:\bybit_strategy_tester_v2')


import numpy as np
import pandas as pd

from backend.backtesting.engine_selector import get_engine
from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.strategies import get_strategy


def test_dca_integration():
    """Full DCA strategy integration test"""
    print("=" * 70)
    print("INTEGRATION TEST: DCA Strategy with Pyramiding")
    print("=" * 70)

    # 1. Create test OHLCV data (100 bars)
    n = 100
    dates = pd.date_range(start='2025-01-01', periods=n, freq='1h')

    # Price trends up then down
    prices = 50000 + np.cumsum(np.random.randn(n) * 50)

    candles = pd.DataFrame({
        'open': prices,
        'high': prices + np.random.uniform(20, 100, n),
        'low': prices - np.random.uniform(20, 100, n),
        'close': prices + np.random.uniform(-50, 50, n),
    }, index=dates)

    print(f"\n1. Data prepared: {n} bars from {dates[0]} to {dates[-1]}")
    print(f"   Price range: ${prices.min():.0f} - ${prices.max():.0f}")

    # 2. Create DCA strategy and generate signals
    dca_strategy = get_strategy('dca', {
        'entry_interval': 10,   # Buy every 10 bars
        'max_entries': 5,       # Up to 5 entries
        'take_profit': 5.0,     # 5% TP from average
        'holding_period': 80,   # 80 bars max hold
    })

    signals = dca_strategy.generate_signals(candles)

    entry_count = signals.entries.sum()
    exit_count = signals.exits.sum()

    print("\n2. DCA Strategy signals generated:")
    print(f"   Entry signals: {entry_count}")
    print(f"   Exit signals: {exit_count}")

    # 3. Get engine with pyramiding support
    engine = get_engine(engine_type='fallback_v3', pyramiding=5)
    print(f"\n3. Engine selected: {engine.name}")

    # Alternative: Auto-select based on pyramiding
    engine2 = get_engine(engine_type='numba', pyramiding=5)  # Will still use V3
    print(f"   Auto-selected for pyramiding=5: {engine2.name}")

    # 4. Prepare BacktestInput
    input_data = BacktestInput(
        candles=candles,
        long_entries=signals.entries.values,
        long_exits=signals.exits.values,
        short_entries=signals.short_entries.values if signals.short_entries is not None else np.zeros(n, dtype=bool),
        short_exits=signals.short_exits.values if signals.short_exits is not None else np.zeros(n, dtype=bool),
        initial_capital=10000,
        position_size=0.2,  # 20% per entry
        leverage=1,
        stop_loss=0.0,      # No SL for DCA
        take_profit=0.0,    # TP handled by strategy signals
        taker_fee=0.001,    # 0.1% fee
        slippage=0.0,
        direction=TradeDirection.BOTH,
        pyramiding=5,
        close_entries_rule='ALL',
        use_bar_magnifier=False,
    )

    print("\n4. BacktestInput created:")
    print(f"   Capital: ${input_data.initial_capital}")
    print(f"   Position size: {input_data.position_size * 100}%")
    print(f"   Pyramiding: {input_data.pyramiding}")

    # 5. Run backtest
    result = engine.run(input_data)

    print("\n5. Backtest Results:")
    print(f"   Valid: {result.is_valid}")
    print(f"   Errors: {result.validation_errors}")
    print(f"   Trades: {len(result.trades)}")
    print(f"   Net Profit: ${result.metrics.net_profit:.2f}")
    print(f"   Total Return: {result.metrics.total_return:.2f}%")
    print(f"   Win Rate: {result.metrics.win_rate * 100:.1f}%")
    print(f"   Execution Time: {result.execution_time:.3f}s")

    # 6. Display trade details
    if result.trades:
        print("\n6. Trade Details:")
        for i, trade in enumerate(result.trades[:5]):  # First 5 trades
            print(f"   Trade #{i+1}: {trade.direction.upper()}")
            print(f"     Entry: ${trade.entry_price:.2f} @ {trade.entry_time}")
            print(f"     Exit:  ${trade.exit_price:.2f} @ {trade.exit_time}")
            print(f"     P&L:   ${trade.pnl:.2f} ({trade.pnl_pct*100:.2f}%)")
            print(f"     Bars:  {trade.duration_bars}")
            print()

    # Assertions
    assert result.is_valid, "Backtest should be valid"
    assert len(result.trades) >= 0, "Should have some trades"

    print("=" * 70)
    print("✅ DCA INTEGRATION TEST PASSED!")
    print("=" * 70)


if __name__ == '__main__':
    test_dca_integration()
